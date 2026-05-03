""" 工具调用基类
本文件部分代码源自 https://github.com/HKUDS/nanobot.git
Copyright (c) [2026.3.30] [HKUDS]
Licensed under the MIT License.
需要实现： 转化为schemas，参数验证和执行
"""

from abc import ABC, abstractmethod
from typing import Any
ERROR = "error"

class Tool(ABC):
    """
    Agent 工具的抽象基类。

    工具是 agent 与环境交互的能力封装，
    例如读取文件、执行命令等。
    """

    _TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    @staticmethod
    def _resolve_type(t: Any) -> str | None:
        """将 JSON Schema 的类型解析为简单字符串。

        JSON Schema 支持 ``"type": ["string", "null"]`` 这类联合类型。
        这里提取第一个非 null 类型，便于后续校验与类型转换。
        """
        if isinstance(t, list):
            for item in t:
                if item != "null":
                    return item
            return None
        return t

    @property
    @abstractmethod
    def name(self) -> str:
        """函数调用中使用的工具名。"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能说明。"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """工具参数的 JSON Schema。
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

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """
        使用给定参数执行工具。

        参数:
            **kwargs: 工具特有参数。

        返回:
            工具执行结果（字符串或内容块列表）。
        """
        pass

    def cast_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """在校验前按 schema 做安全类型转换。"""
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            return params

        return self._cast_object(params, schema)

    def _cast_object(self, obj: Any, schema: dict[str, Any]) -> dict[str, Any]:
        """根据 schema 转换对象（dict）中的字段类型。"""
        if not isinstance(obj, dict):
            return obj

        props = schema.get("properties", {})
        result = {}

        for key, value in obj.items():
            if key in props:
                result[key] = self._cast_value(value, props[key])
            else:
                result[key] = value

        return result

    def _cast_value(self, val: Any, schema: dict[str, Any]) -> Any:
        """根据 schema 转换单个值。"""
        target_type = self._resolve_type(schema.get("type"))

        if target_type == "boolean" and isinstance(val, bool):
            return val
        if target_type == "integer" and isinstance(val, int) and not isinstance(val, bool):
            return val
        if target_type in self._TYPE_MAP and target_type not in ("boolean", "integer", "array", "object"):
            expected = self._TYPE_MAP[target_type]
            if isinstance(val, expected):
                return val

        if target_type == "integer" and isinstance(val, str):
            try:
                return int(val)
            except ValueError:
                return val

        if target_type == "number" and isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                return val

        if target_type == "string":
            return val if val is None else str(val)

        if target_type == "boolean" and isinstance(val, str):
            val_lower = val.lower()
            if val_lower in ("true", "1", "yes"):
                return True
            if val_lower in ("false", "0", "no"):
                return False
            return val

        if target_type == "array" and isinstance(val, list):
            item_schema = schema.get("items")
            return [self._cast_value(item, item_schema) for item in val] if item_schema else val

        if target_type == "object" and isinstance(val, dict):
            return self._cast_object(val, schema)

        return val

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """根据 JSON Schema 校验参数，返回错误列表（空列表表示通过）。"""
        if not isinstance(params, dict):
            return [f"parameters 必须是 object，当前为 {type(params).__name__}"]
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            raise ValueError(f"Schema 必须是 object 类型，当前为 {schema.get('type')!r}")
        return self._validate(params, {**schema, "type": "object"}, "")

    def _validate(self, val: Any, schema: dict[str, Any], path: str) -> list[str]:
        raw_type = schema.get("type")
        nullable = (isinstance(raw_type, list) and "null" in raw_type) or schema.get(
            "nullable", False
        )
        t, label = self._resolve_type(raw_type), path or "parameter"
        if nullable and val is None:
            return []
        if t == "integer" and (not isinstance(val, int) or isinstance(val, bool)):
            return [f"{label} 应为 integer"]
        if t == "number" and (
            not isinstance(val, self._TYPE_MAP[t]) or isinstance(val, bool)
        ):
            return [f"{label} 应为 number"]
        if t in self._TYPE_MAP and t not in ("integer", "number") and not isinstance(val, self._TYPE_MAP[t]):
            return [f"{label} 应为 {t}"]

        errors = []
        if "enum" in schema and val not in schema["enum"]:
            errors.append(f"{label} 必须是 {schema['enum']} 之一")
        if t in ("integer", "number"):
            if "minimum" in schema and val < schema["minimum"]:
                errors.append(f"{label} 必须 >= {schema['minimum']}")
            if "maximum" in schema and val > schema["maximum"]:
                errors.append(f"{label} 必须 <= {schema['maximum']}")
        if t == "string":
            if "minLength" in schema and len(val) < schema["minLength"]:
                errors.append(f"{label} 长度至少为 {schema['minLength']}")
            if "maxLength" in schema and len(val) > schema["maxLength"]:
                errors.append(f"{label} 长度至多为 {schema['maxLength']}")
        if t == "object":
            props = schema.get("properties", {})
            for k in schema.get("required", []):
                if k not in val:
                    errors.append(f"缺少必填字段 {path + '.' + k if path else k}")
            for k, v in val.items():
                if k in props:
                    errors.extend(self._validate(v, props[k], path + "." + k if path else k))
        if t == "array" and "items" in schema:
            for i, item in enumerate(val):
                errors.extend(
                    self._validate(item, schema["items"], f"{path}[{i}]" if path else f"[{i}]")
                )
        return errors

    def to_schema(self) -> dict[str, Any]:
        """将工具转换为 OpenAI function schema 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
