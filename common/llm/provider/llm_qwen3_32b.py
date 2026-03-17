import json
import re
import requests
from typing import Union, Tuple

from common.llm.config.llm_config import LLMType, LLMConfig
from common.llm.provider.base_llm import BaseLLM
from common.llm.provider.llm_provider_registry import register_provider


@register_provider(LLMType.QWEN3_32B)
class Qwen3LLM(BaseLLM):
    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)

    def _ask_llm(self, prompt: str) -> Union[str, Tuple[str, str]]:
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": f"{prompt}"
            }],
            "stream": False
        }
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        response = requests.request("post", self.base_url, headers=headers, data=json.dumps(payload))
        res = response.json()['choices'][0]['message']['content']

        pattern = r'<think>(.*?)</think>'
        ob = re.findall(pattern, res, re.DOTALL)
        think = ob[0].strip() if ob else ""
        index = res.find('</think>')
        ans = res[index + len('</think>'):]
        return think, ans
