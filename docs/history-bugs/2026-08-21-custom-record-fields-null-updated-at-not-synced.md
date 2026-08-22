---
version: 1.2
created_at: 2026-08-21
updated_at: 2026-08-21
last_updated: 5.1 三处代码修复已按 TDD 落地（红→绿），复现测试见 5.1 各测试位置
abstract: create_type 写 custom_record_fields 时漏写 updated_at，字段行 updated_at 为 NULL，增量同步 WHERE updated_at > ? 永远查不到 NULL 行，云端缺失字段定义导致 create_custom_record_entry 报 INVALID_FIELD_KEY。
---

# custom_record_fields 字段行 updated_at 为 NULL 导致增量同步丢失

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |
| 1.1 | 独立审查修正：tokens_usage_log NULL 的真正来源是 save_tokens_usage（非 batch_insert_tokens_usage 死代码）；新增第三处漏写路径 raw_behavior_analysis_provider；根本方案补充 data_initializer 种子 INSERT 对 DDL DEFAULT 的硬依赖 |
| 1.2 | 5.1 三处代码修复已按 TDD 落地（先写失败测试复现 NULL，再修复转绿） |

## 1. Bug 简述

`CustomRecordRepository.create_type` 写入 `custom_record_fields` 时 INSERT 列清单漏写 `updated_at`，该列在旧表结构中无 DEFAULT（m012 迁移用 `ALTER TABLE ADD COLUMN` 补列，SQLite 限制不能加非常量默认值），导致字段行 `updated_at` 存入字面 NULL。增量同步 `query_incremental` 的 `WHERE updated_at > ?` 中 `NULL > ?` 恒为假，NULL 行永远不被推送。云端只收到类型行和数据行（各自正确写了 updated_at），唯独缺失字段定义行，云端 Agent 调用 `create_custom_record_entry` 时 `_get_fields_by_type_id` 查不到字段，报 `INVALID_FIELD_KEY ... valid_fields: []`。

## 2. 复用场景

- 排查"本地创建的自定义记录类型同步后云端查不到字段 / create_custom_record_entry 报 INVALID_FIELD_KEY 且 valid_fields 为空"时阅读
- 排查"某行数据本地存在、云端永远缺失、但无任何同步错误日志"（NULL updated_at 静默不可见）时阅读
- 为 SYNC_TABLES 中的表编写**手写 SQL** 的 INSERT 路径（绕过 `LWBaseDataProvider._generic_insert` 的时间注入）时阅读
- 编写 `ALTER TABLE ADD COLUMN updated_at` 类迁移脚本（无 DEFAULT 的 NULL 陷阱）时阅读
- 排查 `tokens_usage_log` 表大量 `updated_at IS NULL` 行（同一 bug 类：`save_tokens_usage` 只注入 created_at 未注入 updated_at，每次 LLM 调用产生一行）时阅读
- 排查 `raw_behavior_analysis` 表新写入行不同步（同一 bug 类：`_insert_analysis` 漏写 updated_at）时阅读
- 讨论"updated_at 列是否应改为 NOT NULL"的 schema 根本治理方案（含 data_initializer 种子数据对 DDL DEFAULT 的依赖）时阅读

## 3. 代码位置

