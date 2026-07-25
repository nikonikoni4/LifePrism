# PRD 3 墓碑同步流程 - 实现方案 v2

> 依据：`.scratch/deletion-sync-03-tombstone/prd.md` + 4 个 issue 文件（v2 已通过 subagent 审查）
> 日期：2026-07-23
> 修订：v2 — 修复审查报告 C1/C2/C3 + M1/M2/M3 + m1-m10 + R1-R5 + G1-G7

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
- `lifeprism/repository/__init__.py` — `deletion_log_repository` 别名已导出（line 69）✅
- `test/core/unit/storage/test_deletion_log_provider.py` — S1 单元测试完整（8 个 seam）✅

### 待实现
| 项 | 状态 |
|----|------|
| `SYNC_TABLES` 移除 `deletion_log`（C2） | ❌ 仍在 SYNC_TABLES（constants.py:64） |
| `test_deletion_log_sync_membership.py` 翻转断言 | ❌ 仍断言 "in SYNC_TABLES" |
| `SyncRepository.execute_tombstone_delete` + `_with_cursor` 变体（M3/M4 + C1） | ❌ 不存在 |
| `DeletionLogProvider.get_tombstone_with_cursor` + `create_tombstone_with_cursor`（C1/C2） | ❌ |
| `sync_client._pull_deletion_log`（使用 cursor 变体） | ❌ |
| `sync_client._push_deletion_log` | ❌ |
| `sync_client._cleanup_deletion_log` | ❌ |
| `sync_once` 主流程集成 3 个新方法 | ❌ |
| `sync_cloud_api.py` 3 个专用端点 + Pydantic 模型 + 认证（C1） | ❌ |
| `full-clear` 显式清空 deletion_log（try/except 模式） | ❌ |
| `sync_status_api.py` 显式查询 deletion_log | ❌ |
| `custom_record_aggregator.delete_entry` 写墓碑（C4，实例化 Provider） | ❌ |
| 端到端测试 `test_sync_deletion.py` | ❌ |
| ADR `docs/adr/2026-07-22-deletion-sync-tombstone.md` | ❌ |
| spec 更新、known-limitations 更新、history-bugs 标记已修复 | ❌ |

## 二、实现策略

采用 TDD：每个 Slice 先写测试（红），再写实现（绿）。Slice 之间严格顺序依赖（01→02→03→04）。

### Slice 01：验证既有 + 修复 SYNC_TABLES 归属（C2）

DeletionLogProvider 代码已实现，本 slice 只做：
1. 从 `lifeprism/sync/constants.py` 的 `SYNC_TABLES` 移除 `"deletion_log"`（含注释，line 62-64）
2. 翻转 `test/core/unit/sync/test_deletion_log_sync_membership.py`：
   - **Seam 1 三个测试**（`TestDeletionLogInSyncTables` 类）改为断言 `"deletion_log" not in SYNC_TABLES`，类名改为 `TestDeletionLogNotInSyncTables`，注释改为"墓碑走专用通道，不走 SYNC_TABLES"
   - **Seam 2 保持不变**（`TestDeletionLogNotInHashIdPrefixes` 类仍断言 `deletion_log not in HASH_ID_PREFIXES`）
3. 修改 `sync_cloud_api.py` 的 `full-clear` 端点（line 982-988 之后）：在 SYNC_TABLES 遍历之后，**复用 try/except 模式**显式清空 `deletion_log`：
   ```python
   # 4. 显式清空 deletion_log（墓碑表已从 SYNC_TABLES 移除，走专用通道）
   try:
       sync_repository.delete_all_rows("deletion_log")
       cleared_tables.append("deletion_log")
   except DataAccessError as e:
       logger.warning("清空 deletion_log 失败: %s", e)
   ```
   **验证**：`deletion_log` 在 `TABLE_CONFIGS`（`database.py` line 1743），`_validate_table_name` 通过白名单校验。
