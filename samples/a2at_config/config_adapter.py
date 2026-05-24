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

from pathlib import Path
import json
from typing import Optional
from loguru import logger


def get_a2at_env_path() -> Path:
    return Path(__file__).parent / ".env"


def get_llm_config_path() -> Path:
    return Path(__file__).parent.parent.parent / "config" / "llm_config.json"


def generate_env_from_llm_config(
    llm_config_path: Optional[Path] = None,
    env_output_path: Optional[Path] = None,
    llm_type: str = "openai_style_llm"
) -> Path:
    if llm_config_path is None:
        llm_config_path = get_llm_config_path()
    
    if env_output_path is None:
        env_output_path = get_a2at_env_path()
    
    if not llm_config_path.exists():
        raise FileNotFoundError(f"LLM config file not found: {llm_config_path}")
    
    try:
        config_content = llm_config_path.read_text(encoding='utf-8')
        config = json.loads(config_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in llm_config.json: {e}")
    
    llm_item = config.get(llm_type, {})
    if not llm_item:
        raise ValueError(f"LLM type '{llm_type}' not found in config")
    
    model = llm_item.get("model", "")
    api_key = llm_item.get("api_key", "")
    base_url = llm_item.get("api", "")
    
    if not model:
        raise ValueError("Missing 'model' in llm_config.json")
    
    a2at_provider = "deepseek"
    if "deepseek" in base_url.lower():
        a2at_provider = "deepseek"
    
    env_content = f"""# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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

# A2A-T SDK Configuration
# Auto-generated from config/llm_config.json

# Prompt runtime
A2AT_LANGUAGE=zh-CN
A2AT_PROMPT_SOURCE_TYPE=local_file
A2AT_PROMPT_RESOURCE_LOCAL_ROOT_DIR=

# Prompt compliance
A2AT_PROMPT_COMPLIANCE_ENABLED=false
A2AT_PROMPT_COMPLIANCE_GUARDRAIL_PROVIDER=noop

# LLM runtime
A2AT_LLM_PROVIDER={a2at_provider}
A2AT_LLM_MODEL={model}
A2AT_LLM_API_KEY={api_key}
A2AT_LLM_BASE_URL={base_url}
A2AT_LLM_MAX_TOKENS=2000
A2AT_LLM_TEMPERATURE=0
A2AT_LLM_TIMEOUT_SECONDS=60
A2AT_LLM_HISTORY_WINDOW=10
A2AT_LLM_SESSION_MAX_TOTAL=300
A2AT_LLM_SESSION_MAX_PER_PROVIDER=100

# Negotiation
A2AT_NEGOTIATION_STATE_STORE_TYPE=in_memory
"""
    
    env_output_path.write_text(env_content, encoding='utf-8')
    logger.info(f"Generated A2AT .env file at: {env_output_path}")
    return env_output_path


def ensure_env_file_exists() -> Path:
    env_path = get_a2at_env_path()
    if not env_path.exists():
        logger.warning(f"A2AT .env file not found, generating from llm_config.json")
        return generate_env_from_llm_config()
    
    env_content = env_path.read_text(encoding='utf-8')
    if "A2AT_LLM_MODEL=" in env_content:
        lines = env_content.split('\n')
        model_lines = [l for l in lines if l.startswith("A2AT_LLM_MODEL=")]
        if model_lines and model_lines[0].strip() == "A2AT_LLM_MODEL=":
            logger.info(f"A2AT .env file has empty LLM config, regenerating")
            return generate_env_from_llm_config()
    
    return env_path