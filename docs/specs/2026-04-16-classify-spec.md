---
version: 1.0
created_at: 2026-04-16
updated_at: 2026-04-16
last_updated: 创建 spec 初稿，从 docs/temp/old_docs/user_guide.md 提取分类流程规格
abstract: >
  AI 数据分类流程规格文档。定义 LifePrism 系统对 ActivityWatch 采集的活动数据进行分类的
  完整业务规则与技术契约，涵盖数据清洗管道（EventTransformer → CacheMatcher → ClassifyCollector）、
  三级分类优先级（缓存命中 → LLM 分类中的 Goal 匹配 → AI 纯分类）、
  两种分类模式（classify_graph / classify_simple）及对应的 API 契约。
id: classify-spec
title: AI 数据分类流程
status: stable
module: lifeprism/processors, lifeprism/llm/classify
sourc_spec: docs/temp/old_docs/user_guide.md
related_plan: ""
code_scope:
  - lifeprism/processors/data_clean.py
  - lifeprism/processors/components/
  - lifeprism/llm/classify/
  - lifeprism/llm/schemas/classify_shemas.py
  - lifeprism/server/services/data_processing_service.py
  - lifeprism/server/api/sync.py
contract_refs:
  - lifeprism/llm/schemas/classify_shemas.py
  - lifeprism/server/schemas/sync.py
---

# AI 数据分类流程

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |

## Overview

LifePrism 对 ActivityWatch（AW）采集的电脑活动数据进行智能分类，最终输出每条活动记录对应的 `category`（主分类）、`sub_category`（子分类）及 `link_to_goal`（关联目标）。

整个流程分为两个阶段：

1. **数据清洗管道**：将原始 AW 事件标准化，并用 Map Cache 预匹配已知分类
2. **LLM 分类阶段**：对未命中缓存的事件由 AI 进行智能分类，分类结果写回 Map Cache

## Scope

**在范围内：**

- ActivityWatch 原始事件的清洗与标准化
- Map Cache（category_map_cache）的缓存命中逻辑
- LLM 智能分类（Goal 优先匹配 + 纯 AI 分类）
- 两种分类器模式（`classify_graph` / `classify_simple`）
- 分类结果写入 `user_app_behavior_log` 及 `category_map_cache`
- 增量同步 API 与时间范围同步 API

**不在范围内：**

- Map Cache 的 CRUD 管理界面
- 分类类别（Category / Sub-Category）的创建与编辑
- Goal（目标）的创建与管理
- 移动端/穿戴设备数据分类

## Core Behavior

### 1. 数据源选择

系统根据 `settings.monitor_type` 决定原始数据来源：

- `"lifeprism"`：使用内置 Windows 监控数据源（`processor_monitor_data_provider`）
- 其他值（如 `"activitywatch"`）：使用 ActivityWatch 数据源（`processor_aw_data_provider`）

### 2. 数据清洗管道

原始事件经过以下组件顺序处理：

```
原始事件 → EventTransformer → CacheMatcher → ClassifyCollector → classifyState
```

#### 2.1 EventTransformer（事件转换与过滤）

- **时长过滤**：`duration < settings.data_cleaning_threshold`（秒）的事件被丢弃
- **应用名标准化**：`app_name.lower().strip().split('.exe')[0]`
- **标题标准化**：`title.split('和另外')[0].strip().lower()`
- **脏数据过滤**：多用途应用（`is_multipurpose=True`）且无 title 的事件被丢弃
- **时间戳转换**：UTC ISO 8601 → 本地时区字符串（格式 `YYYY-MM-DD HH:MM:SS`）

#### 2.2 CacheMatcher（缓存匹配策略）

使用 `CategoryCache` 构建的倒排索引：

| 应用类型 | 匹配键 | 缓存命中条件 |
|---------|-------|------------|
| 单用途（`is_multipurpose=0`） | `app`（小写） | `category_id` 不为空 且 `state=1` |
| 多用途（`is_multipurpose=1`） | `app + title`（均小写） | `category_id` 不为空 且 `title` 不为空 且 `state=1` |

