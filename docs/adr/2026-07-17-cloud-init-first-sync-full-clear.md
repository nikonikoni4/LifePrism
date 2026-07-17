---
version: 1.0
created_at: 2026-07-17
updated_at: 2026-07-17
last_updated: 2026-07-17
abstract: 云端跳过种子数据初始化，首次同步由本地全量覆盖云端（清空 + 推送），替代原"黑名单双向过滤 + 本地全量推送"方案。否决 mood_impacts 自增键改造和数据库同步黑名单。
status: decided
---

# 云端初始化与首次同步策略：全清覆盖替代黑名单过滤

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

`data_initializer.py` 在启动时检查表为空则写入种子数据（4 个分类、4 个子分类、7 种心情、18 个影响因素、2 个示例目标等），这些表全部在同步范围内（SYNC_TABLES）。云端和本地各自独立初始化相同种子数据，同步时互相传播，导致数据重复。分类表影响尤其严重——涉及自动分类管线。

### 讨论范围

- 云端种子数据初始化策略（跳过 vs 保留）
- 首次同步策略（黑名单过滤 vs 全清覆盖）
- 同步数据一致性的保证方式
- 动态表在首次同步中的处理方式

### 非讨论范围

- mood_impacts 表的自增键改造（INTEGER → TEXT PK）。已判定为无功能影响的技术债，不处理。
- 数据库同步黑名单（SEED_DATA_BLACKLIST）实现。已否决，不实现。
- 多客户端并发首次同步的锁机制。当前前提（单客户端）下不处理。
- 云端孤儿动态表的清理。不影响功能，不处理。

### 问题深度

同步系统启动阶段的基础策略选择，涉及数据一致性、同步流程架构和可维护性。否决已部分实施的 Phase 1 方案（黑名单），转向更彻底的首次同步覆盖方案表明这是一个"方向性"决策，而非局部优化。

## 现状

1. **种子数据初始化**：`data_initializer.initialize_default_data()` 在 `init_database_full()` 中调用，写入 6 张种子数据表（category、sub_category、goal、plan_doc、mood_types、mood_impacts）。
2. **同步范围**：这 6 张表全部在 SYNC_TABLES 中。
3. **当前同步流程**：sync_once 执行动态表对比 → Pull（增量拉取）→ Push（增量推送）→ 文件同步。
4. **初始方案**：分两阶段——Phase 1 建数据库同步黑名单过滤种子数据（需将 mood_impacts 自增键改造为 TEXT PK），Phase 2 云端跳过初始化 + 首次同步全量推送。
5. **已实施部分**：mood_impacts 表配置已改为 TEXT PK，MoodImpactProvider 已适配。

## 决策前提

- **前提 1**：mood_impacts 表的 AUTOINCREMENT PRIMARY KEY 不影响同步。无其他表通过外键引用 mood_impacts.id；mood_entries.factors 存储的是 name 字符串（JSON 数组形式），不是 ID。字段排序由 sort_order 控制，不依赖自增 ID 语义。
- **前提 2**：黑名单只能过滤种子数据（已知固定 ID 的记录），无法处理用户本地特有的数据或云端在首次同步前 agent 产生的数据。黑名单是"局部治标"，无法保证整体数据一致性。
- **前提 3**：云端仅在 agent_only 模式下运行，无网页端查看和修改数据的能力。此前提当前成立；若未来加入网页端，当前所有同步策略整体失效，需重新评估。
- **前提 4**：首次同步永远是 本地→云端 单向全量推送。前提 3 自然保证此前提。
- **前提 5**：动态表的入口只有定义表（custom_record_types/custom_record_fields）。云端存在的孤儿表（custom_* 表存在但 custom_record_types 无对应记录）不会被加入同步表列表（sync_tables 由定义表 slug 拼接生成），也不被前端/Agent 使用。孤儿表不影响功能。
- **前提 6**：云端 config/ 目录（用于存放初始化标志文件）在源码运行模式下由文件系统天然保证持久化。
- **前提 7**：首次同步非原子 —— full-clear 后推送失败，云端处于"半空"状态。恢复策略：幂等重试（不设置标志位，下次重试 full-clear + 推送）。
- **前提 8**：Agent Only 模式只有在首次同步之后才能正常使用。此前提是主备模式的直接推导——本地是数据生产端（主），云端是数据消费端（备），云端在首次同步前不应处理任何用户数据。因此云端跳过所有初始化（包括种子数据和资源模板文件）是安全的，空白的 Agent 聊天文件、prompts 等均由首次同步覆盖或在首次使用时由 PromptLoader 懒加载。

