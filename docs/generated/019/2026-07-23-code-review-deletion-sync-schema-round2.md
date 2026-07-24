# Code Review Report (Round 2 — 修复后重新审查)

**审查范围**: 同步删除阶段1 - Schema 变更（hash_id + 墓碑表），修复原始审查 4 个 ≥80 问题后的当前工作区代码
**原始报告**: `docs/generated/019/2026-07-22-code-review-deletion-sync-schema.md`
**审查时间**: 2026-07-23
**变更文件**: 12 个修改文件 + 新增 m015/9 个测试文件 + 4 个 ADR + 1 个 known-limitation

## 审查方法

8 维度并行审查:Security / Performance / Architecture / Code Quality / Best Practices / Testing / Documentation / 代码注释合规。置信度 ≥ 80 保留,< 80 过滤但列在末尾。所有结论已验证到具体文件/行号。

## 修复验证摘要

| 原始 Issue | 修复状态 | 说明 |
|-----------|---------|------|
| Issue 1 (LWW 被 INSERT OR REPLACE 绕过, 90) | **已修复** | 表级 UNIQUE 已修 + 列级 UNIQUE(`mood_impacts`)也已修(2026-07-23) |
| Issue 2 (`last_updated_at` → `last_updated`, 85) | **已修复** | 4 个 ADR frontmatter 现全部为 `last_updated:` |
| Issue 3 (m015 新库冗余索引, 82) | **已修复** | 新增 `_has_unique_index_on_hash_id` 检测 sqlite_autoindex_*,新库跳过 CREATE INDEX |
| Issue 4 (LWW 失效回归测试, 80) | **仅部分修复** | 仅 `timeline_custom_block` 和 `user_app_behavior_log` 有端到端 LWW 测试;`time_paradoxes` 只测元数据解析未测端到端 LWW;`mood_impacts` 回归场景完全缺失 |

修复暴露出更严重的**架构级问题**:hash_id 兜底仅在 `_generic_insert` 一处,而项目中存在 6+ 处**直接 INSERT 绕过该方法**的写入路径。新库启动会因 `NOT NULL UNIQUE` 约束触发失败。

## 审查结果

Found 6 issues(置信度 ≥ 80),按严重程度排序:

---

### Issue 1: hash_id 兜底仅覆盖 _generic_insert,新库启动会因默认数据初始化失败 (P0 阻断)

- **类型**: Architecture / Best Practices(正确性)
- **置信度**: 100
- **位置**:
  - 兜底逻辑: `lifeprism/repository/base_providers/lw_base_data_provider.py:1145-1156`
  - 绕过路径 1: `lifeprism/repository/data_initializer.py:466`(默认 mood_impacts 初始化,不带 hash_id)
  - 绕过路径 2: `lifeprism/repository/providers/mood_providers.py:512`(create_mood_impact 手写 INSERT)
  - 绕过路径 3: `lifeprism/repository/base_providers/lw_base_data_provider.py:814`(save_user_app_behavior_log 批量 INSERT OR IGNORE)
  - 绕过路径 4: `lifeprism/server/providers/being_provider.py:192`(time_paradoxes create 手写 INSERT)
  - 绕过路径 5: `lifeprism/repository/providers/habit_chain_providers.py:100`
  - 绕过路径 6: `lifeprism/repository/providers/habit_chain_providers.py:281`
  - Schema 声明: `database.py:184-187, 685-688, 926-929, 1092-1095, 1312, 1339`(全部 `NOT NULL UNIQUE`)

- **详情**: 修复方案将 hash_id 自动生成放在 `_generic_insert` 中,但项目实际上有多个 Provider 完全不走 `_generic_insert`,而是手写 `INSERT INTO ...` SQL。这些路径没有生成 hash_id,与 6 张表 schema 的 `NOT NULL UNIQUE` 声明冲突。

