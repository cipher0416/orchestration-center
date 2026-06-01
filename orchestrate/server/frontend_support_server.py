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

import os
import tempfile
import json
import re
import time
import uuid
from typing import Optional, List, Any, Dict

import anyio
from a2a.types import AgentCard
from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Request, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google.protobuf.json_format import Parse, MessageToDict
from loguru import logger
from pydantic import BaseModel, Field
from starlette import status
from starlette.responses import Response

from common.config import (
    MAX_URL_LENGTH, MAX_REQUEST_BODY_SIZE, MAX_FILE_SIZE_BYTES, CONN_MAX, CONN_TIMEOUT,
    FLOW_CTL_PARALLEL_RETRIEVE_PSOP, FLOW_CTL_PARALLEL_GENERATE_PSOP,
    FLOW_CTL_PARALLEL_AGENT_CARDS, FLOW_CTL_PARALLEL_DELETE_PSOP,
    FLOW_CTL_PARALLEL_SAVE_PSOP, FLOW_CTL_PARALLEL_ONE_PSOP,
    FLOW_CTL_PARALLEL_ALL_PSOPS, FLOW_CTL_PARALLEL_PLAN, FLOW_CTL_PARALLEL_PARSE_PDF
)
from common.custom.default_handle import HandlerRegistry
from common.custom.interface_type import InterfaceType
from orchestrate.server.sse_executor import run_psop_sse
from orchestrate.server.response_utils import ok, created, get_agent_cards
from common.log.audit_logger import audit_logger, OperationObject, OperationName, LogLevel, OperationResult
from common.util.config_util import get_conf
from orchestrate.core.model.preflow import PreFlow
from orchestrate.core.model.psop import PSOP
from orchestrate.server.external_api import router as external_router
from orchestrate.core.psop_generator import PsopGenerator
from orchestrate.core.intent_psop_generator import IntentPsopGenerator
from orchestrate.core.retrieval import WorkflowRetrieval
from orchestrate.core.workflow_search_result import WorkflowSearchResult
from orchestrate.server.middleware import ConnectionLimitMiddleware, TimeoutMiddleware, RateLimiter
from orchestrate.solution_package.parse_flow import SolutionPackageParser
from orchestrate.registry_client.client_factory import AgentRegistryClientFactory
from orchestrate.workflow_storage_instance import get_workflow_storage

app = FastAPI(title="Workflow Orchestration API", version="1.0.0", docs_url=None, redoc_url=None, openapi_url=None)

config = get_conf()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ConnectionLimitMiddleware, max_connections=int(config.get(CONN_MAX, 200)))
app.add_middleware(TimeoutMiddleware, timeout_seconds=int(config.get(CONN_TIMEOUT, 300)))


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    client_ip = request.client.host if request.client else "unknown"
    query_params = dict(request.query_params)
    logger.info(f"[{request_id}] --> {request.method} {request.url.path} "
                f"client={client_ip}"
                f"{' params=' + str(query_params) if query_params else ''}")
    start_time = time.time()
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(f"[{request_id}] <-- {request.method} {request.url.path} "
                    f"status={response.status_code} duration={duration:.3f}s")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{request_id}] <-- {request.method} {request.url.path} "
                     f"ERROR={e} duration={duration:.3f}s")
        raise


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if len(str(request.url)) > MAX_URL_LENGTH:
        return Response(content="URI Too Long", status_code=status.HTTP_414_URI_TOO_LONG)
    if request.method in ("POST", "PUT"):
        total_size = 0
        body_chunks = []
        try:
            async for chunk in request.stream():
                total_size += len(chunk)
                if total_size > MAX_REQUEST_BODY_SIZE:
                    return Response(
                        content=f"Request body is too large, maximum allowed {MAX_REQUEST_BODY_SIZE // 1024} KB",
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE
                    )
                body_chunks.append(chunk)
            request._body = b''.join(body_chunks)
        except Exception as e:
            logger.error(f"Bad Request: {e}")
            return Response(content="Bad Request", status_code=status.HTTP_400_BAD_REQUEST)
    return await call_next(request)