## 可选方案

### 方案 A：两阶段方案（黑名单 + 本地全量推送）

**阶段 1**：所有初始化数据表使用固定 ID，固定 ID 加入数据库同步黑名单。mood_impacts 表改造 INTEGER PK → TEXT PK（此前唯一使用自增键的种子数据表）。sync_repository 的 query_incremental / upsert_rows 双向过滤黑名单 ID。

**阶段 2**：云端不做种子数据初始化。第一次同步由本地全量推送数据到云端。通过标志文件判断云端是否已初始化。

**优势**

- 双向过滤后，后续同步中种子数据永不重复传播
- 方案设计清晰，两阶段独立实施

**劣势**

- mood_impacts 表改造带来迁移成本和风险（INTEGER → TEXT 重建表）
- **黑名单无法保证数据一致性**：用户本地特有的数据、云端首次同步前 agent 产生的噪音数据不会被黑名单覆盖，仍然可能残留或重复
- 黑名单需要两处同步维护（data_initializer 的种子数据定义 + sync/constants 的黑名单常量）
- 新增种子数据时若忘记更新黑名单，问题复现

### 方案 B：全清覆盖方案（否决黑名单）★ 选定

云端不做种子数据初始化。首次同步时，本地向云端发起"全清 + 全量覆盖"流程：
1. full-clear 清空云端所有 SYNC_TABLES + 动态表定义表 + 同步文件
2. 本地全量推送所有数据和文件到云端
3. 设置云端初始化标志
4. 后续同步走现有增量流程

**优势**

- **真正保证数据一致性**：云端所有旧数据被清空，本地完整数据覆盖，无残留风险
- **无需修改种子数据结构**：不改造 mood_impacts 自增键，无迁移成本
- **无需维护黑名单**：无"忘记更新"的风险
- **设计一致**：clean slate 策略，不存在"黑白名单"这种局部过滤的妥协
- **现有端点可复用**：/push（数据库推送）和 /push-files（文件推送）均可复用

**劣势**

- 首次同步非原子：full-clear 到 mark-initialized 之间有窗口期，依赖幂等重试恢复
- 首次同步期间云端 agent 无法使用数据
- 需要新增 2 个端点（/initialization-status、/full-clear、/mark-initialized）

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 前提 1~8 全部成立 | 方案 B（全清覆盖） | 当前选择 |
| 前提 3 失效（出现网页端修改能力） | 整体同步策略需重新评估 | 方案 B 的"云端数据无效"前提不成立，首次同步数据不可丢弃 |
| 前提 8 失效（云端需要独立处理数据） | 需重新评估初始化策略 | 主备模式失效，云端需要自己的初始化流程 |

## 演进历史

| 版本 | 方案 | 解决的问题 | 引入的新问题 |
| ---- | ---- | ---------- | ------------ |
| v1（初始） | 两阶段方案（黑名单 + 本地全量推送） | 种子数据同步重复 | mood_impacts 需迁移，黑名单维护成本，无法保证数据一致性 |
| v2（最终） | 全清覆盖方案（否决黑名单） | 一致性问题彻底解决，无迁移成本 | 首次同步非原子，依赖幂等重试 |

## 最终决策

当前成立的前提：全部 8 个前提成立。

因此选择**方案 B：全清覆盖方案（否决黑名单）**。

前提失效时的切换路径：
- 前提 3 失效（出现网页端）→ 需重新评估整个同步策略，不受本 ADR 约束
- 前提 8 失效（云端需要独立处理数据）→ 主备模式不成立，云端需要自己的初始化流程

### 回滚事项

