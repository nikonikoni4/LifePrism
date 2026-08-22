---
version: 1.0
created_at: 2026-08-19
updated_at: 2026-08-19
last_updated: 创建文档，登记 llm/agent/tools/habit_tool.py 反向依赖 server.services 的耦合及修复方向
abstract: LLM 工具层反向依赖 server.services.habit_service，破坏单向依赖原则；修复方向是将 Service 从 server 中剥离，形成可同时被 LLM 和 HTTP API 消费的独立层。
---

# LLM 工具层反向依赖 server.services 的耦合

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档，登记 habit_tool.py 反向依赖及 Application/Service 解耦修复方向 |

## 问题描述

### 当前耦合点

`lifeprism/llm/agent/tools/habit_tool.py` 反向依赖 `lifeprism/server/`，破坏架构文档定义的 `utils → config → repository → monitor → processors → server` 与 `llm` 之间的单向依赖原则。

**反向依赖具体位置**：

| 文件 | 行号 | 依赖目标 | 性质 |
|------|------|---------|------|
| `lifeprism/llm/agent/tools/habit_tool.py` | 15-21 | `lifeprism.server.schemas.habit_schemas`（5 个 Pydantic 模型） | schema 反向依赖 |
| `lifeprism/llm/agent/tools/habit_tool.py` | 29-37 | `lifeprism.server.services.habit_service.habit_service`（单例） | service 反向依赖 |

**循环依赖物证**：

`habit_tool.py` 中的 `_get_habit_service()` 函数采用**函数体内延迟导入**规避循环导入，其注释自证：

> `lifeprism/server/services/__init__.py -> schedule_service -> lifeprism.llm（agent loop）`，若在本模块顶层导入 habit_service 会循环导入，必须在函数体内延迟导入。

延迟导入只是掩盖了"依赖图存在环"的事实，没有改变拓扑错误。

### 离群点特征

整个 `lifeprism/llm/` 目录下，`habit_tool.py` 是**唯一**直接 import `lifeprism.server` 的文件。同目录其他 LifePrism 业务工具均走 repository 层：

- `lifeprism/llm/agent/tools/lifeprismsystem.py`：直连 `lifeprism.repository` 的多个 repository
- `lifeprism/llm/agent/tools/custom_records_tool.py`：直连 `custom_record_repository`，注释明确"不经过 service（遵循现有架构，避免循环引用）"

这说明项目内部已有统一约定，habit_tool.py 是例外。

## 当前影响

| 维度 | 影响 |
|------|------|
| **架构原则** | 违反依赖倒置（DIP）、无环依赖（ADP）、稳定依赖（SDP）三大原则 |
| **静态分析** | 循环依赖通过延迟导入掩盖，IDE / mypy / import linter 无法在编译期发现 |
| **稳定性** | `server` 是易变层（HTTP 路由、API schema 经常调整），`llm` 依赖它导致 llm 稳定性被 server 拖累 |
| **扩展性** | 后续若新增 LLM 工具需要复用 server.service 业务规则（用户已预判不止 habit 一处），会被迫沿用此反模式 |
| **共同复用** | `habit_tool.py` 仅使用 5 个 schema 子集，却引入整个 `habit_schemas` 模块；schema 本是数据契约，不该是 server 专属资产 |

## 根因分析

`HabitService` 当前形态包含两类职责的混合：

1. **核心业务规则**（挑战结算、Streak 计算、补签窗口判定、等级推进）——无状态领域逻辑
2. **HTTP 编排**（FastAPI 调用入口、与 router 的契约）——应用层编排

这两类职责被放在 `lifeprism/server/services/habit_service.py` 同一个类中。当 LLM 工具需要复用核心业务规则时，被迫引入整个 server 模块，触发循环依赖。

## 优化方案

**核心思路**：将 Service 从 server 中剥离，形成独立层，使 Service 可同时服务于 LLM 和 HTTP Application。

### 目标分层

```
repository
    ↑
application / service 层  ← 业务规则 + schema + 无状态应用服务
    ↑               ↑
server.services    llm.agent.tools   ← 各自做自己的编排
(HTTP/路由编排)    (LLM tool 编排)
```

### 推荐实施顺序（按代价由低到高）

**方案 A：schema 共享先行**（低成本，独立可做）

- 把 `lifeprism/server/schemas/habit_schemas.py` 中 LLM 与 HTTP 共用的 Pydantic 模型抽到共享位置（如 `lifeprism/schemas/habit_schemas.py` 或领域模块下）
- `server/schemas/habit_schemas.py` 退化为仅保留 HTTP 专属的 Request/Response 包装
- 风险：纯数据契约迁移，不涉及业务逻辑，最低风险
- 收益：立即消除 `habit_tool.py` 中 schema 的反向依赖

**方案 B：抽应用服务层**（中等成本，需测试覆盖）

- 把 `HabitService` 中无状态业务逻辑（挑战结算、Streak 计算、补签判定）拆到 `lifeprism/application/habit_service.py` 或 `lifeprism/domain/habit/`
- `server/services/habit_service.py` 退化为薄薄的 HTTP 编排壳，依赖 application 层
- `llm/agent/tools/habit_tool.py` 改为依赖 application 层，不再反向依赖 server
- 风险：涉及 `HabitService` 单例状态（`_habit_name_map` 缓存）的迁移，需保证现有调用方行为不变
- 收益：彻底消除循环依赖，为后续 LLM 工具复用业务规则扫清障碍

**方案 C：完整领域模块**（高成本，长期演进）

- 业务模块（habit/goal/mood…）各自成域：repository + domain + schema 聚合
- server 和 llm 都从域内取用
- 风险：大范围结构迁移，需配合 ADR
- 收益：最彻底的领域驱动设计落地

### 触发条件

**立即触发**（满足任一即应启动方案 B）：

- 出现第二个 LLM 工具需要复用 server.service 业务规则（用户已预判会来）
- `HabitService` 因新增业务规则进一步膨胀，与 HTTP 编排耦合加剧

**择机触发**（方案 A 可独立做，无强触发条件）：

- 任何涉及 habit_schemas 位置变更的任务

## 相关代码文件

- `lifeprism/llm/agent/tools/habit_tool.py` — 反向依赖发起方
- `lifeprism/server/services/habit_service.py` — 业务规则与 HTTP 编排混合载体
- `lifeprism/server/schemas/habit_schemas.py` — 被 LLM 工具反向依赖的 schema
- `lifeprism/llm/agent/tools/lifeprismsystem.py` — 对照样本，正确走 repository 层
- `lifeprism/llm/agent/tools/custom_records_tool.py` — 对照样本，注释明确"不经过 service"

## 相关文档

- [ARCHITECTURE.md - 关键依赖方向](../ARCHITECTURE.md#关键依赖方向) — 单向依赖原则的权威定义
- [llm-agent-spec - 习惯打卡工具](../specs/2026-07-06-llm-agent-spec.md) — habit_tool 工具契约
- [habit-system spec](../specs/2026-04-15-habit-system.md) — 习惯系统业务规则

## 约束

- 重构不得影响 `HabitService` 对外行为，需有测试覆盖保护
- 遵循 `docs/coding-rules/repository-module-rules.md` 中"repository 只 CRUD，业务逻辑属上层"的分层原则
- 遵循用户偏好：单一类管理所有生命周期、清晰分层、Service 同时服务于模型和 Application
