# 工具调用链记录功能 - 验证清单

## ✅ 已完成的修改

### 1. 代码修改
- [x] `lifeprism/llm/agent/loop.py` - 记录工具调用链
  - [x] 修改 `_run_agent_loop` 返回值为 `(response, tool_call_chain)`
  - [x] 在工具调用循环中记录每轮的工具调用（id、name、arguments、result）
  - [x] 在 `_process_msg` 中通过 `OutboundMessage.extra` 传递工具调用链

- [x] `lifeprism/llm/utils/llm_call_logger.py` - 保存工具调用链
  - [x] 从 `outbound_msg.extra` 提取 `tool_call_chain`
  - [x] 在 record 中添加 `tool_call_chain` 字段

### 2. 测试
- [x] 创建单元测试 `test/debug/test_tool_call_chain_unit.py`
  - [x] 测试 OutboundMessage 数据结构
  - [x] 测试 llm_call_logger 记录功能
  - [x] 所有测试通过 ✅

- [x] 验证日志文件
  - [x] 确认 `tool_call_chain` 字段正确保存
  - [x] 确认数据结构完整

### 3. 文档
- [x] 创建设计决策文档 `docs/design-decisions/2026-06-30-tool-call-chain-logging.md`
- [x] 更新索引文件 `docs/design-decisions/index.md`

## 📊 验证结果

### 单元测试结果
```
[成功] OutboundMessage 结构正确
  - extra 包含键: ['tool_call_chain']
  - tool_call_chain 长度: 2
  - 第 1 轮: 1 个工具调用
  - 第 2 轮: 1 个工具调用

[成功] 记录 ID: 620d084d-f59e-431e-acb4-f5daab46ba58
[成功] 日志文件存在: localData\debug_logs\llm_logs\llm_calls_2026-06-30.json
[成功] 日志文件包含 tool_call_chain
  - 共 1 轮
```

### 日志文件示例
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

## 🎯 功能特性

1. **完整性** - 记录所有轮次的工具调用，而不仅是最后一轮
2. **可调试性** - 可以追踪每个工具的调用参数和返回结果
3. **向后兼容** - 通过 `extra` 传递，不影响现有代码
4. **全量保存** - 工具结果不做截断，便于问题排查

## 📝 使用示例

```python
from lifeprism.llm.bus import InboundMessage, MessageType, bus
from lifeprism.llm.utils import llm_call_logger

# 启用 logger
llm_call_logger.enabled = True

# 发送消息
msg = InboundMessage(type=MessageType.CHAT, content="查询今天的活动")
result = await bus.send(msg)

# 查看工具调用链
if result.extra and "tool_call_chain" in result.extra:
    for round_data in result.extra["tool_call_chain"]:
        print(f"第 {round_data['round']} 轮:")
        for tc in round_data["tool_calls"]:
            print(f"  工具: {tc['name']}")
            print(f"  参数: {tc['arguments']}")
            print(f"  结果: {tc['result'][:100]}...")

# 记录到 logger
llm_call_logger.log_call(
    inbound_msg=msg,
    outbound_msg=result,
    prompt_module="schedule",
    prompt_name="activity_summary"
)
```

## 🔍 后续优化建议

1. 添加工具调用的时间戳，便于性能分析
2. 添加工具调用的错误统计到链中
3. 基于 `tool_call_chain` 生成可视化的调用流程图
4. 考虑添加工具调用的耗时统计

## ✅ 最终状态

**功能状态**: ✅ 已完成并验证
**测试状态**: ✅ 单元测试通过
**文档状态**: ✅ 已完成
**代码质量**: ✅ 无语法错误，导入成功
