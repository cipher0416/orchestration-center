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
Your responsibilities include:
1. Dispatching leased-line fault diagnosis instructions to SPN fault handling agents in different cities simultaneously.
2. Collecting and aggregating diagnosis results from multiple cities.
3. Performing comprehensive analysis on the aggregated results and generating a summary report.

Please simulate a brief success response based on the received user task. When you receive upstream step context containing diagnosis results from SPN agents, incorporate those results into your analysis and output a comprehensive summary report.

Task content: {task}
Output the response directly in Chinese without any additional content.
"""


class DispatchAgentExecutor(NegotiationBaseAgentExecutor):

    def __init__(self) -> None:
        super().__init__(agent_prompt_template=DISPATCH_AGENT_PROMPT)
