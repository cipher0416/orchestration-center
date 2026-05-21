# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
External API Module

Public-facing API for other systems to integrate with the Orchestration Center.
Provides SOP-based orchestration, intent-based orchestration, and workflow execution.

Endpoints:
  POST /api/v1/orchestrate/sop           — SOP-based orchestration (text or PDF upload)
  POST /api/v1/orchestrate/intent        — Intent-based orchestration
  POST /api/v1/orchestrate/execute       — Auto-orchestrate + execute (SSE)
  GET  /api/v1/orchestrate/execute/{id}  — Execute a known PSOP (SSE)
  GET  /api/v1/agents                    — List available agents
  GET  /api/v1/executions/{id}           — Get execution result
"""

import json
import re
from typing import Any, List, Optional

import anyio
from a2a.types import AgentCard
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, Depends
from loguru import logger
from pydantic import BaseModel, Field

from common.config import FLOW_CTL_START_PROCESS_STREAM, FLOW_CTL_PLAN, FLOW_CTL_GENERATE_PSOP
from common.custom.default_handle import HandlerRegistry
from common.custom.interface_type import InterfaceType
from orchestrate.core.intent_psop_generator import IntentPsopGenerator
from orchestrate.core.model.preflow import PreFlow
from orchestrate.core.model.psop import PSOP
from orchestrate.core.psop_generator import PsopGenerator
from orchestrate.core.retrieval import WorkflowRetrieval
from orchestrate.registry_client.client_factory import AgentRegistryClientFactory
from orchestrate.server.sse_executor import run_psop_sse
from orchestrate.server.response_utils import ok, created, get_agent_cards
from orchestrate.server.middleware import RateLimiter
from orchestrate.solution_package.parse_flow import SolutionPackageParser
from orchestrate.workflow_storage_instance import get_workflow_storage
from common.util.config_util import get_conf

router = APIRouter(prefix="/api/v1")
config = get_conf()

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024

execute_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_START_PROCESS_STREAM)))
sop_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_PLAN)))
intent_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_GENERATE_PSOP)))


# ═══════════════════════════════════════════════════════════════════════════════
# Request Models
# ═══════════════════════════════════════════════════════════════════════════════

class SOPOrchestrateRequest(BaseModel):
    sop_content: str = Field(..., description="Natural language SOP steps (markdown text)")
    name: Optional[str] = Field(None, description="Optional workflow name")


class IntentOrchestrateRequest(BaseModel):
    intent: str = Field(..., description="Natural language intent or task description")
    name: Optional[str] = Field(None, description="Optional workflow name")


class ExecuteRequest(BaseModel):
    task: str = Field(..., description="Task description. System will search existing PSOPs first, auto-generate if none found")
    name: Optional[str] = Field(None, description="Optional workflow name for auto-generation")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SOP-based orchestration
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/orchestrate/sop")
async def orchestrate_sop(
    request: Request,
    file: Optional[UploadFile] = File(None),
    name: Optional[str] = Form(None),
    _: Any = Depends(RateLimiter(config, "sop_orchestrate"))
):
    """
    SOP-based orchestration.

    Accepts either:
    - JSON body with `sop_content` (natural language SOP text)
    - File upload (PDF/TXT/MD SolutionPackage), with optional `name` form field

    When both JSON body and file are provided, the file takes precedence.

    Returns a generated PSOP workflow.
    """
    acquired = False
    try:
        sop_semaphore.acquire_nowait()
        acquired = True

        sop_text = ""
        workflow_name = name
        body = None

        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                raw_body = await request.json()
                body = SOPOrchestrateRequest.model_validate(raw_body)
            except Exception:
                pass

        if file:
            filename = file.filename or ""
            if not re.match(r'^[\w\-. ]{1,128}\.(pdf|txt|md)$', filename, re.IGNORECASE):
                raise HTTPException(status_code=400, detail=f"Invalid filename: {filename}")
            content = await file.read()
            if len(content) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="File too large")
            if filename.lower().endswith('.pdf') and not content.startswith(b'%PDF-'):
                raise HTTPException(status_code=400, detail="Not a valid PDF file")
            await file.seek(0)
            parser = SolutionPackageParser()
            try:
                preflow = parser.parse_pdf(file.file, filename)
                sop_text = preflow.steps_md
                workflow_name = workflow_name or preflow.name
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        elif body:
            sop_text = body.sop_content
            workflow_name = workflow_name or body.name
        else:
            raise HTTPException(status_code=400, detail="Either sop_content or file upload is required")

        if not sop_text or not sop_text.strip():
            raise HTTPException(status_code=400, detail="SOP content is empty")

        agent_cards = get_agent_cards()
        preflow = PreFlow(name=workflow_name or "SOP Workflow", steps_md=sop_text)
        generator = PsopGenerator()
        psop = generator.generate_psop_workflow(preflow, agent_cards)
        psop.user_intent = sop_text[:200]
        psop.related_preflow = preflow.id

        save_handler = HandlerRegistry.get_handler(InterfaceType.SAVE_PSOP)
        save_handler.handle(psop)
        return created(data=psop.model_dump(), message="PSOP generated and saved")
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    finally:
        if acquired:
            sop_semaphore.release()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Intent-based orchestration
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/orchestrate/intent")
async def orchestrate_intent(
    request: Request,
    body: IntentOrchestrateRequest,
    _: Any = Depends(RateLimiter(config, "intent_orchestrate"))
):
    """
    Intent-based orchestration.

    Generates a PSOP workflow directly from a natural language intent/task description.
    No SOP steps required — the LLM plans the workflow autonomously.
    """
    acquired = False
    try:
        intent_semaphore.acquire_nowait()
        acquired = True
        agent_cards = get_agent_cards()
        generator = IntentPsopGenerator()
        psop = generator.generate_psop_from_intent(body.intent, agent_cards, body.name)

        save_handler = HandlerRegistry.get_handler(InterfaceType.SAVE_PSOP)
        save_handler.handle(psop)
        return created(data=psop.model_dump(), message="PSOP generated and saved")
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    finally:
        if acquired:
            intent_semaphore.release()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Auto-orchestrate + execute (composite)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/orchestrate/execute")
async def execute_workflow(
    request: Request,
    body: ExecuteRequest,
    _: Any = Depends(RateLimiter(config, "ext_execute_auto"))
):
    """
    Auto-orchestrate and execute.

    Given a task description:
    1. Search for existing matching PSOPs
    2. If found, execute the best match
    3. If not found, auto-generate a new PSOP then execute it

    Returns an SSE stream with execution progress and results.
    """
    acquired = False
    try:
        execute_semaphore.acquire_nowait()
        acquired = True
        retrieval = WorkflowRetrieval(get_workflow_storage())
        psop = retrieval.retrieve_psop_by_intent(body.task)

        if not psop:
            logger.info(f"No existing PSOP found for task, auto-generating...")
            try:
                agent_cards = get_agent_cards()
                generator = IntentPsopGenerator()
                psop = generator.generate_psop_from_intent(body.task, agent_cards, body.name)
                save_handler = HandlerRegistry.get_handler(InterfaceType.SAVE_PSOP)
                save_handler.handle(psop)
                logger.info(f"Auto-generated PSOP: {psop.id}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Auto-generation failed: {e}")

        agent_cards = get_agent_cards()
        return await run_psop_sse(psop, agent_cards, runtime_intent=body.task)
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    finally:
        if acquired:
            execute_semaphore.release()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Execute known PSOP
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/orchestrate/execute/{psop_id}")
async def execute_psop_by_id(
    request: Request,
    psop_id: str,
    user_intent: str = Query(None, description="Runtime user intent for context injection"),
    _: Any = Depends(RateLimiter(config, "ext_execute_by_id"))
):
    """
    Execute a known PSOP workflow by ID.

    Returns an SSE stream with execution progress and results.
    """
    acquired = False
    try:
        execute_semaphore.acquire_nowait()
        acquired = True
        retrieval = WorkflowRetrieval(get_workflow_storage())
        psop = retrieval.get_psop_by_id(psop_id)
        if not psop:
            raise HTTPException(status_code=404, detail=f"PSOP {psop_id} not found")
        return await run_psop_sse(psop, get_agent_cards(), runtime_intent=user_intent)
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    finally:
        if acquired:
            execute_semaphore.release()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. List available agents
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/agents")
async def list_agents(
    _: Any = Depends(RateLimiter(config, "list_agents"))
):
    """
    List all available agents with their skills.

    Returns agent inventory from the agent registry.
    """
    factory = AgentRegistryClientFactory()
    agents = factory.create_from_env().list_exact()
    return ok(data=agents)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Execution result
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    _: Any = Depends(RateLimiter(config, "get_execution"))
):
    """
    Get execution result by execution ID.
    """
    handler = HandlerRegistry.get_handler(InterfaceType.GET_EXECUTION_RECORD)
    record = handler.handle(execution_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    return ok(data=record.model_dump() if hasattr(record, 'model_dump') else record)
