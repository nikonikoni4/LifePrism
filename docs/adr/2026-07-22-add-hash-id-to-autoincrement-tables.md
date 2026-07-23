---
version: 1.0
created_at: 2026-07-22
updated_at: 2026-07-22
last_updated: 2026-07-22
abstract: 为实现删除同步功能，6 张 AUTOINCREMENT 表新增 hash_id 字段作为跨端稳定标识，采用 ALTER TABLE + 回填 + CREATE UNIQUE INDEX 迁移方法
status: decided
---

# 为 AUTOINCREMENT 表新增 hash_id 字段

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

删除操作无法跨端同步——A 设备删除后，B 设备 pull 时云端又拉回来。删除同步需要墓碑表模式（Tombstone Pattern），而墓碑机制需要被删记录有跨端稳定标识。6 张 AUTOINCREMENT 表的自增 id 在两端不同，无法作为跨端标识。

### 讨论范围

- 6 张 AUTOINCREMENT 表（`timeline_custom_block`、`time_paradoxes`、`mood_impacts`、`habit_chains`、`habit_chain_nodes`、`user_app_behavior_log`）
- hash_id 字段的 schema 定义、迁移方法、生成逻辑
- `HASH_ID_PREFIXES` 常量定义
- 墓碑表模式的依赖关系

### 非讨论范围

- hash_id 是否作为主键（见 [2026-07-22-hash-id-sync-only-identifier.md](./2026-07-22-hash-id-sync-only-identifier.md)）
- `chain_id` 外键改造（见 [2026-07-22-habit-chain-tables-not-synced.md](./2026-07-22-habit-chain-tables-not-synced.md)）
- 墓碑表的具体实现（PRD 3 范围）

### 模糊信息的明确定义

- "跨端稳定标识"：在多端数据库中保持一致的字符串标识，不随自增 id 变化
- "墓碑表模式"：删除操作不真正删除记录，而是写入一条删除日志（墓碑），对端拉取墓碑后执行删除

### 问题深度

涉及架构原则——为支持删除同步引入新的标识字段，这是 PRD 1（schema 变更）的根本决策，决定了后续 PRD 2（代码适配）和 PRD 3（墓碑集成）的可行性。

## 现状

- 6 张 AUTOINCREMENT 表的自增 id 在两端不同
- TEXT 主键表已具备跨端稳定标识（主键本身即跨端一致）
- 项目已采用 LWW 冲突解决策略（见 [2026-07-09-lww-conflict-resolution.md](./2026-07-09-lww-conflict-resolution.md)）
- SQLite 的 `ALTER TABLE ADD COLUMN` 不支持直接添加有 UNIQUE 约束的 NOT NULL 列
- 现有 m012 迁移脚本采用 ALTER + 回填 + INDEX 方式（[m012_add_updated_at_to_sync_tables.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/migrations/scripts/m012_add_updated_at_to_sync_tables.py)）

## 决策前提

- 前提 1：删除操作无法跨端同步——A 设备删除后，B 设备 pull 时云端又拉回来
- 前提 2：删除同步需要墓碑表模式，墓碑机制需要被删记录有跨端稳定标识
- 前提 3：6 张 AUTOINCREMENT 表的自增 id 在两端不同，无法作为跨端标识
- 前提 4：项目已采用 LWW 冲突解决策略，墓碑模式与之契合
- 前提 5：SQLite ALTER TABLE ADD COLUMN 不支持直接加 UNIQUE 约束的 NOT NULL 列

## 可选方案

### 方案 A：为 AUTOINCREMENT 表新增 hash_id 字段

为 6 张表新增 `hash_id TEXT NOT NULL UNIQUE` 字段，作为跨端稳定标识。

**迁移方法**：ALTER TABLE ADD COLUMN（允许 NULL）→ 回填 → CREATE UNIQUE INDEX（部分索引，NULL 不参与唯一性检查）

**优势**

- 与 LWW 冲突解决策略契合
- 改动面收敛在 schema 变更，PRD 1 范围清晰
- 迁移方法不丢数据，符合"修改不能影响正常运行"原则
- 与现有 m012 迁移脚本风格一致

**劣势**

- schema 新旧库差异（新库用 column UNIQUE，旧库用 UNIQUE INDEX）
- 需要维护 `HASH_ID_PREFIXES` 前缀字典

### 方案 B：删表重建

删除当前表 → 重建带 hash_id 字段的表 → 写入数据。

**优势**

- 新旧库 schema 完全一致
- 实现简单直接

**劣势**

- 需备份，有数据丢失风险
- 与现有 m012 迁移脚本风格不一致
- 不符合"修改不能影响正常运行"原则

### 方案 C：CRDT 或版本号字段

引入 CRDT 或版本号字段作为跨端标识。

**优势**

- 理论上更完备

**劣势**

- 与现有 LWW 冲突解决策略不契合
- 改动面大，不符合 PRD 1 范围

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 前提 1 + 前提 2 + 前提 3 + 前提 4 + 前提 5 成立 | 方案 A | 当前选择 |
| 未来转向多客户端并发场景，LWW + 墓碑模式不足 | 方案 C | 备选触发条件 |

## 演进历史

| 版本 | 方案 | 解决的问题 | 引入的新问题 |
| ---- | ---- | ---------- | ------------ |
| v1 | 删表重建 | 实现 hash_id 字段 | 数据丢失风险，与 m012 风格不一致 |
| v2 | ALTER + 回填 + CREATE UNIQUE INDEX | 不丢数据，与 m012 一致 | 新旧库 schema 差异 |

## 最终决策

当前成立的前提：前提 1、2、3、4、5 均成立。

因此选择 `方案 A：为 AUTOINCREMENT 表新增 hash_id 字段`，迁移方法采用 `ALTER TABLE ADD COLUMN + 回填 + CREATE UNIQUE INDEX`。

前提失效时的切换路径：当未来转向多客户端并发场景，LWW + 墓碑模式不足时，考虑 CRDT 或版本号字段（方案 C）。

## 决策原因

- 原因 1：方案 A 与现有 LWW 冲突解决策略契合，墓碑模式是 LWW 的自然延伸
- 原因 2：用户初始倾向删表重建（方案 B）是因为简单且对 SQLite ALTER TABLE 限制不了解，经评估 ALTER + 回填 + CREATE UNIQUE INDEX 方式不丢数据且与 m012 一致，更优
- 原因 3：方案 C 改动面大，不符合 PRD 1 范围，且与现有架构不契合

## 后续影响

- PRD 1 范围：
  - 6 张表 schema 新增 `hash_id TEXT NOT NULL UNIQUE` 字段
  - `time_paradoxes` 表 id 改为 `INTEGER PRIMARY KEY AUTOINCREMENT`（未投入使用，无需向后兼容）
  - `HASH_ID_PREFIXES` 常量定义 6 张表的前缀
  - 迁移脚本采用 ALTER + 回填 + CREATE UNIQUE INDEX 方法
- PRD 2 范围：Provider 子类无需改造（_PRIMARY_KEY 不变，见 [2026-07-22-hash-id-sync-only-identifier.md](./2026-07-22-hash-id-sync-only-identifier.md)）
- PRD 3 范围：墓碑表 record_id 字段存 hash_id，对端按 hash_id 删除
- 文档影响：`data-sync-core-spec.md` 同步表数量从 31 张变 30 张（移除 2 张 habit 表 + 新增 1 张 `deletion_log` 墓碑表：31 - 2 + 1 = 30）
- 需要后续验证：迁移脚本的幂等性、回填 hash_id 的唯一性
