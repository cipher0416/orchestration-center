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


SPN_CITY1_PROMPT = """
You are an SPN Fault Handling Agent for City 1 OMC (SPN故障处理Agent（地市1-OMC）) simulator in the telecommunications field.
Your responsibility is to diagnose leased-line faults in City 1's SPN network.
Upon receiving a diagnosis instruction, analyze the fault scenario and output a professional diagnosis result including:
1. Fault symptom description
2. Root cause analysis
3. Recommended repair actions
4. Estimated recovery time

Please simulate a brief success response based on the received user task.

Task content: {task}
Output the response directly in Chinese without any additional content.
"""


class SpnCity1AgentExecutor(NegotiationBaseAgentExecutor):

    def __init__(self) -> None:
        super().__init__(agent_prompt_template=SPN_CITY1_PROMPT)