- **失败场景**:
  1. **新库启动 → 立即失败**:`init_database` 建表后,`data_initializer._initialize_default_mood_impacts()` 执行 `INSERT INTO mood_impacts (name, sort_order) VALUES (?, ?)` — 缺少 hash_id → SQLite 抛 `NOT NULL constraint failed: mood_impacts.hash_id` → 数据库初始化中止 → 应用无法启动。
  2. **旧库启动 → 静默产生无效记录**:m015 迁移后 hash_id 列允许 NULL(SQLite 无法直接加 NOT NULL 列),上述直写路径将持续插入 NULL hash_id 的记录,无法参与同步/删除映射。
  3. **BeingProvider create() → 抛 NOT NULL 错误**:PRD 声称 time_paradoxes 未投入使用,但 `create()` 存在且 API 层可能调用。
  4. **user_app_behavior_log 批量写入失败**:监控模块每次批量写入行为日志会全部失败。

- **依据**:
  - `_generic_insert` 兜底逻辑第 1152-1156 行仅在该函数被调用时生效
  - `data_initializer.py:459-471` 使用 `cursor.execute("INSERT INTO mood_impacts (name, sort_order)...")` — 直接 SQL
  - `save_user_app_behavior_log` 使用 `INSERT OR IGNORE INTO user_app_behavior_log`(第 814 行)
  - `being_provider.py:192` 使用 `f"INSERT INTO {self.TABLE_NAME} ..."` 拼接 SQL

- **修复建议**:
  1. **紧急**:所有直接 INSERT 的路径必须在插入前调用共享的 `generate_hash_id(table_name)` 函数补齐 hash_id
  2. **根本**:抽取 `generate_hash_id(prefix: str) -> str` 到 `lifeprism/sync/hash_id.py`(供 Provider 和 m015 共用),并统一让 mood/habit_chain/being/user_app_behavior 的直写路径迁移到 `_generic_insert` 或显式调用 `generate_hash_id`
  3. **测试**:新增 "全新数据库启动 → data_initializer 完成" 冒烟测试,任何未生成 hash_id 的路径都会被暴露

---

### Issue 2: mood_impacts 的 LWW 保护仍被 INSERT OR REPLACE 绕过(Issue 1 只部分修复)

- **类型**: Architecture / Best Practices(正确性)
- **置信度**: 100
- **位置**:
  - Schema 声明: `lifeprism/config/database.py:1097-1100`(`name` 列级 `NOT NULL UNIQUE`)
  - `table_constraints` 为空: `lifeprism/config/database.py:1108`
  - `get_unique_fields`: `lifeprism/repository/sync_repository.py:898-916`(仅解析 `table_constraints`,不解析列级 UNIQUE → 回退 hash_id)
  - REPLACE 触发点: `lifeprism/repository/sync_repository.py:525`

- **详情**: 原始 Issue 1 的修复方案是"业务 UNIQUE 优先于 hash_id",但实现只解析 `table_constraints` 中的表级 UNIQUE。`mood_impacts.name` 是列级 UNIQUE(在 columns dict 内声明 constraints,不在 table_constraints),因此 `get_unique_fields("mood_impacts")` 仍回退到 `["hash_id"]`。而 `INSERT OR REPLACE INTO mood_impacts` 仍会因 `UNIQUE(name)` 触发替换 → 与原始 Issue 1 完全相同的绕过路径。

- **失败场景**: 两台设备独立创建 `name="工作"` 但 hash_id 不同的记录:
  1. B 设备:`{name="工作", hash_id="mi-B", updated_at=T2}`(新)
  2. A 设备推送:`{name="工作", hash_id="mi-A", updated_at=T1}`(旧)
  3. `upsert_rows_with_lww` 按 hash_id=mi-A 查找 → B 没有 mi-A → 放行
  4. `INSERT OR REPLACE` 触发 `UNIQUE(name)` 冲突 → 删 B 的 mi-B 行 → 插 A 的 mi-A 行
  5. 结果: **B 的较新数据被 A 的较旧数据静默覆盖**(与原始 Issue 1 相同)
