# read_file 工具 max_chars 默认值过小导致工具调用次数爆炸

## 元信息
- **updated_at**: 2026-06-30
- **severity**: HIGH（导致 `update_memory` 消耗 20 次工具调用上限，其中 15 次是无效的重复读取）

## 问题描述

### 症状
`update_memory`（DREAM_TASK）一次执行触发了 21 次 LLM 调用（21 轮工具循环），达到 `MAX_TOOL_CALL=20` 上限后被强制终止。其中仅 5 次调用有效，其余 16 次是反复读取同一个文件的不同偏移量/搜索方式。

### 具体表现
从日志中提取的工具调用序列：
```
 1. read_file  recent_state.md        ✓ 有效
 2. read_file  user.md                ✓ 有效
 3. write_file recent_state.md        ✓ 有效
 4. read_file  user.md offset=17      ✗ 尝试读"剩余"
 5. read_file  user.md offset=1 limit=50     ✗
 6. read_file  user.md offset=17 limit=50    ✗
 7. search_string_py 搜索 "##"         ✗ 换搜索方式
 8. read_file  user.md limit=30       ✗
 9. read_file  user.md limit=100      ✗
10. search_file_py 搜索 user.md       ✗
11. read_file  user.md limit=200      ✗
12. search_string_py 搜索 "健康状况"   ✗
13. search_string_py 搜索 "^"          ✗ 匹配每行开头
14. read_file  user.md offset=18      ✗
15. search_string_py 搜索 "心情\d+分"  ✗
16. edit_file  user.md                ✓ 有效
17. edit_file  user.md                ✓ 有效
18. read_file  recent_state.md        ✗ 验证读取
19. read_file  recent_state.md offset=21  ✗
20. read_file  recent_state.md offset=42  ✗
21. write_file recent_state.md        ⚠️ 触发 MAX_TOOL_CALL 强制终止
```

## 根本原因

### 代码位置
`lifeprism/llm/agent/tools/filesystem.py:92-98`（参数定义）和 `_read_file()` 函数

### 问题机制

1. `read_file` 工具有一个 `max_chars` 参数，**默认值为 1024**：
   ```python
   "max_chars": {
       "default": 1024,
       "maximum": 5000,
   }
   ```

2. `_read_file()` 在返回内容前会按 `max_chars` 硬截断：
   ```python
   if len(content) > max_chars:
       content = content[:max_chars]
   ```

3. `read_ratio` 计算为 `len(content) / total_body_chars`。因为内容被截断到 1024 字符，对于 > 1024 字符的文件，`read_ratio` 永远 < 1.0。

4. user.md 约 3300 字符，每次读取返回 1024 字符（`read_ratio=0.91`），内容末尾被截断（如 "睡眠严"）。LLM 看到 `read_ratio < 1.0` 和截断的内容，判断文件"还没读完"，不断尝试不同参数去读"剩余"内容。

5. **关键：LLM 不断调整 `offset` 和 `limit`，但从未想过调整 `max_chars`**，因为参数描述只是"最大字符数限制"，LLM 不知道默认值只有 1024。

6. 每次尝试都消耗一次 LLM 调用 + 工具执行，15 次无效调用消耗完 20 次的 `MAX_TOOL_CALL` 预算。

## 正确解决方案

**去掉 `max_chars` 参数**。理由：
- 和 `limit`（行数控制）功能重叠
- 它要解决的问题（某行太长）几乎不存在于 markdown 文档中
- 即使某行超长，截断它反而产生畸形内容，不如整行返回
- `limit` 参数已经足够控制输出量

修改后 `read_ratio` 语义变为准确的"已读行数占全文比例"，读完就是 1.0。

## 关键教训

1. **工具返回值中的比例/进度信息必须准确**。虚假的 < 1.0 的 `read_ratio` 会误导 LLM 进入无限循环。

2. **默认参数值对 LLM 行为有巨大影响**。LLM 会尝试调整它能看到的参数（offset、limit），但很难发现隐藏的瓶颈参数（max_chars）。

3. **相同的控制维度不要有两个**。`limit`（行数）和 `max_chars`（字符数）同时存在会让 LLM 困惑，也增加调试难度。

4. **`MAX_TOOL_CALL=20` 是一个安全网，但不应成为常态**。正常操作应该在 5-8 次工具调用内完成。

## 相关文件
- `lifeprism/llm/agent/tools/filesystem.py` - `ReadFileTool` 和 `_read_file()`
- `lifeprism/llm/agent/loop.py:_run_agent_loop()` - `MAX_TOOL_CALL=20` 限制
- `lifeprism/llm/function/agent_schedule_job.py:update_memory()` - 受影响的调用方

## 标签
`tool-design` `max-chars` `read_ratio` `max-tool-call` `infinite-loop` `llm-confusion` `dream-task`
