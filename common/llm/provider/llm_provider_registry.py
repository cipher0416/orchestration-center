from common.llm.config.llm_config import LLMType, LLMConfig
from common.llm.provider.base_llm import BaseLLM


class LLMProviderRegistry:
    def __init__(self):
        self.providers = {}

    def register(self, key, provider_cls):
        self.providers[key] = provider_cls

    def get_provider(self, llm_type: LLMType):
        return self.providers[llm_type]


def register_provider(keys):
    def decorator(cls):
        if isinstance(keys, list):
            for key in keys:
                LLM_REGISTRY.register(key, cls)
        else:
            LLM_REGISTRY.register(keys, cls)
        return cls

    return decorator


LLM_REGISTRY = LLMProviderRegistry()

llm_instance = {str: BaseLLM}


def get_or_create_llm_instance(config: LLMConfig) -> BaseLLM:
    if config.llm_type in llm_instance:
        return llm_instance[config.llm_type]
    else:
        llm = LLM_REGISTRY.get_provider(config.llm_type)(config)
        llm_instance[config.llm_type] = llm
        return llm
