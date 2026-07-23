---
version: 1.0
created_at: 2026-07-22
updated_at: 2026-07-22
last_updated: 2026-07-22
abstract: 新增 deletion_log 墓碑表，字段名用 target_table 而非 table_name（避免变量名混淆），update_at=True 使 LWW 用 updated_at 比较（墓碑不更新，updated_at == created_at）
status: decided
---

# deletion_log 墓碑表 schema 决策

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

删除操作无法跨端同步——A 设备删除后，B 设备 pull 时云端又拉回来。需要墓碑表（Tombstone）记录删除意图，让对端拉取墓碑后执行本地删除。本 ADR 记录墓碑表 schema 的三个关键决策：字段命名、时间戳语义、LWW 比较字段选择。

### 讨论范围

- `deletion_log` 表的 schema 定义（4 个业务字段 + 时间戳配置）
- 字段名 `target_table` 而非 `table_name` 的命名选择
- `update_at: True` 配置的语义影响（`has_updated_at()` 返回 True，LWW 用 `updated_at` 比较）
- 墓碑"插入即不变"特性下的 `updated_at == created_at` 语义

### 非讨论范围

- 墓碑清理策略（属于 PRD 3 范围）
- `DeletionLogProvider` 的 CRUD 实现（属于 PRD 3 范围）
- `dl-` id 生成逻辑（在 PRD 3 的 DeletionLogProvider 中通过 `_generic_insert(id_prefix='dl-')` 实现，不加入 `HASH_ID_PREFIXES`）
- 是否将 `deletion_log` 加入 `SYNC_TABLES`（决策已确定加入，详见 [2026-07-22-add-hash-id-to-autoincrement-tables.md](./2026-07-22-add-hash-id-to-autoincrement-tables.md) 中"文档影响"段落：31 - 2 + 1 = 30）

### 模糊信息的明确定义

- "墓碑表"：记录删除意图的日志表，不真正删除被删记录，而是写入一条墓碑记录，对端拉取后按 `record_id` 执行本地删除
- "LWW（Last-Write-Wins）"：项目现有的冲突解决策略，比较记录的 `updated_at` 时间戳决定保留哪一端版本（见 [2026-07-09-lww-conflict-resolution.md](./2026-07-09-lww-conflict-resolution.md)）
- "墓碑不更新"：墓碑记录插入后不再修改（不 UPDATE），因此 `updated_at` 在生命周期内与 `created_at` 相等

### 问题深度

涉及架构原则——墓碑表是删除同步的核心数据结构，schema 决策影响 PRD 3 的 LWW 比较路径、字段命名影响代码可读性。三个决策都需要从"语义清晰"和"与现有 LWW 机制契合"两个维度权衡。

## 现状

- 项目已采用 LWW 冲突解决策略（见 [2026-07-09-lww-conflict-resolution.md](./2026-07-09-lww-conflict-resolution.md)）
- `LWBaseDataProvider.has_updated_at()` 通过 `config["update_at"]` 判断表是否有 `updated_at` 字段（[lw_base_data_provider.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/base_providers/lw_base_data_provider.py)）
- `sync_repository` 的 LWW 比较使用 `updated_at` 字段（仅当 `has_updated_at()` 返回 True 时）
- 6 张 AUTOINCREMENT 表已新增 `hash_id` 字段作为跨端稳定标识（见 [2026-07-22-add-hash-id-to-autoincrement-tables.md](./2026-07-22-add-hash-id-to-autoincrement-tables.md)）
- TEXT 主键表本身即具备跨端稳定标识
- 现有 schema 配置中 `table_name` 是表配置 dict 的元字段（如 `{"table_name": "goal", "columns": {...}}`），不是任何表的业务字段

## 决策前提

- 前提 1：删除同步需要墓碑表，墓碑记录需要参与同步（加入 `SYNC_TABLES`）
- 前提 2：墓碑记录插入后不再修改（墓碑不更新），`updated_at` 在生命周期内与 `created_at` 相等
- 前提 3：项目 LWW 机制通过 `has_updated_at()` 判断是否用 `updated_at` 比较，未配置 `update_at=True` 时退化为不参与 LWW（仅插入）
- 前提 4：现有 schema 配置中 `table_name` 是表配置 dict 的元字段（key），不是任何表的业务字段
- 前提 5：被删记录所在表的表名是墓碑的业务字段（需要存储"被删记录来自哪张表"），需要一个字段名

