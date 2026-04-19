# 内置监控数据清理逻辑设计文档

## 1. 背景
目前 LifeWatch-AI 正在从依赖外部 ActivityWatch 转向内置监控。已经实现了 `window_events` 表的存储逻辑，现在需要让 `processors` 模块能够从该表读取数据并进行数据清洗。

## 2. 设计目标
- 在 `lifeprism/processors/provider` 中增加一个新的 Provider，用于读取 `window_events` 表。
- 在 `data_clean.py` 中根据 `settings.monitor_type` 切换数据源。
- 保持现有组件化清洗流程不变（`EventTransformer`, `CacheMatcher` 等）。

## 3. 详细设计

### 3.1 Provider 扩展
新建 `lifeprism/processors/provider/processor_monitor_data_provider.py`：
- 继承 `LWBaseDataProvider`。
- 实现 `get_window_events(start_time, end_time)` 方法，查询 `window_events` 表。
- 将 `window_events` 字段映射为清洗组件预期的格式：
  - `timestamp` -> `timestamp` (ISO 格式)
  - `duration` -> `duration` (秒)
  - `app` -> `data['app']` 
  - `title` -> `data['title']`

### 3.2 数据清理逻辑修改 (`lifeprism/processors/data_clean.py`)
在 `clean_activitywatch_data` 函数中：
- 根据 `settings.monitor_type` 判断：
  - 如果值为 `lifeprism`：使用 `ProcessorMonitorDataProvider` 从内置数据库读取。
  - 否则（默认/其他）：使用 `ProcessorAWDataProvider` 从 ActivityWatch 读取。

## 4. 风险与测试
- **数据格式对齐**：确保 `ProcessorMonitorDataProvider` 返回的 `data` 嵌套字典结构与 `ActivityWatch` 原始格式一致，以便 `EventTransformer` 无缝处理。
- **时区处理**：验证内置监控存储的时间戳（通常为 ISO 本地时间）在 `EventTransformer` 中的转换逻辑是否正确。

