"""工具调用基类
本文件部分代码源自 https://github.com/HKUDS/nanobot.git
Copyright (c) [2026.3.30] [HKUDS]
Licensed under the MIT License.
需要实现： 转化为schemas，参数验证和执行
"""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    _TYPE_MAP: dict[str, Any] = {  # 将类型转为无编程语言的通用类型
        "string": str,
        "integer": int,
        "float": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    def cast_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """参数类型强制转换"""
        schemas = self.parameters or {}
        if schemas.get("type", "object") != "object":
            return params

        return self._cast_object(params, schemas)

    def _cast_object(self, obj: dict[str, Any], schemas: dict[str, Any]) -> dict[str, Any]:
        """检查字典类型参数"""

        props = schemas.get("properties", {})
        for key, value in obj.items():
            # 获取schemas 中的参数类型
            if key in props:
                # 验证 value 的类型
                obj[key] = self._cast_value(value, props[key])
        return obj

    def _cast_immutable_types(self, value, schemas: dict):
        """处理不可变类型强转"""
        if value is not None:
            current_type = type(value)
            target_type = self._TYPE_MAP[schemas.get("type")]  # schemas出错直接错误
            if current_type not in [dict, list] and current_type is not target_type:
                # 不一致，则进行强转
                if target_type is bool:
                    if value in ["true", True, "1", 1]:
                        return True
                    elif value in ["false", False, "0", 0]:
                        return False
                elif current_type is bool:
                    # bool 不强转到其他类型，原样返回让 validate 报错
                    return value
                # 其他剩余三个类型不一致直接强转：str,int,float,
                else:
                    try:
                        value = target_type(value)
                        return value
                    except (ValueError, TypeError):
                        return value
        return value

    def _cast_value(self, value: Any, schemas: dict[str, Any]):

        if value is None:
            return value

        current_type = type(value)
        target_type = self._TYPE_MAP[schemas.get("type")]  # schemas出错直接错误

        # list dict等可变类型即使类型想要也要处理
        if target_type is dict and current_type is dict:
            return self._cast_object(value, schemas)

        if target_type is list and current_type is list:
            target_item_type = self._TYPE_MAP[schemas.get("items").get("type")]

            for i in range(len(value)):
                if target_item_type is dict and type(value[i]) is dict:
                    value[i] = self._cast_object(value[i], schemas.get("items"))
                elif target_item_type is list and type(value[i]) is list:
                    value[i] = self._cast_value(value[i], schemas.get("items"))
                else:
                    value[i] = self._cast_immutable_types(value[i], schemas.get("items"))

        # 处理不可变类型
        if target_type is not current_type:
            return self._cast_immutable_types(value, schemas)
        return value

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """工具参数，返回 JSON Schema 格式的参数定义。

        完整格式模板：
        {
            "type": "object",
            "properties": {

                # --- 基础类型 ---

                "title": {
                    "type": "string",          # 字符串
                    "description": "文章标题",
                    "minLength": 1,            # 可选：最小长度
                    "maxLength": 200,          # 可选：最大长度
                },

                "count": {
                    "type": "integer",         # 整数（不含小数）
                    "description": "数量",
                    "minimum": 0,              # 可选：最小值
                    "maximum": 100,            # 可选：最大值
                },

                "score": {
                    "type": "number",          # 数字（含小数）
                    "description": "评分",
                    "minimum": 0.0,
                    "maximum": 10.0,
                },

                "enabled": {
                    "type": "boolean",         # 布尔值
                    "description": "是否启用",
                },

                # --- 可空类型（AI 可能传 null）---

                "nickname": {
                    "type": ["string", "null"], # 字符串或 null
                    "description": "昵称，可为空",
                },

                # --- 枚举（限定取值范围）---

                "mode": {
                    "type": "string",
                    "description": "模式",
                    "enum": ["read", "write", "append"],  # 只允许这几个值
                },

                # --- array：元素类型统一 ---

                "tags": {
                    "type": "array",
                    "description": "标签列表",
                    "items": {"type": "string"},  # 每个元素都是 string
                },

                "ids": {
                    "type": "array",
                    "description": "ID 列表",
                    "items": {"type": "integer"},
                    "minItems": 1,              # 可选：最少元素数
                    "maxItems": 50,             # 可选：最多元素数
                },

                # --- object：嵌套结构 ---

                "filter": {
                    "type": "object",
                    "description": "过滤条件",
                    "properties": {
                        "keyword": {"type": "string", "description": "关键词"},
                        "limit":   {"type": "integer", "description": "数量上限"},
                    },
                    "required": ["keyword"],    # filter.keyword 必填
                },

            },

            # required 列出必填参数名，未列出的为可选
            "required": ["title", "count"],
        }
        """
        pass

    def to_schemas(self) -> str:
        """
        返回工具schemas, 格式:
        {
            "type": "function",
            "function": {
                "name": ,
                "description": ,
                "parameters": ,
            },
        }
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    def validate_params(self, **kw):
        """参数验证"""
        pass

    @abstractmethod
    async def execute(self, **kw: Any) -> Any:
        """执行工具函数"""
        pass
