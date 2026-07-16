---
version: 1.0
created_at: 2026-07-16
updated_at: 2026-07-16
last_updated: 2026-07-16
abstract: 动态表同步采用"拉取云端定义 → 本地 slug 对比 → 双向建表"方案，替代原 pull 前后快照对比。新增端点查询云端动态表定义（types + fields 两表），本地用 slug 集合对比触发双向建表，删除 get_all_sync_tables，由建表步骤产出动态表列表。
status: decided
---

# 动态表同步：定义对比方案（替代快照对比）

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

当前动态表同步的触发条件存在严重逻辑缺陷，导致每次同步都触发无意义的云端重建请求。根因是触发条件由两部分组成：
- 条件 A：比较 pull 前后本地 `custom_record_types` 的快照变化——只能检测"云端→本地"方向的变化，无法检测"本地主动新增动态表"
- 条件 B（兜底）：`or dynamic_tables`（本地存在任何 `custom_*` 数据表则触发）——本意是兜底"首次同步"，但写成了永真条件

两者 OR 关系导致：只要本地有动态表，每次 sync_once 都触发 `_rebuild_remote_dynamic_tables`，云端走 skipped 分支无副作用，但产生无意义的 HTTP 往返和日志噪音。更严重的是，条件 A 方向错误（检测云端→本地，但 rebuild 方向是本地→云端），掩盖了真正需要检测的"本地定义相比上次告诉云端时是否变化"。

### 讨论范围

- 动态表同步的触发机制：从快照对比改为定义对比
- 新增端点 `GET /api/sync/dynamic-tables-definitions` 的职责
- 动态表列表的获取方式：删除 `get_all_sync_tables`，由建表步骤产出
- 本地建表时是否写入 meta 数据（types + fields 定义表）
- 步骤3a/3b 的建表策略（全量 vs 差异、是否写 meta）

### 非讨论范围

- 动态表字段变更检测（当前设计假设字段不会变更，见决策前提 1）
- sync_once 期间的并发锁机制（见决策前提 3 的假设标注，需单独决策）
- pull/push 的 LWW 冲突解决（已在 `2026-07-09-lww-conflict-resolution.md` 决定）
- 文件同步流程（已在 `2026-07-14-file-sync-conflict-resolution.md` 决定）

### 模糊信息的明确定义

- `动态表定义`：两张 meta 表的完整内容——`custom_record_types`（类型定义：id、name、slug、description 等）+ `custom_record_fields`（字段定义：id、type_id、field_name、field_key、field_type、sort_order 等）
- `动态数据表`：实际存储用户记录的数据表，表名格式 `custom_<slug>`（如 `custom_reading_log`）
- `slug 集合对比`：取两端的 slug 集合做差集，不比较字段定义内容

## 现状

- `sync_once` 中通过 `snapshot_before` / `snapshot_after` 对比 pull 前后本地 `custom_record_types` 的 `(id, updated_at)` 集合
- 兜底条件 `or dynamic_tables` 永远为 True（本地有 3 个动态表）
- `_rebuild_remote_dynamic_tables` 全量发送本地定义给云端，云端 `rebuild_dynamic_tables` 按 slug 逐个 CREATE/ALTER/SKIP/DROP
- `get_all_sync_tables` 查询 `custom_record_types` 拿 slug 列表，拼接 `custom_<slug>` 到 `SYNC_TABLES`
- 本地创建动态表的入口 `CustomRecordRepository.create_type` 是完整事务（meta 写入 + DDL），生成新的 type_id/field_id
- DDL 生成逻辑 `generate_create_table_ddl(slug, fields)` 是静态方法，只需 slug + fields，不依赖 meta 表

## 决策前提

- **前提 1 — 动态表字段不会被修改**：当前设计假设动态表的字段定义（`custom_record_fields`）创建后不会被修改。前端和 Agent 只能创建新的动态表类型，不能修改已有类型的字段。
  - **校验方式**：查看前端动态表管理界面和 Agent 工具，确认无"修改字段"功能
  - **前提失效触发**：当前端或 Agent 支持修改字段时，需要重新决策——从"只对比 slug 集合"升级为"对比 slug + fields 内容"，并评估是否需要触发云端 ALTER TABLE

- **前提 2 — 主备模式**：继承自 `2026-07-14-file-sync-conflict-resolution.md`，同一时间只有一端的 Agent 在工作，不会两端同时新增不同的动态表。
  - **校验方式**：参考文件同步 ADR 的前提 1
  - **前提失效触发**：多端同时新增动态表时，两端拉取到的 slug 集合都会包含对方的 slug，建表后 pull 阶段会同步对方的 meta 数据。需要评估 id 冲突问题（两端生成的 type_id 不同）

