# 截图查询时间戳格式不匹配导致查询失败

## 基本信息

- **Bug ID**: 2026-04-30-screenshot-timestamp-format-mismatch
- **发现日期**: 2026-04-30
- **影响模块**: 截图分析功能
- **严重程度**: 高（导致截图分析完全失败）

## 问题描述

修改 `screen_captures` 表的 `captured_at` 字段格式为 `YYYY-MM-DD HH:MM:SS` 后，截图分析功能查询不到任何截图，导致分析失败。

## 根本原因

1. **数据库存储格式**：`captured_at` 字段存储格式为 `YYYY-MM-DD HH:MM:SS`（空格分隔）
2. **查询输入格式**：`screenshot_analysis.py` 中传入的是 ISO 格式 `YYYY-MM-DDTHH:MM:SS`（带 `T`）
3. **SQLite 字符串比较**：两种格式无法匹配，导致查询结果为空

## 触发场景

- 截图分析功能调用 `screen_capture_repository.query_screenshots()` 时
- 任何使用时间范围查询 `screen_captures` 表的场景

## 解决方案

在 `screen_capture_provider.py` 的 `query_screenshots()` 方法中添加格式转换：

```python
# 将 ISO 格式（带 T）转换为数据库格式（空格分隔）
start_time_db = start_time.replace('T', ' ') if 'T' in start_time else start_time
end_time_db = end_time.replace('T', ' ') if 'T' in end_time else end_time
```

**修改文件**：
- `lifeprism/repository/providers/screen_capture_provider.py:184-223`

## 附加优化

同时发现截图数量过多问题（127张），进行了以下优化：

1. **添加截图数量限制**：每个 chunk 最多 9 张（Doubao Seed 2.0 Lite 限制）
2. **动态 chunk 大小**：根据截图频率等级调整
   - 等级1（低频）：12分钟
   - 等级2（中频）：10分钟
   - 等级3（高频）：8分钟

**修改文件**：
- `lifeprism/llm/function/screenshot_analysis.py:109-121, 351-354, 463-496`

## 经验教训

1. **数据格式一致性**：修改数据库字段格式时，必须同步检查所有查询代码
2. **时间格式标准化**：建议在 provider 层统一处理时间格式转换，避免调用方感知
3. **模型限制考虑**：使用 LLM 分析时要考虑模型的输入限制（图片数量、token 数等）

## 相关文档

- `docs/specs/2026-04-26-screenshot-analysis-spec.md`
- `lifeprism/config/database.py:1465-1522` (SCREEN_CAPTURES_CONFIG)
