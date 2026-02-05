# database_tools

数据库相关的 LLM 工具列表。

## 工具列表

### 统计查询工具

- **get_daily_stats**: 用于获取单日（<24h）用户行为统计摘要，包含电脑使用时间、分类占比、目标投入、用户备注、任务、环比对比
- **get_multi_days_stats**: 用于获取多天用户行为统计摘要，包含行为统计、目标趋势、任务、分类趋势、用户备注、作息分析、环比对比

### 行为日志查询

- **query_behavior_logs**: 用于查询指定时间段的详细行为日志，支持按分类筛选

### 用户数据查询

- **query_goals**: 用于查询用户设置的目标列表
- **query_psychological_assessment**: 用于查询用户的心理测评数据（过去/现在/未来的自我探索）

### 周报/月报规律性总结工具

- **get_daily_breakdown**: 用于获取每日分解数据表格（使用时长、分类占比、电脑启用/结束时间），便于发现异常天
- **query_daily_summaries**: 用于获取每日 AI 摘要列表，快速了解每天情况
- **query_weekly_focus**: 用于查询指定周的焦点内容

### 内部辅助函数

- **_get_comparison_stats_internal**: 用于计算两个时间段的环比对比（分类时间变化、目标投入变化）
