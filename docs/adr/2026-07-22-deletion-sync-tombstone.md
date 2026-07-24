---
version: 1.0
created_at: 2026-07-22
updated_at: 2026-07-23
last_updated: 创建文档初稿；supersede 2026-07-22-deletion-log-table.md 中"deletion_log 加入 SYNC_TABLES"决策
abstract: 墓碑同步流程的架构决策——从 SYNC_TABLES 移除 deletion_log 改用 3 个专用端点（pull/push/cleanup），事务边界设计为 HTTP 外事务内，LWW 简化为 INSERT OR IGNORE 跳过，Aggregator 实例化 DeletionLogProvider 而非导入单例
status: decided
---

# 墓碑同步流程架构决策（PRD 3）

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿；supersede 既有 ADR 中"deletion_log 加入 SYNC_TABLES"决策 |

## 问题界定

### 问题简述

PRD 1 已建好 `deletion_log` 墓碑表 schema（见 [2026-07-22-deletion-log-table.md](./2026-07-22-deletion-log-table.md)），PRD 2 已让所有 Provider 的删除走 `_generic_delete` 写墓碑。PRD 3 需要设计"墓碑如何跨端传播"的同步流程：本地删除产生墓碑后，如何让对端感知并执行同样的删除？既有 ADR 把 `deletion_log` 放入 `SYNC_TABLES` 走数据同步通道，但实施前发现该方案有严重的双重同步和 LWW 语义不匹配问题。本 ADR 记录五个关键决策：同步通道选择、事务边界设计、LWW 简化策略、Aggregator 实例化方式、sync_once 流程顺序。

### 讨论范围

- `deletion_log` 是否留在 `SYNC_TABLES`（决策 1）
- 墓碑同步的事务边界：HTTP 与事务的关系（决策 2）
- 跨端墓碑的 LWW 处理：是否比较 `updated_at`（决策 3）
- `CustomRecordRepository` 如何访问 `DeletionLogProvider`（决策 4）
- `sync_once` 中墓碑 Pull/Push 与数据 Pull/Push 的顺序（决策 5）

### 非讨论范围

- `deletion_log` 表的 schema 定义（见 [2026-07-22-deletion-log-table.md](./2026-07-22-deletion-log-table.md)，本 ADR supersede 其中"加入 SYNC_TABLES"部分）
- `DeletionLogProvider` 的基础 CRUD（属 PRD 3 实现细节）
- 墓碑清理的保留期限策略（本 ADR 只决定"何时调用清理"，清理策略本身见 spec）
- `hash_id` 字段设计（见 [2026-07-22-add-hash-id-to-autoincrement-tables.md](./2026-07-22-add-hash-id-to-autoincrement-tables.md)）

### 模糊信息的明确定义

- "双重同步"：`deletion_log` 若留在 `SYNC_TABLES`，会同时被数据同步通道（`pull_from_remote`/`push_to_remote`）和墓碑专用通道处理，导致同一墓碑被两次拉取/推送
- "墓碑不更新"：墓碑记录插入后不再 UPDATE，`updated_at == created_at`，因此 LWW 比较 `updated_at` 等价于比较 `created_at`
- "专用端点"：为墓碑同步单独设计的 3 个 HTTP 端点（`/pull-deletion-log`、`/push-deletion-log`、`/cleanup-deletion-log`），不复用 `/pull`、`/push`
- "cursor 变体"：Provider/Repository 方法接受外部 `sqlite3.Cursor` 参数，让 SQL 仍封装在 Repository 层但事务边界由调用方控制

### 问题深度

涉及架构原则——墓碑同步通道的选择决定了整个删除同步的可靠性。若选错通道（如留在 `SYNC_TABLES`），会导致双重同步、LWW 语义错乱、事务边界无法保证等系统性问题。五个决策都需要从"语义正确性"和"与现有架构契合"两个维度权衡。

## 现状

- `deletion_log` 表已建好（PRD 1），字段 `id/target_table/record_id/source/created_at/updated_at`，`UNIQUE(target_table, record_id)`
- `deletion_log` 当前在 `SYNC_TABLES` 中（PRD 1 决策，见 [2026-07-22-deletion-log-table.md](./2026-07-22-deletion-log-table.md) "后续影响"段落）
- 所有 Provider 的删除已走 `_generic_delete` 写墓碑（PRD 2）
- 6 张 AUTOINCREMENT 表已有 `hash_id` 字段作为跨端稳定标识（见 [2026-07-22-add-hash-id-to-autoincrement-tables.md](./2026-07-22-add-hash-id-to-autoincrement-tables.md)）
- 项目已采用 LWW 冲突解决策略（见 [2026-07-09-lww-conflict-resolution.md](./2026-07-09-lww-conflict-resolution.md)）
- `sync_once` 流程为：动态表对比 → 数据 Pull → 数据 Push → 文件同步 → 更新 `last_sync_time`
- `LWBaseDataProvider._generic_delete` 通过 `is_sync_table = self._TABLE_NAME in SYNC_TABLES` 判断是否写墓碑
- `CustomRecordRepository`（Aggregator）管理动态表 `custom_*` 的 CRUD，动态表删除需要写墓碑
- Repository 规则要求 Aggregator 内部实例化 Provider，不导入全局单例

