---
version: 1.0
created_at: 2026-07-13
updated_at: 2026-07-13
last_updated: 初始版本
abstract: Repository 数据访问层编码规则，覆盖 Provider 继承体系、Aggregator 组合模式、统一导出规范、实例化策略、导入纪律、时间处理规则
---

# Repository 模块编码规则

## 触发场景

编写、修改或重构 `lifeprism/repository/` 模块下的代码时必须遵守。

## 1. 三层架构

```
repository/
├── base_providers/       # 基类：LWBaseDataProvider、AWBaseDataProvider
├── providers/            # 单表 Provider，继承 LWBaseDataProvider
├── aggregators/          # 多表聚合层，组合多个 Provider
└── __init__.py           # 统一出口，以 xxx_repository 导出
```

### 1.1 Provider 层（单表数据访问）

- 所有 Provider 必须继承 `LWBaseDataProvider`
- 子类通过类级元数据驱动通用 CRUD：`_TABLE_NAME`、`_PRIMARY_KEY`、`_DATE_FIELD`、`_TIME_FIELD`、`_FILTER_FIELDS`、`_ORDER_FIELDS`、`_SELECT_FIELDS`、`_UPDATE_FIELDS`、`_ON_CONFLICT`
- 通用 CRUD（`_generic_query`、`_generic_insert`、`_generic_update`、`_generic_delete`）由基类提供，子类定义元数据即可获得完整单表增删改查能力
- 子类可在元数据驱动 CRUD 之上添加领域专用方法（如 `get_activity_logs`、`calculate_time_invested` 等）

**参考**：[repository-core-spec#LWBaseDataProvider](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-06-repository-core-spec.md#lwbasedataprovider)

### 1.2 Aggregator 层（多表聚合）

- 只有当表需要跨表 JOIN 或聚合查询时才创建 Aggregator
- Aggregator 内部 **创建新的 Provider 实例**（`ComputerUsageProvider()`），**不允许** import 全局 `LazySingleton` 单例
- Aggregator 通过组合多个 Provider 实现跨表数据聚合

```python
# ✅ 正确：Aggregator 内部创建 Provider 实例
class ComputerUsageAggregator:
    def __init__(self):
        self.computer_usage_provider = ComputerUsageProvider()
        self.category_provider = CategoryProvider()

# ❌ 错误：Aggregator 引入全局单例
from lifeprism.repository.providers import computer_usage_provider
```

**设计理由**：见 [repository-core-spec#Design Rationale](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-06-repository-core-spec.md#design-rationale) — Provider 负责单表 CRUD，Aggregator 负责多表聚合，职责单一。Aggregator 使用自己的 Provider 实例保证隔离性。

### 1.3 统一出口（`repository/__init__.py`）

- 所有对外暴露的数据访问入口统一在 `lifeprism/repository/__init__.py` 导出
- 命名规范：**统一使用 `xxx_repository` 后缀**，无论底层是 Provider 还是 Aggregator
- 使用 `LazySingleton` 包裹，延迟实例化

```python
# ✅ 正确：统一以 xxx_repository 导出
from lifeprism.repository.providers import diary_provider as diary_repository
from lifeprism.repository.aggregators import goal_aggregator as goal_repository

# ❌ 错误：暴露内部层级结构
from lifeprism.repository.providers import diary_provider  # 调用方不应关心是 Provider 还是 Aggregator
```

**设计理由**：避免"有些是聚合有些是 Provider"导致对外命名不规范，降低调用方心智负担。

## 2. 实例化与导入纪律

### 2.1 全局单例

- Provider 和 Aggregator 在 `repository/providers/__init__.py` 或 `repository/aggregators/__init__.py` 中以 `LazySingleton` 创建
- 在 `repository/__init__.py` 以 `xxx_repository` 别名导出
- 调用方通过 `from lifeprism.repository import xxx_repository` 使用

### 2.2 导入纪律

- **外部调用方**（server/services、llm/ 等）只能从 `lifeprism.repository` 导入，**禁止**直接从 `lifeprism.repository.providers` 或 `lifeprism.repository.aggregators` 导入
- **Aggregator 内部**可以直接 import Provider 类（用于创建实例），但不 import 全局单例
- **Provider 之间**不应互相 import（各自独立）

```python
# ✅ 外部调用方
from lifeprism.repository import computer_usage_repository

# ❌ 外部调用方——穿透到内部层级
from lifeprism.repository.providers import computer_usage_provider
from lifeprism.repository.aggregators import computer_usage_aggregator
```

## 4. 修改现有 Provider/Aggregator 时的检查清单

1. **子类元数据完整性**：`_TABLE_NAME` 是否已定义？`_FILTER_FIELDS` 等白名单是否覆盖了新增查询字段？
2. **是否需要 Aggregator**：新功能是单表操作还是跨表？单表 → Provider，跨表 → Aggregator
3. **导出命名**：是否已在 `repository/__init__.py` 以 `xxx_repository` 导出？
4. **导入纪律**：外部调用方是否从 `lifeprism.repository` 导入？Aggregator 内部是否避免了引入全局单例？
5. **时间处理**：涉及 datetime 字段查询时，是否由调用方完成 UTC 转换而不是在 Repository 层？

## 5. 常见反模式

| 反模式 | 正确做法 |
|--------|---------|
| 从 `lifeprism.repository.providers` 直接 import Provider 单例 | 从 `lifeprism.repository` import `xxx_repository` |
| Aggregator 内 import 全局 `LazySingleton` 单例 | Aggregator 内部 `Class()` 创建新实例 |
| 在 Provider 层接受 `date` 参数并内部转 UTC | 要求调用方传 UTC `start_time`/`end_time` |
| 在非专用 Provider 中直接写 `FROM other_table` SQL | 使用对应表的 Provider 或 Aggregator |
| Provider 之间互相调用 | Provider 保持独立，跨表逻辑放在 Aggregator |

## 6. 相关文档

- 核心规格：[`docs/specs/2026-07-06-repository-core-spec.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-06-repository-core-spec.md)
- 数据访问流：[`docs/flows/2026-07-06-repository-data-access-flow.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/flows/2026-07-06-repository-data-access-flow.md)
- 时间处理规则：[`docs/coding-rules/time-handling-rules.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/coding-rules/time-handling-rules.md)
- 已知限制：[`docs/known-limitations/time-format-iso-vs-space-in-db-queries.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/known-limitations/time-format-iso-vs-space-in-db-queries.md)
