# monitor_type=none 导致云端数据清洗时触发 ActivityWatch 数据库连接失败

**创建时间**: 2026-07-09
**严重程度**: 中（静默隐藏，数据清洗触发时才暴露）
**影响范围**: 云端部署（agent_only / web_demo），`monitor_type: none`

---

## 问题描述

云端部署时 `monitor_type` 被强制设为 `none`（表示禁用监控）。执行数据清洗流程时，`data_clean.py` 中根据 `monitor_type` 选择数据源的逻辑只有两个分支：

```python
if settings.monitor_type == "lifeprism":
    # 走内置 Monitor 数据源（window_events 表）
else:
    # 走 ActivityWatch 数据源
```

`none` 不匹配 `"lifeprism"`，落入 `else` 分支，走 `ProcessorAWDataProvider` → `AWBaseDataProvider._validate_database()` → 检查 AW 数据库文件是否存在 → `FileNotFoundError`。

## 根因

1. **`aw_db_manager` 懒加载只保护了 import 阶段**：issue #11 将 `readonly=True` 的 `DatabaseManager` 改为懒加载，避免模块导入时就崩溃，但**首次 `get_connection()` 时仍会因为文件不存在而失败**。

2. **`data_clean.py` 缺少对 `none` 的显式处理**：只区分了 `lifeprism` 和 "其他"，但 `none` 和 `activitywatch` 是不同的语义——`none` 表示根本没有监控，不应该走任何数据源。

## 为什么这个 bug 很隐蔽

- `import` 阶段不报错（感谢懒加载），启动一切正常
- 只有实际执行数据清洗任务时才触发（如日记总结、行为分析等定时任务）
- 云端首次部署时可能几天都不会触发数据清洗，测试环境容易漏掉

## 修复方案

在 `lifeprism/processors/data_clean.py` L486 增加 `elif` 分支：

```python
if settings.monitor_type == "lifeprism":
    raw_events = processor_monitor_data_provider.get_window_events(...)
elif settings.monitor_type == "none":
    # 监控已禁用，直接返回空数据，不走任何数据源
    raw_events = []
else:
    raw_events = processor_aw_data_provider.get_window_events(...)
```

## 相关

- issue #11: `aw_db_manager` 懒加载修复（解决了 import 崩溃，但未解决查询时的问题）
- `cloud_initializer.py` L238: 强制 `monitor_type: none`
- `cloud_initializer.py` L313-339: `validate_monitor_type()` 双重校验
