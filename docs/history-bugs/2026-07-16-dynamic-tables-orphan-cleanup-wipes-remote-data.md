# 动态表同步孤儿表清理导致云端数据丢失 — 错误假设本地为 SSOT

## 元信息

- **发生时间**: 2026-07-16（在方案 B 双向同步首次集成测试中发现）
- **发现时间**: 2026-07-16
- **修复状态**: ✅ 已修复（移除孤儿表清理逻辑，commit `39b2b5f5`）
- **影响范围**: 双向动态表同步 — 云端自己创建的动态表被误删，数据丢失
- **bug 类型**: 逻辑设计缺陷 — 清理逻辑错误假设本地是唯一数据源（SSOT）
- **严重程度**: 严重（P1）— 导致云端动态表数据被 DROP TABLE 物理删除，不可自动恢复

## 触发规则

在以下场景时阅读此文档：
- 排查"云端动态表不见了 / 云端数据被删除了"问题
- 看到日志 `重建动态表: 删除孤儿表 custom_xxx`
- 修改 `rebuild_dynamic_tables` 的建表 / 删表逻辑
- 讨论双向同步中"谁的数据是权威来源（SSOT）"的设计假设
- 设计同步系统中的删除传播机制（tombstone / 软删除）

## Bug 简述

`SyncRepository.rebuild_dynamic_tables()` 在云端执行时，第 2 步会扫描云端所有 `custom_*` 数据表，与本地发送的 type slug 列表做对比。任何云端存在但不在本地 types 列表中的表，都被当作"孤儿表"执行 `DROP TABLE` 物理删除。

这个"清理孤儿表"的逻辑隐含了一个错误假设：**本地动态表定义是 SSOT（唯一权威来源）**。但在双向同步的"方案 B"设计中，两端都可以独立创建动态表——当本地发送 `{exercise_log}` 给云端建表时，云端自己创建的 `reading_log` 完全合法，不应被删除。

## 复现场景

1. 准备测试环境：
   - 本地数据库：有 `exercise_log` 动态表（2 条数据）
   - 云端数据库：有 `reading_log` 动态表（2 条数据）
2. 本地启动 `sync_once`，拉取云端定义 `{"types": [{"slug": "reading_log", ...}]}`
3. 本地对比发现云端有 reading_log → 本地建表 `custom_reading_log`
4. 本地对比发现 exercise_log 不在云端 → 发送重建请求 `{types: [{slug: "exercise_log", ...}]}`
5. 云端 `rebuild_dynamic_tables` 执行：
   - 步骤 1：CREATE TABLE `custom_exercise_log`（正确）
   - 步骤 2：扫描云端所有 `custom_*` 表 → 发现 `custom_reading_log`
   - 步骤 2：`custom_reading_log` 不在本地 types 列表 `{exercise_log}` 中 → DROP TABLE `custom_reading_log`（**错误！**）
6. 结果：云端 `reading_log` 表及 2 条数据被物理删除

## 根因分析

### 问题代码位置

`lifeprism/repository/sync_repository.py` 中 `rebuild_dynamic_tables()` 方法的第 2 步（已删除）：

```python
# 步骤 2: 清理云端有但本地已删除的 type → DROP TABLE
local_slugs = {t["slug"] for t in types}
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'custom_%'")
existing_tables = {row[0] for row in cursor.fetchall()}
for data_table in existing_tables:
    slug = data_table.replace("custom_", "", 1)
    if slug not in local_slugs:
        cursor.execute(f"DROP TABLE IF EXISTS {data_table}")
        logger.info("重建动态表: 删除孤儿表 %s", data_table)
```

### 设计假设错误

这段代码的逻辑是：发送给云端的 types 列表代表了"完整的、应该存在的动态表集合"，任何不在这个集合中的云端 `custom_*` 表都是"需要清理的孤儿"。

这个假设在**单向同步**（本地→云端，本地是 SSOT）场景下成立，但在**双向同步**（两端都可以独立创建动态表）场景下不成立。方案 B 的设计明确支持双向建表，因此这个假设是错误的。

### 为什么之前没暴露

在方案 B 之前，快照对比（条件 A）+ 永真兜底（条件 B）每次都触发全量发送，但因为两端动态表完全相同（通过单向同步早已同步好），孤儿表列表总是空的，所以未暴露。方案 B 引入了 slug 集合对比后，两端发送只包含自己独有的 types，孤儿表清理逻辑立刻触发。

## 修复方案

**直接删除孤儿表清理逻辑**，不做任何替代。

理由：
- 清理孤儿表的语义本质是"删除同步"——将本地的删除操作传播到云端
- 删除同步需要**独立的 tombstone 机制**（记录"某 type 已被删除"的事实），不能由建表逻辑隐式推断
- 当前架构不支持删除同步（见 bug `2026-07-16-database-delete-not-synced.md`），孤儿表清理是错误的前置实现
- 云端独有的动态表是合法数据，没有任何理由被删除

修复提交：`39b2b5f5`

## 设计教训

- **不要在建表逻辑中嵌入删除语义**：建表（CREATE）和删表（DROP）是两个独立操作，需要独立的数据源和触发条件。建表逻辑"顺便"清理孤儿表是职责越界
- **SSOT 假设必须显式验证**：假设某端是唯一权威来源时，必须有显式的理由（如单向同步模式、主从架构），不能仅靠"本地发送了全量列表"就推断"不在列表中的应该删除"。在双向同步中，两端发送的都是"差异"而非"全量清单"
- **删除操作需要 tombstone**：任何会导致对端数据删除的操作，都需要一个独立、持久化的"删除记录"作为依据。不能通过"不在某个列表里"来隐式推断需要删除——这等于用缺失信息做决策，极易误判
- **DROP TABLE 是高风险操作**：物理删除不可逆，应极其谨慎。如果一定要做孤儿清理，至少应该先重命名（RENAME TO）做逻辑删除，确认无误后再手动清理
