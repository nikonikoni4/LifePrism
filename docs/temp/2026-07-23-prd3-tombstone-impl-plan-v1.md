# PRD 3 墓碑同步流程 - 实现方案 v1

> 依据：`.scratch/deletion-sync-03-tombstone/prd.md` + 4 个 issue 文件（v2 已通过 subagent 审查）
> 日期：2026-07-23

## 一、当前代码状态盘点

### 已完成（Slice 01 代码层面）
- `lifeprism/repository/providers/deletion_log_provider.py` — DeletionLogProvider 完整实现：
  - `create_tombstone(target_table, record_id, source, created_at=None)` ✅
  - `write_tombstone_with_cursor(cursor, target_table, record_id, source="local")` ✅
  - `get_tombstones_since(last_sync_time, source=None)` ✅
  - `get_tombstone(target_table, record_id)` ✅
  - `cleanup_before(last_sync_time)` ✅
  - `_ON_CONFLICT = "ignore"` ✅
  - source 校验 `local/cloud` ✅
- `lifeprism/repository/providers/__init__.py` — `deletion_log_provider` 单例已注册 ✅
- `lifeprism/repository/__init__.py` — `deletion_log_repository` 别名已导出 ✅
- `test/core/unit/storage/test_deletion_log_provider.py` — S1 单元测试完整（8 个 seam）✅

### 待实现
| 项 | 状态 |
|----|------|
| `SYNC_TABLES` 移除 `deletion_log`（C2） | ❌ 仍在 SYNC_TABLES（constants.py:64） |
| `test_deletion_log_sync_membership.py` 翻转断言 | ❌ 仍断言 "in SYNC_TABLES" |
| `SyncRepository.execute_tombstone_delete`（M3/M4） | ❌ 不存在 |
| `sync_client._pull_deletion_log` | ❌ 不存在 |
| `sync_client._push_deletion_log` | ❌ 不存在 |
| `sync_client._cleanup_deletion_log` | ❌ 不存在 |
| `sync_once` 主流程集成 3 个新方法 | ❌ |
| `sync_cloud_api.py` 3 个专用端点（C1） | ❌ |
| `full-clear` 显式清空 deletion_log | ❌ 依赖 SYNC_TABLES 遍历 |
| `sync_status_api.py` 显式查询 deletion_log | ❌ 依赖 SYNC_TABLES 遍历 |
| `custom_record_aggregator.delete_entry` 写墓碑（C4） | ❌ 直接 DELETE 不写墓碑 |
| 端到端测试 `test_sync_deletion.py` | ❌ 不存在 |
| ADR `docs/adr/2026-07-22-deletion-sync-tombstone.md` | ❌ |
| spec 更新、known-limitations 更新、history-bugs 标记已修复 | ❌ |

## 二、实现策略

采用 TDD：每个 Slice 先写测试（红），再写实现（绿）。Slice 之间严格顺序依赖（01→02→03→04）。

### Slice 01：验证既有 + 修复 SYNC_TABLES 归属（C2）

DeletionLogProvider 代码已实现，本 slice 只做：
1. 从 `lifeprism/sync/constants.py` 的 `SYNC_TABLES` 移除 `"deletion_log"`（含注释）
2. 翻转 `test/core/unit/unit/sync/test_deletion_log_sync_membership.py`：
   - Seam 1 三个测试改为断言 `"deletion_log" not in SYNC_TABLES`
   - 类名/注释改为反映"墓碑走专用通道，不走 SYNC_TABLES"
3. 修改 `sync_cloud_api.py` 的 `full-clear` 端点：在 SYNC_TABLES 遍历之后，显式调用 `sync_repository.delete_all_rows("deletion_log")` 清空墓碑表
4. 修改 `sync_status_api.py` 的 `/status` 端点：`count_rows_batch(list(SYNC_TABLES))` 之后追加 `deletion_log` 计数

**风险**：移除 `deletion_log` 后，`_generic_delete` 中 `is_sync_table = self._TABLE_NAME in SYNC_TABLES` 对 `deletion_log` 表本身变为 False。但 `deletion_log` 表从不调用 `_generic_delete`（清理走 `cleanup_before` 直接 DELETE），无影响。

### Slice 02：墓碑 Pull + Push 集成 + SyncRepository 方法（C1/M3/M4/M5/M6/M7）