| 位置 | 说明 |
| ---- | ---- |
| `lifeprism/repository/aggregators/custom_record_aggregator.py` `create_type` 第 209-221 行 | **bug 源头**：`INSERT INTO custom_record_fields (id, type_id, field_name, field_key, field_type, sort_order, created_at)` 漏写 `updated_at` 列；同方法第 199-203 行写 `custom_record_types` 时显式写了 `created_at, updated_at`（对照组） |
| `lifeprism/repository/sync_repository.py` `query_incremental` 第 275 行 | 机制链：`SELECT * FROM {table} WHERE updated_at > ?`，NULL 行恒不命中 |
| `lifeprism/repository/migrations/scripts/m012_add_updated_at_to_sync_tables.py` 第 63 行 | `ALTER TABLE ... ADD COLUMN updated_at TIMESTAMP`，无 DEFAULT 无 NOT NULL，INSERT 省略该列时存入 NULL（同类迁移还有 m006/m007/m013，合计覆盖 16 张表） |
| `lifeprism/repository/base_providers/lw_base_data_provider.py` `save_tokens_usage` 第 837-884 行 | 同一 bug 类的第二实例（**v1.0 误判为 tokens_usage_provider.batch_insert_tokens_usage，实为其无生产调用方**）：第 869-871 行只注入 `created_at` 不注入 `updated_at`，第 865 行注释"无 update_at"已过时；调用链 `llm_usage_db_provider.py:69`（每次 LLM 调用）+ `data_processing_service.py:445`，产生 437 行 NULL |
| `lifeprism/repository/providers/raw_behavior_analysis_provider.py` `_insert_analysis` 第 187-198 行 | 同一 bug 类的第三实例：INSERT 列 `(start_time, end_time, behavior, screen_count, created_at)` 漏写 `updated_at`，该表在 SYNC_TABLES 且属 m012 无 DEFAULT 列，**持续产生新 NULL 行** |
| `lifeprism/repository/base_providers/lw_base_data_provider.py` 第 1244-1248 行 | 正确范例：`_generic_update` 已注入 `get_utc_now_iso()`；基类 insert 路径无此问题，问题仅在手写 SQL 绕过基类处 |
| `lifeprism/repository/lw_table_manager.py` 第 79-83 行 | 隐患：DDL 生成 `updated_at TIMESTAMP DEFAULT (datetime('now'))`，SQLite 格式（空格分隔无时区）与应用层 ISO 8601 混用会错乱增量水位 |
| `lifeprism/config/data_initializer.py` 6 处种子 INSERT | 根本方案的前置依赖：category/sub_category/goal/plan_doc/mood_types/mood_impacts 的种子 INSERT 全部不含时间戳列，硬依赖 DDL DEFAULT 填充 |

## 4. 发生原因

机制链（每一环都必要，缺一不会发病）：

1. **源头漏写**：`create_type` 手写 SQL 绕过 provider 基类的时间注入，`custom_record_fields` 的 INSERT 列清单不含 `updated_at`。
2. **列无兜底**：本地库的 `custom_record_fields.updated_at` 列由 m012 迁移（2026-07-15 上线）用 `ALTER TABLE ADD COLUMN updated_at TIMESTAMP` 补出，SQLite 限制 ALTER 不能加非常量默认值，列 nullable 无 DEFAULT → INSERT 省略该列存入字面 NULL。
3. **NULL 不可见**：增量 push 走 `query_incremental`（`WHERE updated_at > ?`），SQL 中 `NULL > ?` 恒为假 → NULL 行永远不会被增量推送，且无任何错误日志（静默丢失）。
4. **云端表结构正常但 meta 缺行**：云端数据表由 `rebuild_dynamic_tables` 按 DDL 重建（只建结构不写 meta 行），类型行和数据行各自正确写了 updated_at 正常推送 → 出现"类型行在、数据表在、数据在、唯独字段定义行缺失"的分裂现象。
5. **云端 DEFAULT 不生效**：云端库新表虽有 `DEFAULT (datetime('now'))`，但同步 push 是显式 INSERT 所有列（含 NULL），DEFAULT 不参与，NULL 原样穿透。

历史背景（为什么部分字段行有值）：2026-07-15 m012 上线前的旧行由迁移一次性回填 `updated_at = created_at`（毫秒位全 .000）；上线后新创建的类型（锻炼 07-21、支出 07-22、预算池 08-18）全靠应用层写入，而 `create_type` 恰好漏写 → 全部 NULL。锻炼/支出赶上首次全量同步（`query_all` 不过滤 NULL）侥幸到达云端；预算池只走增量通道，彻底丢失。

## 5. 最佳方案

