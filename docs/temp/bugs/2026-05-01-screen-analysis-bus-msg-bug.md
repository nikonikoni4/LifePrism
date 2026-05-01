# 2026-05-01 screenshot_analysis extra字段 system_prompt 导致 context 无法正确导入 prompt

## Bug 信息

- **发现日期**: 2026-05-01
- **严重程度**: 严重（影响核心功能，导致测试结果不可靠）
- **影响范围**: 截图语义分析功能，所有使用该功能的场景
- **状态**: 已修复（需重新测试验证）
- **相关文件**: 
  - `lifeprism/llm/function/screenshot_analysis.py` (第 421 行)

## 问题描述

在 `screenshot_analysis.py` 中，`InboundMessage` 的 `extra` 字段原来使用 `'ANALYSIS_SYSTEM_PROMPT'` 作为 key：

```python
msg = InboundMessage(
    content=user_content,
    type=MessageType.GENERAL_TASK,
    extra={'ANALYSIS_SYSTEM_PROMPT' : ANALYSIS_SYSTEM_PROMPT}  # ← 原来错误的写法
)
```

这导致后续 `context` 在处理消息时无法正确识别和导入该 prompt。

## 症状表现

1. **功能异常**：截图语义分析返回的结果不正确或不符合预期
2. **测试失效**：之前编写的测试用例结果不可靠，无法作为功能验证依据
3. **难以排查**：错误静默发生，没有明显的错误日志

## 根本原因分析

### 1. key 名称不一致

`extra` 字段中使用的 key `'system_prompt'` 与系统其他部分期望的 key 名称不一致，导致：

```python
# context 期望的 key 可能是 ANALYSIS_SYSTEM_PROMPT 或其他
# 但收到的是 'system_prompt'
```

### 2. 影响链路

```
screenshot_analysis.py
    ↓ 发送消息
InboundMessage(extra={'system_prompt': ...})
    ↓ 传递
context 处理层
    ↓ 无法识别
prompt 未正确加载/注入
    ↓ 结果
LLM 返回结果不正确
```

## 修复方案

将 `extra={'ANALYSIS_SYSTEM_PROMPT' : ANALYSIS_SYSTEM_PROMPT}` 修改为正确的 key 名称。

**修复代码**：

```python
msg = InboundMessage(
    content=user_content,
    type=MessageType.GENERAL_TASK,
    extra={'system_prompt': ANALYSIS_SYSTEM_PROMPT}  # ← 正确的 key 名称
)
```

## 后续改进

### 自定义 lint 检查

为防止此类问题再次发生，建议在自定义 lint 检查中添加 `extra` 字段的检查规则：

1. **检查场景**：
   - 当 `extra` 字段包含 `system_prompt` 相关内容时
   - 验证 key 名称是否与预期的常量名一致

2. **检查规则建议**：
   - `extra` 中使用常量名作为 key 时应给出警告
   - 应使用字符串（如 `'system_prompt'`）作为 key
   - 建议统一 `extra` 字段的 key 命名规范

3. **实现位置**：
   - `docs/coding-rules/` 下的 lint 规则文件
   - 或在 pre-commit hook 中添加检查

## 测试验证

修复后需要重新测试以下场景：

1. 截图分析基本功能
2. 长时间段截图批量分析
3. 不同格式的 todolist 输入
4. 与其他功能模块的集成测试

## 教训总结

1. **常量使用**：当使用常量作为值时，key 也应使用对应常量，避免硬编码字符串
2. **接口契约**：修改 `extra` 等接口字段时，应同步检查所有依赖方
3. **测试有效性**：发现接口不匹配时，应重新验证历史测试结果的有效性