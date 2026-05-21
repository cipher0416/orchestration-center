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

import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.helpers import new_text_message
from a2a.types import SendMessageRequest
from google.protobuf.json_format import MessageToJson, MessageToDict
from loguru import logger

try:
    from a2a_t.client import A2ATClient
    from samples.a2at_config import get_a2at_env_path
    from samples.negotiation_utils import (
        extract_negotiation_context_from_task_metadata,
        log_negotiation_context,
    )
    _A2AT_AVAILABLE = True
except ImportError:
    _A2AT_AVAILABLE = False
    A2ATClient = None

from common.llm import get_llm_instance
from orchestrate.core.model.psop import PSOP, Step, Task, TaskStatus

class DynamicWorkflowEngine:
    def __init__(self, psop: PSOP, agent_cards, runtime_intent: str = None, a2at_env_path: Path = None):
        self.workflow = psop
        self.runtime_intent = runtime_intent
        self.current_step_idx = 0
        self.execution_history = []
        self.llm_client = get_llm_instance()
        self.agent_cards = agent_cards
        self.push_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.step_outputs: Dict[str, Dict[str, Any]] = {}
        self.a2at_client = None

        if _A2AT_AVAILABLE:
            env_path = a2at_env_path or get_a2at_env_path()
            try:
                self.a2at_client = A2ATClient(env_path=env_path)
                logger.info(f"DynamicWorkflowEngine initialized with A2ATClient, env_path={env_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize A2ATClient: {e}, continuing without negotiation support")
        else:
            logger.debug("a2a_t not available, negotiation support disabled")


    def set_push_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        self.push_callback = callback

    def _push_event(self, event_type: str, data: Dict[str, Any]):
        log_data = dict(data)
        if event_type == "agent_response" and isinstance(log_data.get("response"), str):
            try:
                log_data["response"] = json.loads(log_data["response"])
            except (json.JSONDecodeError, TypeError):
                pass
        try:
            serialized = json.dumps(log_data, indent=4, ensure_ascii=False, default=str)
        except Exception:
            serialized = str(log_data)
        logger.info(f"push {event_type}:\n{serialized}")
        if self.push_callback:
            try:
                self.push_callback(event_type, data)
            except Exception as e:
                logger.error(f"Failed to push event: {e}")

    async def run(self):
        logger.info(f"Starting PSOP workflow, total {len(self.workflow.steps)} steps")
        pending = [i for i, s in enumerate(self.workflow.steps) if s.layer == 0 and not self._get_step_predecessors(s.name)]
        executed = set()
        defer_count = {}
        try:
            while pending:
                idx = pending.pop(0)
                if idx >= len(self.workflow.steps) or idx in executed:
                    continue
                current_step = self.workflow.steps[idx]
                predecessors = self._get_step_predecessors(current_step.name)
                if not all(p in self.step_outputs for p in predecessors):
                    dc = defer_count.get(idx, 0) + 1
                    if dc > len(self.workflow.steps):
                        logger.warning(f"Step {current_step.name} waiting too long, skipping")
                        executed.add(idx)
                        continue
                    defer_count[idx] = dc
                    pending.append(idx)
                    continue
                executed.add(idx)
                self.current_step_idx = idx
                current_step = self.workflow.steps[idx]
                logger.info(f"--- Executing step: {current_step.name} ---")

                step_result, success = await self._execute_subtasks(current_step)
                if not success:
                    logger.error(
                        f"Step {current_step.name} execution failed, stopping workflow.")
                    self._record_stop_event("Task execution failed", step_result)
                    break
                self.step_outputs[current_step.name] = step_result

                next_indices = self._determine_next_steps(current_step, step_result)
                for nxt in reversed(next_indices):
                    if nxt not in executed and nxt not in pending:
                        pending.insert(0, nxt)
        except Exception as e:
            logger.critical(f"Unexpected exception occurred in engine: {e}", exc_info=True)
            raise

        return self.execution_history

    def _determine_next_steps(self, step: Step, step_result: Dict[str, Any]) -> List[int]:
        if not step.next:
            return []
        if all(jc.condition == "" for jc in step.next):
            indices = []
            for jc in step.next:
                if jc.step in ("end", "retry", "endNode"):
                    continue
                tgt = self._find_step_index(jc.step)
                if tgt is not None:
                    target_step = self.workflow.steps[tgt]
                    predecessors = self._get_step_predecessors(target_step.name)
                    if all(p in self.step_outputs for p in predecessors):
                        indices.append(tgt)
            return indices
        next_name = self._llm_route_decision(step, step_result)
        if next_name in ("end", "retry"):
            return []
        tgt = self._find_step_index(next_name)
        if tgt is not None:
            target_step = self.workflow.steps[tgt]
            predecessors = self._get_step_predecessors(target_step.name)
            if not all(p in self.step_outputs for p in predecessors):
                return []
        return [tgt] if tgt is not None else []

    async def send_message_to_agent(self, agent_name: str, task: str, httpx_client=None):
        agent_card = None
        for card in self.agent_cards:
            if card.name == agent_name:
                agent_card = card
        if not agent_card:
            raise RuntimeError(f"Agent not found: {agent_name}")

        task_text = task
        if self.a2at_client:
            try:
                prompt_result = self.a2at_client.generate_task_prompt(task)
                if prompt_result.success and prompt_result.prompt_text:
                    task_text = prompt_result.prompt_text
                    logger.info(f"[A2AT] Generated task prompt for agent '{agent_name}'")
                else:
                    logger.warning(f"[A2AT] Task prompt generation failed, using original task")
            except Exception as e:
                logger.warning(f"[A2AT] Failed to generate task prompt: {e}")

        try:
            timeout_config = httpx.Timeout(
                connect=60,
                read=60,
                write=60,
                pool=10.0
            )
            config = ClientConfig(
                httpx_client=httpx.AsyncClient(timeout=timeout_config),
                supported_protocol_bindings=[
                    "JSONRPC",
                    "HTTP+JSON",
                ],
                streaming=agent_card.capabilities.streaming if agent_card.capabilities else False,
            )
            client = ClientFactory(config).create(agent_card)
            request = new_text_message(text=task_text)
            # Push request information
            try:
                request_data = request.model_dump_json() if hasattr(request, 'model_dump_json') else str(request)
            except Exception:
                request_data = str(request)

            self._push_event("agent_request", {
                "agent": agent_name,
                "request": request_data
            })
            response_text = None
            last_response = None

            from a2a.types import Task, Message

            async for response in client.send_message(SendMessageRequest(message=request)):
                # response is now a StreamResponse object, containing both Task and Message objects
                task_result = response.task
                message_result = response.message

                last_response = response

                # Process response
                if isinstance(task_result, Task):
                    response_text = ""
                    if hasattr(task_result, 'artifacts') and task_result.artifacts:
                        for artifact in task_result.artifacts:
                            if hasattr(artifact, 'parts') and artifact.parts:
                                for part in artifact.parts:
                                    if hasattr(part, 'text') and part.text:
                                        response_text += part.text

                    if hasattr(task_result, 'metadata') and task_result.metadata:
                        metadata = task_result.metadata
                        if isinstance(metadata, dict):
                            metadata_dict = metadata
                        else:
                            metadata_dict = MessageToDict(metadata, preserving_proto_field_name=True)
                        negotiation_ctx = extract_negotiation_context_from_task_metadata(metadata_dict)
                        if negotiation_ctx:
                            log_negotiation_context(negotiation_ctx, f"[{agent_name}]")

                    response_data = MessageToJson(task_result, preserving_proto_field_name=True)
                    self._push_event("agent_response", {
                        "agent": agent_name,
                        "response": response_data
                    })

                elif isinstance(message_result, Message):
                    # Handle Message type response
                    response_text = ""
                    if hasattr(message_result, 'parts') and message_result.parts:
                        for part in message_result.parts:
                            if hasattr(part, 'text') and part.text:
                                response_text += part.text

                    # Push response information
                    response_data = MessageToJson(message_result, preserving_proto_field_name=True)
                    self._push_event("agent_response", {
                        "agent": agent_name,
                        "response": response_data
                    })

            if response_text is not None:
                return response_text
            elif last_response is not None:
                # If text cannot be extracted, at least return the last response object
                return str(last_response)
            else:
                raise RuntimeError("Agent completed but no response received")
        except httpx.TimeoutException as e:
            raise RuntimeError(f"Agent call timed out") from e
        except httpx.ConnectError as e:
            raise RuntimeError(f"Faild to connect to Agent : {e}") from e
        except Exception as e:
            logger.error(f"Communicate with agent failed : {e}", exc_info=True)
            raise

    async def _process_llm_decision(self, current_step, step_result):
        next_step_name = self._llm_route_decision(current_step, step_result)
        if next_step_name == "end":
            logger.info(f"Process normal (LLM determined).")
            self.current_step_idx = len(self.workflow.steps)
        elif next_step_name == "retry":
            logger.warning("Request retry, current logic does not support automatic retry, terminating process.")
            self.current_step_idx = len(self.workflow.steps)
        else:
            target_idx = self._find_step_index(next_step_name)
            if target_idx is not None:
                self.current_step_idx = target_idx
                logger.info(f"Jump to next step: {next_step_name} (index: {target_idx})")
            else:
                logger.error(f"Target step '{next_step_name}' does not exist, terminating process.")

    def _record_stop_event(self, reason, details):
        self.execution_history.append({
            "event": "STOPPED",
            "reason": reason,
            "details": details
        })

    async def _execute_subtasks(self, step: Step) -> tuple[Dict[str, Any], bool]:
        results = {}
        overall_success = True
        context_message = self._build_context_for_step(step)
        for task in step.subtasks:
            try:
                logger.info(f"   > Calling Agent: {task.agent}, Skill: {task.skill}, Desc: {task.description}")

                task_message = self._build_task_message(task, context_message)
                raw_output = await self.send_message_to_agent(task.agent, task_message)
                task.status = TaskStatus.SUCCESS
                results[task.description] = raw_output

                # Push complete PSOP status
                try:
                    psop_data = (
                        self.workflow.model_dump_json()
                        if hasattr(self.workflow, 'model_dump_json')
                        else self.workflow.model_dump()
                    )
                except Exception:
                    psop_data = str(self.workflow)

                self._push_event("psop_update", {
                    "psop": psop_data
                })

                self.execution_history.append({
                    "step": step.name,
                    "task": task.description,
                    "status": "success",
                    "output": raw_output[:200]
                })

            except Exception as e:
                task.status = TaskStatus.FAILED
                overall_success = False
                error_msg = f"Agent call failed : {str(e)}"
                results[task.skill] = {"error": error_msg}
                logger.error(f"  >Task failed: {task.description} | Error: {error_msg}")

                # Push PSOP status on failure
                try:
                    psop_data = (
                        self.workflow.model_dump_json()
                        if hasattr(self.workflow, 'model_dump_json')
                        else self.workflow.model_dump()
                    )
                except Exception:
                    psop_data = str(self.workflow)

                self._push_event("psop_update", {
                    "psop": psop_data
                })

                self.execution_history.append({
                    "step": step.name,
                    "task": task.description,
                    "status": "failed",
                    "output": error_msg
                })
                break
        return results, overall_success

    def _get_step_predecessors(self, step_name: str) -> List[str]:
        predecessors = []
        for s in self.workflow.steps:
            if s.next:
                for jc in s.next:
                    if jc.step == step_name:
                        predecessors.append(s.name)
                        break
        return predecessors

    def _build_context_for_step(self, step: Step) -> str:
        if step.layer <= 0:
            if self.runtime_intent:
                return f"## Runtime Context\n\nUser's original intent and scenario description:\n{self.runtime_intent}"
            return ""
        parts = []
        if self.runtime_intent:
            parts.append(f"## Runtime Context\n\nUser's original intent and scenario description:\n{self.runtime_intent}")
        parts.append("## Previous Step Execution Results\n")
        if step.context_from and "*" in step.context_from:
            ref_pairs = [(name, results) for name, results in self.step_outputs.items()]
        elif step.context_from:
            ref_pairs = [(name, self.step_outputs[name])
                         for name in step.context_from if name in self.step_outputs]
        else:
            predecessor_names = self._get_step_predecessors(step.name)
            ref_pairs = [(name, self.step_outputs[name])
                         for name in predecessor_names if name in self.step_outputs]
        for ref_step_name, ref_results in ref_pairs:
            parts.append(f"### {ref_step_name} Results")
            for task_desc, output in ref_results.items():
                text = output if isinstance(output, str) else str(output)
                parts.append(f"**Input (Task)**: {task_desc}")
                parts.append(f"**Output (Result)**: {text}")
                parts.append("")
        return "\n".join(parts).strip()

    @staticmethod
    def _build_task_message(task: Task, context_message: str) -> str:
        if context_message:
            return f"{context_message}\n\n## Current Task\n{task.description}"
        return task.description

    def _llm_route_decision(self, current_step: Step, task_result: Dict[str, Any]) -> str:
        results_context = []
        for skill, res in task_result.items():
            if isinstance(res, dict) and "error" in res:
                results_context.append(f"[{skill}]: Execution failed - {res['error']}")
            else:
                text_res = res if isinstance(res, str) else str(res)
                text_res = text_res[:500] if len(text_res) > 500 else text_res
                results_context.append(f"[{skill}]: Execution succeeded - Output summary: {text_res}")
        results_text = "\n".join(results_context)
        next_conditions = json.dumps(
            [{"step": c.step, "condition": c.condition} for c in (current_step.next or [])],
            ensure_ascii=False,
            indent=2,
        )
        prompt_template = f"""
# Role
You are a workflow logic controller. Your task is to determine the next step of the
workflow based on the task execution results and predefined conditions.

# Current Context
Current step: {current_step.name}
Step type: {current_step.type.value}

# Execution Results (Previous Step Output)
{results_text}

# Next Conditions (Required for Transition)
{next_conditions}

# Decision Logic
1. Analyze the Execution Results above.
2. Check whether any of the Next Conditions' "condition" descriptions are satisfied.
   - If a condition says e.g. "xx succeeded", check the results for evidence that xx succeeded.
   - An empty condition ('""') typically means unconditional transition to the next step.
3. If a condition is met, output the corresponding target step name.
4. If no condition is met, or the task execution contains an error, output "end".
5. If the result is ambiguous but appears successful, output "retry" to request manual intervention.

# Output Format
- Output exactly one word or phrase: the target step name (e.g. "step2"), "end", or "retry".
- Do NOT output any explanation, punctuation, or other characters.
"""
        if not self.llm_client:
            raise ValueError("LLM Client not initialized. Please set engine.llm_client.")
        try:
            _, decision = self.llm_client.ask_llm(prompt_template)
            decision = decision.strip()
            logger.info(f'LLM selected next step: {decision}')
            if decision in ["end", "retry"]:
                return decision
            step_names = [s.name for s in self.workflow.steps]
            if decision in step_names:
                return decision
            else:
                logger.warning(f"LLM returned illegal Step name: '{decision}', defaulting to termination.")
                return "end"
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return "end"

    def _find_step_index(self, step_name: str) -> Optional[int]:
        for i, step in enumerate(self.workflow.steps):
            if step.name == step_name:
                return i
        return None