# ──── Shared state (lazily initialized) ────
_save_handle = None
_delete_handle = None
_retrievals = {}


def _get_save_handle():
    global _save_handle
    if _save_handle is None:
        _save_handle = HandlerRegistry.get_handler(InterfaceType.SAVE_PSOP)
    return _save_handle


def _get_delete_handle():
    global _delete_handle
    if _delete_handle is None:
        _delete_handle = HandlerRegistry.get_handler(InterfaceType.DELETE_PSOP)
    return _delete_handle


def _get_retrieval(lang: str = None):
    key = lang or "zh"
    if key not in _retrievals:
        _retrievals[key] = WorkflowRetrieval(get_workflow_storage(lang=key))
    return _retrievals[key]


# ═══════════════════════════════════════════════════════════════════════════════
# Standard response envelope
# ═══════════════════════════════════════════════════════════════════════════════

# ──── Request models ────

class PlanRequest(BaseModel):
    preflow: dict = Field(..., description="PreFlow model JSON")
    agent_cards: List[dict] = Field(..., description="AgentCard list JSON")


class SavePSOPRequest(BaseModel):
    psop: dict = Field(..., description="PSOP model JSON")


class IntentRequest(BaseModel):
    user_intent: str = Field(..., description="Natural language intent description")
    workflow_name: Optional[str] = Field(None, description="Optional workflow name")


class RetrieveIntentRequest(BaseModel):
    user_intent: str = Field(..., description="Natural language intent for retrieval")


# ──── Router ────
router = APIRouter(prefix="/rest/v1/orchestrate")


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow CRUD
# ═══════════════════════════════════════════════════════════════════════════════

all_psop_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_PARALLEL_ALL_PSOPS, 20)))


@router.get("/workflows")
async def list_workflows(
    limit: int = Query(10, ge=1, le=100, description="Max workflows to return"),
    lang: str = Query(None, description="Language code (zh/en)"),
    _: Any = Depends(RateLimiter(config, "list_workflows"))
):
    acquired = False
    try:
        all_psop_semaphore.acquire_nowait()
        acquired = True
        logger.info(f"Listing workflows: limit={limit}")
        recent_workflows = _get_retrieval(lang=lang).list_recent_workflows(limit=limit, workflow_type='psop')
        logger.info(f"Retrieved {len(recent_workflows)} workflows")
        return ok(data=[wf.to_dict() for wf in recent_workflows])
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acquired:
            all_psop_semaphore.release()


one_psop_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_PARALLEL_ONE_PSOP, 10)))


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    lang: str = Query(None, description="Language code (zh/en)"),
    _: Any = Depends(RateLimiter(config, "get_workflow"))
):
    acquired = False
    try:
        one_psop_semaphore.acquire_nowait()
        acquired = True
        logger.info(f"Getting workflow: {workflow_id}")
        psop = _get_retrieval(lang=lang).get_psop_by_id(workflow_id)
        if not psop:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
        return ok(data=psop.model_dump())
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acquired:
            one_psop_semaphore.release()


save_psop_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_PARALLEL_SAVE_PSOP, 10)))


@router.post("/workflows", status_code=201)
async def create_workflow(
    request: SavePSOPRequest,
    _: Any = Depends(RateLimiter(config, "create_workflow"))
):
    acquired = False
    try:
        save_psop_semaphore.acquire_nowait()
        acquired = True
        psop = PSOP.model_validate(request.psop)
        logger.info(f"Creating workflow: name={psop.name}, id={psop.id}")
        saved_id = _get_save_handle().handle(psop)
        logger.info(f"Workflow saved: id={saved_id}")
        audit_logger.audit({
            'object_name': OperationObject.PSOP,
            'operation_name': OperationName.SAVE_PSOP,
            'level': LogLevel.MINOR,
            'result': OperationResult.SUCCESS,
            'details': {"id": psop.id, "name": psop.name, "steps_count": len(psop.steps)},
        })
        return created(data={"workflow_id": saved_id}, message="Workflow created successfully")
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        audit_logger.audit({
            'object_name': OperationObject.PSOP,
            'operation_name': OperationName.SAVE_PSOP,
            'level': LogLevel.MINOR,
            'result': OperationResult.FAILURE,
            'details': {"message": str(e)},
        })
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acquired:
            save_psop_semaphore.release()


