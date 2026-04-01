"""测试 Tool.cast_params / _cast_value / _cast_immutable_types 的行为。"""
import pytest
from typing import Any
from lifeprism.llm.agent.tools.base import Tool


class MockTool(Tool):
    """可配置 parameters 的测试用工具。"""

    def __init__(self, schema: dict):
        self._schema = schema

    @property
    def name(self) -> str:
        return "mock"

    @property
    def description(self) -> str:
        return "mock tool"

    @property
    def parameters(self) -> dict[str, Any]:
        return self._schema

    async def execute(self, **kw):
        pass


def make_tool(properties: dict, required: list[str] | None = None) -> MockTool:
    """快速构造带有 object schema 的工具。"""
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return MockTool(schema)


# --- string ---

class TestCastString:

    def test_string_passthrough(self):
        tool = make_tool({"name": {"type": "string"}})
        assert tool.cast_params({"name": "hello"})["name"] == "hello"

    def test_int_to_string(self):
        tool = make_tool({"name": {"type": "string"}})
        assert tool.cast_params({"name": 42})["name"] == "42"

    def test_float_to_string(self):
        tool = make_tool({"name": {"type": "string"}})
        assert tool.cast_params({"name": 3.14})["name"] == "3.14"


# --- integer ---

class TestCastInteger:

    def test_integer_passthrough(self):
        tool = make_tool({"count": {"type": "integer"}})
        assert tool.cast_params({"count": 5})["count"] == 5

    def test_string_to_integer(self):
        tool = make_tool({"count": {"type": "integer"}})
        assert tool.cast_params({"count": "5"})["count"] == 5

    def test_float_to_integer(self):
        # float 强转 int 会截断小数
        tool = make_tool({"count": {"type": "integer"}})
        assert tool.cast_params({"count": 3.9})["count"] == 3

    def test_invalid_string_stays(self):
        # "abc" 无法转 int，原样返回
        tool = make_tool({"count": {"type": "integer"}})
        assert tool.cast_params({"count": "abc"})["count"] == "abc"

    def test_bool_not_cast_to_integer(self):
        # bool 传给 integer 字段，拒绝强转，原样返回让 validate 报错
        tool = make_tool({"count": {"type": "integer"}})
        result = tool.cast_params({"count": True})["count"]
        assert result is True  # 拒绝转换，validate 会发现类型不匹配


# --- float ---

class TestCastFloat:

    def test_float_passthrough(self):
        tool = make_tool({"score": {"type": "float"}})
        assert tool.cast_params({"score": 3.14})["score"] == 3.14

    def test_string_to_float(self):
        tool = make_tool({"score": {"type": "float"}})
        assert tool.cast_params({"score": "3.14"})["score"] == pytest.approx(3.14)

    def test_int_to_float(self):
        tool = make_tool({"score": {"type": "float"}})
        assert tool.cast_params({"score": 3})["score"] == 3.0

    def test_invalid_string_stays(self):
        tool = make_tool({"score": {"type": "float"}})
        assert tool.cast_params({"score": "abc"})["score"] == "abc"


# --- boolean ---

class TestCastBoolean:

    def test_bool_passthrough(self):
        tool = make_tool({"enabled": {"type": "boolean"}})
        assert tool.cast_params({"enabled": True})["enabled"] is True

    def test_string_true_variants(self):
        tool = make_tool({"enabled": {"type": "boolean"}})
        for val in ["true", "1"]:
            assert tool.cast_params({"enabled": val})["enabled"] is True, f"failed for {val!r}"

    def test_string_false_variants(self):
        tool = make_tool({"enabled": {"type": "boolean"}})
        for val in ["false", "0"]:
            assert tool.cast_params({"enabled": val})["enabled"] is False, f"failed for {val!r}"

    def test_int_1_to_true(self):
        tool = make_tool({"enabled": {"type": "boolean"}})
        assert tool.cast_params({"enabled": 1})["enabled"] is True

    def test_int_0_to_false(self):
        tool = make_tool({"enabled": {"type": "boolean"}})
        assert tool.cast_params({"enabled": 0})["enabled"] is False

    def test_unrecognized_string_stays(self):
        # "yes"/"no" 等不在列表里，原样返回
        tool = make_tool({"enabled": {"type": "boolean"}})
        assert tool.cast_params({"enabled": "yes"})["enabled"] == "yes"