4. 修改 `sync_status_api.py` 的 `/status` 端点（line 64）：将 `deletion_log` 合并到一次批量查询，避免多一次连接获取：
   ```python
   tables = sync_repository.count_rows_batch(list(SYNC_TABLES) + ["deletion_log"])
   ```

**风险**：移除 `deletion_log` 后，`_generic_delete` 中 `is_sync_table = self._TABLE_NAME in SYNC_TABLES` 对 `deletion_log` 表本身变为 False。但 `deletion_log` 表从不调用 `_generic_delete`（清理走 `cleanup_before` 直接 DELETE，不写墓碑），无影响。

### Slice 02：墓碑 Pull + Push 集成 + SyncRepository cursor 方法（C1/M3/M4/M5/M6/M7）

#### 2.1 `SyncRepository.execute_tombstone_delete` + cursor 变体（M3/M4 + C1）

新增两个方法（一个独立连接版本 + 一个 cursor 版本），依据 `HASH_ID_PREFIXES.get(target_table)` 判断列：

```python
def execute_tombstone_delete(self, target_table: str, record_id: str) -> int:
    """执行墓碑对应的目标表 DELETE（独立连接版本，不写墓碑）

    供 push-deletion-log 端点等非事务场景使用。
    """
    self._validate_table_name(target_table)
    from lifeprism.sync.constants import HASH_ID_PREFIXES
    if HASH_ID_PREFIXES.get(target_table):
        where_col = "hash_id"
    else:
        where_col = self.get_primary_key_field(target_table) or "id"
    sql = f"DELETE FROM {target_table} WHERE {where_col} = ?"
    try:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (record_id,))
            conn.commit()
            affected = cursor.rowcount
        return affected
    except sqlite3.Error as e:
        raise DataAccessError(...) from e

def execute_tombstone_delete_with_cursor(
    self, cursor: sqlite3.Cursor, target_table: str, record_id: str
) -> int:
    """执行墓碑对应的目标表 DELETE（cursor 版本，供 _pull_deletion_log 事务内调用）

    SQL 封装在 Repository 层（符合 Repository Pattern），cursor 由调用方传入，
    事务边界由调用方控制。不写墓碑（墓碑已在 Pull 时写入本地副本）。
    """
    self._validate_table_name(target_table)
    from lifeprism.sync.constants import HASH_ID_PREFIXES
    if HASH_ID_PREFIXES.get(target_table):
        where_col = "hash_id"
    else:
        where_col = self.get_primary_key_field(target_table) or "id"
    sql = f"DELETE FROM {target_table} WHERE {where_col} = ?"
    cursor.execute(sql, (record_id,))
    return cursor.rowcount
```

**注意**：
- 动态表 `custom_*` 不在 `HASH_ID_PREFIXES`，`get_primary_key_field` 对动态表返回 `"id"`，正确。
- 表名经 `_validate_table_name` 白名单校验，防 SQL 注入。

#### 2.2 `DeletionLogProvider` cursor 变体（C1/C2 修复）

新增两个 cursor 版本方法（与 `write_tombstone_with_cursor` 对称），供 `_pull_deletion_log` 和 `push-deletion-log` 端点事务内调用：

```python
def get_tombstone_with_cursor(
    self, cursor: sqlite3.Cursor, target_table: str, record_id: str
) -> dict[str, Any] | None:
    """按 (target_table, record_id) 查询墓碑（cursor 版本）

    供 _pull_deletion_log 事务内 LWW 检查使用。SQL 封装在 Provider 层。
    """
    cursor.execute(
        "SELECT id, target_table, record_id, source, created_at, updated_at "
        "FROM deletion_log WHERE target_table = ? AND record_id = ?",
        (target_table, record_id),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip(["id", "target_table", "record_id", "source", "created_at", "updated_at"], row))

def create_tombstone_with_cursor(
    self,
    cursor: sqlite3.Cursor,
    target_table: str,
    record_id: str,
    source: str,
    created_at: str | None = None,
) -> None:
    """写入墓碑（cursor 版本，供 _pull_deletion_log 事务内写副本）

    保留原 created_at（Pull/Push 写副本时保持两端 LWW 一致）。
    updated_at = created_at（墓碑不修改语义）。
    """
    if source not in self._VALID_SOURCES:
        raise ValidationError(...)
    timestamp = created_at if created_at is not None else get_utc_now_iso()
    tombstone_id = f"dl-{uuid.uuid4().hex[:8]}"
    cursor.execute(
        "INSERT OR IGNORE INTO deletion_log "
        "(id, target_table, record_id, source, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (tombstone_id, target_table, record_id, source, timestamp, timestamp),
    )
```

