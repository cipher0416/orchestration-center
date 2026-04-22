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

from abc import ABC, abstractmethod
from typing import Dict, Type

from common.custom.interface_type import InterfaceType
from orchestrate.core.workflow_search_result import WorkflowSearchResult
from orchestrate.workflow_storage_instance import get_workflow_storage


class BaseHandler(ABC):
    """统一的抽象基类，所有接口实现必须继承此类并实现 handle 方法"""

    @abstractmethod
    def handle(self, *args, **kwargs):
        """具体业务逻辑由子类实现"""
        pass


# ==================== 默认实现 ====================
class SavePsopHandler(BaseHandler):
    def handle(self, *args, **kwargs):
        return get_workflow_storage().save_psop(*args)


class GetAllPsopsHandler(BaseHandler):
    def handle(self, *args, **kwargs):
        results = []
        storage = get_workflow_storage()
        for wf_id in storage.list_psops():
            psop = storage.load_psop(wf_id)
            if psop:
                results.append(WorkflowSearchResult(
                    workflow_id=psop.id,
                    workflow_type="psop",
                    name=psop.name,
                    description=psop.description,
                    tags=psop.tags,
                    created_at=psop.created_at,
                ))
        return results


class GetPsopHandler(BaseHandler):
    def handle(self, *args, **kwargs):
        storage = get_workflow_storage()
        return storage.load_psop(*args)


class DeletePsopHandler(BaseHandler):
    async def handle(self, *args, **kwargs):
        return get_workflow_storage().delete_psop(*args)


# ==================== 注册表 ====================
class HandlerRegistry:
    _registry: Dict[str, Type[BaseHandler]] = {}

    @classmethod
    def register(cls, interface_type: InterfaceType, handler_class: Type[BaseHandler]) -> None:
        """
        注册用户自定义实现类
        :param interface_type: 接口类型标识，例如 "decrypt", "audit", "authenticate", "insert", "query"
        :param handler_class: 继承自 BaseHandler 的自定义类
        """
        if not issubclass(handler_class, BaseHandler):
            raise TypeError("handler_class must be a subclass of BaseHandler")
        cls._registry[interface_type.value] = handler_class

    @classmethod
    def get_handler(cls, interface_type: InterfaceType) -> BaseHandler:
        """
        根据接口类型获取处理器实例
        :param interface_type: 接口类型标识
        :return: BaseHandler 实例（用户自定义或默认）
        """
        # 若存在用户注册的类，则实例化并返回
        if interface_type.value in cls._registry:
            return cls._registry[interface_type.value]()

        # 否则返回对应的默认实现
        default_map = {
            "save_psop": SavePsopHandler,
            "get_all_psop": GetAllPsopsHandler,
            "get_psop_by_id": GetPsopHandler,
            "delete_psop": DeletePsopHandler,
        }
        handler_class = default_map.get(interface_type.value)
        if handler_class is None:
            raise ValueError(f"Unknown interface type: {interface_type}")
        return handler_class()