- 该表当前 30 张同步表之一,回归影响真实。

- **依据**:
  - `get_unique_fields` docstring(sync_repository.py:880-886)明确声称"LWW 查找键必须与 REPLACE 键一致,否则较新数据被静默覆盖"—— docstring 与实现自相矛盾
  - `mood_impacts.name` 是列级 UNIQUE(第 1099 行 `constraints: ["NOT NULL", "UNIQUE"]`)
  - `SYNC_TABLES` 包含 `mood_impacts`(constants.py:44)
  - 新增测试 `test_get_unique_fields_returns_hash_id_for_mood_impacts`(第 907-910 行)只断言返回值,没有端到端 LWW 测试暴露该问题

- **修复建议**:
  1. `get_unique_fields` 增加列级 UNIQUE 解析(遍历 columns,收集除 hash_id 外的 UNIQUE 列)
  2. 或者补充 `table_constraints: ["UNIQUE(name)"]` 到 `MOOD_IMPACTS_CONFIG`(最小改动)
  3. 补 `mood_impacts` 端到端 LWW 回归测试暴露该问题

**修复状态**: 已修复(2026-07-23),详见 `docs/history-bugs/2026-07-23-mood-impacts-lww-bypass-by-column-level-unique.md`

---

### Issue 3: m015 迁移的 hash_id 冲突重试**永远不会触发**,真正的冲突点在最后 CREATE UNIQUE INDEX 时才抛出

- **类型**: Code Quality / Best Practices
- **置信度**: 98
- **位置**: `lifeprism/repository/migrations/scripts/m015_add_hash_id_to_autoincrement_tables.py:80-98, 112-131`

- **详情**: 迁移流程:
  1. ALTER ADD COLUMN(允许 NULL,无 UNIQUE 索引)
  2. 逐行 UPDATE 回填 hash_id — **此时没有 UNIQUE 约束**
  3. 完成回填后 `CREATE UNIQUE INDEX`

  第 2 步因为没有 UNIQUE 索引,即便生成相同 hash_id 也不会抛 `IntegrityError`。`_backfill_row_hash_id` 中捕获 `IntegrityError` 并重试的逻辑(第 121-127 行)在旧库首次迁移时**永远不会进入**。真正的冲突点是第 3 步 CREATE UNIQUE INDEX,一旦碰撞就会失败,整个迁移事务回滚,而这里**没有重试机制**。

- **失败场景**: 大表(如已有 50 万+ 行的 `user_app_behavior_log`)回填时 48 位随机(uuid.hex[:12] = 12 hex chars = 48 bit)碰撞概率约 0.18%。碰撞发生时:
  - UPDATE 全部成功(无 UNIQUE 索引)
  - CREATE UNIQUE INDEX 抛 UNIQUE constraint failed
  - 整个迁移事务回滚 → 应用启动失败
  - 下次启动重跑 m015,由于是随机 uuid,可能再次或再再次碰撞

- **依据**:
  - m015:80-86 逐行 UPDATE(索引尚未创建)
  - m015:94-97 索引创建在所有回填之后
  - m015:113-127 `_backfill_row_hash_id` 的 `except sqlite3.IntegrityError` — 该异常在此阶段不可能发生
  - Code Quality Agent、Best Practices Agent 独立指出

- **修复建议**:
  1. 调整顺序:ALTER → CREATE UNIQUE INDEX(索引在 NULL 列上允许多 NULL)→ 逐行 UPDATE(此时冲突会真正触发 IntegrityError 并重试)
  2. 或者删除死代码的重试逻辑,承认 m015 是"生成一次,不重试"策略,并接受极小的迁移失败概率
  3. 提高熵至 96+ bit(uuid.hex[:24] 或直接 uuid.hex)减少碰撞概率

---

### Issue 4: deletion_log 缺少 UNIQUE(target_table, record_id) 业务唯一键,ADR 声明的"跨端 LWW 处理重复墓碑"实际不成立

