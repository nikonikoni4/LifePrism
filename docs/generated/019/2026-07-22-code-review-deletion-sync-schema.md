# Code Review Report

**审查范围**: 同步删除阶段1 - Schema 变更（hash_id + 墓碑表），当前工作区代码更改
**实现文档**: `.scratch/deletion-sync-01-schema/prd.md` + `issues/`（6 个 issue）
**审查时间**: 2026-07-22
**变更文件**: 12 个修改文件（+777 -32）+ 新增 `m015` 迁移脚本 + 7 个测试文件 + 4 个 ADR + 1 个 known-limitation + 1 个 temp 文档

## 架构上下文

### 相关 ADR
- `docs/adr/2026-07-22-hash-id-sync-only-identifier.md` (decided): hash_id 定位为同步专用标识，`_PRIMARY_KEY` 保持自增 id 不变，本地 CRUD 不用 hash_id
- `docs/adr/2026-07-22-add-hash-id-to-autoincrement-tables.md` (decided): 迁移用 ALTER + 回填 + CREATE UNIQUE INDEX（不删表重建）
- `docs/adr/2026-07-22-deletion-log-table.md` (decided): 墓碑表 schema（字段名 `target_table`，`update_at: True`，LWW 用 `updated_at`）
- `docs/adr/2026-07-22-habit-chain-tables-not-synced.md` (decided): `habit_chains`/`habit_chain_nodes` 从 `SYNC_TABLES` 移除（chain_id 外键引用自增 id）

### 相关 Spec
- `docs/specs/2026-07-16-data-sync-core-spec.md`: 数据同步核心 spec（同步表数量描述待更新，PRD 明确延后到 PRD 2/3）
- `docs/adr/2026-07-09-lww-conflict-resolution.md`: LWW 冲突解决 ADR

### 决策覆盖
- 4 个 ADR 完整覆盖本次变更的架构决策，实现总体符合 ADR（依赖方向、hash_id 定位、迁移方法、墓碑表命名、habit 表移除均合规）
- 8 维度并行审查：Security / Performance / Architecture / Code Quality / Best Practices / Testing / Documentation / 代码注释合规
- Security 维度未发现问题（m015 表名来自硬编码字典 key，无注入路径；无密钥泄露；认证未变）

## 审查结果

Found 4 issues（置信度 ≥ 80，已过滤 < 80 的低分项）:

### Issue 1: get_unique_fields 改用 hash_id 后，LWW 保护被 INSERT OR REPLACE 的业务 UNIQUE 约束绕过（正确性回归）

- **类型**: Architecture / Best Practices（正确性）
- **置信度**: 90
- **位置**: `lifeprism/repository/sync_repository.py:897-898`（get_unique_fields 返回 `["hash_id"]`）、`:525`（upsert_rows 的 `INSERT OR REPLACE`）、`:728-734`（upsert_rows_with_lww 按 hash_id 查找）
- **详情**: 本次变更使 `get_unique_fields` 对 `HASH_ID_PREFIXES` 中的表返回 `["hash_id"]`，`upsert_rows_with_lww` 据此按 `hash_id` 做 LWW 过滤。但最终写入仍走 `upsert_rows` 的 `INSERT OR REPLACE INTO`，SQLite REPLACE 在违反**任意** UNIQUE 约束时都会删除旧行 + 插入新行。这 3 张仍同步表的业务 UNIQUE 约束仍在 `table_constraints` 中生效：
  - `user_app_behavior_log`: `UNIQUE(app, start_time)`（`database.py:219-220`）
  - `timeline_custom_block`: `UNIQUE(start_time)`（`database.py:711-714`）
  - `time_paradoxes`: `UNIQUE(user_id,mode,version)`（`database.py:941`）

  LWW 键（hash_id）与 REPLACE 键（业务 UNIQUE）现在不一致。
- **失败场景**: 两台设备独立创建相同业务键但不同 hash_id 的记录（每端 `_generic_insert` 各自生成 hash_id）：
  1. 设备 B 已有 `hash_id=H2, app=X, start_time=T, updated_at=10:00`（较新）
  2. 设备 A 同步推送到 B：`hash_id=H1, app=X, start_time=T, updated_at=09:00`（较旧）
  3. B 执行 `upsert_rows_with_lww`：按 `hash_id=H1` 查找 → B 没有 H1 → LWW 查不到匹配 → 放行该行
  4. `upsert_rows` 执行 `INSERT OR REPLACE` → `UNIQUE(app, start_time)` 冲突 → SQLite 删除 B 的行（H2, 10:00），插入 A 的行（H1, 09:00）
  5. 结果：B 的较新数据被 A 的较旧数据**静默覆盖**，LWW 被完全绕过
