"""
自定义记录模块 LLM Tools

直接调用 custom_record_repository，不经过 service（遵循现有架构，避免循环引用）。
遵循 lifeprism/llm/agent/tools/CLAUDE.md：所有 execute() 返回 str。
"""

import json
from typing import Any

from lifeprism.llm.agent.tools.base import ERROR, SUCCESS, Tool
from lifeprism.repository import custom_record_repository
from lifeprism.utils.exceptions import ValidationError
from lifeprism.utils.time_utils import build_utc_time_range, local_to_utc_iso, utc_to_local_display


class ListCustomRecordTypesTool(Tool):
    """列出自定义记录类型工具"""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "list_custom_record_types"

    @property
    def description(self) -> str:
        return (
            "列出自定义记录模块中已创建的所有记录类型，包括每个类型的字段定义。"
            "在录入数据前，应先调用此工具获取类型 ID 和字段定义。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        try:
            types = custom_record_repository.list_types()
            for t in types:
                if "created_at" in t and t["created_at"]:
                    t["created_at"] = utc_to_local_display(t["created_at"])
                if "updated_at" in t and t["updated_at"]:
                    t["updated_at"] = utc_to_local_display(t["updated_at"])
            return f"{SUCCESS}{json.dumps(types, ensure_ascii=False)}"
        except Exception as e:
            return f"{ERROR}查询自定义记录类型失败: {e}"


class CreateCustomRecordTypeTool(Tool):
    """创建自定义记录类型工具"""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "create_custom_record_type"

    @property
    def description(self) -> str:
        return (
            "创建自定义记录类型。用户表达「想记录某类内容」时调用此工具。\n"
            "参数说明：\n"
            "- name: 类型显示名（如「体育活动」）\n"
            "- slug: 语义化标识，英文小写+下划线（如 sport），用作表名后缀\n"
            "- fields: 字段定义列表，每项含 field_name（显示名）、field_key（列名，英文小写+下划线）、field_type（P1 仅 text）\n"
            "约束：fields 至少 1 个；slug 和 field_key 需匹配 ^[a-z][a-z0-9_]*$；slug 全局唯一。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "类型显示名（如「体育活动」、「每日饮食」）",
                },
                "slug": {
                    "type": "string",
                    "description": "语义化标识，英文小写+下划线（如 sport、diet），用作表名后缀",
                },
                "fields": {
                    "type": "array",
                    "description": "字段定义列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field_name": {
                                "type": "string",
                                "description": "字段显示名（如「锻炼内容」）",
                            },
                            "field_key": {
                                "type": "string",
                                "description": "数据库列名，英文小写+下划线（如 exercise_content）",
                            },
                            "field_type": {
                                "type": "string",
                                "description": "字段类型，P1 仅 text",
                                "enum": ["text"],
                            },
                        },
                        "required": ["field_name", "field_key", "field_type"],
                    },
                    "minItems": 1,
                },
                "description": {
                    "type": "string",
                    "description": "类型描述（可选）",
                },
            },
            "required": ["name", "slug", "fields"],
        }

    async def execute(self, **kwargs: Any) -> str:
        try:
            name = kwargs.get("name", "")
            slug = kwargs.get("slug", "")
            fields = kwargs.get("fields", [])
            description = kwargs.get("description")

            if not name or not slug or not fields:
                return f"{ERROR}参数缺失：name、slug、fields 均为必填"

            type_id = custom_record_repository.create_type(
                name=name,
                slug=slug,
                fields=fields,
                description=description,
            )
            result = {"type_id": type_id, "name": name, "slug": slug}
            return f"{SUCCESS}创建自定义记录类型成功: {json.dumps(result, ensure_ascii=False)}"
        except Exception as e:
            return f"{ERROR}创建自定义记录类型失败: {e}"


