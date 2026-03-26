import json
from typing import Dict, Any, Optional, Callable

import httpx
from a2a.client import ClientConfig, ClientFactory, create_text_message_object
from a2a.types import TransportProtocol
from a2a.utils import get_message_text
from loguru import logger

from framework.llm import get_or_create_deepseek_llm_instance
from framework.orchestration.model.psop import PSOP, Step, TaskStatus


class DynamicWorkflowEngine:
    def __init__(self, psop: PSOP, agent_cards):
        self.workflow = psop
        self.current_step_idx = 0
        self.execution_history = []
        self.llm_client = get_or_create_deepseek_llm_instance()
        self.agent_cards = agent_cards
        self.push_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    
    def set_push_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        self.push_callback = callback
    
    def _push_event(self, event_type: str, data: Dict[str, Any]):
        logger.info(f'push {event_type}:{data}')
        if self.push_callback:
            try:
                self.push_callback(event_type, data)
            except Exception as e:
                logger.error(f"推送事件失败: {e}")

    async def run(self):
        logger.info(f"启动PSOP工作流，共 {len(self.workflow.steps)} 个步骤")
        try:
            while self.current_step_idx < len(self.workflow.steps):
                await self._execute_single_step()
        except Exception as e:
            logger.critical(f"引擎发生未预期异常：{e}", exc_info=True)
            raise
        
        return self.execution_history

    async def send_message_to_agent(self, agent_name: str, task: str, httpx_client=None):
        agent_card = None
        for card in self.agent_cards:
            if card.name == agent_name:
                agent_card = card
        if not agent_card:
            raise RuntimeError(f"未找到Agent: {agent_name}")
        
        try:
            timeout_config = httpx.Timeout(
                connect=60,
                read=60,
                write=60,
                pool=10.0
            )
            config = ClientConfig(
                httpx_client=httpx.AsyncClient(timeout=timeout_config),
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                streaming=agent_card.capabilities.streaming if agent_card.capabilities else False,
            )
            client = ClientFactory(config).create(agent_card)
            request = create_text_message_object(content=task)
            # 推送请求信息
            try:
                request_data = request.model_dump_json() if hasattr(request, 'model_dump_json') else str(request)
            except:
                request_data = str(request)
            
            self._push_event("agent_request", {
                "agent": agent_name,
                "request": request_data
            })
            response_text = None
            last_response = None
            
            async for response in client.send_message(request):
                # response is a tuple of (task, metadata)
                task_obj, metadata = response
                last_response = response
                # Try to get text from artifacts
                try:
                    # 使用类型忽略来避免静态类型检查错误
                    if hasattr(task_obj, 'artifacts') and task_obj.artifacts:  # type: ignore
                        response_text = get_message_text(task_obj.artifacts[-1])  # type: ignore
                    else:
                        response_text = str(task_obj)
                except Exception as artifact_error:
                    logger.warning(f"获取artifact文本失败: {artifact_error}")
                    response_text = str(task_obj)
                finally:
                    # 推送响应信息
                    try:
                        response_data = task_obj.model_dump_json() if hasattr(task_obj, 'model_dump_json') else str(task_obj)
                    except:
                        response_data = str(task_obj)
                    
                    self._push_event("agent_response", {
                        "agent": agent_name,
                        "response": response_data
                    })

            
            if response_text is not None:
                return response_text
            elif last_response is not None:
                # 如果无法提取文本，至少返回最后一个响应对象
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

    async def _execute_single_step(self):
        current_step = self.workflow.steps[self.current_step_idx]
        logger.info(f"--- 正在执行步骤:{current_step.name} ---")

        step_result, success = await self._execute_subtasks(current_step)
        if not success:
            logger.error(f"步骤{current_step.name} 执行失败，触发错误处理策略：停止流程。")
            self._record_stop_event("Task execution failed", step_result)
            self.current_step_idx = len(self.workflow.steps)
            return
        await self._process_llm_decision(current_step, step_result)

    async def _process_llm_decision(self, current_step, step_result):
        next_step_name = self._llm_route_decision(current_step, step_result)
        if next_step_name == "end":
            logger.info(f"流程正常（LLM判定）。")
            self.current_step_idx = len(self.workflow.steps)
        elif next_step_name == "retry":
            logger.warning("请求重试，当前逻辑不支持子哦对那个重试，终止流程。")
            self.current_step_idx = len(self.workflow.steps)
        else:
            target_idx = self._find_step_index(next_step_name)
            if target_idx is not None:
                self.current_step_idx = target_idx
                logger.info(f"跳转至下一步：{next_step_name} (索引：{target_idx})")
            else:
                logger.error(f"目标步骤  '{next_step_name}'不存在，终止流程。")

    def _record_stop_event(self, reason, details):
        self.execution_history.append({
            "event": "STOPPED",
            "reason": reason,
            "details": details
        })

    async def _execute_subtasks(self, step: Step) -> tuple[Dict[str, Any], bool]:
        results = {}
        overall_success = True
        for task in step.subtasks:
            try:
                logger.info(f"   > 调用Agent ： {task.agent}, Skill: {task.skill}, Desc : {task.description}")
                
                raw_output = await self.send_message_to_agent(task.agent, task.description)
                task.status = TaskStatus.SUCCESS
                results[task.description] = raw_output

                # 推送完整的PSOP状态
                try:
                    psop_data = self.workflow.model_dump_json() if hasattr(self.workflow, 'model_dump_json') else self.workflow.model_dump()
                except:
                    psop_data = str(self.workflow)
                
                self._push_event("psop_update", {
                    "psop": psop_data
                })
                
                self.execution_history.append({
                    "step": step.name,
                    "task": task.description,
                    "status": "SUCCESS",
                    "output": raw_output[:200]
                })

            except Exception as e:
                task.status = TaskStatus.FAILED
                overall_success = False
                error_msg = f"Agent call failed : {str(e)}"
                results[task.skill] = {"error": error_msg}
                logger.error(f"  >Task失败：{task.description} | Error : {error_msg}")
                
                # 推送失败时的PSOP状态
                try:
                    psop_data = self.workflow.model_dump_json() if hasattr(self.workflow, 'model_dump_json') else self.workflow.model_dump()
                except:
                    psop_data = str(self.workflow)
                
                self._push_event("psop_update", {
                    "psop": psop_data
                })
                
                self.execution_history.append({
                    "step": step.name,
                    "task": task.description,
                    "status": "FAILED",
                    "output": error_msg
                })
                break
        return results, overall_success

    def _llm_route_decision(self, current_step: Step, task_result: Dict[str, Any]) -> str:
        results_context = []
        for skill, res in task_result.items():
            if isinstance(res, dict) and "error" in res:
                results_context.append(f"[{skill}]: 执行失败 - {res['error']}")
            else:
                text_res = res if isinstance(res, str) else str(res)
                text_res = text_res[:500] if len(text_res) > 500 else text_res
                results_context.append(f"[{skill}]:执行成功 - 输出摘要：{text_res}")
        results_text = "\n".join(results_context)
        prompt_template = f"""
# Role
你是一个工作流逻辑控制器。你的任务是根据【任务执行结果】和【预设条件】，决定工作流的下一步走向。

# Current context
当前步骤： {current_step.name}
步骤类型： {current_step.type.value}

# Execution Result (Previous Step Output)
{results_text}

# Next Conditions (Required for Transition)
{json.dumps([{"step": c.step, "condition": c.condition} for c in (current_step.next or [])], ensure_ascii=False, indent=2)}

# Decision Logic
1. 分析上述【Execution Results】。
2. 检查是否满足任意一条【Next Conditions】中的'condition' 描述。
    - 如果'condition'是"xx成功"，请检查结果中是否有 xx 成功的证据。
    - 如果'condition'为空字符串('""')，通常表示无条件跳转至下一个step。
3. 如果满足条件，输出对应的目标'step'名称。
4. 如果不满足条件，或者任务执行中出现了'error'，输出"end"。
5. 如果结果模糊不清但看似成功，输出"retry"表示需要人工介入或重试。

# Output Format
- 仅输出一个单词或短语：目标 Step 名称（如 "step2"）,"end", 或"retry"。
- 不要输出任何解释、标点符号或其他字符。
"""
        if not self.llm_client:
            raise ValueError("LLM Client not initialized. Please set engine.llm_client.")
        try:
            _, decision = self.llm_client.ask_llm(prompt_template)
            decision = decision.strip().lower()
            logger.info(f'LLM 选择的下一步: {decision}')
            if decision in ["end", "retry"]:
                return decision
            step_names = [s.name for s in self.workflow.steps]
            if decision in step_names:
                return decision
            else:
                logger.warning(f"LLM返回了非法的 Step 名称 : '{decision}', 默认终止。")
                return "end"
        except Exception as e:
            logger.error(f"LLM 调用失败:{e}")
            return "end"

    def _find_step_index(self, step_name: str) -> Optional[int]:
        for i, step in enumerate(self.workflow.steps):
            if step.name == step_name:
                return i
        return None