- **依据**: 经验证，这 3 张表的业务 UNIQUE 都是 `table_constraints` 格式（非列级），变更前 `get_unique_fields` 能解析，LWW 按业务 UNIQUE 判重与 INSERT OR REPLACE 一致；变更是**引入回归**。PRD Out of Scope #9 仅提及列级 UNIQUE 解析 bug，未覆盖 table-level UNIQUE 冲突，且"无实际影响"判断不准确。`mood_impacts`（列级 `UNIQUE(name)`）变更前已因解析 bug 失效，属既有问题。Best Practices Agent 独立印证（置信度 92），Testing Agent 指出该回归点无测试覆盖（见 Issue 4）。
- **修复建议**: 对 `HASH_ID_PREFIXES` 表，`upsert_rows` 改用 `INSERT INTO ... ON CONFLICT(hash_id) DO UPDATE SET ...`（显式冲突目标），使写入冲突目标与 LWW 查找键一致，用 UPDATE 而非 DELETE+INSERT（同时保留自增 id，避免触发器/级联副作用）；或在同步写入前按业务 UNIQUE 预去重。

### Issue 2: 4 个新 ADR 的 frontmatter 字段名 `last_updated_at` 不符合 docs-write-rules，与全部既有 ADR 不一致

- **类型**: Documentation
- **置信度**: 85
- **位置**: `docs/adr/2026-07-22-hash-id-sync-only-identifier.md:5`、`docs/adr/2026-07-22-add-hash-id-to-autoincrement-tables.md:5`、`docs/adr/2026-07-22-deletion-log-table.md:5`、`docs/adr/2026-07-22-habit-chain-tables-not-synced.md:5`
- **详情**: `docs/docs-rules/docs-write-rules.md:49` 规定正式文档 frontmatter 必含字段为 `version / created_at / updated_at / last_updated / abstract`，字段名是 `last_updated`。但本次新增的 4 个 ADR 第 5 行均写 `last_updated_at:`（多了 `_at` 后缀）。全目录既有 ADR（2026-05 至 2026-07-17 共 20+ 个）均使用 `last_updated:`，本次新增的 known-limitation 文档（`habit-chain-tables-not-synced.md:5`）也正确使用了 `last_updated:`，唯独这 4 个 ADR 偏离。这不是单次笔误而是 4 个文件系统性偏差，按字段名解析 frontmatter 的工具/LLM 会无法定位 `last_updated` 字段。
- **依据**: `docs/docs-rules/docs-write-rules.md:49`（`last_updated:`）；既有 ADR `2026-07-17-backup-sync-decoupled-scope.md:5`（`last_updated: 2026-07-17`）；新 known-limitation `habit-chain-tables-not-synced.md:5`（`last_updated:`）。
- **修复建议**: 将 4 个新 ADR 的 `last_updated_at:` 改为 `last_updated:`。

### Issue 3: m015 在新库上创建冗余的唯一索引（与列级 UNIQUE 自动索引重复）

- **类型**: Performance
- **置信度**: 82
- **位置**: `lifeprism/repository/migrations/scripts/m015_add_hash_id_to_autoincrement_tables.py:94-96`
- **详情**: 启动顺序 `init_database()` → `run_migrations()`（`lifeprism/server/bootstrap.py:67-68`）。新库经 `init_database()` 按 `TABLE_CONFIGS` 建表时，6 张表的 `hash_id` 配置为 `["NOT NULL", "UNIQUE"]`（如 `database.py:186-187`），SQLite 自动创建隐式唯一索引 `sqlite_autoindex_<table>_<n>`。随后 `run_migrations()` 运行（新库 `schema_version` 表为空，`_get_current_version` 返回 0，所有迁移 pending，m015 的 `check_if_applied` 返回 False）。m015 的 `upgrade()` 中 hash_id 列已存在跳过 ALTER、回填跳过（新库无 NULL 行），但 `CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_hash_id`（:94-96）仍执行，创建第二个命名唯一索引。`IF NOT EXISTS` 按索引名匹配，不会发现已有的自动索引，于是 6 张表上 hash_id 永久存在两个唯一索引。对比 m012（`m012_add_updated_at_to_sync_tables.py:58-60`）在列已存在时 `continue` 跳过索引创建（m012 的 updated_at 无列级 UNIQUE，故无冗余）。影响最大的是 `user_app_behavior_log`（高频写入），每次行为日志插入维护两个索引而非一个。
- **依据**: `database.py:184-188` hash_id 列级 `UNIQUE` → 自动索引；`m015:94-96` CREATE UNIQUE INDEX → 第二个索引；`bootstrap.py:67-68` init_database 先于 run_migrations；`migration_runner.py` 新库 version=0 → m015 运行；`m015:75` 仅跳过 ALTER 未跳过索引（与 m012:60 `continue` 不同）。
- **修复建议**: 在 `CREATE UNIQUE INDEX` 前查询 `sqlite_master` 检查 hash_id 上是否已有唯一索引，已有则跳过；或新库场景整体跳过 m015 的索引创建。

### Issue 4: LWW 失效场景（不同 hash_id + 相同业务 UNIQUE 字段）无测试覆盖

