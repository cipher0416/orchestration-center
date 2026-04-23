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
from typing import Dict, Any, Tuple, List

from common.llm.config.llm_config import LLMType, LLMConfig
from common.llm.provider.aoc_base_llm import AOCBaseLLM
from common.llm.provider.llm_provider_registry import registry_provider


@registry_provider(LLMType.AOC_EMBEDDING_LLM)
class AOCEmbeddingLLM(AOCBaseLLM):
    """AOC 嵌入模型（如 bge_m3）"""

    def _build_request_body(self, prompt: str) -> Dict[str, Any]:
        # 默认格式：{"model": "...", "input": "..."}
        extra = self.llm_config.config_item.extra
        template = extra.get('request_template')
        if template and isinstance(template, str):
            template_str = template.replace('{prompt}', json.dumps(prompt)[1:-1])
            return json.loads(template_str)
        else:
            return {
                "model": self.model,
                "input": prompt
            }

    def _parse_response(self, data: Dict[str, Any]) -> Tuple[str, str]:
        # 将向量转为字符串，便于基类返回
        vector = self._extract_embedding(data)
        return '', json.dumps(vector)

    def _extract_embedding(self, data: Dict[str, Any]) -> List[float]:
        """从响应中提取向量，子类可覆盖以适应不同返回格式"""
        # 常见格式：{"data": [{"embedding": [...]}]}
        try:
            return data['data'][0]['embedding']
        except (KeyError, IndexError, TypeError):
            # 尝试其他格式或抛出异常
            raise ValueError(f"无法从响应中提取嵌入向量: {data}")

    def embed(self, prompt: str) -> List[float]:
        """
        专门用于获取嵌入向量的方法，返回浮点数列表。
        """
        headers = self._build_headers()
        body = self._build_request_body(prompt)
        response = self.client.post(self.base_url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
        return self._extract_embedding(data)

    # 重写 _ask_llm，使其调用 embed 并返回字符串（兼容基类）
    def _ask_llm(self, prompt: str) -> Tuple[str, str]:
        vector = self.embed(prompt)
        return '', json.dumps(vector)