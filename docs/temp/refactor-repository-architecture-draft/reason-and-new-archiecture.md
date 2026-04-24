# 1. 当前现状

### 1.1 架构问题

**问题描述**：
- Provider分散在`server/providers/`和`llm/providers/dataset_providers/`两个位置
- 当多个模块（server、llm）需要访问相同的数据库表时，存在代码重复
- 表结构变更时需要在多个位置同步修改，维护成本高
- Provider的物理位置与逻辑职责不匹配（数据访问层却放在业务模块中）

**当前目录结构**：
```
lifeprism/
├── config/
│   └── database.py              # 表结构定义
├── storage/
│   ├── database_manager.py      # 数据库连接管理
│   ├── base_providers/
│   │   └── lw_base_data_provider.py  # 基类
│   └── migrations/              # 数据库迁移
├── server/
│   ├── providers/               # ❌ 20+ provider类（应该在storage）
│   │   ├── goal_provider.py
│   │   ├── todo_provider.py
│   │   └── ...
│   ├── services/                # 业务逻辑层
│   └── schemas/                 # API schemas (Pydantic)
└── llm/
    └── providers/
        └── dataset_providers/   # ❌ 重复的数据访问代码
            └── llm_dataset_provider.py
```


## 2. 新架构设计

### 2.1 目标架构

**三层数据访问模式**：Provider（原子操作）→ Aggregator（数据聚合）→ Service（业务逻辑）

```
lifeprism/
├── config/
│   ├── settings_manager.py      # 用户设置（保持不变）
│   └── providers.yaml            # LLM提供商配置（保持不变）
│
├── storage/                      # 🎯 数据存储层（核心重构区域）
│   ├── schemas.py                # ✅ 表结构定义（从config/database.py迁移）
│   ├── database_manager.py       # 数据库连接管理（保持不变）
│   │
│   ├── providers/                # ✅ 所有provider集中在这里
│   │   ├── __init__.py
│   │   ├── todo_provider.py
│   │   ├── goal_provider.py
│   │   ├── diary_provider.py
│   │   ├── activity_provider.py
│   │   ├── habit_provider.py
│   │   └── ...（所有数据访问provider）
│   │
│   ├── aggregators/              # 🆕 数据聚合层
│   │   ├── __init__.py
│   │   ├── activity_aggregator.py
│   │   ├── todo_aggregator.py
│   │   ├── goal_aggregator.py
│   │   └── ...
│   │
│   └── migrations/               # 数据库迁移（保持不变）
│       └── scripts/
│
├── server/                       # 业务模块
│   ├── services/                 # 业务逻辑层（调用provider和aggregator）
│   ├── api/                      # API路由（保持不变）
│   └── schemas/                  # API schemas（保持不变，不移动）
│
└── llm/                          # LLM模块
    ├── services/                 # 🆕 LLM业务逻辑（直接使用storage.providers）
    └── ...                       # 删除llm/providers/dataset_providers/
```

### 2.2 三层职责划分

| 层级 | 位置 | 职责 | 示例 |
|------|------|------|------|
| **Provider** | `storage/providers/` | 原子的数据库操作，通用、可复用 | `query_todos(filters, sort, page)` |
| **Aggregator** | `storage/aggregators/` | 组合多个provider调用，数据聚合计算 | `aggregate_daily_stats()` 调用多个provider |
| **Service** | `server/services/` 或 `llm/services/` | 业务逻辑、事务协调、外部调用 | `complete_todo()` 更新数据库 + 发送通知 |