delete_psop_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_PARALLEL_DELETE_PSOP, 5)))


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    _: Any = Depends(RateLimiter(config, "delete_workflow"))
):
    acquired = False
    try:
        delete_psop_semaphore.acquire_nowait()
        acquired = True
        logger.info(f"Deleting workflow: {workflow_id}")
        psop = _get_retrieval().get_psop_by_id(workflow_id)
        if not psop:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
        deleted = _get_delete_handle().handle(workflow_id)
        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete workflow")
        logger.info(f"Workflow deleted: {workflow_id}")
        audit_logger.audit({
            'object_name': OperationObject.PSOP,
            'operation_name': OperationName.DELETE_PSOP,
            'level': LogLevel.MINOR,
            'result': OperationResult.SUCCESS,
            'details': {"workflow_id": workflow_id, "name": psop.name},
        })
        return ok(message=f"Workflow {workflow_id} deleted")
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acquired:
            delete_psop_semaphore.release()


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow generation endpoints
# ═══════════════════════════════════════════════════════════════════════════════

parse_pdf_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_PARALLEL_PARSE_PDF, 5)))


@router.post("/parse-pdf")
async def parse_pdf(
    file: UploadFile = File(...),
    _: Any = Depends(RateLimiter(config, "parse_pdf"))
):
    acquired = False
    tmp_file_path = None
    try:
        parse_pdf_semaphore.acquire_nowait()
        acquired = True

        filename = file.filename or "unknown"
        logger.info(f"Parsing PDF: {filename}, size={file.size}")

        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        if not re.fullmatch(r"^[\w\-. ]{1,128}\.pdf$", file.filename):
            raise HTTPException(status_code=400, detail="Invalid filename format")

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp_file_path = tmp.name
            content = await file.read()

        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413,
                detail=f"File size exceeds maximum allowed {MAX_FILE_SIZE_BYTES // (1024*1024)} MB")
        if len(content) < 5 or content[:5] != b'%PDF-':
            raise HTTPException(status_code=400, detail="File is not a valid PDF")

        with open(tmp_file_path, 'wb') as f:
            f.write(content)

        parser = SolutionPackageParser()
        pre_md = parser.parse_pdf_chapter(tmp_file_path, "5. Interaction Flow")
        if not pre_md:
            raise HTTPException(status_code=400, detail="Chapter '5. Interaction Flow' not found in PDF")

        logger.info(f"PDF chapter extracted (markdown, {len(pre_md)} chars):\n{pre_md}")

        preflow = PreFlow(
            name=file.filename,
            description=f"Workflow parsed from PDF {file.filename}",
            steps_md=pre_md
        )
        logger.info(f"PDF parsed: preflow_id={preflow.id}")
        return ok(data=json.loads(preflow.model_dump_json()))
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF parsing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        if acquired:
            parse_pdf_semaphore.release()


plan_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_PARALLEL_PLAN, 10)))