原先按方案 A 已做的修改需要回滚：
1. `database.py`：MOOD_IMPACTS_CONFIG.id 类型从 TEXT → INTEGER AUTOINCREMENT
2. `mood_providers.py`：MoodImpactProvider.create_mood_impact 返回类型从 str → int，delete_mood_impact 参数从 str → int

mood_impacts 表与项目主流 TEXT ID 风格不一致的技术债，记录在"后续影响"中，当前不处理。

## 决策原因

1. **真正保证数据一致性**：全清覆盖从源头消除云端残留数据风险，黑名单方案本质上是用"允许部分不一致"换取"种子数据不重复"，无法应对云端 agent 在首次同步前产生的数据。用户明确表述："仅仅是黑名单并不能真正的确保数据一致性"。

2. **零迁移成本**：mood_impacts 的 AUTOINCREMENT PK 经验证不影响任何功能（无外键引用、mood_entries 存 name 而非 ID）。改造它纯粹是为了支持黑名单机制。既然黑名单方案被否决，改造理由消失。

3. **复用现有同步基础设施**：全量推送可复用现有 /push 端点的分页机制和 /push-files 的文件推送逻辑，无需重新设计数据传输协议。

## 后续影响

### 需要实施的变更

- **Phase A**：修改 `init_database_full()`（bootstrap.py），在 agent-only 模式下跳过 `initialize_resources()` 和 `initialize_default_data()`。理由：前提 8 保证云端首次同步前不需处理用户数据，`initialize_resources()` 复制的 prompts/ 由 PromptLoader 懒加载，agent/ + user/ 文件由首次文件推送覆盖，config/ 由 cloud_init 管理。
- **Phase B**：云端初始化状态管理——标志文件 `<localData>/config/cloud_initialized`，新增 3 个端点：
  - `GET /api/sync/initialization-status` — 检查是否已初始化
  - `POST /api/sync/full-clear` — 清空云端所有 SYNC_TABLES + SYNC_DIRECTORIES 文件（保留 schema_version、custom_* 表结构）
  - `POST /api/sync/mark-initialized` — 创建标志文件
- **Phase C**：修改 `sync_once`，新增首次同步分支：检测未初始化 → full-clear → 全量推送数据库 → 全量推送文件 → mark-initialized → 设置 last_sync_time。
- **Phase D**：实现全量推送逻辑（复用 /push 分页 + /push-files）。
- **回滚**：将 mood_impacts 表配置和 Provider 恢复为 INTEGER AUTOINCREMENT。

### 已知限制

1. **首次同步非原子**：full-clear 后推送失败→云端半空→下次幂等重试。接受此风险。
2. **动态表首次只覆盖定义表**：custom_record_types/custom_record_fields 由全量推送覆盖，实际数据表（custom_\*）在后续增量同步中处理。云端已有的孤儿表不被使用也不被清理。
3. **mood_impacts 自增键技术债**：与项目主流 TEXT ID 风格不一致，但不影响功能，延期处理。
4. **网页端前提**：如果未来加入网页端修改能力（前提 3 失效），当前同步策略整体失效，需重新设计。
5. **测试覆盖缺失（技术债）**：首次同步全清流程的 8 个核心方法（query_all/delete_all_rows/3个API端点/_initial_push_db/_initial_push_files/_advance_local_parent_after_initial_sync/_full_sync_to_cloud）当前无单元测试和集成测试覆盖。建议在首次部署验证前补全关键路径测试（尤其是 P0 修复相关的批量操作和矩阵判定）。详见代码审查报告 docs/generated/014/。
6. **SyncClient 类职责膨胀（技术债）**：SyncClient 现承担首次同步 + 增量同步两条流程，规模超 1780 行。建议在下次涉及同步模块大改时抽取独立的 InitialSyncService 类，改善单一职责。当前功能正确，重构非紧急。

### 验证策略

- 编写测试验证首次同步分支（全清 → 全量推送 → 标志设置）
- 验证后续同步恢复为增量流程
- 验证云端 agent 在首次同步前启动不产生数据（或产生的数据被全清覆盖）
