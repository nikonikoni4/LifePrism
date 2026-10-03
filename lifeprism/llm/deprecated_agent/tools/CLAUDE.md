# Agent Tools 规则

## 工具返回类型规范

**强制规则**：所有工具的 `execute()` 方法**必须返回 `str`**

```python
# ✅ 正确：返回字符串
class MyTool(Tool):
    async def execute(self, **kwargs: Any) -> str:
        result = {"key": "value"}
        return json.dumps(result, ensure_ascii=False)

# ✅ 正确：错误时也返回字符串
class MyTool(Tool):
    async def execute(self, **kwargs: Any) -> str:
        if error:
            return f"{ERROR}错误信息"
        return json.dumps(result, ensure_ascii=False)

# ❌ 错误：返回 dict 或 list
class MyTool(Tool):
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return {"key": "value"}  # 会导致 tool 消息 content 是 dict

# ❌ 错误：使用 Any 作为返回类型
class MyTool(Tool):
    async def execute(self, **kwargs: Any) -> Any:
        return result  # 调用方无法知道返回什么类型

原因

1. 技术约束：LLM 提供商要求 tool 角色消息的 content 必须是字符串
2. 统一接口：所有工具统一返回字符串，简化调用方处理逻辑
3. 明确类型：避免使用 Any，让调用方明确知道返回字符串

返回格式

成功时：
- 结构化数据：使用 json.dumps(result, ensure_ascii=False) 序列化为 JSON 字符串
- 简单文本：直接返回字符串

失败时：
- 返回 f"{ERROR}错误描述"（ERROR 常量来自 lifeprism.llm.agent.tools.base）
- 必须包含足够的错误上下文（参见 lifeprism/CLAUDE.md 日志规范）