### 5.1 立即修复（代码，3 处补列）

**修复点 1**：`custom_record_aggregator.py` `create_type` 中 `custom_record_fields` 的 INSERT 列清单从

```python
(id, type_id, field_name, field_key, field_type, sort_order, created_at)
```

改为

```python
(id, type_id, field_name, field_key, field_type, sort_order, created_at, updated_at)
```

值用同事务的 `now` 变量（ISO 8601 + UTC）。参照同文件 `create_entry`（第 564-566 行）的正确写法。

测试要求（TDD 先行）：`test/core/integration/repository/test_custom_record_aggregator_utc.py` 增加断言——`create_type` 后 `custom_record_fields` 新行的 `updated_at` 非空且匹配 `UTC_ISO_PATTERN`。

**修复点 2**（v1.1 修正）：`lw_base_data_provider.py` `save_tokens_usage`（第 837-884 行）在注入 `created_at` 的同时注入 `updated_at`（同值），并修正第 865 行过时注释。**不要修 `batch_insert_tokens_usage`——它是无生产调用方的死代码**（v1.0 的定位错误，见审查报告）。

**修复点 3**（v1.1 新增）：`raw_behavior_analysis_provider.py` `_insert_analysis`（第 187-198 行）INSERT 列清单补 `updated_at`（与 `created_at` 同值）。该表在 SYNC_TABLES，不修则每次数据分析持续产生新 NULL 行。

### 5.2 存量修复（数据回填）

回填值必须**大于当前 last_sync_time**（存于 config.yaml 的 `sync.last_sync_time`，UTC ISO 8601），否则回填后仍不会推送。2026-08-21 实际使用的回填值（北京时间 8-21 10:00 = UTC 02:00）：

```sql
-- 本地生产库（D:\数据文档\lifeprismData\dataset\lifewatch_ai.db）
UPDATE custom_record_fields
SET updated_at = '2026-08-21T02:00:00.000000+00:00'
WHERE updated_at IS NULL;

UPDATE tokens_usage_log
SET updated_at = '2026-08-21T02:00:00.000000+00:00'
WHERE updated_at IS NULL;

-- v1.1 新增：raw_behavior_analysis 持续产生 NULL，需一并回填
UPDATE raw_behavior_analysis
SET updated_at = '2026-08-21T02:00:00.000000+00:00'
WHERE updated_at IS NULL;
```

v1.1 补充：回填前建议对全部 SYNC_TABLES 做 NULL 行普查（重点 m006/m007/m012/m013 四个 ALTER 加列迁移覆盖的 16 张表），按普查结果确定回填范围，不要只盯事故表。

云端库对已到达的 NULL 行（锻炼/支出字段行）执行相同回填，避免后续 LWW 比较边界问题；预算池 6 行靠本地同步推送到达，**不要**云端手工 INSERT。固定回填值设计已验证正确：云端 LWW 分支对 incoming 非 NULL 值正常放行，pull 回程时本地同值被 LWW 跳过，无副作用。

回填后验证：下次同步完成后云端执行 `SELECT field_key, updated_at FROM custom_record_fields WHERE type_id='crt-df3979d5' ORDER BY sort_order;` 应返回 6 行；云端 Agent 原参数调用 `create_custom_record_entry` 应成功。

### 5.3 根本方案：updated_at 全表 NOT NULL（必写）

**结论：把所有同步表的 updated_at 改为 NOT NULL（且不配 DDL DEFAULT）能从根本上解决这一类 bug**——它把"静默的数据不可同步"转化为"写入时的硬错误（IntegrityError）"，任何新代码路径漏写都会当场暴露而不是数周后在云端发作。但必须四件事同时做，缺一会变形为另一种隐蔽 bug或直接崩溃：

