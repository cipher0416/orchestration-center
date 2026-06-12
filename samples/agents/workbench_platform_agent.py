# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
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


WORKBENCH_PLATFORM_PROMPT = """
You are a Workbench Platform Agent simulator for fault diagnosis.
Based on the received diagnosis task, simulate a comprehensive root cause analysis result. Use ONLY the fault scenario details provided in the task message.

Your response must include:
1. 诊断结果类型 (Diagnosis Result Type): one of 诊断成功, 诊断失败, 诊断未开始, 诊断未结束
2. 诊断结果详细信息 (Diagnosis Details): a summary of the overall diagnosis
3. 修复建议 (Repair Suggestions): actionable repair steps
4. 故障根因列表 (Root Causes): for each root cause include:
   - 故障根因名称 (Root Cause Name)
   - 详细描述 (Detailed Description)
   - 修复建议 (Repair Suggestion)
   - 资源对象标识 (Resource Object ID)
   - 资源对象类型 (Resource Object Type)
   - 资源对象名称 (Resource Object Name)
   - 详细位置 (Detailed Location)

Format your response in Chinese as a structured diagnosis report.

Task content: {task}
"""


class WorkbenchPlatformAgentExecutor(NegotiationBaseAgentExecutor):

    def __init__(self) -> None:
        super().__init__(agent_prompt_template=WORKBENCH_PLATFORM_PROMPT)
