---
title: LifePrism Tool Use
status: 草稿
created: 2026-04-02
updated: 2026-04-05
---

# LifePrism Tool Use

## 目标与范围

### 核心目标

让 LifePrism 以"只读总结能力"的形式被 AI 使用，在数据不完整的情况下仍能稳定生成：
- 日报
- 周报
- 月报

### 第一阶段范围

**包含**：
1. 今日/本周/本月概览
2. 电脑使用模式
3. 重点记录与补充说明
4. 说明与限制

**不包含**：
- 数据写入与操作型能力
- Goal review / PlanDoc review
- 依赖心智模型的高级解释

---

## 核心概念

### 术语定义

**只读总结能力**：LifePrism 在不修改用户数据的前提下，为 AI 提供结构化上下文并生成日报/周报/月报的能力。

**Summary Context**：`get_summary_context` 返回的统一结构化证据包，是日报/周报/月报的共同输入。

**电脑使用节奏**：在单日分析窗口内，通过较低活跃密度阈值识别出的"较活跃时间段"分布。表达一天内电脑使用主要集中在哪些时间段，不直接表达起床/睡觉时间。

**长时间电脑使用段**：通过较高活跃密度阈值识别出的高密度电脑使用时间段，语义为"长时间电脑使用，包括中途短暂休息"。

**桥接桶**：在时间桶分段过程中，允许插入的单个"不满足阈值"的时间桶，用于容忍短暂休息或短时中断。

### 状态枚举

```python
# 总结类型
SUMMARY_TYPE = ["daily", "weekly", "monthly"]

# 单日窗口模式
DAY_WINDOW_MODE = ["4_to_4"]  # 4:00-次日4:00

# 覆盖度等级
COVERAGE_LEVEL = ["none", "low", "medium", "high"]

# 置信度等级
CONFIDENCE_LEVEL = ["low", "medium", "high"]

# 分段类型
SEGMENT_TYPE = ["active", "long_computer_usage"]
```

### 配置常量

```python
# 单日分析窗口
DAY_WINDOW_START_HOUR = 4
DAY_WINDOW_MODE_DEFAULT = "4_to_4"

# 时间桶参数
TIME_BUCKET_MINUTES = 10
MAX_BRIDGE_BUCKETS = 1

# 电脑使用节奏参数
ACTIVE_SEGMENT_DENSITY_THRESHOLD = 0.2
ACTIVE_SEGMENT_MIN_DURATION_MINUTES = 30

# 长时间电脑使用段参数
LONG_USAGE_DENSITY_THRESHOLD = 0.7
LONG_USAGE_MIN_DURATION_MINUTES = 60
```

---

## 业务规则

### 总结输出结构

三类总结（日报/周报/月报）共用同一套展示结构：

1. **数据覆盖**：说明数据完整性
2. **今日/本周/本月概览**：核心统计数据
3. **电脑使用模式**：活跃时间段分布
4. **重点记录与补充说明**：用户明确记录的内容
5. **说明与限制**：数据缺失和不确定性说明

### 证据分层规则

**事实层**（只允许输出可被直接证据支持的内容）：
- 活跃时长
- 分类分布
- Todo/Habit 完成情况
- 较活跃时间段
- 长时间电脑使用段
- 用户明确记录的 timeline_custom_block、diary 内容

**推断层**（允许输出弱推断，但必须保留不确定性）：
- 电脑使用较集中
- 当天存在明显夜间延续
- 存在长时间电脑使用

**缺失层**（必须明确说明数据缺失）：
- 数据覆盖度不足时，必须在"说明与限制"中说明
- 禁止在数据缺失时输出推测性结论

### 降级规则

- 数据覆盖度 `none` → 只输出"数据覆盖"和"说明与限制"
- 数据覆盖度 `low` → 输出基本统计，标注置信度为 `low`
- 数据覆盖度 `medium` → 输出完整结构，标注置信度为 `medium`
- 数据覆盖度 `high` → 输出完整结构，标注置信度为 `high`

---

## 数据模型

### Summary Context Schema

```python
class SummaryContext:
    summary_type: str  # daily/weekly/monthly
    date_range: DateRange
    data_coverage: DataCoverageContext
    overview: OverviewContext
    activity_patterns: ActivityContext
    authored: AuthoredContext
    uncertainty: UncertaintyContext
```

