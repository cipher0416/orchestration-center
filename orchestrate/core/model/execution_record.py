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

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ExecutionRecord(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(uuid4()),
                              description="Unique execution record identifier")
    psop_id: str = Field(..., description="ID of the executed PSOP workflow")
    psop_name: str = Field("", description="Name of the executed PSOP workflow")
    started_at: datetime = Field(default_factory=datetime.now, description="Execution start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Execution completion timestamp")
    status: str = Field("running", description="Execution status: running, success, failed, stopped")
    execution_history: List[Dict[str, Any]] = Field(default_factory=list,
                                                     description="Step-level execution history")
    final_psop: Optional[Dict[str, Any]] = Field(None,
                                                  description="Final PSOP state with task statuses")
    events: List[Dict[str, Any]] = Field(default_factory=list,
                                          description="Agent interaction events for replay")
    error: Optional[str] = Field(None, description="Error message if execution failed")