#### 2.1 `SyncRepository.execute_tombstone_delete`（M3/M4）
新增方法，依据 `HASH_ID_PREFIXES.get(target_table)` 判断列：
```python
def execute_tombstone_delete(self, target_table: str, record_id: str) -> int:
    """执行墓碑对应的目标表 DELETE，不写墓碑"""
    self._validate_table_name(target_table)
    from lifeprism.sync.constants import HASH_ID_PREFIXES
    if HASH_ID_PREFIXES.get(target_table):
        where_col = "hash_id"
    else:
        where_col = self.get_primary_key_field(target_table) or "id"
    sql = f"DELETE FROM {target_table} WHERE {where_col} = ?"
    # 执行 + 返回受影响行数
```
**注意**：动态表 `custom_*` 不在 HASH_ID_PREFIXES，`get_primary_key_field` 对动态表返回 `"id"`，正确。

#### 2.2 `sync_cloud_api.py` 3 个专用端点（C1）

**端点 1：`POST /api/sync/pull-deletion-log`**
- 请求：`{last_sync_time: str}`
- 云端：`deletion_log_repository.get_tombstones_since(last_sync_time)`（所有 source）
- 响应：`{tombstones: [...]}`

**端点 2：`POST /api/sync/push-deletion-log`**
- 请求：`{tombstones: [...]}`
- 云端对每条墓碑（单事务）：
  a. `deletion_log_repository.get_tombstone(target_table, record_id)` 查云端已有，有则跳过
  b. `sync_repository.execute_tombstone_delete(target_table, record_id)`
  c. `deletion_log_repository.create_tombstone(target_table, record_id, source='cloud', created_at=原墓碑.created_at)`
- 响应：`{success: bool, applied_count: int, skipped_count: int}`

**端点 3：`POST /api/sync/cleanup-deletion-log`**（Slice 03 使用，本 slice 先建空壳）
- 请求：`{last_sync_time: str}`
- 云端：`deletion_log_repository.cleanup_before(last_sync_time)`
- 响应：`{success: bool, cleaned_count: int}`

#### 2.3 `sync_client._pull_deletion_log`（M5/M6/M7）
```python
def _pull_deletion_log(self, remote_url, api_key, last_sync_time):
    # 1. HTTP 拉取（事务外）
    resp = httpx.post(f"{remote_url}/api/sync/pull-deletion-log",
                      json={"last_sync_time": last_sync_time}, ...)
    tombstones = resp.json()["tombstones"]
    # 2. 事务内处理
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        for t in tombstones:
            # LWW 跳过（M6）：本地已有同 (target_table, record_id) 墓碑则跳过
            local = deletion_log_repository.get_tombstone(t["target_table"], t["record_id"])
            if local is not None:
                continue
            # 执行 DELETE（M3/M4）
            self.sync_repository.execute_tombstone_delete(t["target_table"], t["record_id"])
            # 写本地副本（M7）：保留原 created_at
            deletion_log_repository.create_tombstone(
                t["target_table"], t["record_id"], source="cloud",
                created_at=t["created_at"])
        conn.commit()
```
**关键决策**：`deletion_log_repository` 是全局单例，它内部用自己的 db 连接。但本事务需要用同一 conn 保证原子性。**问题**：`get_tombstone`/`create_tombstone` 内部各自 `with self.db.get_connection()`，与外层事务不是同一连接，无法保证原子性。

**解决方案**：在 DeletionLogProvider 增加 `get_tombstone_with_cursor` 和 `create_tombstone_with_cursor` 方法（接受外部 cursor），供 `_pull_deletion_log` 事务内调用。这符合 Repository Pattern（SQL 封装在 Provider 内）。

> **这是方案 v1 新增的点**：issue 02 中只提到 `execute_tombstone_delete` 用 SyncRepository，但 `get_tombstone` 和 `create_tombstone` 在事务内调用需要 cursor 版本。否则事务边界失效。

#### 2.4 `sync_client._push_deletion_log`
```python
def _push_deletion_log(self, remote_url, api_key, last_sync_time):
    tombstones = deletion_log_repository.get_tombstones_since(last_sync_time, source="local")
    if not tombstones:
        return
    resp = httpx.post(f"{remote_url}/api/sync/push-deletion-log",
                      json={"tombstones": tombstones}, ...)
```
Push 是查询本地 + HTTP 推送，云端处理，无需本地事务。

