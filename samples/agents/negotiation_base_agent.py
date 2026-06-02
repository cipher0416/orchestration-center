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

import asyncio
import uuid
from typing import Dict, Any
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Task, TaskStatus, TaskState, Artifact, Part
from loguru import logger

from a2a_t.server import A2ATServer
from a2a_t.negotiation.common.enums import NegotiationType
from a2a_t.negotiation.common.models import StartNegotiationInput, NegotiationContext

from common.a2at_config import get_a2at_env_path
from common.llm import get_llm_instance
from common.negotiation_utils import (
    NEGOTIATION_CONTEXT_KEY,
    NEGOTIATION_TEXT_KEY,
    build_negotiation_metadata,
    log_negotiation_context,
)


class NegotiationBaseAgentExecutor(AgentExecutor):
    def __init__(self, agent_prompt_template: str) -> None:
        self.llm = get_llm_instance()
        env_path = get_a2at_env_path()
        self.a2at_server = A2ATServer(env_path=env_path)
        self.prompt_template = agent_prompt_template
        logger.info(f"[{self.__class__.__name__}] Initialized with A2ATServer, env_path={env_path}")

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user_input = context.get_user_input()
        
        negotiation_result = self._start_negotiation(user_input)
        
        negotiation_context_data = negotiation_result.get(NEGOTIATION_CONTEXT_KEY, {})
        if negotiation_context_data:
            try:
                negotiation_ctx = NegotiationContext.from_context(negotiation_context_data)
                log_negotiation_context(negotiation_ctx, f"[{self.__class__.__name__}]")
            except Exception as e:
                logger.warning(f"Failed to parse negotiation context: {e}")
        
        response = await asyncio.to_thread(self._execute_task, user_input)
        
        task = self._build_task_response(
            context=context,
            response=response,
            negotiation_context=negotiation_context_data
        )
        
        logger.info(f"[{self.__class__.__name__}] Task completed successfully")
        await event_queue.enqueue_event(task)

    def _start_negotiation(self, user_input: str) -> Dict[str, Any]:
        try:
            negotiation_result = self.a2at_server.start_negotiation(
                StartNegotiationInput(
                    type=NegotiationType.FULFILLMENT,
                    content_text=user_input,
                    facts={"agent": self.__class__.__name__}
                )
            )
            negotiation_text = negotiation_result.get(NEGOTIATION_TEXT_KEY)
            if negotiation_text:
                logger.info(f"[{self.__class__.__name__}] Started fulfillment negotiation: {negotiation_text[:100]}...")
            else:
                logger.info(f"[{self.__class__.__name__}] Started fulfillment negotiation (no text in result)")
            return negotiation_result
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Failed to start negotiation: {e}")
            return {}

    def _execute_task(self, user_input: str) -> str:
        prompt = self.prompt_template.format(task=user_input)
        _, res = self.llm.ask_llm(prompt)
        logger.info(f"[{self.__class__.__name__}] Task: {user_input[:50]}..., Result: {res[:100]}...")
        return res

    def _build_task_response(
        self,
        context: RequestContext,
        response: str,
        negotiation_context: Dict[str, Any]
    ) -> Task:
        metadata: Dict[str, Any] = {}
        if negotiation_context:
            metadata["negotiationContext"] = negotiation_context
        
        return Task(
            id=context.task_id,
            context_id=context.context_id,
            status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
            artifacts=[
                Artifact(
                    artifact_id=str(uuid.uuid4()),
                    parts=[Part(text=response)]
                )
            ],
            metadata=metadata
        )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        logger.info(f"[{self.__class__.__name__}] Task cancelled: {context.task_id}")