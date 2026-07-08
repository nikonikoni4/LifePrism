# 本地同步客户端 - 基础同步逻辑

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

实现 Windows 本地的同步客户端，执行 Pull + Push 双向同步，应用 Last-Write-Wins 冲突解决策略。

**实现端到端**：
1. 新增 `lifeprism/sync/sync_client.py`
2. 实现 `SyncClient` 类：
   - `sync_once()` - 执行一次完整同步（Pull → Push）
   - `pull_from_remote()` - 拉取云端数据，应用 Last-Write-Wins
   - `push_to_remote()` - 推送本地数据
3. **本地数据库操作通过 `SyncRepository`**（Issue #03 创建）：
   - **编码规范要求**：不得在非 repository 的任何位置直接编写 SQL
   - 本地增量查询调用 `sync_repository.query_incremental()`
   - 本地批量写入调用 `sync_repository.upsert_rows()`
   - SyncClient 自身只负责 HTTP 通信和冲突解决逻辑，不直接执行 SQL
4. Last-Write-Wins 冲突解决逻辑：
   - 比较 `updated_at` 时间戳
   - 本地未修改（`local.updated_at <= last_sync_time`）→ 覆盖
   - 本地已修改 → 比较时间戳，谁更晚谁保留
5. **数据库写入策略 - 按主键类型分类处理**：

   `TABLE_CONFIGS` 中没有 `_PRIMARY_KEY` 字段，主键信息嵌套在 `columns[name]["constraints"]` 列表中（值为 `"PRIMARY KEY"`）。需编写解析函数从 `columns` 中提取主键字段名。

   同步范围内的表按主键类型分为 3 类，每类采用不同写入策略：

   **Category A：TEXT 主键（跨实例稳定，`INSERT OR REPLACE` 安全）**
   - `mood_entries`（id: TEXT）、`diary`（date: TEXT）、`todo_list`（id: TEXT）
   - `goal`（id: TEXT）、`habits`（id: TEXT）、`behavior_analysis`（start_time: TEXT）
   - `category`（id: TEXT）、`sub_category`（id: TEXT）
   - `multi_purpose_map_cache`（id: TEXT）、`single_purpose_map_cache`（id: TEXT）
   - **策略**：直接 `INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})`，按主键判断存在性

   **Category B：AUTOINCREMENT 主键 + UNIQUE 约束（id 本地生成，用 UNIQUE 约束判重）**
   - `user_app_behavior_log`（id AUTOINCREMENT，UNIQUE(app, start_time)）
   - `category_map_cache`（id AUTOINCREMENT，UNIQUE(app, title, state)）
   - **策略**：`INSERT OR REPLACE` 传入完整行数据（含远程 id）。SQLite 遇到 UNIQUE 约束冲突时会删除旧行再插入新行，逻辑记录被正确覆盖。本地 `id` 会变化，但经验证无外键引用这两张表的 `id`，不会破坏引用完整性
   - **注意**：传入的远程 `id` 可能与本地 AUTOINCREMENT 序列冲突，但由于 UNIQUE 约束优先判重，不会产生逻辑错误

   **Category C：AUTOINCREMENT 主键，无 UNIQUE 约束（需补充约束）**
   - `timeline_custom_block`（id AUTOINCREMENT，无 UNIQUE 约束）
   - **问题**：`INSERT OR REPLACE` 按远程 `id` 判断存在性，但本地和远程的 `id` 独立自增，同一逻辑记录的 `id` 不同，会导致重复插入或错误覆盖
   - **解决方案**：在 Issue #01 的迁移脚本中，为 `timeline_custom_block` 添加 `UNIQUE(start_time)` 约束（两个自定义时间块不应有相同开始时间）。添加约束后归入 Category B 策略
   - **如果无法添加约束**：排除该表出同步范围，在 PRD 中标注为 P3

6. 主键解析函数实现（放在 `SyncRepository` 中）：
   ```python
   def get_primary_key_field(table_config: dict) -> str | None:
       """从 TABLE_CONFIGS 的 columns 中解析主键字段名"""
       for col_name, col_config in table_config["columns"].items():
           if "PRIMARY KEY" in col_config.get("constraints", []):
               return col_name
       return None
   ```
7. 原子性保证：只有全部成功才更新 `last_sync_time`
8. 集成到 `main.py` 启动流程（启动时立即同步）
9. 单元测试（同步逻辑、冲突处理、原子性、三类主键表）

---

## Acceptance criteria

- [ ] `SyncClient` 类已实现，包含 `sync_once()`、`pull_from_remote()`、`push_to_remote()`
- [ ] **SyncClient 不直接执行 SQL**，所有数据库操作通过 `SyncRepository`
- [ ] Last-Write-Wins 冲突解决逻辑正确：
  - 本地未修改时，云端数据覆盖本地
  - 本地已修改时，比较时间戳
- [ ] **主键解析函数正确实现**：
  - 从 `TABLE_CONFIGS[table]["columns"]` 的 `constraints` 列表中解析 `"PRIMARY KEY"`
  - 不依赖不存在的 `_PRIMARY_KEY` 字段
- [ ] **三类表的写入策略正确**：
  - Category A（TEXT 主键）：`INSERT OR REPLACE` 按主键工作
  - Category B（AUTOINCREMENT + UNIQUE）：`INSERT OR REPLACE` 依赖 UNIQUE 约束判重
  - Category C（AUTOINCREMENT 无 UNIQUE）：已添加 UNIQUE 约束或排除出同步范围
- [ ] 原子性保证：部分失败时不更新 `last_sync_time`
- [ ] 启动时自动同步（集成到 `main.py`）
- [ ] 单元测试通过：
  - 测试 Pull 插入新记录
  - 测试 Pull 覆盖本地未修改记录
  - 测试 Pull 保留本地更新记录
  - 测试 Push 推送本地变更
  - 测试部分失败时不更新 `last_sync_time`
  - **测试 `diary` 表同步（Category A，主键 `date`）**
  - **测试 `user_app_behavior_log` 表同步（Category B，UNIQUE(app, start_time) 判重）**
  - **测试 `timeline_custom_block` 表同步（Category C，依赖新增的 UNIQUE(start_time) 约束）**

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/03-sync-api-pull.md`
- `.scratch/linux-deployment-discussion/issues-p2/04-sync-api-push.md`
