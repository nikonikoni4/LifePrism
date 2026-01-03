# Report Summary Tokens 使用量跟踪功能

## 修改概述

为 `report_summary.py` 中的两个函数添加了 tokens 使用量的跟踪、保存和返回功能。

## 修改的文件

### 1. `lifewatch/llm/llm_classify/function/report_summary.py`

#### 修改内容:

1. **添加导入**:
   - `from lifewatch.storage.base_providers.lw_base_data_provider import LWBaseDataProvider`
   - `import logging`

2. **修改 `daily_summary()` 函数**:
   - 从 LLM 响应的 `response_metadata['token_usage']` 中提取 tokens 使用量
   - 使用 `session_id` 格式: `summary-{date}` (例如: `summary-2026-01-01`)
   - 调用 `LWBaseDataProvider.upsert_session_tokens_usage()` 保存到数据库
   - 返回格式从字符串改为字典:
     ```python
     {
         'content': str,  # 总结内容
         'tokens_usage': {
             'input_tokens': int,
             'output_tokens': int,
             'total_tokens': int
         }
     }
     ```

3. **修改 `multi_days_summary()` 函数**:
   - 从 LLM 响应的 `response_metadata['token_usage']` 中提取 tokens 使用量
   - 使用 `session_id` 格式: `summary-{start_date}_to_{end_date}` (例如: `summary-2026-01-01_to_2026-01-07`)
   - 调用 `LWBaseDataProvider.upsert_session_tokens_usage()` 保存到数据库
   - 返回格式从字符串改为字典 (同上)

## 数据库表结构

使用的数据库表: `tokens_usage_log`

相关字段:
- `session_id`: 会话ID (PRIMARY KEY)
- `input_tokens`: 输入 token 数量
- `output_tokens`: 输出 token 数量
- `total_tokens`: 总 token 数量
- `search_count`: 搜索次数 (对于 summary 模式设置为 0)
- `result_items_count`: 结果项目数量 (对于 summary 模式设置为 0)
- `mode`: 模式 (设置为 'summary')
- `created_at`: 创建时间 (自动添加)

## Session ID 格式

- **每日总结**: `summary-YYYY-MM-DD`
  - 例如: `summary-2026-01-01`

- **多日总结**: `summary-YYYY-MM-DD_to_YYYY-MM-DD`
  - 例如: `summary-2026-01-01_to_2026-01-07`

## 使用示例

### 每日总结

```python
from lifewatch.llm.llm_classify.function.report_summary import daily_summary

result = daily_summary(date="2026-01-01", options=["时间分布", "主要活动"])

# 访问总结内容
content = result['content']

# 访问 tokens 使用量
tokens_usage = result['tokens_usage']
print(f"输入 tokens: {tokens_usage['input_tokens']}")
print(f"输出 tokens: {tokens_usage['output_tokens']}")
print(f"总 tokens: {tokens_usage['total_tokens']}")
```

### 多日总结

```python
from lifewatch.llm.llm_classify.function.report_summary import multi_days_summary

result = multi_days_summary(
    start_time="2026-01-01 00:00:00",
    end_time="2026-01-07 23:59:59",
    split_count=7,
    options=["时间分布", "主要活动", "趋势分析"]
)

# 访问总结内容
content = result['content']

# 访问 tokens 使用量
tokens_usage = result['tokens_usage']
print(f"输入 tokens: {tokens_usage['input_tokens']}")
print(f"输出 tokens: {tokens_usage['output_tokens']}")
print(f"总 tokens: {tokens_usage['total_tokens']}")
```

## 注意事项

### ⚠️ 破坏性变更

**返回值格式已更改**: 这两个函数的返回值从 `str` 改为 `dict`。

如果有其他代码调用这两个函数，需要相应更新:

**修改前**:
```python
summary = daily_summary(date, options)
# summary 是字符串
```

**修改后**:
```python
result = daily_summary(date, options)
summary = result['content']  # 获取总结内容
tokens_usage = result['tokens_usage']  # 获取 tokens 使用量
```

### 数据库保存

- 使用 `upsert` 策略: 如果 `session_id` 已存在则更新，否则插入新记录
- 每次调用都会保存/更新 tokens 使用量到数据库
- 如果保存失败，会记录错误日志但不会影响函数返回

## 测试

运行测试脚本验证功能:

```bash
python test_report_summary_tokens.py
```

测试脚本会:
1. 调用 `daily_summary()` 函数
2. 调用 `multi_days_summary()` 函数
3. 验证返回值格式
4. 显示 tokens 使用量信息

## 日志

函数会记录以下日志:

- **成功保存**: `INFO` 级别
  - `已保存每日总结的 tokens 使用量: {session_id}, total_tokens={total_tokens}`
  - `已保存多日总结的 tokens 使用量: {session_id}, total_tokens={total_tokens}`

- **保存失败**: `ERROR` 级别
  - `保存 tokens 使用量失败: {error}`
