# Issue #31: Repository 层时间查询兜底校验（低优先级）

## Parent

`.scratch/utc-timezone-migration/prd.md`

## 背景

当前 Repository 层直接用传入的字符串做 SQL `WHERE` 比较，如果传入格式和数据库格式不一致（如本地 `YYYY-MM-DD HH:MM:SS` 查 UTC ISO 字段），查询结果错误但不会报错。

**当前状态**：
- 上游（LLM 工具 execute 层、API 层、Service 层）负责正确转换时间格式
- Repository 层不做校验，信任上游传入的格式

**潜在风险**：
- 如果上游转换逻辑有 bug，Repository 层不会报错，导致查询结果静默错误
- 调试困难：错误现象是"查不到数据"或"查到错误数据"，根因在 upstream 转换

**优先级**：低。当前主要靠上游正确转换保证一致性，本 issue 作为防御性增强。

## What to build

### 1. 时间格式校验装饰器（可选方案）

在 Repository 层的关键查询函数增加时间参数校验：

```python
def validate_time_format(param_names: list[str]):
    """装饰器：校验时间参数格式为 UTC ISO 8601"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for name in param_names:
                value = kwargs.get(name)
                if value and not _is_utc_iso(value):
                    raise ValueError(
                        f"参数 {name} 格式错误，期望 UTC ISO 8601，实际: {value}"
                    )
            return func(*args, **kwargs)
        return wrapper
    return decorator

def _is_utc_iso(time_str: str) -> bool:
    """检查字符串是否为 UTC ISO 8601 格式"""
    try:
        dt = datetime.fromisoformat(time_str)
        return dt.tzinfo is not None and dt.utcoffset() == timedelta(0)
    except (ValueError, TypeError):
        return False
```

### 2. 关键查询函数增加校验

为以下 Repository 函数增加时间参数校验：

- `behavior_analysis_provider.get_behaviors_by_date`
- `behavior_analysis_provider.get_behaviors_by_date_range`
- `raw_behavior_analysis_provider.get_raw_behaviors_by_date_range`
- `computer_usage_repository.query_computer_usage_with_names`
- `custom_block_repository.query_custom_blocks`
- `mood_repository.get_mood_entries`

### 3. 日志告警

对格式不匹配的输入，除了抛异常外，增加 `logger.warning` 记录：

```python
logger.warning(
    "时间参数格式非 UTC ISO: param=%s, value=%s, func=%s",
    name, value, func.__name__
)
```

## Acceptance criteria

- [ ] 实现时间格式校验装饰器（或内联校验）
- [ ] 关键查询函数增加校验
- [ ] 校验失败时抛 `ValueError` 并记录日志
- [ ] 单元测试覆盖：正确格式通过、错误格式报错
- [ ] `ruff check` 和 `ruff format` 全部通过
- [ ] 现有测试全部通过（无回归）

## Blocked by

- Issue #30 - Repository 层遗留 bug 修复（先修复 bug，再加校验）

## 注意事项

1. **低优先级**：本 issue 不是必须的，是防御性增强
2. **不影响正常流程**：校验只在格式错误时报错，不影响正确调用
3. **性能考虑**：校验逻辑应轻量，避免对高频查询造成性能影响
4. **可选方案**：如果装饰器方案过于复杂，可以改为在关键函数内联校验
5. **依赖 #30**：先修复 Repository 层的 bug，再加兜底校验
