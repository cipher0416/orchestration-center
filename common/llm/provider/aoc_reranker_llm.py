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
from typing import Dict, Any, Tuple, List, Optional

from common.llm.config.llm_config import LLMType, LLMConfig
from common.llm.provider.aoc_base_llm import AOCBaseLLM
from common.llm.provider.llm_provider_registry import registry_provider


@registry_provider(LLMType.AOC_RERANKER_LLM)
class AOCRerankerLLM(AOCBaseLLM):
    """AOC 重排模型（如 bge_reranker_v2_m3）"""

    def _build_request_body(self, prompt: str) -> Dict[str, Any]:
        # prompt 在这里是 query；documents 需要额外传入，此处先占位
        extra = self.llm_config.config_item.extra
        template = extra.get('request_template')
        if template and isinstance(template, str):
            template_str = template.replace('{prompt}', json.dumps(prompt)[1:-1])
            return json.loads(template_str)
        else:
            # 默认格式：需要 query 和 documents，但 documents 需由调用者提供
            # 因此重排模型更适合提供专用的 rerank 方法
            raise NotImplementedError("请通过 rerank(query, documents) 方法调用重排模型")

    def _parse_response(self, data: Dict[str, Any]) -> Tuple[str, str]:
        # 不直接使用
        return '', json.dumps(data)

    def rerank(self, query: str, documents: List[str]) -> List[Dict[str, Any]]:
        """
        重排接口，返回排序结果列表，每个元素包含 index 和 relevance_score。
        """
        extra = self.llm_config.config_item.extra
        template = extra.get('request_template')
        if template and isinstance(template, str):
            # 替换 {query} 和 {documents} 占位符（注意 documents 是 JSON 数组）
            template_str = template.replace('{query}', json.dumps(query)[1:-1])
            template_str = template_str.replace('{documents}', json.dumps(documents))
            body = json.loads(template_str)
        else:
            body = {
                "model": self.model,
                "query": query,
                "documents": documents
            }

        headers = self._build_headers()
        response = self.client.post(self.base_url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

        # 提取排序结果（假设格式为 {"results": [{"index": 0, "relevance_score": 0.9}]}）
        try:
            return data.get('results', [])
        except Exception:
            raise ValueError(f"无法解析重排响应: {data}")

    def _ask_llm(self, prompt: str) -> Tuple[str, str]:
        # 不支持直接调用，建议使用 rerank
        raise NotImplementedError("请使用 rerank(query, documents) 方法")