**决策理由**：`get_tombstone` / `create_tombstone` 内部各自 `with self.db.get_connection()` 开新连接，与外层事务不同连接，无法保证原子性。cursor 版本让 SQL 仍封装在 Provider 层（符合 Repository Pattern），事务边界由调用方控制。这是 M5 事务边界决策的必要补充。

#### 2.3 `sync_cloud_api.py` 3 个专用端点 + Pydantic 模型 + 认证（C1）

**导入**（在 `sync_cloud_api.py` line 32 追加）：
```python
from lifeprism.repository import (
    SyncRepository,
    deletion_log_repository,
    file_sync_state_repository,
)
```

**Pydantic 模型**（在现有 `SyncPullRequest` / `SyncPushRequest` 附近定义）：
```python
class SyncPullDeletionLogRequest(BaseModel):
    last_sync_time: str

class SyncPushDeletionLogRequest(BaseModel):
    tombstones: list[dict[str, Any]]

class SyncCleanupDeletionLogRequest(BaseModel):
    last_sync_time: str
```

**端点 1：`POST /api/sync/pull-deletion-log`**
```python
@router.post("/pull-deletion-log", summary="拉取云端墓碑列表")
def sync_pull_deletion_log(
    request: SyncPullDeletionLogRequest,
    _: None = Depends(verify_sync_api_key),
):
    """拉取云端 created_at > last_sync_time 的墓碑列表"""
    tombstones = deletion_log_repository.get_tombstones_since(request.last_sync_time)
    return {"tombstones": tombstones}
```

**端点 2：`POST /api/sync/push-deletion-log`**（明确事务边界：每条墓碑一个事务）
```python
@router.post("/push-deletion-log", summary="推送本地墓碑到云端")
def sync_push_deletion_log(
    request: SyncPushDeletionLogRequest,
    _: None = Depends(verify_sync_api_key),
):
    """云端对每条墓碑（单事务）：
    a. get_tombstone_with_cursor 查云端已有，有则跳过
    b. execute_tombstone_delete_with_cursor 执行 DELETE
    c. create_tombstone_with_cursor 写云端副本（source=cloud，保留原 created_at）

    事务边界：每条墓碑一个事务，失败则该条回滚并抛异常（sync_once 失败）。
    """
    applied_count = 0
    skipped_count = 0
    for t in request.tombstones:
        target_table = t["target_table"]
        record_id = t["record_id"]
        original_created_at = t["created_at"]
        try:
            with sync_repository.db.get_connection() as conn:
                cursor = conn.cursor()
                # a. LWW 检查：云端已有同 (target_table, record_id) 则跳过
                existing = deletion_log_repository.get_tombstone_with_cursor(
                    cursor, target_table, record_id
                )
                if existing is not None:
                    skipped_count += 1
                    continue
                # b. 执行 DELETE（不写墓碑）
                sync_repository.execute_tombstone_delete_with_cursor(
                    cursor, target_table, record_id
                )
                # c. 写云端副本（source=cloud，保留原 created_at）
                deletion_log_repository.create_tombstone_with_cursor(
                    cursor, target_table, record_id,
                    source="cloud", created_at=original_created_at,
                )
                conn.commit()
                applied_count += 1
        except Exception as e:
            logger.error("push-deletion-log 处理墓碑失败: %s, error: %s", t, e)
            raise
    return {"success": True, "applied_count": applied_count, "skipped_count": skipped_count}
```