## 决策前提

- 前提 1：`deletion_log` 在 `SYNC_TABLES` 中会被 `pull_from_remote`/`push_to_remote` 当作普通数据表同步
- 前提 2：墓碑同步需要额外的 DELETE 操作（对端按 `record_id` 删除业务表记录），普通数据同步只做 upsert 不做 DELETE
- 前提 3：墓碑不更新，`updated_at == created_at`，LWW 比较 `updated_at` 不会产生实际覆盖效果
- 前提 4：DELETE 和墓碑写入必须在同一事务，否则 DELETE 成功但墓碑写入失败会导致对端无法感知删除
- 前提 5：HTTP 请求可能超时或失败，不应占用数据库事务连接
- 前提 6：动态表 `custom_*` 的删除在 `CustomRecordRepository.delete_entry` 中执行，需要写墓碑
- 前提 7：Repository 规则要求 Aggregator 内部实例化 Provider，不导入全局单例

## 可选方案

### 决策 1：墓碑同步通道——SYNC_TABLES vs 专用端点

#### 方案 A：从 SYNC_TABLES 移除 deletion_log，改用 3 个专用端点

新增 `/pull-deletion-log`、`/push-deletion-log`、`/cleanup-deletion-log` 三个端点，`deletion_log` 不走 `SYNC_TABLES` 通道。

**优势**

- 避免双重同步：墓碑只走专用通道，不会被 `pull_from_remote`/`push_to_remote` 重复处理
- 语义清晰：专用端点可以携带额外的 DELETE 语义（对端拉取墓碑后执行 DELETE + 写副本），普通数据同步只做 upsert
- 事务边界可控：专用端点可以在事务内完成 DELETE + 墓碑写入，普通数据同步的事务边界不适合此场景
- 清理独立：`/cleanup-deletion-log` 可以按 `last_sync_time` 精确清理，不受数据同步流程干扰

**劣势**

- 新增 3 个端点，代码量增加
- 需要从 `SYNC_TABLES` 移除 `deletion_log`，修改既有测试

#### 方案 B：保留 deletion_log 在 SYNC_TABLES，在 pull/push 中增加墓碑处理逻辑

在 `pull_from_remote`/`push_to_remote` 中为 `deletion_log` 表增加特殊处理分支（检测到墓碑后执行 DELETE）。

**优势**

- 不新增端点，复用现有同步通道

**劣势**

- 双重同步：`deletion_log` 会被 `pull_from_remote`/`push_to_remote` 当作普通数据 upsert，同时还要执行 DELETE，逻辑混乱
- `pull_from_remote` 需要为 `deletion_log` 写特殊分支，违反开闭原则
- LWW 语义不匹配：普通数据同步的 LWW 比较 `updated_at` 决定是否覆盖，但墓碑不更新，LWW 无实际意义
- 清理时机难以与数据同步解耦

### 决策 2：事务边界——HTTP 与事务的关系

#### 方案 A：HTTP 在事务外，DELETE + 墓碑写入在事务内

HTTP 请求（拉取/推送墓碑）在事务外执行，获取到墓碑列表后开事务执行 DELETE + 写副本，失败则整个事务回滚。

**优势**

- HTTP 超时不占用数据库连接，避免长事务锁库
- DELETE 和墓碑写入在同一事务，保证原子性（要么都成功，要么都回滚）
- 失败时 `sync_once` 抛异常，`last_sync_time` 不更新，下次同步会重试

**劣势**

- 需要为 Provider/Repository 提供 cursor 变体方法（让 SQL 封装在 Repository 层但事务边界由调用方控制）
- HTTP 成功但事务失败时，对端可能已消费墓碑（但本地未写副本），下次同步会重新拉取（幂等）

#### 方案 B：HTTP 和事务混合

在事务内发起 HTTP 请求。

**优势**

- 实现简单，无需 cursor 变体

**劣势**

- HTTP 超时会导致长事务，锁库风险高
- 违反"HTTP 操作不应占用数据库事务连接"原则

### 决策 3：LWW 处理——比较 updated_at vs INSERT OR IGNORE 跳过

