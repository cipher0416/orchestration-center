import logging
import time
from abc import abstractmethod, ABC
from typing import Union, Tuple

from common.llm.config.llm_config import LLMConfig

logger = logging.getLogger(__name__)


class BaseLLM(ABC):
    llm_config: LLMConfig

    def __init__(self, config: LLMConfig):
        self.llm_config = config
        self.model = config.config_item.model
        self.base_url = config.config_item.api
        self.api_key = config.config_item.apikey

    def ask_llm(self, prompt) -> Union[str, Tuple[str, str]]:
        start_time = time.time()
        try:
            result = self._ask_llm(prompt)
            duration = time.time() - start_time
            logger.info(f"ask llm cost {duration:.1f} s")
            return result
        except Exception as e:
            logger.error(f"ask llm exception {e}")
        return ""

    def ask_llm_with_duration(self, prompt):
        start_time = time.time()
        ans = self.ask_llm(prompt)
        duration = time.time() - start_time
        return ans, duration

    def to_dict(self):
        return {
            "name": self.llm_config.llm_type.value
        }

    @abstractmethod
    def _ask_llm(self, prompt: str) -> Union[str, Tuple[str, str]]:
        """_ask_llm function is implemented by inherited class"""