**端点 3：`POST /api/sync/cleanup-deletion-log`**（Slice 03 使用，本 slice 先建）
```python
@router.post("/cleanup-deletion-log", summary="清理云端过期墓碑")
def sync_cleanup_deletion_log(
    request: SyncCleanupDeletionLogRequest,
    _: None = Depends(verify_sync_api_key),
):
    cleaned_count = deletion_log_repository.cleanup_before(request.last_sync_time)
    return {"success": True, "cleaned_count": cleaned_count}
```

#### 2.4 `sync_client._pull_deletion_log`（M5/M6/M7，统一使用 cursor 变体）

**导入**（在 `sync_client.py` 顶部）：
```python
from lifeprism.repository import deletion_log_repository
```

```python
def _pull_deletion_log(self, remote_url: str, api_key: str, last_sync_time: str) -> None:
    """墓碑 Pull：HTTP 拉取（事务外）→ 事务内 LWW 检查 + DELETE + 写副本

    失败则整个事务回滚，sync_once 抛异常不更新 last_sync_time。
    """
    # 1. HTTP 拉取（事务外，避免长事务占用连接）
    resp = httpx.post(
        url=f"{remote_url}/api/sync/pull-deletion-log",
        json={"last_sync_time": last_sync_time},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=PUSH_ENDPOINT_TIMEOUT,
    )
    resp.raise_for_status()
    tombstones = resp.json().get("tombstones", [])

    if not tombstones:
        logger.info("墓碑 Pull: 云端无新墓碑")
        return

    # 2. 事务内处理（所有 DELETE + 副本写入在同一事务，失败则回滚）
    try:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for t in tombstones:
                target_table = t["target_table"]
                record_id = t["record_id"]
                original_created_at = t["created_at"]

                # a. LWW 检查（M6 简化）：本地已有同 (target_table, record_id) 墓碑则跳过
                local = deletion_log_repository.get_tombstone_with_cursor(
                    cursor, target_table, record_id
                )
                if local is not None:
                    continue

                # b. 执行 DELETE（M3/M4，不写墓碑）
                self.sync_repository.execute_tombstone_delete_with_cursor(
                    cursor, target_table, record_id
                )

                # c. 写本地副本（M7，保留原 created_at）
                deletion_log_repository.create_tombstone_with_cursor(
                    cursor, target_table, record_id,
                    source="cloud", created_at=original_created_at,
                )
            conn.commit()
        logger.info("墓碑 Pull: 处理 %d 条墓碑", len(tombstones))
    except Exception:
        # with 块异常时 conn 未 commit，自动回滚
        logger.error("墓碑 Pull 失败，事务已回滚")
        raise
```

**关键决策（C1/C2 修复）**：三个方法（`get_tombstone_with_cursor` / `execute_tombstone_delete_with_cursor` / `create_tombstone_with_cursor`）全部使用 cursor 变体，共用同一 cursor，保证 DELETE + 副本写入在同一事务。失败时 `with` 块未 commit，连接归还时自动回滚。

#### 2.5 `sync_client._push_deletion_log`

```python
def _push_deletion_log(self, remote_url: str, api_key: str, last_sync_time: str) -> None:
    """墓碑 Push：查询本地 source=local 墓碑 → HTTP 推送到云端"""
    tombstones = deletion_log_repository.get_tombstones_since(last_sync_time, source="local")
    if not tombstones:
        logger.info("墓碑 Push: 本地无新墓碑")
        return
    resp = httpx.post(
        url=f"{remote_url}/api/sync/push-deletion-log",
        json={"tombstones": tombstones},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=PUSH_ENDPOINT_TIMEOUT,
    )
    resp.raise_for_status()
    logger.info("墓碑 Push: 推送 %d 条墓碑", len(tombstones))
```

Push 是查询本地 + HTTP 推送，云端处理，无需本地事务。

#### 2.6 `sync_once` 主流程修改

在 `sync_once` 中（非 `_full_sync_to_cloud`，line 248-273）：
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

