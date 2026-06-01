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

import yaml
from pathlib import Path
from typing import List, Dict, Any
from a2a.types import AgentCard
from google.protobuf.json_format import Parse
from loguru import logger


_CARDS_DIR = Path(__file__).parent / "agentcard"


class AgentCardLoader:

    def __init__(self):
        pass

    def _get_config_file(self) -> Path:
        return _CARDS_DIR / "agent_cards.yaml"

    def get_all_agent_cards(self) -> List[AgentCard]:
        cards = []
        for agent_dict in self.get_raw_agent_dicts():
            try:
                agent_card = Parse(json.dumps(agent_dict), AgentCard())
                cards.append(agent_card)
            except Exception as e:
                logger.warning(f"Failed to parse AgentCard: {agent_dict.get('name', 'unknown')} - {e}")
        return cards

    def get_raw_agent_dicts(self) -> List[Dict[str, Any]]:
        config_file = self._get_config_file()
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if not config:
            raise ValueError(f"Configuration file is empty or has invalid format: {config_file}")
        if "agents" not in config:
            raise ValueError(f"Invalid configuration format, missing 'agents' field: {config_file}")
        agents_data = config["agents"]
        if not isinstance(agents_data, list):
            raise ValueError(f"The 'agents' field in configuration must be a list: {config_file}")
        return agents_data
