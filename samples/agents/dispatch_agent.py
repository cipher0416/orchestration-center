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

from samples.agents.negotiation_base_agent import NegotiationBaseAgentExecutor


DISPATCH_AGENT_PROMPT = """
You are a Transport Workbench Agent (传输工作台Agent) simulator in the telecommunications field.
Follow the specific task described in the received message:
- If the task is about dispatching diagnosis instructions to city agents, confirm the dispatch action with the specified cities and fault scenario details. Do NOT simulate downstream diagnosis results or generate a summary report.
- If the task is about aggregating results, use ONLY the upstream context provided to synthesize a concise summary report.

Task content: {task}
Output directly in Chinese, concise and professional. Do not add extra content beyond the task scope.
"""


class DispatchAgentExecutor(NegotiationBaseAgentExecutor):

    def __init__(self) -> None:
        super().__init__(agent_prompt_template=DISPATCH_AGENT_PROMPT)
