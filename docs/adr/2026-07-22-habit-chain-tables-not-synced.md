---
version: 1.0
created_at: 2026-07-22
updated_at: 2026-07-22
last_updated: 2026-07-22
abstract: habit_chains 和 habit_chain_nodes 因 chain_id 外键引用自增 id 导致同步后断裂，从 SYNC_TABLES 移除，待云端 agent 需求驱动时恢复
status: decided
---

# habit 链条表从 SYNC_TABLES 移除

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

`habit_chain_nodes.chain_id` 引用 `habit_chains.id`（自增 id）。两端自增 id 不同，同步后 B 端的 chain_id 会指向错误链条。这是既有问题（PRD 1 之前就存在），但删除同步未实现前用户未感知。

### 讨论范围

- `habit_chains` 和 `habit_chain_nodes` 两张表
- `SYNC_TABLES` 常量定义
- `chain_id` 外键引用关系
- 已知限制文档（`docs/known-limitations/`）

### 非讨论范围

- `chain_id` 字段类型改造（属于 PRD 2 代码适配范围）
- 其他 4 张 AUTOINCREMENT 表的同步行为
- Provider 子类的改造

### 模糊信息的明确定义

- "外键断裂"：同步后 B 端 `habit_chains.id` 与 A 端不同，`habit_chain_nodes.chain_id` 指向错误的链条记录
- "服务器网页浏览"：未来云端部署的 web 界面查看 habit 链条数据

### 问题深度

涉及数据一致性边界——在"chain_id 外键问题未解决"的前提下，是否允许这两张表参与同步。这关系到 PRD 1 完成后用户可见的数据一致性预期。

## 现状

- `habit_chain_nodes.chain_id` 引用 `habit_chains.id`（[database.py#L1325](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/config/database.py#L1325)）
- 两表都在 `SYNC_TABLES`（[constants.py#L31-L33](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/constants.py#L31)）
- 当前 `upsert_rows` 已对 AUTOINCREMENT 表剥离 id（[sync_repository.py#L515-L516](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/sync_repository.py#L515)），同步后 chain_id 就会错位
- 当前云端 agent 实际上没有使用 habit 链条数据的需求

## 决策前提

- 前提 1：`habit_chain_nodes.chain_id` 引用 `habit_chains.id`（自增 id），同步后两端 id 不一致导致外键断裂
- 前提 2：当前云端 agent 实际上没有使用 habit 链条数据的需求，不同步也能接受
- 前提 3：`chain_id` 改引用 `hash_id` 属于 PRD 2 代码适配范围，不在 PRD 1 schema 变更范围内

## 可选方案

### 方案 A：临时从 SYNC_TABLES 移除

PRD 1 后从 `SYNC_TABLES` 移除这两张表，但仍加 `hash_id` 字段并回填。

**优势**

- 改动最小，避免同步后链条错乱
- 仍为未来恢复同步做准备（hash_id 字段已加）
- 符合"修改不能影响正常运行"原则

**劣势**

- 习惯链条不参与同步，跨端无法访问
- 需要写已知限制文档说明

### 方案 B：保留同步，文档化已知限制

保留在 `SYNC_TABLES` 中，记录外键断裂问题。

**优势**

- 零改动
- 习惯链条仍参与同步（虽然可能错乱）

**劣势**

- 同步后可能链条错乱，用户可见 bug
- 不符合"修改不能影响正常运行"原则

### 方案 C：在 PRD 1 中直接改 chain_id 引用 hash_id

schema 改 `chain_id TEXT`，所有使用 chain_id 的代码适配。

**优势**

- 彻底解决外键问题

**劣势**

- 改动面跨 PRD 2（Provider/API/Service 类型注解）
- 不符合 PRD 1 只做 schema 变更的范围

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 前提 1 + 前提 2 + 前提 3 成立 | 方案 A | 当前选择 |
| 云端 agent 需要 habit 链条数据 + 需要服务器网页浏览 | 方案 C | 备选触发条件 |

## 最终决策

当前成立的前提：前提 1、2、3 均成立。

因此选择 `方案 A：临时从 SYNC_TABLES 移除`。

前提失效时的切换路径：当云端 agent 需要 habit 链条数据 + 需要通过服务器网页浏览时，恢复同步。恢复同步前**必须先解决 chain_id 外键问题**（chain_id 改引用 hash_id），属于 PRD 2 代码适配范围。

## 决策原因

- 原因 1：方案 B 会留下用户可见 bug（链条错乱），不符合"修改不能影响正常运行"原则
- 原因 2：方案 C 改动面跨 PRD 2，不符合 PRD 1 只做 schema 变更的范围
- 原因 3：当前云端 agent 无 habit 链条数据需求，不同步也能接受（前提 2），方案 A 改动最小

## 后续影响

- PRD 1 范围：`SYNC_TABLES` 中注释掉 `habit_chains` 和 `habit_chain_nodes`，标注 `# TODO PRD 3: 恢复同步前需解决 chain_id 外键映射问题`
- PRD 1 范围：`HASH_ID_PREFIXES` 仍包含这两张表（hash_id 字段照加，迁移脚本仍回填）
- 文档影响：需写已知限制文档 `docs/known-limitations/habit-chain-tables-not-synced.md`
- PRD 2/3 范围：`chain_id` 字段类型从 INTEGER 改为 TEXT，引用 `habit_chains.hash_id`；适配 `habit_chain_providers.py` 中所有 `chain_id: int` → `chain_id: str`；适配 JOIN；恢复 `SYNC_TABLES` 中的两张表
- 需要后续验证：恢复同步前必须确认 chain_id 外键问题已解决