**注意**：`_full_sync_to_cloud` 不调用墓碑方法（US20）。首同步通过 `full-clear` 端点清空云端 `deletion_log`（Slice 01 修复），本地首同步前的孤儿墓碑会在首次增量 sync 的 `_cleanup_deletion_log` 中被清理（`created_at <= last_sync_time`）。

#### 2.7 端到端测试（TEXT 主键表）

新建 `test/core/integration/sync/test_sync_deletion.py`：
- **测试模式**：参考 `test/core/integration/sync/test_sync_conflict_resolve.py`，用两个 DatabaseManager 实例模拟 A/B 设备，**mock httpx** 把请求路由到"云端" DatabaseManager 的 SyncRepository/DeletionLogProvider。
- 场景 1：A 删除 TEXT 主键表记录（如 `mood_entries`）→ 同步 → B 记录消失
- 场景 2（US22 显式测试）：A 删除 R → A sync（cloud 收到墓碑并删 R）→ 手动在 cloud DB 重新插入 R（模拟残留）→ B sync → 验证 B 的 R 被删除（墓碑 Pull 先删）且未被数据 Pull 写回。**或简化**：通过 mock 顺序断言 `_pull_deletion_log` 在 `pull_from_remote` 之前调用。

### Slice 03：墓碑清理 + LWW + 失败处理

#### 3.1 `sync_client._cleanup_deletion_log`

```python
def _cleanup_deletion_log(self, remote_url: str, api_key: str, last_sync_time: str) -> None:
    """墓碑清理：清理本地 + 云端 created_at <= last_sync_time 的记录

    使用旧 last_sync_time（同步前的值），在更新 last_sync_time 之前执行。
    刚 Pull/Push 产生的墓碑 created_at > 旧 last_sync_time，不会被清理。
    清理是同步成功后的内部操作，不写墓碑。
    """
    # 1. 清理本地
    local_cleaned = deletion_log_repository.cleanup_before(last_sync_time)
    # 2. 清理云端
    resp = httpx.post(
        url=f"{remote_url}/api/sync/cleanup-deletion-log",
        json={"last_sync_time": last_sync_time},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=PUSH_ENDPOINT_TIMEOUT,
    )
    resp.raise_for_status()
    logger.info("墓碑清理: 本地 %d 条, 云端 %s", local_cleaned, resp.json())
```

**清理非原子说明（R3）**：先清本地后清云端（HTTP），若云端 HTTP 失败，本地已清而云端未清，下次 Pull 会重新拉回云端墓碑并重新执行 DELETE（幂等，无害但浪费）。反向（本地失败、云端成功）则本地残留旧墓碑，触发 M3 的 LWW 跳过边缘场景。依赖幂等重试，记入 ADR。

#### 3.2 `sync_once` 集成清理

```python
self._sync_files_full_flow(...)
self._cleanup_deletion_log(remote_url, api_key, last_sync_time)  # 旧 last_sync_time
current_time = ...
set_setting("sync.last_sync_time", current_time)
```

#### 3.3 端到端测试扩展

- 墓碑清理在同步成功后执行（验证 `deletion_log` 中 `created_at <= last_sync_time` 的记录被清理）
- 墓碑 LWW 冲突保留更晚 `updated_at`
- 墓碑同步失败时整个 `sync_once` 失败（验证 `last_sync_time` 未更新）
- **墓碑 Pull 失败回滚**（G2）：构造"部分删除后失败"场景——mock `execute_tombstone_delete_with_cursor` 在第 N 条抛异常，验证前 N-1 条 DELETE 被回滚（事务未 commit，连接归还时自动回滚）

### Slice 04：边界场景 + 表类型覆盖 + 文档

#### 4.1 `custom_record_aggregator.delete_entry` 改造（C4，实例化 Provider，C3 修复）

**导入**（在 `custom_record_aggregator.py` 顶部，按 Aggregator 规则 import Provider 类）：
```python
from lifeprism.repository.providers.deletion_log_provider import DeletionLogProvider
```