@router.post("/generate-from-preflow")
async def generate_from_preflow(
    request: PlanRequest,
    _: Any = Depends(RateLimiter(config, "generate_from_preflow"))
):
    acquired = False
    try:
        plan_semaphore.acquire_nowait()
        acquired = True
        preflow_name = request.preflow.get("name", "unknown")
        preflow_steps_md = request.preflow.get("steps_md", "")
        logger.info(f"Generating PSOP from PreFlow: {preflow_name}, agents={len(request.agent_cards)}")
        logger.info(f"PreFlow steps_md ({len(preflow_steps_md)} chars):\n{preflow_steps_md}")

        generator = PsopGenerator()
        workflow = generator.generate_psop_workflow(
            PreFlow.model_validate(request.preflow),
            [Parse(json.dumps(card), AgentCard()) for card in request.agent_cards]
        )
        _get_save_handle().handle(workflow)
        logger.info(f"PSOP generated: id={workflow.id}, steps={len(workflow.steps)}")
        audit_logger.audit({
            'object_name': OperationObject.PSOP,
            'operation_name': OperationName.SAVE_PSOP,
            'level': LogLevel.MINOR,
            'result': OperationResult.SUCCESS,
            'details': {"id": workflow.id, "name": workflow.name, "steps_count": len(workflow.steps)},
        })
        return ok(data=json.loads(workflow.model_dump_json()))
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except Exception as e:
        logger.error(f"PreFlow generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acquired:
            plan_semaphore.release()


generate_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_PARALLEL_GENERATE_PSOP, 10)))


@router.post("/generate-from-intent")
async def generate_from_intent(
    request: IntentRequest,
    _: Any = Depends(RateLimiter(config, "generate_from_intent"))
):
    acquired = False
    try:
        generate_semaphore.acquire_nowait()
        acquired = True
        intent_preview = request.user_intent[:80] + "..." if len(request.user_intent) > 80 else request.user_intent
        logger.info(f"Generating PSOP from intent: {intent_preview}")

        agent_registry_factory = AgentRegistryClientFactory()
        agent_cards_raw = agent_registry_factory.create_from_env().list_exact()
        if not agent_cards_raw:
            raise HTTPException(status_code=404, detail="No available AgentCards found")

        generator = IntentPsopGenerator()
        psop = generator.generate_psop_from_intent(
            user_intent=request.user_intent,
            agent_cards=[Parse(json.dumps(agent), AgentCard()) for agent in agent_cards_raw],
            workflow_name=request.workflow_name
        )
        logger.info(f"PSOP generated from intent: id={psop.id}, steps={len(psop.steps)}")

        try:
            _get_save_handle().handle(psop)
            logger.info(f"PSOP auto-saved: {psop.id}")
            audit_logger.audit({
                'object_name': OperationObject.PSOP,
                'operation_name': OperationName.SAVE_PSOP,
                'level': LogLevel.MINOR,
                'result': OperationResult.SUCCESS,
                'details': {"id": psop.id, "name": psop.name, "steps_count": len(psop.steps)},
            })
        except Exception as save_error:
            logger.warning(f"Auto-save failed (non-fatal): {save_error}")

        return ok(data=psop.model_dump())
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intent generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acquired:
            generate_semaphore.release()


retrieve_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_PARALLEL_RETRIEVE_PSOP, 10)))


@router.post("/retrieve-by-intent")
async def retrieve_by_intent(
    request: RetrieveIntentRequest,
    _: Any = Depends(RateLimiter(config, "retrieve_by_intent"))
):
    acquired = False
    try:
        retrieve_semaphore.acquire_nowait()
        acquired = True
        logger.info(f"Retrieving PSOP by intent: {request.user_intent[:80]}")
        psop = _get_retrieval().retrieve_psop_by_intent(request.user_intent)
        if not psop:
            return ok(data=None, message="No matching workflow found")
        logger.info(f"Retrieved: {psop.name} (id={psop.id})")
        return ok(data=psop.model_dump())
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acquired:
            retrieve_semaphore.release()


class RetrieveTopNRequest(BaseModel):
    user_intent: str = Field(..., description="Natural language intent for retrieval")
    top_n: int = Field(default=3, ge=1, le=10, description="Max results to return")