- **前提 3（假设）— sync_once 期间无并发修改**：当前假设 sync_once 执行期间没有其他代码并发访问或修改动态表。具体表现为：建表后到 pull 完成 meta 同步之间存在短暂窗口，本地 `custom_xxx` 数据表已存在但 `custom_record_types` 里还没有对应记录。
  - **当前状态**：标注为假设，未经验证
  - **后续决策**：sync_once 期间的并发锁机制是独立的决策点，不在本 ADR 范围内。如果未来发现 sync_once 期间有并发访问导致数据不一致，需要单独决策并发控制方案

## 可选方案

### 方案 A：持久化 last_synced_snapshot

在 settings 中持久化"上次成功 rebuild 后的本地 snapshot"，触发条件改为 `current_snapshot != last_synced_snapshot`。

**优势**

- 改动最小，只修改 sync_client.py 的判断逻辑
- 不新增端点，不改变流程顺序

**劣势**

- 只解决"每次触发"问题，未解决"快照方向错误"问题——snapshot 仍然是 pull 前后对比，本质是检测"云端→本地"变化
- 本地新增动态表时 snapshot 不变，需要靠"首次触发后更新 last_synced"来覆盖，逻辑绕
- 持久化 set 序列化问题需要额外处理

### 方案 B：新增端点拉取云端定义，本地 slug 对比

新增 `GET /api/sync/dynamic-tables-definitions`，返回云端两张 meta 表的完整内容。本地拉取后用 slug 集合对比，触发双向建表。

**优势**

- 直接对比两端定义，方向正确——既能检测"本地新增"也能检测"云端新增"
- 职责单一：建表步骤只负责建表（schema），pull 只负责同步数据（data）
- 删除 `get_all_sync_tables`，动态表列表由建表步骤产出，不依赖 `custom_record_types` 查询，避免"定义有但表没建"的错位状态
- 对比逻辑简单（slug 集合差集），易维护

**劣势**

- 新增一个 HTTP 端点，增加同步流程的请求次数
- 需要修改 `sync_once` 主流程顺序（对比前置到 pull 之前）
- 删除 `get_all_sync_tables` 影响调用方

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 前提 1（字段不变）+ 前提 2（主备模式）+ 前提 3（无并发，假设） | 方案 B | 当前选择 |
| 前提 1 失效（支持字段修改） | 方案 B + 扩展对比逻辑 | 需要从 slug 对比升级为 slug + fields 内容对比 |
| 前提 2 失效（多端同时新增） | 需重新评估 | 评估 id 冲突问题，可能需要全局 id 生成策略 |
| 前提 3 失效（有并发访问） | 需独立决策 | sync_once 并发锁机制，不在本 ADR 范围 |

## 最终决策

当前成立的前提：前提 1（字段不变，已校验）、前提 2（主备模式，继承自文件同步 ADR）、前提 3（无并发，假设）。

因此选择 **方案 B：新增端点拉取云端定义，本地 slug 对比**。

前提失效时的切换路径：
- 前提 1 失效 → 扩展对比逻辑（slug → slug + fields），评估 ALTER TABLE 触发
- 前提 2 失效 → 重新评估 id 冲突问题
- 前提 3 失效 → 独立决策并发锁机制

## 决策原因

- **方向正确性**：方案 B 直接对比两端定义，能同时覆盖"本地新增"和"云端新增"两个方向，而方案 A 的快照对比本质是单方向检测
- **职责单一**：建表（schema）和数据同步（data）分离，建表步骤只执行 DDL 不写 meta，pull 统一处理数据同步和 LWW，逻辑不重复
- **避免错位状态**：动态表列表由建表步骤产出（云端 slug ∪ 本地 slug），不依赖 `custom_record_types` 查询，避免"定义有但表没建"导致 pull 报错
- **可扩展性**：前提 1 失效时，从 slug 对比升级为 slug + fields 对比是自然扩展，不需要重构整个流程

## 后续影响

- **新增端点**：`GET /api/sync/dynamic-tables-definitions`，返回 `{"types": [...]}`，每个 type 含 slug 和内嵌 fields，需在 `sync_cloud_api.py` 实现
- **删除 `get_all_sync_tables`**：主函数 `sync_once` 内拼接 `SYNC_TABLES + 步骤3产出的动态表列表`，去重
- **修改 `sync_once` 流程顺序**：原"pull → 快照对比 → 重建"改为"拉取云端定义 → 本地对比 → 双向建表 → pull → push"
- **本地建表只执行 DDL**：复用 `generate_create_table_ddl(slug, fields)`，不调用 `create_type`（避免写 meta 和 id 冲突）
- **`_rebuild_remote_dynamic_tables` 保持全量发送**：端点幂等，简单优先
- **待后续决策**：sync_once 期间的并发锁机制（前提 3 的假设需要独立决策验证）
- **测试影响**：需更新 `test_sync_files_full_flow.py` 和 `test_rebuild_dynamic_tables.py`，新增端点的集成测试