命中后填充事件的 `category_id`、`sub_category_id`、`link_to_goal_id`，并标记 `cache_matched=True`。

#### 2.3 ClassifyCollector（待分类项收集）

对 `cache_matched=False` 的事件：

- **单用途**：每个 app 只收集一次（app 级去重）
- **多用途**：每个 title 收集一次（title 级去重）；同一 app 可有多个 title

收集结果构建 `classifyState`：

```
classifyState {
  app_registry: { app: AppInFo }   # 应用注册表
  log_items: [LogItem]              # 待分类日志项
  result_items: null                # 分类结果，初始为 null
}
```

已有描述的 app（来自 `category_map_cache.app_description`）会被复用，避免 LLM 重复搜索。

### 3. LLM 分类阶段（三级优先级）

**第 0 级：缓存命中**（已在 CacheMatcher 完成，无需 LLM）

**第 1 级：Goal 匹配**（在 LLM 分类器内部，通过 System Prompt 注入 goals 列表实现，不是独立的管道步骤）

- 调用 `goal_provider.get_active_goals_for_classify()` 获取活跃且开启自动追踪（`track_time_automatically=1`）且已绑定分类的 Goal
- Goals 以 `{goal: 名称, category: 主分类, sub_category: 子分类}` 格式注入 System Prompt
- LLM 判断活动内容（app 名称、标题）与 Goal 高度相关时，优先使用 Goal 绑定的分类，并输出 `link_to_goal = goal_name`
- 无关联时 `link_to_goal = null`
- 若 Goal 绑定的分类被禁用，则该 Goal 不参与分类流程（构建 category_tree 时已过滤禁用分类）

**第 2 级：AI 纯分类**（依据 app 用途 / title 语义）

分类器由 `LLMClassify` 统一入口，根据 `settings.classification_mode` 选择：

| 模式 | 类 | 描述 |
|------|----|------|
| `classify_graph` | `ClassifyGraph` | 复杂多步分类，区分单/多用途并发流 |
| `classify_simple` | `ClassifySimple` | 简化一步分类，全量并发 |

#### classify_graph 分类流程

```
Step 1: get_app_description（并发，仅对无描述的 app 调用）
   ↓
Step 2a: single_classify（单用途，批量并发，每批 ≤10 条）
Step 2b: multi_classify_short（多用途短活动，批量并发，每批 ≤10 条）
Step 2c: get_titles → multi_classify_long（多用途长活动，串行，再批量并发）
```

- **长/短活动阈值**：`settings.long_log_threshold`（单位：秒，由 `split_by_duration` 读取）
- **单用途分类**：依据 `app_description` + `app_name` 进行分类
- **多用途短活动**：依据 `app_name` + `title` 进行分类
- **多用途长活动**：先 `get_titles` 搜索 title 语义，再综合 `app_description` + `app_name` + `title` + `title_analysis` 分类

#### classify_simple 分类流程

一步并发批量分类，所有条目统一处理，每批 ≤15 条：

- 单用途依据 `app_description` 分类
- 多用途依据 `app`、`app_description`、`title` 分类

### 4. 分类结果处理

分类结果 `LogItem` 携带 `category`、`sub_category`、`link_to_goal`，经过以下处理后写入数据库：

#### 4.1 分类结果层级验证（`_validate_classification_results`）

按以下规则校验 category / sub_category 的层级合法性：

| 情况 | 处理方式 |
|-----|--------|
| 主分类为 null，子分类为 null | 合法，保留 |
| 主分类有值，子分类为 null | 需验证主分类在分类树中，否则修正为 null |
| 主分类为 null，子分类有值 | 不合法，将子分类修正为 null |
| 主分类有值，子分类有值 | 需验证子分类属于主分类，否则两者均修正为 null |

#### 4.2 写入目标

1. `category_map_cache` 表——生成新的 Map Cache 记录，供后续事件直接缓存命中
2. `user_app_behavior_log` 表——回填已分类的分类字段（通过 `_merge_classification_results` 合并）

## Technical Contract

### 核心数据模型