## 可选方案

### 决策 1：字段命名 `target_table` vs `table_name`

#### 方案 A：用 `target_table` 作为字段名

将"被删记录所在表名"字段命名为 `target_table`。

**优势**

- 语义清晰：`target_table` 直观表达"删除操作的目标表"
- 避免与 schema 配置 dict 中的 `table_name` 元字段混淆（同一份配置里既有 `table_name` 元字段又有 `table_name` 业务字段会引发认知冲突）
- 在 Provider 代码中访问 `record["target_table"]` 时，与 `config["table_name"]` 明显区分，避免 `table_name` 变量名遮蔽

**劣势**

- 与日常英语习惯略偏（`table_name` 更常见），但语义准确性优先

#### 方案 B：用 `table_name` 作为字段名

将"被删记录所在表名"字段命名为 `table_name`。

**优势**

- 命名常见，符合英语习惯

**劣势**

- 与 schema 配置 dict 中的 `table_name` 元字段重名，在同一份配置中产生歧义
- 在 Provider 代码中 `table_name = record["table_name"]` 与 `table_name = config["table_name"]` 重名遮蔽，可读性差
- 未来读者需要区分"这是配置元字段还是业务字段"

### 决策 2：`update_at: True` vs `update_at: False`

#### 方案 A：配置 `update_at: True`

开启 `update_at`，使 `has_updated_at()` 返回 True，LWW 比较使用 `updated_at`。

**优势**

- 墓碑表参与 sync_repository 的 LWW 比较路径，与其他同步表行为一致
- 跨端同时删除同一条记录时（A、B 都写墓碑），LWW 能正确处理重复墓碑（按 `updated_at` 比较，新墓碑覆盖旧墓碑）
- 与项目所有同步表的配置风格一致（所有 SYNC_TABLES 表均配置 `update_at: True`）

**劣势**

- 墓碑不更新，`updated_at` 实际等价于 `created_at`，看似冗余

#### 方案 B：配置 `update_at: False`

关闭 `update_at`，墓碑表不参与 LWW 比较。

**优势**

- 反映"墓碑不更新"的语义，配置更诚实

**劣势**

- 与其他同步表行为不一致，sync_repository 需要为墓碑表走特殊分支
- 跨端同时删除时无法用 LWW 处理重复墓碑（需要其他去重逻辑，如按 `record_id + target_table` 唯一约束）
- 未来若需要"复活墓碑"（如撤销删除）会受限于无 `updated_at` 字段

### 决策 3：LWW 比较字段选择 `updated_at` vs `created_at`

#### 方案 A：用 `updated_at`（依赖 `update_at: True`）

通过 `update_at: True` 让 `has_updated_at()` 返回 True，LWW 比较使用 `updated_at`。

**优势**

- 与所有同步表的 LWW 路径完全一致，无需为墓碑表写特殊比较逻辑
- 跨端同时删除时，LWW 自然处理重复墓碑（按 `updated_at` 比较，新覆盖旧）
- 利用现有 LWW 基础设施，零改动

**劣势**

- 墓碑不更新，`updated_at == created_at`，用 `updated_at` 比较等价于用 `created_at` 比较（语义略冗余）

#### 方案 B：用 `created_at`（需要新增 LWW 分支）

为墓碑表新增"按 `created_at` 比较"的 LWW 分支。

**优势**

- 语义精确：墓碑只有插入时间，用 `created_at` 比较更符合实际

**劣势**

- 需要为墓碑表新增 LWW 分支，sync_repository 改动面扩大
- 与现有 LWW 路径不一致，未来维护成本上升
- 跨端同时删除时，按 `created_at` 比较与按 `updated_at` 比较结果相同（因为 `updated_at == created_at`），新增分支无实际收益

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 前提 1 + 前提 4 + 前提 5 成立 | 决策 1 方案 A：用 `target_table` | 当前选择 |
| 前提 1 + 前提 2 + 前提 3 成立 | 决策 2 方案 A：`update_at: True` | 当前选择 |
| 前提 1 + 前提 2 + 前提 3 成立 | 决策 3 方案 A：用 `updated_at` | 当前选择（依赖决策 2） |