**`__init__` 中创建实例**（符合 repository-module-rules.md 1.2 节"Aggregator 内部创建 Provider 实例"）：
```python
class CustomRecordRepository:
    def __init__(self, db_manager=None):
        super().__init__(db_manager)  # 如果继承 LWBaseDataProvider
        # 或 self.db = db_manager or lw_db_manager
        # 创建 DeletionLogProvider 实例（db_manager 透传，保证测试可注入）
        self.deletion_log_provider = DeletionLogProvider(db_manager=self.db)
```

**`delete_entry` 改造（M1 修复：先判存在再写墓碑，避免孤儿墓碑）**：
```python
def delete_entry(self, type_id: str, entry_id: str) -> bool:
    _, data_table = self._get_type_and_table(type_id)
    try:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. 先查询记录是否存在（避免对不存在的 entry_id 产生孤儿墓碑）
            cursor.execute(
                f"SELECT 1 FROM {data_table} WHERE id = ?",
                (entry_id,),
            )
            if cursor.fetchone() is None:
                raise EntityNotFoundError(entity_type="CustomRecordEntry", entity_id=entry_id)
            # 2. 写墓碑（与 DELETE 同事务，使用实例方法）
            self.deletion_log_provider.write_tombstone_with_cursor(
                cursor, data_table, entry_id, source="local"
            )
            # 3. 执行 DELETE
            cursor.execute(
                f"DELETE FROM {data_table} WHERE id = ?",
                (entry_id,),
            )
            deleted = cursor.rowcount > 0
            conn.commit()
    except sqlite3.Error as e:
        logger.error(...)
        raise DataAccessError(...) from e
    if not deleted:
        raise EntityNotFoundError(entity_type="CustomRecordEntry", entity_id=entry_id)
    logger.info("删除自定义记录成功: type_id=%s, entry_id=%s", type_id, entry_id)
    return True
```

**注意**：
- `self.deletion_log_provider.write_tombstone_with_cursor` 只用传入的 cursor，不碰自己的 db 连接，可安全使用。
- 对齐 `_generic_delete` 的 `_resolve_tombstone_record_id` 模式（先查存在再写墓碑）。

#### 4.2 端到端测试扩展

- AUTOINCREMENT 表删除同步（`timeline_custom_block`，墓碑 record_id = hash_id）
- 级联删除同步（habit + challenges + checkins）
- 动态表删除同步（custom_*，验证 `delete_entry` 写墓碑）
- 重置 `last_sync_time` 后墓碑仍工作（G7）：重置后 `last_sync_time=""`，`get_tombstones_since("")` 返回所有墓碑，会重新 Pull/Push 所有未清理的墓碑。验证此行为正确。
- 全量首同步不传播墓碑
- 多表批量删除同步
- 删除-更新冲突反向测试（已知限制预期行为）

#### 4.3 文档

**前置要求**（m4）：编写文档前阅读 `docs/docs-rules/index.md` 和 `docs/docs-rules/docs-write-rules.md`

**ADR `docs/adr/2026-07-22-deletion-sync-tombstone.md`**（m8 补充）：
- 删除同步墓碑机制决策
- 含两节点假设、墓碑清理策略、`updated_at` LWW（墓碑不修改，`created_at == updated_at`，行为等价）
- Pull/Push 顺序（墓碑 Pull/Push 在数据 Pull/Push 之前）
- 专用端点（3 个端点 + Pydantic 模型 + 认证）
- `deletion_log` 从 `SYNC_TABLES` 移除的决策（走专用通道）
- **事务边界 cursor 版本决策**（为何 DeletionLogProvider/SyncRepository 需要 `_with_cursor` 变体：保证 DELETE + 副本写入在同一事务）
- **墓碑不可变 + INSERT OR IGNORE 语义决策**（`_ON_CONFLICT = "ignore"`，重复写入保留旧墓碑）
- **LWW 跳过简化的适用前提与边缘场景**（M3）：适用前提是墓碑不可变 + 清理一致；失效场景是清理不一致 + 重新删除（本地旧墓碑未清理导致跳过云端新墓碑的 DELETE）
- **清理非原子说明**（R3）：依赖幂等重试