1. **NOT NULL 必须配合"去掉 DDL DEFAULT"**。若保留 `DEFAULT (datetime('now'))`，漏写时会静默写入 SQLite 格式时间（`2026-08-21 02:00:00`，空格分隔无时区），与应用层 ISO 8601（`2026-08-21T02:00:00.000000+00:00`）混用；`query_incremental` 是字符串比较，同一天内 `" " < "T"`，增量水位判断会错乱。修改点：`lw_table_manager.py` 第 79-83 行 timestamps 列生成改为 `NOT NULL` 无 DEFAULT。v1.1 澄清：生产 NULL 的直接根因是 ALTER 加列无 DEFAULT（DEFAULT 反而会填值），去 DEFAULT 的真正价值是**配合 NOT NULL 让漏列 INSERT 显性报错**，而非消灭 NULL。
2. **前置改造 data_initializer（v1.1 新增，P1）**。`data_initializer.py` 6 处种子 INSERT（category/sub_category/goal/plan_doc/mood_types/mood_impacts）全部不含时间戳列，硬依赖 DDL DEFAULT 填充。直接去 DEFAULT + NOT NULL 会让**新库首次启动即崩溃**（NOT NULL constraint failed）。必须先改造种子写入（显式注入双时间戳或走 `_generic_insert`），再动 schema。
3. **存量表需表重建迁移**。SQLite 的 `ALTER TABLE ADD COLUMN` 不能加"NOT NULL 且无 DEFAULT"的列，SYNC_TABLES 的 29 张静态表 + 存量动态表需一次性迁移（新建表 → copy 数据 → drop → rename，参考 m008 全表重建迁移的先例），迁移中顺手回填 NULL 行（`updated_at = COALESCE(updated_at, created_at, 迁移时间)`）并清洗 m007 遗留的 `datetime('now','localtime')` 本地时区格式存量（goal_journal/daily_focus/weekly_focus）。动态表 DDL 生成函数 `generate_create_table_ddl`（custom_record_aggregator.py 第 68-91 行）也应同步改为 `NOT NULL`（只影响新建动态表，存量动态表靠表重建迁移覆盖）。`file_sync_state` 已是"NOT NULL 无 DEFAULT + 应用层注入"模式的成功先例，佐证此方案可行。
4. **补齐现有手写 SQL 路径并加契约测试**。5.1 的三处修复必须先落地，否则 NOT NULL 上线后这些路径立即报错。再加一道防御性测试：用 `pytest.mark.parametrize` 对 SYNC_TABLES 29 张表断言"INSERT 不含 updated_at 的行应失败"（单测试函数覆盖，从 TABLE_CONFIGS 解析 NOT NULL 列自动构造最小合法行），防止未来新表漏配。注意契约测试只守护新 DDL/重建后的表，存量旧库的守卫必须靠表重建迁移。

分层防御总结：Schema 层 NOT NULL（fail-fast 兜底）＞ 应用层基类注入（主路径）＞ 手写 SQL 显式写（直写路径）＞ 契约测试（防回归）。

### 沉淀教训

- 增量同步体系中，`updated_at IS NULL` 的行是"幽灵行"：查询、日志、错误全无感知，属于最危险的静默失败。所有走 `updated_at >` 水位查询的表，其 updated_at 必须有 NOT NULL 约束兜底。
- 绕过基类时间注入的直写路径是漏写源头（全项目共三处：custom_record_aggregator.create_type、lw_base_data_provider.save_tokens_usage、raw_behavior_analysis_provider._insert_analysis）；新写直写路径时必须对照基类 `_generic_insert/_generic_update` 的时间注入行为。**修复定位前先查调用链确认活跃路径**——batch_insert_tokens_usage 是死代码，修它不能止血（v1.0 教训）。
- 不要依赖 DDL 的 `DEFAULT (datetime('now'))` 兜底：它生成的时间格式与应用层 ISO 8601 不一致，会引入第二种格式分裂 bug。
- 改 schema 约束前先审计 DEFAULT 的依赖方：data_initializer 种子数据这类"隐式依赖 DEFAULT"的路径，会在去 DEFAULT + NOT NULL 后变成启动崩溃。
