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

from typing import Dict, Any, Optional
from loguru import logger

from a2a_t.negotiation.common.enums import NegotiationType, NegotiationStatus, NegotiationRole
from a2a_t.negotiation.common.models import NegotiationContext


NEGOTIATION_TEXT_KEY = "https://github.com/a2aproject/telecommunication/extensions/NEGOTIATION-T"
NEGOTIATION_CONTEXT_KEY = "https://github.com/a2aproject/telecommunication/extensions/DATA-NEGOTIATION-T/v1"
TASK_PROMPT_KEY = "https://github.com/a2aproject/telecommunication/extensions/Task-T/v1"


def extract_negotiation_context_from_task_metadata(
    task_metadata: Dict[str, Any]
) -> Optional[NegotiationContext]:
    if not task_metadata:
        return None

    context_data = task_metadata.get("negotiationContext")
    if not context_data:
        return None

    try:
        return NegotiationContext.from_context(context_data)
    except Exception as e:
        logger.error(f"Failed to parse negotiation context: {e}")
        return None


def extract_negotiation_context_from_artifact_metadata(
    artifact_metadata: Dict[str, Any]
) -> Optional[NegotiationContext]:
    if not artifact_metadata:
        return None

    context_data = artifact_metadata.get("negotiationContext")
    if not context_data:
        return None

    try:
        return NegotiationContext.from_context(context_data)
    except Exception as e:
        logger.error(f"Failed to parse negotiation context from artifact: {e}")
        return None


def build_negotiation_metadata(
    negotiation_result: Dict[str, Any]
) -> Dict[str, Any]:
    context_data = negotiation_result.get(NEGOTIATION_CONTEXT_KEY)
    if not context_data:
        logger.warning("No negotiation context in result")
        return {}

    return {"negotiationContext": context_data}


def is_negotiation_in_progress(context: NegotiationContext) -> bool:
    return context.status == NegotiationStatus.IN_PROGRESS


def is_negotiation_agreed(context: NegotiationContext) -> bool:
    return context.status == NegotiationStatus.AGREED


def is_negotiation_rejected(context: NegotiationContext) -> bool:
    return context.status == NegotiationStatus.REJECTED


def get_negotiation_round(context: NegotiationContext) -> int:
    return context.round


def get_negotiation_type(context: NegotiationContext) -> NegotiationType:
    return context.negotiation_type


def log_negotiation_context(context: NegotiationContext, prefix: str = "") -> None:
    logger.info(
        f"{prefix} Negotiation context: "
        f"type={context.negotiation_type.value}, "
        f"id={context.negotiation_id}, "
        f"role={context.role.value}, "
        f"round={context.round}, "
        f"status={context.status.value}"
    )