- **类型**: Testing
- **置信度**: 80
- **位置**: `test/core/integration/repository/test_sync_repository.py`（`TestHashIdSyncDedup` 类，约 836-1156 行）
- **详情**: 现有测试只覆盖"相同 hash_id + 不同 updated_at"的 LWW 去重（如 `test_upsert_rows_with_lww_skips_older_data_by_hash_id`），未覆盖"不同 hash_id + 相同业务 UNIQUE 字段"的冲突场景——即 Issue 1 的回归点。这是变更前（按业务 UNIQUE 去重）能正确处理、变更后（按 hash_id 去重）失效的场景，缺少测试意味着该回归无法被捕获。`user_app_behavior_log` 仍保留 `UNIQUE(app, start_time)`、`time_paradoxes` 仍保留 `UNIQUE(user_id,mode,version)`，这些表的两端独立创建相同业务键但不同 hash_id 的记录时，LWW 查不到匹配 → 放行 → INSERT OR REPLACE 触发业务 UNIQUE 替换 → 旧数据覆盖新数据。
- **依据**: PRD 验收标准"upsert_rows_with_lww 对在 HASH_ID_PREFIXES 中的表用 hash_id 作去重键"；PRD Testing Decisions 要求覆盖 LWW 去重。Architecture Agent 与 Best Practices Agent 独立确认该场景为真实回归（Issue 1）。
- **修复建议**: 新增测试：对 `user_app_behavior_log`/`time_paradoxes` 等仍带业务 UNIQUE 的表，构造两条不同 hash_id 但相同业务 UNIQUE 字段、不同 updated_at 的记录，断言较新数据不被较旧数据覆盖（当前实现该测试应失败，即暴露 Issue 1）。

## 变更摘要

本次变更是"数据库删除同步"任务链的**第 1 步（共 3 步）**，只做 schema 变更与同步去重逻辑调整，不涉及 Provider 迁移、不涉及墓碑同步流程：

1. **6 张 AUTOINCREMENT 表新增 `hash_id` 字段**（`TEXT NOT NULL UNIQUE`，12 位 hex + 表名前缀）：`timeline_custom_block`/`time_paradoxes`/`mood_impacts`/`habit_chains`/`habit_chain_nodes`/`user_app_behavior_log`，作为跨端稳定的同步专用标识。
2. **`time_paradoxes` id 改为 AUTOINCREMENT**（该表未投入使用）。
3. **新增 `deletion_log` 墓碑表**（`target_table` + `record_id` + `source` + 时间戳，`update_at: True`），加入 `SYNC_TABLES`。
4. **迁移脚本 m015**：ALTER + 回填 + CREATE UNIQUE INDEX 为旧库回填 hash_id（参考 m012 风格）。
5. **`HASH_ID_PREFIXES` 字典**集中在 `lifeprism/sync/constants.py`，同时作为"哪些表需要 hash_id"的判断依据。
6. **`_generic_insert` 兜底生成 hash_id**：`HASH_ID_PREFIXES.get(table_name)` 判断，未传入则生成。
7. **`get_unique_fields` 改造**：对 `HASH_ID_PREFIXES` 中的表返回 `["hash_id"]`，使 `upsert_rows_with_lww`/`_batch_get_existing_updated_at_by_unique`/`_find_existing_updated_at` 自动用 hash_id 作 LWW 去重键。
8. **`habit_chains`/`habit_chain_nodes` 从 `SYNC_TABLES` 移除**（chain_id 引用自增 id，同步后外键断裂），但 `HASH_ID_PREFIXES` 仍含这两表（hash_id 照加，为恢复同步做准备）。

核心设计：hash_id 定位为"同步专用标识"而非主键，`_PRIMARY_KEY` 保持自增 id 不变，本地 CRUD 无感知。

## 已过滤的低分项（< 80，未展开）

- TODO PRD 编号不一致（`constants.py:19` 标 "PRD 2" vs ADR `habit-chain-tables-not-synced.md:126` 标 "PRD 3"，ADR 自身 57/116/129 与 126 矛盾）— 文档笔误，置信度 75
- m015 `_backfill_row_hash_id` 的 IntegrityError 重试逻辑不可达（回填时无 UNIQUE 约束），真正冲突点 `CREATE UNIQUE INDEX` 无重试 — 死代码 + 注释误导，触发概率极低，置信度 75
- `hash_id` 生成表达式 `f"{prefix}{uuid.uuid4().hex[:12]}"` 在 `_generic_insert` 与 m015 两处重复 — 漂移风险，置信度 72
- `time_paradoxes` 旧库 id 未改 AUTOINCREMENT（m015 未处理），配置与实际 schema 不一致 — ADR 声明该表未投入使用，置信度 45
- m015 逐行 UPDATE 性能（user_app_behavior_log 大表）— 个人级数据可接受，置信度 45
- 迁移未在旧库复制 NOT NULL 约束（schema 偏差）— SQLite ALTER TABLE 限制，ADR 已承认的权衡，置信度 32
- hash_id 传入 None/空字符串边界、m015 新库场景未测试 — 置信度 45-65
