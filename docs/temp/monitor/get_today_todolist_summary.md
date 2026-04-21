# get_today_todolist 函数实现完成

## 功能说明

`get_today_todolist()` 函数用于获取今日的 TodoList 并格式化为结构化文本，供 LLM 截图分析使用。

## 函数签名

```python
def get_today_todolist(date: str) -> str | None:
    """获取今日 TodoList 并格式化为结构化文本

    Args:
        date: 日期（YYYY-MM-DD 格式）

    Returns:
        str | None: 格式化的今日目标文本，如果没有任务则返回 None
    """
```

## 实现细节

1. **查询数据**: 使用 `llm_dataset_provider.query_todos()` 查询指定日期的 TodoList
2. **包含跨天任务**: `include_cross_day=True`，包含跨天未完成的任务
3. **状态过滤**: 只返回 `active` 和 `scheduled` 状态的任务
4. **格式化输出**: 按编号列表格式输出

## 输出格式

```
## 今日目标：

1. 完成《复利效应》的笔记
2. 完成 feat_monitor 监控功能开发
3. 修复 habit 模块 bug：习惯界面链条时间计算有问题
```

## 使用示例

```python
from lifeprism.llm.function.screenshot_analysis import get_today_todolist

# 获取今日 TodoList
today = "2026-04-21"
todolist_text = get_today_todolist(today)

if todolist_text:
    print(todolist_text)
else:
    print("今日没有待办任务")
```

## 测试结果

**文件**: `test/core/unit/llm/test_screenshot_analysis.py`

✅ 6/6 测试全部通过

测试覆盖：
- 基本功能测试
- 输出格式验证
- 空数据处理
- 返回类型检查
- 数据库集成测试
- 输出结构完整性测试

## 与 LLM 截图分析的集成

该函数的输出将作为 context 提供给 LLM 进行截图语义分析，帮助 LLM 更好地理解用户行为与目标的关联性。

在 `SYSTEM_PROMPT` 中的应用场景：

```python
# 获取今日目标
goal_context = get_today_todolist(date)

# 构建 user message
user_content = []
if goal_context:
    user_content.append({"type": "text", "text": goal_context})

user_content.append({
    "type": "text",
    "text": f"时间范围: {chunk['start']} -> {chunk['end']}",
})
# ... 添加截图
```

这样 LLM 就能根据用户的今日目标来判断截图中的行为语义，符合 `SYSTEM_PROMPT` 中的"行为语义推断情况1"。

## 依赖

- `lifeprism.llm.providers.llm_dataset_provider`: 数据查询接口
