# 非 Repository Provider 使用清单

> 生成时间: 2026-04-28
> 说明: 统计所有使用 provider 但不是从 `lifeprism.repository` 导出的数据 provider

---

## 1. lifeprism.server.providers（共 8 个 Provider）

| Provider 类 | 实例变量 | 文件位置 |
|------------|---------|---------|
| ServerLWDataProvider | server_lw_data_provider | lifeprism/server/providers/statistical_data_providers.py |
| JournalProvider | journal_provider | lifeprism/server/providers/journal_provider.py |
| DailyReportProvider | daily_report_provider | lifeprism/server/providers/report_provider.py |
| WeeklyReportProvider | weekly_report_provider | lifeprism/server/providers/report_provider.py |
| MonthlyReportProvider | monthly_report_provider | lifeprism/server/providers/report_provider.py |
| ComparisonDataProvider | comparison_data_provider | lifeprism/server/providers/report_provider.py |
| ValueProvider | value_provider | lifeprism/server/providers/value_provider.py |
| CommitmentProvider | commitment_provider | lifeprism/server/providers/commitment_provider.py |
| BeingProvider | being_provider | lifeprism/server/providers/being_provider.py |

### 使用位置汇总

| Provider | 使用文件 |
|---------|---------|
| server_lw_data_provider | data_processing_service.py, activity_service.py, activity_stats_builder.py, report_service.py, category_service.py, statistical_data_providers.py |
| journal_provider | goal_service.py, journal_service.py |
| daily/weekly/monthly_report_provider, comparison_data_provider | report_service.py, report_api.py |
| value_provider | value_service.py, commitment_service.py |
| commitment_provider | commitment_service.py, value_service.py |
| being_provider | being_service.py |

---

## 2. lifeprism.monitor.provider（共 2 个 Provider）

| Provider 类 | 文件位置 |
|------------|---------|
| MonitorDataProvider | lifeprism/monitor/provider/window_data_provider.py |
| ScreenshotDataProvider | lifeprism/monitor/provider/screenshot_data_provider.py |

### 使用位置

| Provider | 使用文件 |
|---------|---------|
| MonitorDataProvider | monitor.py, runtime.py |
| ScreenshotDataProvider | runtime.py |

---

## 3. lifeprism.processors.provider（共 2 个 Provider）

| Provider 类 | 实例变量 | 文件位置 |
|------------|---------|---------|
| ProcessorAWDataProvider | processor_aw_data_provider | lifeprism/processors/provider/processor_aw_data_provider.py |
| ProcessorMonitorDataProvider | processor_monitor_data_provider | lifeprism/processors/provider/processor_monitor_data_provider.py |

### 使用位置

| Provider | 使用文件 |
|---------|---------|
| ProcessorAWDataProvider | processors/__init__.py |
| ProcessorMonitorDataProvider | processors/__init__.py |

---

## 4. lifeprism.llm.providers.dataset_providers（共 2 个 Provider）

| Provider 类 | 实例变量 | 文件位置 |
|------------|---------|---------|
| LLMDatasetProvider | llm_dataset_provider | lifeprism/llm/providers/dataset_providers/llm_dataset_provider.py |
| LLMLWDataProvider | old_llm_lw_data_provider | lifeprism/llm/providers/dataset_providers/old_llm_lw_data_provider.py |

### 使用位置

| Provider | 使用文件 |
|---------|---------|
| llm_dataset_provider | screenshot_analysis.py, channel/manager.py |

---

## 汇总统计

| 来源目录 | Provider 数量 |
|---------|--------------|
| lifeprism/server/providers | 8 个 |
| lifeprism/monitor/provider | 2 个 |
| lifeprism/processors/provider | 2 个 |
| lifeprism/llm/providers/dataset_providers | 2 个 |

**总计：14 个数据 Provider** 不是从 `lifeprism.repository` 导出的。

---

## 对比: lifeprism.repository 中的 Provider（已统一导出）

以下 Provider 已通过 `from lifeprism.repository import xxx_repository` 方式导出：

- diary_repository
- todo_repository  
- custom_block_repository
- plan_doc_repository
- tokens_usage_repository
- raw_behavior_analysis_repository
- behavior_analysis_repository
- screen_capture_repository
- habit_repository (aggregator)
- mood_repository (aggregator)
- goal_repository (aggregator)
- habit_chain_repository (aggregator)
- category_repository (aggregator)
- map_cache_repository (aggregator)

---

## 架构说明

根据 `docs/temp/Investigation/2026-04-24-provider-aggregator-architecture-research.md` 的设计：

- **Provider**: 单表数据访问（内部实现）
- **Aggregator**: 多表数据聚合（内部实现）
- **Repository**: 统一对外接口（使用 as 重命名）

目前存在多个分散的 provider 位置，架构尚未完全统一。
