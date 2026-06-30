---
date: 2026-06-30
status: implemented
impact: medium
---

# 工具调用链完整记录功能

## 背景

在之前的 `llm_call_logger` 实现中，只记录了最后一次 LLM 响应中的 `tool_calls`，无法完整追踪整个工具调用过程。这导致：

1. 无法查看中间工具调用的完整链路
2. 难以调试多轮工具调用的问题
3. 无法分析工具调用的执行效率

## 解决方案

### 核心设计

在 `_run_agent_loop` 方法中记录完整的工具调用链，通过 `OutboundMessage.extra` 传递给调用方，最终保存到 `llm_call_logger`。

### 数据结构

```python
tool_call_chain = [
    {
        "round": 1,  # 工具调用轮次
        "tool_calls": [
            {
                "id": "call_123",
                "name": "tool_name",
                "arguments": {...},
                "result": "工具执行结果（全量保存）"
            }
        ]
    },
    {
        "round": 2,
        "tool_calls": [...]
    }
]
```

### 实现要点

1. **在 `loop.py` 中记录**
   - `_run_agent_loop` 返回值改为 `(response, tool_call_chain)`
   - 每轮工具调用后立即记录到 `tool_call_chain`
   - 工具结果全量保存，不做截断

2. **通过 `OutboundMessage` 传递**
   - 在 `extra` 字段中添加 `tool_call_chain`
   - 保持向后兼容，`extra` 为可选字段

3. **在 `llm_call_logger` 中保存**
   - 从 `outbound_msg.extra` 提取 `tool_call_chain`
   - 保存到 record 的 `tool_call_chain` 字段
   - 若无工具调用，该字段为 `null`

## 修改文件

1. `lifeprism/llm/agent/loop.py`
   - 修改 `_run_agent_loop` 方法签名，返回 tuple
   - 添加 `tool_call_chain` 记录逻辑
   - 在 `_process_msg` 中传递 `tool_call_chain` 到 `OutboundMessage.extra`

2. `lifeprism/llm/utils/llm_call_logger.py`
   - 修改 `log_call` 方法，提取并保存 `tool_call_chain`
   - 在 record 中添加 `tool_call_chain` 字段

## 验证

创建了单元测试 `test/debug/test_tool_call_chain_unit.py` 验证：

1. ✅ `OutboundMessage` 结构正确
2. ✅ `tool_call_chain` 能正确传递
3. ✅ `llm_call_logger` 能正确保存

测试日志文件示例（`localData/debug_logs/llm_logs/llm_calls_2026-06-30.json`）：

```json
{
  "id": "620d084d-f59e-431e-acb4-f5daab46ba58",
  "tool_call_chain": [
    {
      "round": 1,
      "tool_calls": [
        {
          "id": "call_789",
          "name": "test_tool",
          "arguments": {"param": "value"},
          "result": "测试结果"
        }
      ]
    }
  ]
}
```

## 优势

1. **完整性**：记录所有轮次的工具调用，而不仅是最后一轮
2. **可调试性**：可以追踪每个工具的调用参数和返回结果
3. **向后兼容**：通过 `extra` 传递，不影响现有代码
4. **全量结果**：工具结果不做截断，便于问题排查

## 使用示例

```python
# 在 llm_call_logger 启用的情况下
msg = InboundMessage(type=MessageType.CHAT, content="...")
result = await bus.send(msg)

# 查看工具调用链
if result.extra and "tool_call_chain" in result.extra:
    for round_data in result.extra["tool_call_chain"]:
        print(f"第 {round_data['round']} 轮:")
        for tc in round_data["tool_calls"]:
            print(f"  工具: {tc['name']}, 结果: {tc['result']}")

# 记录到 logger
llm_call_logger.log_call(msg, result, ...)
```

## 后续优化建议

1. 考虑添加工具调用的时间戳，便于性能分析
2. 考虑添加工具调用的错误统计到链中
3. 可以基于 `tool_call_chain` 生成可视化的调用流程图