# --- None 值 ---

class TestCastNone:

    def test_none_always_passthrough(self):
        """None 值不论目标类型是什么，都原样返回。"""
        for type_name in ["string", "integer", "float", "boolean"]:
            tool = make_tool({"val": {"type": type_name}})
            assert tool.cast_params({"val": None})["val"] is None

    def test_zero_not_treated_as_none(self):
        """0 是合法值，不能被跳过。"""
        tool = make_tool({"count": {"type": "integer"}})
        assert tool.cast_params({"count": 0})["count"] == 0

    def test_empty_string_not_treated_as_none(self):
        """空字符串是合法值，不能被跳过。"""
        tool = make_tool({"name": {"type": "string"}})
        assert tool.cast_params({"name": ""})["name"] == ""

    def test_false_not_treated_as_none(self):
        """False 是合法值，不能被跳过。"""
        tool = make_tool({"enabled": {"type": "boolean"}})
        assert tool.cast_params({"enabled": False})["enabled"] is False


# --- array ---

class TestCastArray:

    def test_array_of_string_passthrough(self):
        tool = make_tool({"tags": {"type": "array", "items": {"type": "string"}}})
        assert tool.cast_params({"tags": ["a", "b"]})["tags"] == ["a", "b"]

    def test_array_of_int_strings_cast(self):
        tool = make_tool({"ids": {"type": "array", "items": {"type": "integer"}}})
        result = tool.cast_params({"ids": ["1", "2", "3"]})["ids"]
        assert result == [1, 2, 3]

    def test_array_partial_failure_keeps_bad_element(self):
        """某个元素转换失败，该元素原样保留，其他元素正常转换。"""
        tool = make_tool({"ids": {"type": "array", "items": {"type": "integer"}}})
        result = tool.cast_params({"ids": ["1", "abc", "3"]})["ids"]
        assert result[0] == 1
        assert result[1] == "abc"  # 转换失败，原样保留
        assert result[2] == 3

    def test_nested_array(self):
        """list of list，内层元素也应该被转换。"""
        schema = {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer"}}
        }
        tool = make_tool({"matrix": schema})
        result = tool.cast_params({"matrix": [["1", "2"], ["3", "4"]]})["matrix"]
        assert result == [[1, 2], [3, 4]]


# --- object（嵌套 dict）---

class TestCastObject:

    def test_nested_object_cast(self):
        schema = {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
                "keyword": {"type": "string"},
            }
        }
        tool = make_tool({"filter": schema})
        result = tool.cast_params({"filter": {"limit": "10", "keyword": "hello"}})["filter"]
        assert result["limit"] == 10
        assert result["keyword"] == "hello"

    def test_unknown_key_passthrough(self):
        """schema 里没有定义的 key，原样保留，不报错。"""
        tool = make_tool({"name": {"type": "string"}})
        result = tool.cast_params({"name": "foo", "extra": 123})
        assert result["extra"] == 123


# --- schema 写错时快速失败 ---

class TestCastSchemaError:

    def test_unknown_type_raises(self):
        """schema type 不在 _TYPE_MAP 里，应该直接报错（开发者的错误）。"""
        tool = make_tool({"val": {"type": "datetime"}})
        with pytest.raises(KeyError):
            tool.cast_params({"val": "2026-01-01"})

    def test_array_missing_items_raises(self):
        """array 没有 items 字段，get('items') 返回 None，None.get('type') 报 AttributeError。"""
        tool = make_tool({"ids": {"type": "array"}})
        with pytest.raises((KeyError, AttributeError)):
            tool.cast_params({"ids": [1, 2, 3]})



