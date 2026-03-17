import json
import logging
import re
from a2a.types import AgentCard
from orchestration.model.preflow import PreFlow
from orchestration.prompts import (
    get_preprocess_input_prompt,
    get_choose_skill_prompt,
    get_generate_psop_prompt
)
from orchestration.model.psop import PSOP
from pydantic import BaseModel
from typing import Type, Optional, Union, Any, Dict, List, TYPE_CHECKING

from common.llm.provider.llm_provider_registry import get_or_create_llm_instance
from common.llm.config.llm_config import get_llm_config_by_type, LLMType
logger = logging.getLogger(__name__)


class WorkflowGeneratorError(Exception):
    pass


class WorkflowGenerator:

    def __init__(self, llm_type: LLMType = LLMType.QWEN3_32B):
        self._config = get_llm_config_by_type(llm_type)
        self._llm = get_or_create_llm_instance(self._config)

    @staticmethod
    def _parse_json_respose(
            llm_reponse: str,
            output_model: Optional[Type[BaseModel]] = None
    ) -> Union[BaseModel, Dict[str, Any], List[Any]]:
        matches = re.findall(r''''json(.*?)''', llm_reponse, re.DOTALL)
        if not matches:
            error_msg = "No JSON code block found in LLM answer"
            logger.error(error_msg)
            raise ValueError(error_msg)

        json_str = matches[-1].strip()
        if not json_str:
            error_msg = "Empty JSON content found in code block"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            if output_model:
                return output_model.model_validate_json(json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format : {e}")
            raise
        except Exception as e:
            logger.error(f"Faild to parse JSON into model : {e}")
            raise

    def extract_tasks_from_steps(self, pre_wf_md: str) -> List[str]:
        try:
            prompt = get_preprocess_input_prompt(pre_wf_md)
            _, llm_res = self._llm.ask_llm(prompt)
            all_steps = self._parse_json_respose(llm_res)

            if not isinstance(all_steps, list):
                raise ValueError(f"Expected list from LLM response, got {type(all_steps)}")
            logger.info(f"成功提取{len(all_steps)}个任务:{all_steps}")
            return all_steps
        except Exception as e:
            raise WorkflowGeneratorError(f"Failed to extract tasks from steps : {e}") from e

    def match_actions_to_skills(
            self,
            actions: List[str],
            agents_card: List[AgentCard]
    ) -> Dict[str, Any]:
        try:
            actions_str = json.dumps(actions, ensure_ascii=False, indent=2)
            agent_cards_list = [
                {
                    'name': ac.name,
                    'description': ac.description,
                    'skills': [s.model_dump(include={"name", "description"}) for s in ac.skills]
                }
                for ac in agents_card
            ]
            agents_card_str = json.dumps(agent_cards_list, ensure_ascii=False, indent=2)
            prompt = get_choose_skill_prompt(actions_str, agents_card_str)
            _, llm_res = self._llm.ask_llm(prompt)
            action_skill_pairs = self._parse_json_respose(llm_res)
            if not isinstance(action_skill_pairs, dict):
                raise ValueError(f"Expected dict from LLM response, got {type(action_skill_pairs)}")
            logger.info(f"成功匹配动作与技能:共{len(action_skill_pairs)} 个匹配项")
            logger.info(f"匹配结果 : {action_skill_pairs}")
            return action_skill_pairs
        except Exception as e:
            raise WorkflowGeneratorError(f"Failed to match actions to skills : {e}") from e

    def build_psop_structure(
            self,
            preflow: PreFlow,
            tasks: List[Dict[str, Any]]
    ) -> PSOP:
        try:
            if not tasks:
                raise ValueError("Tasks list cannot be empty")
            psop_schema = json.dumps(tasks, ensure_ascii=False, indent=2)
            prompt = get_generate_psop_prompt(str(preflow), tasks, psop_schema)
            _, llm_res = self._llm.ask_llm(prompt)

            psop_data = self._parse_json_respose(llm_res, PSOP)

            if not getattr(psop_data, 'steps', None):
                raise ValueError("Generated PSOP has not steps")

            if not isinstance(psop_data, PSOP):
                raise ValueError("LLM returned non-PSOP object")
            logger.info("PSOP 工作流结构生成成功")
            logger.info(f"生成的 PSOP 对象结构:\n{psop_data.model_dump_json(indent=2)}")
            return psop_data
        except Exception as e:
            raise WorkflowGeneratorError(f"PSOP workflow generation failed : {e}") from e

    def generate_psop_workflow(
            self,
            preflow: PreFlow,
            agent_cards: List[AgentCard]
    ) -> PSOP:
        if not preflow.steps_md or not preflow.steps_md.strip():
            raise WorkflowGeneratorError("Preflow steps_md cannot be empty")
        if not agent_cards:
            raise WorkflowGeneratorError("agent_cards cannot be empty")

        try:
            all_tasks = self.extract_tasks_from_steps(preflow.steps_md)
            if not all_tasks:
                raise WorkflowGeneratorError("No tasks extracted from preflow")
            action_skill_pair = self.match_actions_to_skills(all_tasks, agent_cards)
            skill_dict: Dict[str, str] = {
                skill.name: agent_cards.name
                for agent_card in agent_cards
                for skill in agent_card.skills
                if skill.name
            }
            step_list = []
            for action, skill_name in action_skill_pair.items():
                if skill_name not in skill_dict:
                    logger.warning(f"Skill '{skill_name}' not found in any agent's skill list")
                    continue
                step_list.append({
                    'task': action,
                    'skill': skill_name,
                    'agent': skill_dict[skill_name]
                })
            if not step_list:
                raise WorkflowGeneratorError("No valid tasks generated from PSOP")

            psop: PSOP = self.build_psop_structure(preflow, step_list)
            psop.name = preflow.name
            preflow.related_preflow = preflow.id

            return psop
        except WorkflowGenerator:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during PSOP generation: {e}")
            raise WorkflowGeneratorError(f"Unexpected error  {e}") from e