### 核心子 Context

**DataCoverageContext**：
- `coverage_level`: 覆盖度等级
- `missing_days`: 缺失天数
- `partial_days`: 部分数据天数

**ActivityContext**：
- `active_segments`: 较活跃时间段列表
- `long_usage_segments`: 长时间电脑使用段列表
- `category_distribution`: 分类分布

**ExecutionContext**：
- `todos_completed`: 完成的 Todo 数量
- `habits_checkins`: 习惯打卡次数

**AuthoredContext**：
- `custom_blocks`: 用户自定义时间块
- `diaries`: 日记内容

详细 Schema 定义见 `lifeprism/llm/schemas/summary_context_schemas.py`。

---

## API 接口

### 核心接口

```python
# 获取总结上下文
def get_summary_context(
    date_range: DateRange,
    summary_type: str  # daily/weekly/monthly
) -> SummaryContext
```

### 内部子接口

```python
def get_data_coverage_context(date_range: DateRange) -> DataCoverageContext
def get_activity_context(date_range: DateRange, day_window_mode: str) -> ActivityContext
def get_execution_context(date_range: DateRange) -> ExecutionContext
def get_authored_context(date_range: DateRange) -> AuthoredContext
```

详细 API 文档见 `docs/generated/api-docs.md`（自动生成）。

---

## 后端实现

### 架构

模块位置：`lifeprism/llm/`

分层结构：
- **Provider 层**：`providers/summary_read_provider.py` - 数据库读取原语
- **Aggregator 层**：`summary_context/aggregators/` - 内容聚合（活动分段、分类统计）
- **Service 层**：`summary_context/service.py` - 业务整理、降级逻辑
- **Builder 层**：`summary_context/builder.py` - 结构化输出
- **Tool 层**：`tools/summary_tools.py` - 对外适配

### 目录结构

```
lifeprism/llm/
├── providers/
│   └── summary_read_provider.py
├── summary_context/
│   ├── aggregators/
│   │   ├── activity_aggregator.py
│   │   ├── coverage_aggregator.py
│   │   ├── execution_aggregator.py
│   │   └── authored_aggregator.py
│   ├── service.py
│   ├── builder.py
│   └── __init__.py
├── schemas/
│   └── summary_context_schemas.py
└── tools/
    └── summary_tools.py
```

### 关键逻辑

**时间桶分段算法**：
1. 将时间范围切分为 10 分钟时间桶
2. 计算每个桶的活跃密度
3. 根据阈值识别满足条件的桶
4. 允许 1 个桥接桶连接相邻段
5. 过滤掉小于最小时长的段

**覆盖度计算**：
- 统计有数据的天数 / 总天数
- 根据比例判定覆盖度等级

详细实现见原 PRD：`docs_old/prd/功能需求/lifeprism_use_tool/`（保留作为参考）。

---

## 验收标准

### 功能完整性

- [ ] 能够生成日报/周报/月报
- [ ] 数据覆盖度计算正确
- [ ] 活跃时间段识别准确
- [ ] 降级规则正确执行
- [ ] 证据分层规则正确执行

### 性能要求

- [ ] 日报生成 < 2s
- [ ] 周报生成 < 5s
- [ ] 月报生成 < 10s

### 质量要求

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试覆盖核心场景
- [ ] 详细测试场景见 `test/scenarios/lifeprism-tool-use-scenarios.md`

---

## 实施计划

见 `docs/plans/completed/2026-04-02-lifeprism-use-tool.md`（如果存在）。

---

## 参考文档

- **原 PRD（7 章节版本）**：`docs_old/prd/功能需求/lifeprism_use_tool/`（保留作为历史参考）
- **后端规范**：[backend-guide.md](../rules/backend-guide.md)
- **架构概览**：[architecture.md](../rules/architecture.md)
- **术语与配置**：`docs_old/prd/功能需求/lifeprism_use_tool/01-术语与配置/术语与配置.md`
- **业务逻辑**：`docs_old/prd/功能需求/lifeprism_use_tool/02-业务逻辑/业务逻辑.md`
- **数据设计**：`docs_old/prd/功能需求/lifeprism_use_tool/03-数据设计/数据设计.md`
- **后端设计**：`docs_old/prd/功能需求/lifeprism_use_tool/06-后端设计/后端设计.md`