@router.post("/retrieve-topn-by-intent")
async def retrieve_topn_by_intent(
    request: RetrieveTopNRequest,
    _: Any = Depends(RateLimiter(config, "retrieve_by_intent"))
):
    acquired = False
    try:
        retrieve_semaphore.acquire_nowait()
        acquired = True
        top_n = request.top_n if request.top_n else 3
        logger.info(f"Retrieving TopN PSOPs by intent (n={top_n}): {request.user_intent[:80]}")
        results: List[WorkflowSearchResult] = _get_retrieval().retrieve_psop_by_intent_topn(request.user_intent, top_n)
        logger.info(f"TopN returned {len(results)} result(s)")
        return ok(data=[r.to_dict() for r in results], message=f"Found {len(results)} matching workflow(s)")
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except Exception as e:
        logger.error(f"TopN retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acquired:
            retrieve_semaphore.release()


# ═══════════════════════════════════════════════════════════════════════════════
# Agent cards
# ═══════════════════════════════════════════════════════════════════════════════

agent_cards_semaphore = anyio.Semaphore(int(config.get(FLOW_CTL_PARALLEL_AGENT_CARDS, 20)))


@router.get("/agent-cards")
async def list_agent_cards(
    lang: str = Query(None, description="Language code (zh/en)"),
    _: Any = Depends(RateLimiter(config, "list_agent_cards"))
):
    acquired = False
    try:
        agent_cards_semaphore.acquire_nowait()
        acquired = True
        logger.info(f"Fetching agent cards (lang={lang})")
        loader = AgentCardLoader()
        agent_cards = loader.get_all_agent_cards(lang=lang or "zh")
        logger.info(f"Retrieved {len(agent_cards)} agent cards")
        return ok(data=[card.model_dump() if hasattr(card, 'model_dump') else MessageToDict(card, preserving_proto_field_name=True) for card in agent_cards])
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to fetch agent cards: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acquired:
            agent_cards_semaphore.release()


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow templates
# ═══════════════════════════════════════════════════════════════════════════════

import pathlib

_templates_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "workflow_templates"


@router.get("/templates")
async def list_templates(
    lang: str = Query(None, description="Language code (zh/en)"),
    _: Any = Depends(RateLimiter(config, "list_workflows"))
):
    try:
        templates = []
        lang_dir = _templates_dir / (lang or "zh")
        scan_dir = lang_dir if lang_dir.exists() else _templates_dir
        for f in sorted(scan_dir.glob("*.json")):
                with open(f, "r", encoding="utf-8") as fh:
                    tpl = json.load(fh)
                templates.append({
                    "id": tpl.get("id", f.stem),
                    "name": tpl.get("name", f.stem),
                    "description": tpl.get("description", ""),
                    "tags": tpl.get("tags", []),
                    "step_count": len(tpl.get("steps", [])),
                    "agent_count": len({
                        t["agent"] for s in tpl.get("steps", [])
                        for t in s.get("subtasks", [])
                    })
                })
        return ok(data=templates)
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates/{template_id}/import", status_code=201)
async def import_template(
    template_id: str,
    lang: str = Query(None, description="Language code (zh/en)"),
    _: Any = Depends(RateLimiter(config, "create_workflow"))
):
    acquired = False
    try:
        save_psop_semaphore.acquire_nowait()
        acquired = True
        lang_dir = _templates_dir / (lang or "zh")
        scan_dirs = [lang_dir] if lang_dir.exists() else []
        if _templates_dir.exists():
            scan_dirs.append(_templates_dir)
        psop_data = None
        for scan_dir in scan_dirs:
            for f in scan_dir.glob("*.json"):
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if data.get("id") == template_id:
                    psop_data = data
                    break
            if psop_data:
                break
        if psop_data is None:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
        psop_data["id"] = str(uuid.uuid4())
        psop = PSOP.model_validate(psop_data)
        saved_id = _get_save_handle().handle(psop)
        logger.info(f"Template imported: {psop.name} ({template_id}) -> {saved_id}")
        audit_logger.audit({
            'object_name': OperationObject.PSOP,
            'object_id': saved_id,
            'operation_name': OperationName.SAVE_PSOP,
            'level': LogLevel.MINOR,
            'result': OperationResult.SUCCESS,
            'details': {"template_id": template_id, "workflow_id": saved_id},
        })
        return created(data=psop.model_dump(), message="Template imported successfully")
    except anyio.WouldBlock:
        raise HTTPException(status_code=503, detail="Server is busy")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if acquired:
            save_psop_semaphore.release()


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow execution (SSE streaming)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/execute")
async def execute_workflow(
    psop_id: str = Query(..., description="PSOP workflow ID to execute"),
    user_intent: str = Query(None, description="Runtime user intent for context injection"),
    lang: str = Query(None, description="Language for agent responses (zh/en)")
):
    if not psop_id:
        raise HTTPException(status_code=400, detail="Missing psop_id parameter")

    logger.info(f"Starting workflow execution: psop_id={psop_id}, user_intent={user_intent[:80] if user_intent else 'N/A'}")
    psop = _get_retrieval().get_psop_by_id(psop_id)
    if not psop:
        raise HTTPException(status_code=404, detail=f"Workflow {psop_id} not found")

    logger.info(f"Workflow loaded: name={psop.name}, steps={len(psop.steps)}")
    agent_cards = get_agent_cards()

    return await run_psop_sse(psop, agent_cards, runtime_intent=user_intent, lang=lang)


@router.delete("/execution-records/{execution_id}")
async def delete_execution_record(execution_id: str):
    handler = HandlerRegistry.get_handler(InterfaceType.DELETE_EXECUTION_RECORD)
    deleted = handler.handle(execution_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Execution record {execution_id} not found")
    return ok(data={"deleted": execution_id})


@router.get("/execution-records")
async def list_execution_records():
    handler = HandlerRegistry.get_handler(InterfaceType.LIST_EXECUTION_RECORDS)
    records = handler.handle()
    return ok(data=records)


@router.get("/execution-records/{execution_id}")
async def get_execution_record(execution_id: str):
    handler = HandlerRegistry.get_handler(InterfaceType.GET_EXECUTION_RECORD)
    record = handler.handle(execution_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Execution record {execution_id} not found")
    return ok(data=record.model_dump() if hasattr(record, 'model_dump') else record)


# ──── Register routers ────
app.include_router(router)
app.include_router(external_router)


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy route aliases (backward compatibility, delegates to new routes)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/agent-cards")
async def legacy_agent_cards():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/rest/v1/orchestrate/agent-cards", status_code=308)


@app.get("/psops")
async def legacy_list_workflows(limit: int = 10):
    recent = _get_retrieval().list_recent_workflows(limit=limit, workflow_type='psop')
    return {"code": 200, "message": "success", "data": [wf.to_dict() for wf in recent]}


@app.get("/psops/{workflow_id}")
async def legacy_get_workflow(workflow_id: str):
    psop = _get_retrieval().get_psop_by_id(workflow_id)
    if not psop:
        raise HTTPException(status_code=404, detail=f"PSOP {workflow_id} not found")
    return {"code": 200, "message": "success", "data": psop.model_dump()}


@app.post("/psops")
async def legacy_save_workflow(request: SavePSOPRequest):
    psop = PSOP.model_validate(request.psop)
    saved_id = _get_save_handle().handle(psop)
    return JSONResponse(status_code=201, content={"code": 201, "message": "created", "data": {"workflow_id": saved_id}})


@app.delete("/psops/{workflow_id}")
async def legacy_delete_workflow(workflow_id: str):
    psop = _get_retrieval().get_psop_by_id(workflow_id)
    if not psop:
        raise HTTPException(status_code=404, detail=f"PSOP {workflow_id} not found")
    _get_delete_handle().handle(workflow_id)
    return {"code": 200, "message": f"Workflow {workflow_id} deleted", "data": None}