**更新 PRD**（M1/Major-4 同步修改）：
- PRD US16：改为"墓碑比较使用 `updated_at` 字段作 LWW——墓碑不修改，插入时 `created_at == updated_at`，行为等价"
- PRD"墓碑 LWW 比较"章节：同步更新描述
- PRD"决策汇总"表"冲突策略"行：更新为"墓碑 `updated_at` 作 LWW（等价于 `created_at`，因墓碑不修改）"
- PRD"模块改造清单"：更新 `sync_cloud_api.py` 改造内容为"新增 3 个专用端点"
- PRD"Implementation Decisions"中 `deletion_log` 从 `SYNC_TABLES` 移除的说明

**更新 spec**：`docs/specs/2026-07-16-data-sync-core-spec.md`
- 新增"墓碑同步流程"章节
- 描述 Pull/Push/清理三个阶段的流程（含专用端点 + cursor 事务边界）

**更新 known-limitations**：
- 文件删除不同步（文件操作不走 LifePrism 同步管控）
- 删除-更新冲突不自动处理（已知限制，引用反向测试）
- **删除-重建冲突**（M3 修正描述）：删除-重建后旧墓碑仍存在但 LWW 跳过简化逻辑不会再次触发删除（因为本地已有墓碑则跳过 DELETE），重新创建的记录通过数据 sync 的 upsert 存活。这是预期行为，不是 bug。

**更新 history-bugs**：`docs/history-bugs/2026-07-16-database-delete-not-synced.md`
- 标记为已修复（引用 PRD 1+2+3 的 commit）

## 三、文件变更清单

### 新建
1. `test/core/integration/sync/test_sync_deletion.py` — 端到端测试
2. `docs/adr/2026-07-22-deletion-sync-tombstone.md` — ADR

### 修改
1. `lifeprism/sync/constants.py` — 从 SYNC_TABLES 移除 deletion_log
2. `lifeprism/repository/sync_repository.py` — 新增 `execute_tombstone_delete` + `execute_tombstone_delete_with_cursor`
3. `lifeprism/repository/providers/deletion_log_provider.py` — 新增 `get_tombstone_with_cursor` + `create_tombstone_with_cursor`
4. `lifeprism/sync/sync_client.py` — 新增 3 个方法 + 修改 sync_once + 导入 deletion_log_repository
5. `lifeprism/server/api/sync_cloud_api.py` — 新增 3 个端点 + Pydantic 模型 + 认证 + 导入 deletion_log_repository + full-clear 显式清空
6. `lifeprism/server/api/sync_status_api.py` — /status 显式查询 deletion_log（合并到 count_rows_batch）
7. `lifeprism/repository/aggregators/custom_record_aggregator.py` — delete_entry 写墓碑 + __init__ 创建 DeletionLogProvider 实例
8. `test/core/unit/sync/test_deletion_log_sync_membership.py` — 翻转 Seam 1 断言，Seam 2 保持不变
9. `docs/specs/2026-07-16-data-sync-core-spec.md` — 墓碑同步流程章节
10. `docs/history-bugs/2026-07-16-database-delete-not-synced.md` — 标记已修复

### 文档（新建/更新）
- `docs/adr/2026-07-22-deletion-sync-tombstone.md`（新建）
- `docs/known-limitations/` 下新增/更新文件删除不同步、删除-更新冲突、删除-重建冲突

## 四、风险与对策

### 风险 1：事务边界（M5）— DeletionLogProvider/SyncRepository 方法与外层事务不同连接（C1/C2 已修复）
**问题**：`_pull_deletion_log` 用 `with self.db.get_connection() as conn` 开事务，但 `deletion_log_repository.get_tombstone` / `create_tombstone` / `sync_repository.execute_tombstone_delete` 内部各自开新连接，不在同一事务。
**对策（v2）**：在 DeletionLogProvider 新增 `get_tombstone_with_cursor` / `create_tombstone_with_cursor`，在 SyncRepository 新增 `execute_tombstone_delete_with_cursor`。三个方法全部接受外部 cursor，SQL 封装在 Repository/Provider 层（符合 Repository Pattern），事务边界由调用方控制。失败时 `with` 块未 commit，连接归还时自动回滚。

