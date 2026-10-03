# runtime_tools 规则

本目录是生产业务工具的运行时实现目录，工具直接继承 myagent 的 `Tool`
（`myagent.agent.core.tool.tool`），不再自定义工具基类。

## 工具返回类型规范

**强制规则**：`execute()` 必须返回 `str` 或 `ToolResult`，禁止返回 `Any` / `dict` / `list`。

| 返回值 | 语义 |
|--------|------|
| `str`（不以 `Error: ` 开头） | 成功，`ToolRegister` 包装为 `ToolResult(content=...)` |
| `ToolResult.error(content, error_type)` | 失败，`ToolRegister` 据此做失败分类与熔断计数 |

## 统一写法

业务实现内部继续用 `ERROR` / `SUCCESS` 前缀返回字符串，在 `execute` 上套用
`normalize_tool_result` 装饰器完成边界转换：

```python
from lifeprism.llm.runtime_tools.base import ERROR, SUCCESS, Tool, ToolResult, normalize_tool_result

class MyTool(Tool):
    def __init__(self):
        super().__init__()  # 必须调用，否则熔断参数未初始化

    @normalize_tool_result
    async def execute(self, **kwargs: Any) -> ToolResult | str:
        if bad:
            return f"{ERROR}错误信息"   # 装饰器 → ToolResult.error(..., TOOL_EXECUTION)
        return f"{SUCCESS}结果"
```

## 约束

- 熔断参数一律使用 `Tool.__init__` 默认值，`__init__` 中禁止显式传阈值或模式
- 每个自定义 `__init__` 必须调用 `super().__init__()`
- 本目录禁止导入 `lifeprism.llm.agent` 与 `lifeprism.llm.session`
- 例外：`web.py` 的 `WebFetchTool.execute` 成功时可能返回多模态内容块列表
  （`build_image_content_blocks`），不套用 `normalize_tool_result`，保持原行为
