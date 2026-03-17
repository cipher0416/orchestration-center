import httpx
from common.llm.provider.llm_provider_registry import register_provider
from openai import OpenAI
from typing import Tuple, Union

from common.llm.config.llm_config import LLMType, LLMConfig
from common.llm.provider.base_llm import BaseLLM

@register_provider(LLMType.DEEPSEEK_CHAT)
class DeepSeekChatLLM(BaseLLM):
    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            http_client=httpx.Client(
                base_url=self.base_url,
                follow_redirects=True,
                verify=False
            )
        )

    def _ask_llm(self, prompt: str) -> Union[str, Tuple[str, str]]:
        user_message = {"role": "user",
                        "content": prompt}
        completion = self.client.chat.completions.create(
            model=self.llm_config.config_item.model,
            messages=[
                user_message
            ]
        )
        return "", completion.choices[0].message.content