## 演进历史

| 版本 | 方案 | 解决的问题 | 引入的新问题 |
| ---- | ---- | ---------- | ------------ |
| v1 | 字段名 `target_table` + `update_at: True` + LWW 用 `updated_at` | 墓碑表 schema 与 LWW 路径契合 | `updated_at == created_at` 语义略冗余 |

## 最终决策

当前成立的前提：前提 1、2、3、4、5 均成立。

因此选择：
- **决策 1 方案 A**：字段命名为 `target_table`（避免与 schema 配置 dict 的 `table_name` 元字段混淆）
- **决策 2 方案 A**：配置 `update_at: True`（让墓碑表参与 LWW 比较路径，与其他同步表行为一致）
- **决策 3 方案 A**：LWW 比较使用 `updated_at`（依赖决策 2，墓碑不更新使 `updated_at == created_at`，比较结果等价于用 `created_at`）

前提失效时的切换路径：
- 若未来墓碑支持"复活"（撤销删除），`update_at: True` 配置天然支持 `updated_at` 变化，无需 schema 改造
- 若未来墓碑表需要与其他同步表行为分化（如不参与 LWW），需重新评估决策 2 和 3

## 决策原因

- 原因 1（决策 1）：`table_name` 已是 schema 配置 dict 的元字段（`{"table_name": "deletion_log", "columns": {...}}`），若再用作业务字段会在同一份配置中产生歧义；Provider 代码中 `table_name = record["table_name"]` 与 `table_name = config["table_name"]` 重名遮蔽，可读性差。`target_table` 语义更清晰（"删除操作的目标表"），与配置元字段明确区分
- 原因 2（决策 2）：所有 `SYNC_TABLES` 表均配置 `update_at: True`，墓碑表加入 `SYNC_TABLES` 后应保持一致；跨端同时删除同一条记录时（A、B 都写墓碑），LWW 能正确处理重复墓碑，无需额外去重逻辑
- 原因 3（决策 3）：墓碑不更新，`updated_at == created_at`，用 `updated_at` 比较与用 `created_at` 比较结果完全等价；但用 `updated_at` 能复用现有 LWW 路径，零改动；为墓碑表新增 `created_at` LWW 分支会引入 sync_repository 改动且无实际收益
- 原因 4：决策 2 和决策 3 是耦合的——决策 3 依赖决策 2（`has_updated_at()` 返回 True 才能用 `updated_at` 比较）；两个决策一起选择方案 A 形成自洽的"墓碑表走标准 LWW 路径"设计

## 后续影响

- PRD 1 范围（本 ADR）：
  - `DELETION_LOG_CONFIG` 在 [database.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/config/database.py) 定义，字段 `id/target_table/record_id/source`，`timestamps: True`，`update_at: True`
  - `deletion_log` 加入 `SYNC_TABLES`（[constants.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/constants.py)）
  - `deletion_log` 注册到 `TABLE_CONFIGS`，`LWTableManager.init_database()` 自动建表
  - `dl-` 前缀**不加入** `HASH_ID_PREFIXES`（`dl-` 不是 hash_id 前缀，id 生成在 PRD 3 的 DeletionLogProvider 中通过 `_generic_insert(id_prefix='dl-')` 直接传入）
- PRD 3 范围：
  - `DeletionLogProvider` 通过 `_generic_insert(id_prefix='dl-')` 生成 `dl-{uuid[:8]}` 格式 id
  - 删除同步路径：本地删除 → 写墓碑 → 同步到对端 → 对端按 `record_id` 删除本地记录
  - 墓碑清理策略（保留期限、批量清理）属于 PRD 3 范围
- 文档影响：`data-sync-core-spec.md` 同步表数量从 31 张变 30 张（移除 2 张 habit 表 + 新增 1 张 `deletion_log` 墓碑表：31 - 2 + 1 = 30，见 [2026-07-22-add-hash-id-to-autoincrement-tables.md](./2026-07-22-add-hash-id-to-autoincrement-tables.md) "后续影响"段落）
- 需要后续验证：PRD 3 完成后，跨端同时删除同一条记录时 LWW 是否正确处理重复墓碑（按 `updated_at` 比较，新覆盖旧）