- **类型**: Architecture / Documentation(设计不一致)
- **置信度**: 95
- **位置**:
  - Schema: `lifeprism/config/database.py:1669-1695`(无 `table_constraints`)
  - `get_unique_fields`: `lifeprism/repository/sync_repository.py:898-916` 对 deletion_log 返回 None(既无 table_constraints UNIQUE 又不在 HASH_ID_PREFIXES)
  - ADR 声明: `docs/adr/2026-07-22-deletion-log-table.md:105-107, 186-187`(明确称跨端同时删除会用 LWW 处理重复墓碑)

- **详情**: `DELETION_LOG_CONFIG` 只有 id/target_table/record_id/source/时间戳,没有任何业务 UNIQUE 约束。两个设备删除同一记录时会各生成一个不同的 `dl-*` 主键墓碑,`get_unique_fields` 返回 None,`upsert_rows_with_lww` 按主键 id 匹配 → 找不到 → 全部作为新记录写入。

- **失败场景**:
  - A 删除 record_1 → 写入墓碑 `dl-A1`
  - B 也删除 record_1 → 写入墓碑 `dl-B2`
  - 双向同步后两台设备都有 `dl-A1` + `dl-B2` 两条墓碑
  - LWW 从未触发(不同 id 就是不同记录)
  - 墓碑重复删除操作被执行,墓碑表持续膨胀,ADR 承诺失效

- **依据**:
  - `DELETION_LOG_CONFIG` 完全没有 table_constraints(database.py:1693)
  - ADR "决策 3" 明确声称"LWW 按 updated_at 处理重复墓碑,新覆盖旧"(第 105-107 行)—— 与实现相反
  - Architecture / Best Practices / Testing Agent 三方一致指出

- **修复建议**:
  1. 添加 `"table_constraints": ["UNIQUE(target_table, record_id)"]` 到 `DELETION_LOG_CONFIG`
  2. `get_unique_fields("deletion_log")` 就会返回 `["target_table", "record_id"]`,LWW 与 INSERT OR REPLACE 键一致
  3. 或修订 ADR "决策 3",明确墓碑表不需要 LWW 去重,单独设计重复墓碑幂等消费机制
  4. 该问题会阻塞 PRD 3 的墓碑消费逻辑设计

---

### Issue 5: hash_id 兜底判断 `"hash_id" not in data` 无法防御 None/空字符串,会产生无效记录

- **类型**: Architecture / Code Quality
- **置信度**: 90
- **位置**: `lifeprism/repository/base_providers/lw_base_data_provider.py:1152-1156`

- **详情**: 兜底条件是 `"hash_id" not in data`,只检查 key 是否存在,不验证值。如果调用方传入:
  - `data["hash_id"] = None` → 新库触发 `NOT NULL constraint failed`(用户可见错误)
  - `data["hash_id"] = ""` → 空字符串通过 NOT NULL 但不通过 UNIQUE(第二条空字符串会冲突);m015 迁移后旧库允许 NULL,空字符串也能持久化
  - `data["hash_id"] = "invalid_format"` → 无格式校验,写入后无法区分 mi- 表或 tcb- 表

- **失败场景**: 前端表单/未来 Provider 代码传入 `{"hash_id": None, "name": "..."}`(可能因 dict 拷贝或 default 值)→ 新库直接抛 IntegrityError;旧库静默写入 NULL,同步/删除操作永久失效于该记录。

- **依据**: `_generic_insert:1153` 判断 `hash_prefix and "hash_id" not in data`

- **修复建议**:
  ```python
  # 更严格:值缺失、None、空字符串都触发生成
  if hash_prefix and not data.get("hash_id"):
      data["hash_id"] = generate_hash_id(hash_prefix)
  # 或者:非空但格式非法应抛 ValidationError
  ```

---

### Issue 6: docs/specs/2026-07-16-data-sync-core-spec.md 同步表清单未更新,新旧数量不一致