#### 2.5 `sync_once` 主流程修改
在 `sync_once` 中（非 `_full_sync_to_cloud`）：
```python
if tables is None:
    dynamic_table_names = self._sync_dynamic_tables_definitions(remote_url, api_key)
    tables = list(set(SYNC_TABLES + dynamic_table_names))

# 【新增】墓碑 Pull（数据 Pull 之前）
self._pull_deletion_log(remote_url, api_key, last_sync_time)

self.pull_from_remote(remote_url, api_key, last_sync_time, tables)

# 【新增】墓碑 Push（数据 Push 之前）
self._push_deletion_log(remote_url, api_key, last_sync_time)

self.push_to_remote(remote_url, api_key, tables)
self._sync_files_full_flow(remote_url, api_key, last_sync_time, directories)
# Slice 03 在此插入 _cleanup_deletion_log
current_time = datetime.now(timezone.utc).isoformat()
set_setting("sync.last_sync_time", current_time)
```
**注意**：`_full_sync_to_cloud` 不调用墓碑方法（US20）。

#### 2.6 端到端测试（TEXT 主键表）
新建 `test/core/integration/sync/test_sync_deletion.py`：
- 场景 1：A 删除 TEXT 主键表记录（如 `mood_entries`）→ 同步 → B 记录消失
- 使用 mock HTTP 或直接调用 SyncClient 方法对两个本地 db 实例

### Slice 03：墓碑清理 + LWW + 失败处理

#### 3.1 `sync_client._cleanup_deletion_log`
```python
def _cleanup_deletion_log(self, remote_url, api_key, last_sync_time):
    # 1. 清理本地（用旧 last_sync_time）
    deletion_log_repository.cleanup_before(last_sync_time)
    # 2. 清理云端
    httpx.post(f"{remote_url}/api/sync/cleanup-deletion-log",
               json={"last_sync_time": last_sync_time}, ...)
```
**时机**：在 `_sync_files_full_flow` 之后、更新 `last_sync_time` 之前，用旧 `last_sync_time`。

#### 3.2 `sync_once` 集成清理
```python
self._sync_files_full_flow(...)
self._cleanup_deletion_log(remote_url, api_key, last_sync_time)  # 旧 last_sync_time
current_time = ...
set_setting("sync.last_sync_time", current_time)
```

#### 3.3 端到端测试扩展
- 墓碑清理在同步成功后执行
- 墓碑 LWW 冲突保留更晚 updated_at
- 墓碑同步失败 sync_once 失败，last_sync_time 未更新
- 墓碑 Pull 失败回滚

### Slice 04：边界场景 + 表类型覆盖 + 文档

#### 4.1 `custom_record_aggregator.delete_entry` 改造（C4）
```python
def delete_entry(self, type_id: str, entry_id: str) -> bool:
    _, data_table = self._get_type_and_table(type_id)
    try:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # 写墓碑（与 DELETE 同事务）
            deletion_log_provider.write_tombstone_with_cursor(
                cursor, data_table, entry_id, source="local")
            cursor.execute(f"DELETE FROM {data_table} WHERE id = ?", (entry_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
    ...
```
**注意**：`deletion_log_provider` 是全局单例，但其 `write_tombstone_with_cursor` 只用传入的 cursor，不碰自己的 db 连接，可安全使用。

#### 4.2 端到端测试扩展
- AUTOINCREMENT 表删除同步（`timeline_custom_block`，墓碑 record_id = hash_id）
- 级联删除同步（habit + challenges + checkins）
- 动态表删除同步（custom_*）
- 重置 last_sync_time 后墓碑仍工作
- 全量首同步不传播墓碑
- 多表批量删除同步
- 删除-更新冲突反向测试（已知限制预期行为）

#### 4.3 文档
- ADR `docs/adr/2026-07-22-deletion-sync-tombstone.md`
- 更新 `docs/specs/2026-07-16-data-sync-core-spec.md`（墓碑同步流程章节）
- 更新 `docs/known-limitations/`（文件删除不同步、删除-更新冲突、删除-重建冲突）
- 更新 `docs/history-bugs/2026-07-16-database-delete-not-synced.md`（标记已修复）

## 三、文件变更清单

### 新建
1. `lifeprism/repository/providers/deletion_log_provider.py` — 已存在 ✅
2. `test/core/integration/sync/test_sync_deletion.py` — 端到端测试
3. `docs/adr/2026-07-22-deletion-sync-tombstone.md` — ADR