#### 方案 A：本地已有墓碑则 INSERT OR IGNORE 跳过

Pull 墓碑时先查询本地是否已有同 `(target_table, record_id)` 的墓碑，有则跳过（不覆盖）。

**优势**

- 实现简单：利用 `UNIQUE(target_table, record_id)` 约束 + `INSERT OR IGNORE`
- 语义正确：墓碑不更新，本地已有墓碑说明已执行过删除，无需重复 DELETE
- 避免覆盖：保留本地墓碑的 `created_at`，不被云端墓碑覆盖

**劣势**

- 若两端同时删除同一条记录（A、B 都写墓碑），两端的 `created_at` 不同，LWW 不会选择更晚的（但结果都是删除，无实际差异）

#### 方案 B：比较 updated_at 决定是否覆盖

Pull 墓碑时比较本地和云端墓碑的 `updated_at`，更晚的保留。

**优势**

- 与现有 LWW 路径完全一致

**劣势**

- 墓碑不更新，`updated_at == created_at`，比较 `updated_at` 等价于比较 `created_at`，无实际覆盖效果
- 增加代码复杂度（需要查询本地墓碑的 `updated_at` 并比较），无实际收益
- 覆盖本地墓碑可能导致 `created_at` 被修改，影响清理逻辑

### 决策 4：Aggregator 访问 DeletionLogProvider——实例化 vs 导入单例

#### 方案 A：Aggregator 在 __init__ 中实例化 DeletionLogProvider

`CustomRecordRepository.__init__` 中 `self.deletion_log_provider = DeletionLogProvider(db_manager=self.db)`。

**优势**

- 符合 Repository 规则（Aggregator 内部实例化 Provider，不导入全局单例）
- `db_manager` 透传，保证事务连接一致性
- 生命周期清晰：Aggregator 持有自己的 Provider 实例

**劣势**

- 每个 Aggregator 实例都创建一个 DeletionLogProvider 实例（但实际只有一个 Aggregator 实例，无内存问题）

#### 方案 B：导入全局单例

`from lifeprism.repository import deletion_log_repository` 直接使用全局单例。

**优势**

- 代码简洁

**劣势**

- 违反 Repository 规则（Aggregator 不应导入全局单例）
- `db_manager` 可能不一致（全局单例用默认 `lw_db_manager`，Aggregator 可能用传入的 `db_manager`）

### 决策 5：sync_once 中墓碑 Pull/Push 与数据 Pull/Push 的顺序

#### 方案 A：墓碑 Pull → 数据 Pull → 墓碑 Push → 数据 Push → 文件 → 清理 → 更新 last_sync_time

**优势**

- 墓碑 Pull 在数据 Pull 之前：确保已删记录先被本地删除，避免数据 Pull 的 upsert 写回（云端已物理删除的记录不会出现在数据 Pull 结果中）
- 墓碑 Push 在数据 Push 之前：确保本地墓碑先同步到云端，云端数据 Push 不会推送已删记录
- 清理在更新 `last_sync_time` 之前：用旧 `last_sync_time` 清理过期墓碑
- 失败时 `last_sync_time` 不更新，下次同步会重试

**劣势**

- 流程步骤增加，但每步语义清晰

#### 方案 B：数据 Pull → 墓碑 Pull → 数据 Push → 墓碑 Push

**优势**

- 无

**劣势**

- 数据 Pull 可能把云端已删记录写回本地（虽然云端已物理删除，但若有延迟可能返回旧数据）
- 墓碑 Push 在数据 Push 之后，可能导致云端数据 Push 推送已删记录

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 前提 1 + 前提 2 + 前提 3 成立 | 决策 1 方案 A：专用端点 | 当前选择 |
| 前提 4 + 前提 5 成立 | 决策 2 方案 A：HTTP 外事务内 | 当前选择 |
| 前提 3 成立 | 决策 3 方案 A：INSERT OR IGNORE 跳过 | 当前选择 |
| 前提 6 + 前提 7 成立 | 决策 4 方案 A：Aggregator 实例化 | 当前选择 |
| 前提 4 成立 | 决策 5 方案 A：墓碑 Pull → 数据 Pull → 墓碑 Push → 数据 Push | 当前选择 |

## 演进历史

| 版本 | 方案 | 解决的问题 | 引入的新问题 |
| ---- | ---- | ---------- | ------------ |
| v1（既有 ADR） | deletion_log 加入 SYNC_TABLES | 墓碑需要跨端同步 | 双重同步、LWW 语义不匹配、事务边界无法保证 |
| v2（本 ADR） | 专用端点 + HTTP 外事务内 + INSERT OR IGNORE | 解决 v1 的三个问题 | 新增 3 个端点，代码量增加 |

## 最终决策

