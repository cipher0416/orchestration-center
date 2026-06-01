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
import copy
import json

import yaml
from pathlib import Path
from typing import List, Dict, Any
from a2a.types import AgentCard
from google.protobuf.json_format import Parse
from loguru import logger


def _localize_agent_dict(agent_dict: Dict[str, Any], lang: str) -> Dict[str, Any]:
    desc_key = f"description_{lang}"
    result = copy.deepcopy(agent_dict)

    if desc_key in result:
        result["description"] = result.pop(desc_key)
    elif "description" not in result:
        result["description"] = result.get("description_zh", "")

    for key in list(result.keys()):
        if key.startswith("description_"):
            result.pop(key, None)

    if "skills" in result and isinstance(result["skills"], list):
        for skill in result["skills"]:
            if desc_key in skill:
                skill["description"] = skill.pop(desc_key)
            elif "description" not in skill:
                skill["description"] = skill.get("description_zh", "")
            for sk in list(skill.keys()):
                if sk.startswith("description_"):
                    skill.pop(sk, None)

    return result


class AgentCardLoader:
    """
    AgentCard library supporting bilingual (zh/en) descriptions.
    """

    def __init__(self):
        self.config_file = Path(__file__).parent / "agentcard" / "agent_cards.yaml"
        self._raw_agents: List[Dict[str, Any]] = []
        self._load_raw_config()

    def _load_raw_config(self) -> None:
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")

        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if not config:
            raise ValueError(f"Configuration file is empty or has invalid format: {self.config_file}")

        if "agents" not in config:
            raise ValueError(f"Invalid configuration format, missing 'agents' field: {self.config_file}")

        agents_data = config["agents"]
        if not isinstance(agents_data, list):
            raise ValueError(f"The 'agents' field in configuration must be a list: {self.config_file}")

        self._raw_agents = agents_data

    def get_all_agent_cards(self, lang: str = "zh") -> List[AgentCard]:
        cards = []
        for agent_dict in self._raw_agents:
            try:
                localized = _localize_agent_dict(agent_dict, lang)
                agent_card = Parse(json.dumps(localized), AgentCard())
                cards.append(agent_card)
            except Exception as e:
                logger.warning(f"Failed to parse AgentCard: {agent_dict.get('name', 'unknown')} - {e}")
        return cards