```python
# lifeprism/llm/schemas/classify_shemas.py

class LogItem(BaseModel):
    id: int
    app: str
    duration: int            # 单位：秒
    title: str | None
    title_analysis: str | None = None
    category: str | None = None
    sub_category: str | None = None
    link_to_goal: str | None = None

class AppInFo(BaseModel):
    description: str        # app 用途描述（LLM 搜索或缓存复用）
    is_multipurpose: bool
    titles: list[str] | None = None

class classifyState(BaseModel):
    app_registry: dict[str, AppInFo]
    log_items: list[LogItem]
    result_items: list[LogItem] | None = None
```

### LLM 分类输出格式

```json
{
  "<id>": ["<category>", "<sub_category>", "<link_to_goal>"]
}
```

- value 必须是长度为 3 的列表
- 无值时使用 `null`
- key 必须为 `LogItem.id`（整数转字符串）

### 分类器注册表

```python
# lifeprism/llm/classify/main_classify.py
CLASSIFIER_REGISTRY = {
    "classify_graph": ClassifyGraph,
    "classify_simple": ClassifySimple,
}
```

`classify_mode` 无效时，分类器降级为 `None`，跳过分类并记录 warning。

### API 契约

#### `POST /sync/activitywatch`（增量同步）

```
Request: SyncRequest { auto_classify: bool = True }
Response: SyncResponse {
    status: "success" | "failed" | "partial"
    synced_events: int
    new_apps_classified: int
    duration: float          # 秒
    message: str | None
}
```

前置校验：`auto_classify=True` 时先调用 `test_connect()` 检测 LLM，失败直接返回 `status="failed"`。

#### `POST /sync/activitywatch/timerange`（时间范围同步）

```
Request: SyncTimeRangeRequest {
    start_time: str          # 格式: YYYY-MM-DD HH:MM:SS
    end_time: str            # 格式: YYYY-MM-DD HH:MM:SS
    auto_classify: bool = True
}
Response: SyncResponse（同上）
```

时间范围同步会覆盖该时间段内已有数据；若 Map Cache 未变化，重新同步后分类结果与原数据一致。

### Map Cache 状态规则

- `state = 1`：启用，参与分类缓存命中
- `state = 0`：禁用，对应分类被禁用时同步禁用；分类重新启用时自动恢复  
- 禁用期间产生的新缓存（归入其他类别）在分类重新启用时会被自动删除，优先级以原有缓存为准

### 应用名称标准化规则（缓存键）

所有 app 名称在缓存索引和事件处理时均统一为：

```
app_name.lower().strip().split('.exe')[0]
```

多用途 title 同样统一为小写。

## Interaction / UX Notes

- **Map Cache 修改 → 同步到日志**：修改缓存后可选择"同步到日志"批量回填历史 `user_app_behavior_log` 记录
- **Data Review 单条修改**：只影响当前记录，不修改 Map Cache；需持久修正须在 Map Cache 修改
- **分类类别禁用交互**：禁用后，该类别的 Map Cache 同步禁用；Goal 绑定该类别时，Goal 不再参与分类流程

## Acceptance Notes

- [ ] 单用途 app 在缓存命中时，`category_id`、`sub_category_id`、`link_to_goal_id` 正确填充
- [ ] 多用途 app 按 `app + title` 组合命中缓存，不同 title 可有不同分类
- [ ] 时长低于阈值的事件不进入 `user_app_behavior_log`
- [ ] 多用途 app 无 title 的事件被过滤，不写入数据库
- [ ] `classify_graph` 模式下，单用途与多用途（短/长）并发执行，长活动先 get_titles 再分类
- [ ] LLM 分类结果写入 Map Cache，后续相同事件直接缓存命中
- [ ] `monitor_type = "lifeprism"` 时使用内置监控；其余使用 ActivityWatch
- [ ] `auto_classify=True` 且 LLM 连接失败时，API 返回 `status="failed"` 不继续同步

## Out of Spec

- 分类类别层级（主/子分类）的 CRUD 规格见 `category` 模块
- Goal 目标管理规格见 `goals` 相关 spec
- Map Cache 管理界面（筛选、删除、批量同步）的 UX 规格
- LLM 服务商配置与 Token 统计规格
- 移动端/穿戴设备数据接入规格
