# CustomProvider 缺少 XML 工具调用解析导致日志记录错误

## 元信息
- **updated_at**: 2026-06-30
- **severity**: HIGH（导致 update_memory 工具调用未执行，llm_call_logger 记录错误输出）

## 问题描述

### 症状
`llm_call_logger` 记录的 `update_memory` 调用输出是 XML 工具调用文本 `<tool_call><function=read_file>...</tool_call>`，而不是 LLM 的最终文本回复。同时第二次工具调用未执行，导致工具调用链提前中断。

### 触发条件
- 使用 `is_direct: true` 的 provider（如 Xiaomi MIMO、Azure OpenAI 等走 `CustomProvider` 的）
- 模型在多轮工具调用时，第二次响应将工具调用以 XML 格式写入 `content` 字段，而非原生 `msg.tool_calls`

## 根本原因

### 代码位置
`lifeprism/llm/providers/llm_providers/custom_provider.py:_parse()`

### 问题机制

1. `LiteLLMProvider._parse_response()` 有 XML 工具调用解析（`_parse_xml_tool_calls` + 条件判断），但 `CustomProvider._parse()` **完全没有**。

2. `CustomProvider._parse()` 只解析原生 `msg.tool_calls`：
   ```python
   tool_calls = [ToolCallRequest(...) for tc in (msg.tool_calls or [])]
   ```

3. 模型 mimo-v2.5 的行为：
   - **第1次调用**：返回原生 `msg.tool_calls` → CustomProvider 解析成功 → 工具执行 ✓
   - **第2次调用**（上下文已有工具结果）：返回 XML 格式工具调用在 `content` 中，`msg.tool_calls` 为空 → CustomProvider 解析失败 → `tool_calls=[]`

4. 链路传导：
   - `tool_calls=[]` → `_run_agent_loop` while 循环退出
   - `response.content` 保留 XML 文本 → `OutboundMessage` 返回
   - `llm_call_logger.log_call()` 记录 XML 文本为"最终输出"

### 为什么 LiteLLMProvider 没这个问题

`LiteLLMProvider._parse_response()` 第 399-406 行有 XML 回退：
```python
if finish_reason == "tool_calls" and not tool_calls and content and "<tool_call>" in content:
    xml_tool_calls = self._parse_xml_tool_calls(content)
    if xml_tool_calls:
        tool_calls = xml_tool_calls
        content = None  # 清除 XML 文本
```

验证测试确认：实际日志中的 XML 内容能被 `_parse_xml_tool_calls` 正确解析（函数名 `read_file`，参数 `file_path`、`offset`、`limit` 全部正确提取）。

## 正确解决方案

将 `LiteLLMProvider` 的 XML 解析逻辑搬到 `CustomProvider`：

1. 新增 `_parse_xml_tool_calls` 静态方法（完全复用 LiteLLMProvider 的实现）
2. `_parse()` 中，在原生 `msg.tool_calls` 解析之后增加 XML 回退逻辑

```python
content = msg.content
finish_reason = choice.finish_reason

tool_calls = [
    ToolCallRequest(...)
    for tc in (msg.tool_calls or [])
]

# XML 工具调用回退
if finish_reason == "tool_calls" and not tool_calls and content and "<tool_call>" in content:
    xml_tool_calls = self._parse_xml_tool_calls(content)
    if xml_tool_calls:
        tool_calls = xml_tool_calls
        content = None  # 清除 XML 文本

return LLMResponse(content=content, tool_calls=tool_calls, ...)
```

## 关键教训

1. **`CustomProvider` 和 `LiteLLMProvider` 的 `_parse` 逻辑应保持同步**。当前有两个平行的解析路径，新增功能容易只加一个漏另一个。

2. **XML 格式工具调用是某些模型（MIMO、MiniMax）的常见行为**，尤其在多轮对话中。不能假设所有模型都只用 OpenAI 原生 `tool_calls` 格式。

3. **日志记录的 `response.content` 不一定是最终输出**，可能是未被解析的中间工具调用文本。

## 相关文件
- `lifeprism/llm/providers/llm_providers/custom_provider.py` - 修复位置
- `lifeprism/llm/providers/llm_providers/litellm_provider.py` - XML 解析参考实现
- `lifeprism/llm/agent/loop.py:_run_agent_loop()` - 工具调用循环
- `lifeprism/llm/utils/llm_call_logger.py` - 受影响的日志记录器

## 标签
`tool-call` `xml-parsing` `custom-provider` `mimo` `llm-call-logger` `dream-task`
