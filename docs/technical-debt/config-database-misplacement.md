---
version: 1.0
created_at: 2026-07-06
updated_at: 2026-07-06
last_updated: 记录 database.py 错放于 config 模块的技术债
abstract: config/database.py 定义了 38 张表的元数据（~55KB），逻辑上应属于 repository 模块，因迁移风险暂放 config。
---

# database.py 错放于 config 模块

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建技术债文档 |

## 问题描述

`lifeprism/config/database.py`（~55KB）定义了整个系统 **38 张数据库表**的完整元数据（字段、约束、索引、注释），但它被放置在 `config` 模块中，而非其逻辑归属地 `repository` 模块。

## 当前状态

### 文件内容

| 项目 | 详情 |
|------|------|
| 文件路径 | `lifeprism/config/database.py` |
| 文件大小 | ~55KB |
| 表数量 | 38 张 |
| 内容性质 | 数据库表结构元数据定义（纯数据，无逻辑） |

### 定义的表（38张）

`multi_purpose_map_cache`, `single_purpose_map_cache`, `category_map_cache`, `user_app_behavior_log`, `category`, `sub_category`, `tokens_usage_log`, `todo_list`, `daily_focus`, `weekly_focus`, `goal`, `goal_journal`, `plan_doc`, `chat_session`, `timeline_custom_block`, `goal_stats`, `daily_report`, `weekly_report`, `monthly_report`, `time_paradoxes`, `diary`, `mood_types`, `mood_entries`, `mood_impacts`, `user_values`, `commitments`, `schema_version`, `habits`, `habit_challenges`, `habit_checkins`, `habit_chains`, `habit_chain_nodes`, `screen_captures`, `window_events`, `raw_behavior_analysis`, `behavior_analysis`, ...

### 当前引用方（4 处）

- `lifeprism/repository/database_manager.py`
- `lifeprism/repository/lw_table_manager.py`
- `lifeprism/repository/base_providers/lw_base_data_provider.py`
- `lifeprism/processors/data_clean.py`

## 应该在哪里

`database.py` 逻辑上属于 **`lifeprism/repository/`** 模块，因为：
1. 它定义的是数据库层的基础元数据
2. 所有引用方都在 repository / data 层
3. config 模块的职责是"配置管理"，不应承载数据库 schema 定义

## 为什么暂不迁移

| 风险 | 说明 |
|------|------|
| **引用分散** | 4 个文件通过 `from lifeprism.config import database` 或类似路径引用 |
| **import 路径变更** | 移动到 repository 后所有 import 需要同步修改 |
| **潜在循环依赖** | config 和 repository 之间已有复杂的 import 关系，移动可能触发循环引用 |
| **收益有限** | 从功能角度看，文件放在 config 或 repository 不影响运行正确性 |

## 清理计划

| 阶段 | 内容 | 条件 |
|------|------|------|
| **短期** | 维持现状，不影响新功能开发 | — |
| **中期** | 当 repository 模块进行较大重构时，同步迁移 database.py | 需要 repository 模块有较大改动 |
| **长期** | 如果 config 模块进一步膨胀（如超过 5 个核心文件），优先处理 | config 模块文件数 > 5 |

## 影响评估

- **功能影响**：无。文件位置不影响运行时行为
- **认知负担**：低。新开发者可能疑惑为什么数据库定义在 config 中，但不会导致 bug
- **维护成本**：低。该文件变更频率极低（表结构稳定后基本不改）