当前成立的前提：前提 1、2、3、4、5、6、7 均成立。

因此选择：
- **决策 1 方案 A**：从 `SYNC_TABLES` 移除 `deletion_log`，新增 3 个专用端点（`/pull-deletion-log`、`/push-deletion-log`、`/cleanup-deletion-log`）
- **决策 2 方案 A**：HTTP 在事务外，DELETE + 墓碑写入在事务内（cursor 变体方法）
- **决策 3 方案 A**：本地已有墓碑则 `INSERT OR IGNORE` 跳过（不比较 `updated_at`）
- **决策 4 方案 A**：`CustomRecordRepository.__init__` 中实例化 `DeletionLogProvider`
- **决策 5 方案 A**：`sync_once` 流程为 墓碑 Pull → 数据 Pull → 墓碑 Push → 数据 Push → 文件 → 清理 → 更新 `last_sync_time`

前提失效时的切换路径：
- 若未来需要"墓碑复活"（撤销删除），决策 3 的 `INSERT OR IGNORE` 需要改为 `INSERT OR REPLACE`，并启用 `updated_at` 比较
- 若未来墓碑量极大，专用端点可能需要分页或压缩，但通道选择（专用端点）不变

## 决策原因

- 原因 1（决策 1）：`deletion_log` 在 `SYNC_TABLES` 中会被数据同步通道当作普通数据 upsert，同时还要执行 DELETE，导致双重同步。专用端点让墓碑同步与数据同步解耦，各自语义清晰
- 原因 2（决策 2）：HTTP 超时不应占用数据库事务连接（避免长事务锁库）。DELETE 和墓碑写入必须原子性（否则 DELETE 成功但墓碑写入失败会导致对端无法感知删除）。cursor 变体方法让 SQL 封装在 Repository 层（符合 Repository Pattern），事务边界由调用方控制
- 原因 3（决策 3）：墓碑不更新，`updated_at == created_at`，比较 `updated_at` 无实际覆盖效果。`INSERT OR IGNORE` 利用 `UNIQUE(target_table, record_id)` 约束自然去重，实现最简。两端同时删除同一记录时，两端都保留自己的墓碑，结果都是删除，无实际差异
- 原因 4（决策 4）：Repository 规则要求 Aggregator 内部实例化 Provider。`db_manager` 透传保证事务连接一致性
- 原因 5（决策 5）：墓碑 Pull 在数据 Pull 之前，确保已删记录先被本地删除。云端数据 Pull 端点不返回已物理删除的记录（因记录已从云端 DB 删除），数据 Pull 不会写回已删记录。墓碑 Push 在数据 Push 之前，确保云端先收到墓碑

## 后续影响

- PRD 3 范围（本 ADR）：
  - 从 `SYNC_TABLES` 移除 `deletion_log`（[constants.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/constants.py)）
  - 新增 3 个专用端点（[sync_cloud_api.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py)）
  - `SyncRepository` 新增 `execute_tombstone_delete_with_cursor` 方法（[sync_repository.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/sync_repository.py)）
  - `DeletionLogProvider` 新增 `get_tombstone_with_cursor` / `create_tombstone_with_cursor` 方法（[deletion_log_provider.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/providers/deletion_log_provider.py)）
  - `SyncClient` 新增 `_pull_deletion_log` / `_push_deletion_log` / `_cleanup_deletion_log` 方法，集成到 `sync_once`（[sync_client.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py)）
  - `CustomRecordRepository.__init__` 实例化 `DeletionLogProvider`（[custom_record_aggregator.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/aggregators/custom_record_aggregator.py)）
- 文档影响：
  - supersede [2026-07-22-deletion-log-table.md](./2026-07-22-deletion-log-table.md) 中"deletion_log 加入 SYNC_TABLES"决策（该 ADR 的 schema 决策仍然有效，仅 supersede 同步通道选择）
  - `data-sync-core-spec.md` 同步表数量从 30 张变 29 张（移除 `deletion_log`：30 - 1 = 29）
  - 新增 3 个 known-limitations 文件（删除-更新冲突不解决、删除-重建冲突跳过墓碑、文件删除不同步）
- 已知限制：
  - 删除与更新并发冲突不解决（A 删除 + B 更新同一条记录，B 端 upsert 会覆盖 A 端的删除）
  - 删除-重建冲突时墓碑跳过（A 删除后 B 重建同一记录，A 端墓碑会跳过 B 端的新记录）
  - 文件删除不走墓碑同步（仅数据库记录走墓碑，文件删除走 file_sync_state 的 LWW）
- 需要后续验证：跨端同时删除同一条记录时，`INSERT OR IGNORE` 是否正确跳过（已通过测试场景 6 验证）
