from enum import Enum

from common.llm.config.config_reader import read_config_as_json


class LLMType(Enum):
    QWEN3_32B = "qwen3-32b"
    DEEPSEEK_CHAT = "deepseek-chat"


def convert_llm_type(llm_type: str) -> LLMType:
    for member in LLMType:
        if member.value == llm_type:
            return member
    return LLMType.QWEN3_32B


class LLMConfigItem:
    description: str
    model: str
    api: str
    version: str

    def __init__(self, config: dict):
        self.description = config.get("description", "")
        self.api = config.get("api", "")
        self.model = config.get("model", "")
        self.version = config.get("version", "")
        self.apikey = config.get("api_key", "")


class LLMConfig:
    llm_type: LLMType
    config_item: LLMConfigItem

    def __init__(self, llm_type: str, config_item: dict):
        self.llm_type = convert_llm_type(llm_type)
        self.config_item = LLMConfigItem(config_item)


def get_llm_config() -> {str, LLMConfig}:
    config: dict[str, dict] = read_config_as_json("../../config/llm_config.json")
    llm_config_item = {}
    for key, config_item in config.items():
        llm_config_item[key] = LLMConfig(key, config_item)
    return llm_config_item


llm_config = get_llm_config()


def get_llm_config_by_type(llm_type: LLMType) -> LLMConfig | None:
    if llm_type.value in llm_config:
        return llm_config[llm_type.value]
    raise ("llm_config for llm_type can not be None, check you llm_config.json")