- **类型**: Documentation
- **置信度**: 100
- **位置**: `docs/specs/2026-07-16-data-sync-core-spec.md:295-303`

- **详情**: 第 295 行说"同步 30 张静态表",但 299-303 行仍列旧的 31 张组成(含 habit_chains/habit_chain_nodes,不含 deletion_log)。当前 `constants.py` 实际是 13 用户+8 元数据+3 Monitor+3 缓存+1 统计+1 wechat+1 deletion_log = 30 张。文档描述与代码不一致。

- **依据**: Documentation Agent 100 置信度确认,详细清单对比已给出。

- **修复建议**: 更新 spec 中同步表清单(移除 habit_chains/habit_chain_nodes,加 deletion_log),或者在该章节标注"清单延后到 PRD 2/3 更新"。

---

## 已过滤的低分项(< 80,未展开)

- m015 逐行 UPDATE 性能(user_app_behavior_log 大表可能几十万行)— 迁移体验影响,置信度 88-92
- m015 直接遍历运行时 HASH_ID_PREFIXES(迁移应是不可变历史)— 版本演进风险,置信度 91
- 12 位 UUID 后缀仅 48 bit 熵(百万级碰撞概率 0.18%)— 需提高至 96+ bit,置信度 90
- m015 docstring "部分索引语义" 描述错误(实际是普通 UNIQUE INDEX 允许多 NULL 的语义)— 注释误导,置信度 99
- 双 UNIQUE 键下 INSERT OR REPLACE 可同时删除多条记录 — 理论风险,置信度 95(与 Issue 2 相关)
- m015 docstring 中 `docs/ADR/...` 大小写错误(应为 `docs/adr/`)— 置信度 100
- m015 迁移终止前无 ERROR 日志(违反 CLAUDE.md 日志规范)— 置信度 84
- `_generic_insert` docstring 未描述 hash_id 副作用 — 置信度 84
- `get_unique_fields` 中 uuid 和 HASH_ID_PREFIXES 局部 import(无循环依赖)— 置信度 95
- `deletion_log` known-limitation 缺"版本"章节 — docs-write-rules 违规,置信度 98
- 恢复 habit chain 同步的 PRD 编号在 3 处不一致(PRD 2/PRD 3/PRD 2-3)— 置信度 100
- deletion_log updated_at 索引测试用 pytest.skip 掩盖缺失 — 置信度 90
- deletion_log 建表测试未验证 PRAGMA 中 pk/notnull 约束 — 置信度 84

## 建议修复优先级

1. **P0(立即修复)**: Issue 1(新库启动阻塞)
2. **P0(数据丢失)**: Issue 2(mood_impacts LWW 绕过)、Issue 4(deletion_log 无业务 UNIQUE)
3. **P1(迁移可靠性)**: Issue 3(m015 重试死代码 + CREATE INDEX 无重试)
4. **P1(接口健壮性)**: Issue 5(hash_id 兜底判空)
5. **P2(文档一致性)**: Issue 6(spec 同步表数量)

## 结论

原始 4 个 ≥80 问题中,Issue 2(ADR frontmatter)和 Issue 3(m015 冗余索引)已完全修复。Issue 1 只对表级 UNIQUE 修复,列级 UNIQUE(mood_impacts.name)仍存在同样的 LWW 绕过。Issue 4 只补了部分场景测试(timeline_custom_block、user_app_behavior_log),time_paradoxes/mood_impacts 端到端 LWW 测试仍缺失。

**修复过程暴露出更严重的 P0 阻断**:hash_id 兜底放在 `_generic_insert` 而项目有 6+ 处直接 INSERT 路径绕过,新库启动会立即失败。此外 deletion_log 表设计缺少业务 UNIQUE 约束,与 ADR 声明的"跨端 LWW 处理重复墓碑"完全矛盾,会阻塞 PRD 3 墓碑消费逻辑的正确性。

建议在开始 PRD 2 之前先修复 Issue 1、Issue 2、Issue 4,并补齐 Issue 3 的迁移可靠性。