class CreateCustomRecordEntryTool(Tool):
    """录入自定义记录工具"""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "create_custom_record_entry"

    @property
    def description(self) -> str:
        return (
            "向已存在的自定义记录类型录入一条数据。\n"
            "调用前应先用 list_custom_record_types 获取 type_id 和字段定义。\n"
            "data 中的 key 必须是类型的 field_key，缺失的字段存为 NULL，空字典允许。\n"
            "若 field_key 错误，返回 INVALID_FIELD_KEY 错误及 valid_fields 列表，请据此重新解析后重试。\n"
            "event_time 为事件发生时间（本地 YYYY-MM-DD HH:MM:SS），不提供则默认使用当前时间。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "type_id": {
                    "type": "string",
                    "description": "记录类型 ID（以 crt- 开头）",
                },
                "data": {
                    "type": "object",
                    "description": "字段值字典 {field_key: value}，key 必须匹配类型的 field_key",
                    "additionalProperties": {"type": "string"},
                },
                "event_time": {
                    "type": "string",
                    "description": "事件发生时间，格式 YYYY-MM-DD HH:MM:SS（本地时间）。不提供则默认当前时间",
                },
            },
            "required": ["type_id", "data"],
        }

    async def execute(self, **kwargs: Any) -> str:
        type_id = kwargs.get("type_id", "")
        data = kwargs.get("data", {})
        event_time_raw = kwargs.get("event_time")

        if not type_id:
            return f"{ERROR}参数缺失：type_id 必填"
        if not isinstance(data, dict):
            return f"{ERROR}参数错误：data 必须是字典"

        # event_time：Agent 提供本地 YYYY-MM-DD HH:MM:SS → 转 UTC ISO
        # 不提供则使用 None，Repository 层默认当前 UTC 时间
        event_time_utc = None
        if event_time_raw:
            if not isinstance(event_time_raw, str):
                return f"{ERROR}参数错误：event_time 必须是字符串"
            # 格式校验
            import re
            if not re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', event_time_raw):
                return f"{ERROR}参数格式错误：event_time 格式应为 YYYY-MM-DD HH:MM:SS，例如 2026-07-13 14:30:00"
            event_time_utc = local_to_utc_iso(event_time_raw)

        try:
            entry_id = custom_record_repository.create_entry(
                type_id=type_id, data=data, event_time=event_time_utc,
            )
            result = {"entry_id": entry_id, "type_id": type_id}
            return f"{SUCCESS}录入自定义记录成功: {json.dumps(result, ensure_ascii=False)}"
        except ValidationError as e:
            # field_key 错误：返回结构化 JSON，引导 AI 根据 valid_fields 重新解析
            error_payload = {
                "error": e.code or "INVALID_FIELD_KEY",
                "message": e.message,
                "valid_fields": e.details.get("valid_fields", []),
            }
            return f"{ERROR}{json.dumps(error_payload, ensure_ascii=False)}"
        except Exception as e:
            return f"{ERROR}录入自定义记录失败: {e}"


class QueryCustomRecordEntriesTool(Tool):
    """查询自定义记录工具"""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "query_custom_record_entries"

    @property
    def description(self) -> str:
        return (
            "查询某个自定义记录类型的记录列表，按事件时间倒序返回。\n"
            "可通过 date_range 按事件时间筛选（格式 YYYY-MM-DD），任一侧可省略。\n"
            "limit 控制返回条数（默认 50，AI 场景一次拿够，无需分页）。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "type_id": {
                    "type": "string",
                    "description": "记录类型 ID（以 crt- 开头）",
                },
                "date_range": {
                    "type": "array",
                    "description": "事件时间筛选区间 [start, end]，格式 YYYY-MM-DD；任一侧可为 null 表示不限制",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "limit": {
                    "type": "integer",
                    "description": "返回条数上限，默认 50",
                    "minimum": 1,
                    "maximum": 500,
                },
            },
            "required": ["type_id"],
        }

    async def execute(self, **kwargs: Any) -> str:
        type_id = kwargs.get("type_id", "")
        date_range_raw = kwargs.get("date_range")
        limit = kwargs.get("limit", 50)

        if not type_id:
            return f"{ERROR}参数缺失：type_id 必填"

        # date_range：Agent 提供本地 YYYY-MM-DD → execute 层转 UTC 范围
        date_range = None
        if date_range_raw and isinstance(date_range_raw, list) and len(date_range_raw) == 2:
            start = date_range_raw[0] or None
            end = date_range_raw[1] or None
            if start:
                start_utc, _ = build_utc_time_range(start)
            else:
                start_utc = None
            if end:
                _, end_utc = build_utc_time_range(end)
            else:
                end_utc = None
            if start_utc or end_utc:
                date_range = (start_utc, end_utc)

        try:
            entries = custom_record_repository.query_entries(
                type_id=type_id,
                date_range=date_range,
                page=1,
                page_size=int(limit),
            )

            # 输出转换：UTC ISO → 本地 YYYY-MM-DD HH:MM:SS（显示用字段）
            for entry in entries:
                if "event_time" in entry and entry["event_time"]:
                    entry["event_time"] = utc_to_local_display(entry["event_time"])
                if "created_at" in entry and entry["created_at"]:
                    entry["created_at"] = utc_to_local_display(entry["created_at"])
                if "updated_at" in entry and entry["updated_at"]:
                    entry["updated_at"] = utc_to_local_display(entry["updated_at"])

            return f"{SUCCESS}{json.dumps(entries, ensure_ascii=False)}"
        except Exception as e:
            return f"{ERROR}查询自定义记录失败: {e}"