### 风险 2：移除 deletion_log 后 _generic_delete 不再为 deletion_log 写墓碑
**问题**：`_generic_delete` 中 `is_sync_table = self._TABLE_NAME in SYNC_TABLES`，移除后对 deletion_log 表本身为 False。
**对策**：deletion_log 表从不走 `_generic_delete`（清理走 `cleanup_before` 直接 DELETE，不写墓碑），无影响。这是预期行为。

### 风险 3：full-clear 后 deletion_log 残留
**问题**：移除出 SYNC_TABLES 后，full-clear 不再遍历清空 deletion_log。
**对策**：在 full-clear 端点 SYNC_TABLES 遍历之后，复用 try/except 模式显式 `sync_repository.delete_all_rows("deletion_log")`。

### 风险 4：sync_status_api 不再显示 deletion_log 计数
**对策**：在 `/status` 端点 `count_rows_batch(list(SYNC_TABLES) + ["deletion_log"])` 合并到一次批量查询。

### 风险 5：端到端测试需要双端 db 实例 + mock httpx
**对策**：参考 `test/core/integration/sync/test_sync_conflict_resolve.py` 的测试模式，用两个 DatabaseManager 实例模拟 A/B 设备，mock httpx 把请求路由到"云端" DatabaseManager 的 SyncRepository/DeletionLogProvider。

### 风险 6：custom_record_aggregator 引入 deletion_log_provider 单例（C3 已修复）
**问题**：repository-module-rules.md 规定 Aggregator 内部不允许 import 全局单例。
**对策（v2）**：在 `CustomRecordRepository.__init__` 中创建 `DeletionLogProvider(db_manager=self.db)` 实例（db_manager 透传，保证测试可注入），符合 Aggregator 模式。

### 风险 7：delete_entry 先写墓碑后判存在产生孤儿墓碑（M1 已修复）
**问题**：原方案先写墓碑再 DELETE，若记录不存在会产生孤儿墓碑。
**对策（v2）**：改为先 `SELECT 1` 判存在，不存在则抛 `EntityNotFoundError`，再写墓碑 + DELETE。

### 风险 8：LWW 跳过简化的边缘场景（M3）
**问题**：本地有旧墓碑（未清理）+ 云端有新墓碑（重新删除）时，简化逻辑会跳过 DELETE，但应按 LWW 保留新墓碑。
**对策（v2）**：
- ADR 补充 LWW 跳过简化的适用前提（墓碑不可变 + 清理一致）与失效场景（清理不一致 + 重新删除）。
- known-limitations 中"删除-重建冲突"描述改为与简化逻辑实际行为一致。
- 长期可考虑 LWW 跳过时比较 updated_at，但超出 v1 范围，记入技术债。

### 风险 9：清理非原子（R3）
**问题**：`_cleanup_deletion_log` 先清本地后清云端（HTTP），非原子。
**对策**：依赖幂等重试（DELETE 幂等，INSERT OR IGNORE 忽略重复），记入 ADR。

## 五、执行顺序

1. Slice 01：修改 constants.py + 翻转测试（Seam 1 翻转，Seam 2 保持）+ full-clear + sync_status_api
2. Slice 02：execute_tombstone_delete + cursor 变体 + DeletionLogProvider cursor 方法 + 3 端点 + Pydantic 模型 + _pull/_push + sync_once 集成 + TEXT 表端到端测试
3. Slice 03：_cleanup_deletion_log + sync_once 集成 + 端到端测试扩展（含 Pull 失败回滚测试）
4. Slice 04：custom_record_aggregator 改造（实例化 Provider + 先判存在）+ 端到端测试扩展 + 文档

每个 Slice 完成后运行相关测试验证。