### 修改
1. `lifeprism/sync/constants.py` — 从 SYNC_TABLES 移除 deletion_log
2. `lifeprism/repository/sync_repository.py` — 新增 `execute_tombstone_delete`
3. `lifeprism/repository/providers/deletion_log_provider.py` — 新增 `get_tombstone_with_cursor` + `create_tombstone_with_cursor`（事务内调用支持）
4. `lifeprism/sync/sync_client.py` — 新增 3 个方法 + 修改 sync_once
5. `lifeprism/server/api/sync_cloud_api.py` — 新增 3 个端点 + 修改 full-clear
6. `lifeprism/server/api/sync_status_api.py` — /status 显式查询 deletion_log
7. `lifeprism/repository/aggregators/custom_record_aggregator.py` — delete_entry 写墓碑
8. `test/core/unit/sync/test_deletion_log_sync_membership.py` — 翻转断言
9. `docs/specs/2026-07-16-data-sync-core-spec.md` — 墓碑同步流程章节
10. `docs/history-bugs/2026-07-16-database-delete-not-synced.md` — 标记已修复

### 文档（新建/更新）
- `docs/adr/2026-07-22-deletion-sync-tombstone.md`（新建）
- `docs/known-limitations/` 下新增/更新文件删除不同步、删除-更新冲突、删除-重建冲突

## 四、风险与对策

### 风险 1：事务边界（M5）— DeletionLogProvider 方法与外层事务不同连接
**问题**：`_pull_deletion_log` 用 `with self.db.get_connection() as conn` 开事务，但 `deletion_log_repository.get_tombstone` / `create_tombstone` 内部各自开新连接，不在同一事务。
**对策**：在 DeletionLogProvider 新增 `get_tombstone_with_cursor(cursor, ...)` 和 `create_tombstone_with_cursor(cursor, ...)`，接受外部 cursor。这符合 Repository Pattern（SQL 封装在 Provider 内），issue 02 未显式提到但属于 M5 事务边界决策的必要补充。

### 风险 2：移除 deletion_log 后 _generic_delete 不再为 deletion_log 写墓碑
**问题**：`_generic_delete` 中 `is_sync_table = self._TABLE_NAME in SYNC_TABLES`，移除后对 deletion_log 表本身为 False。
**对策**：deletion_log 表从不走 `_generic_delete`（清理走 `cleanup_before` 直接 DELETE，不写墓碑），无影响。这是预期行为。

### 风险 3：full-clear 后 deletion_log 残留
**问题**：移除出 SYNC_TABLES 后，full-clear 不再遍历清空 deletion_log。
**对策**：在 full-clear 端点 SYNC_TABLES 遍历之后，显式 `sync_repository.delete_all_rows("deletion_log")`。

### 风险 4：sync_status_api 不再显示 deletion_log 计数
**对策**：在 `/status` 端点 `count_rows_batch(list(SYNC_TABLES))` 后追加 deletion_log 计数。

### 风险 5：端到端测试需要双端 db 实例
**对策**：参考 `test/core/integration/sync/test_sync_conflict_resolve.py` 的测试模式，用两个 DatabaseManager 实例模拟 A/B 设备，mock httpx 或直接调用 SyncClient 方法。

### 风险 6：custom_record_aggregator 引入 deletion_log_provider 单例
**问题**：repository-module-rules.md 规定 Aggregator 内部不允许 import 全局单例。
**对策**：`write_tombstone_with_cursor` 是无状态方法（只用传入 cursor），但 import 单例仍违规。改为在 `CustomRecordRepository.__init__` 中创建 `DeletionLogProvider()` 实例（符合 Aggregator 模式：内部创建 Provider 实例）。

## 五、执行顺序

1. Slice 01：修改 constants.py + 翻转测试 + full-clear + sync_status_api
2. Slice 02：execute_tombstone_delete + 3 端点 + DeletionLogProvider cursor 方法 + _pull/_push + sync_once 集成 + TEXT 表端到端测试
3. Slice 03：_cleanup_deletion_log + sync_once 集成 + 端到端测试扩展
4. Slice 04：custom_record_aggregator 改造 + 端到端测试扩展 + 文档

每个 Slice 完成后运行相关测试验证。
