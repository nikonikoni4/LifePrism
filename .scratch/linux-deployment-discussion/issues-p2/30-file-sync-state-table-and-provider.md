# file_sync_state 表 + FileSyncStateProvider + compute_file_hash()

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 文件同步冲突处理

## What to build

新增 `file_sync_state` 表（存储在 lifewatch_ai.db 中），新建 FileSyncStateProvider（只做纯 CRUD），新建 `compute_file_hash()` 工具函数（规范化 hash 计算）。

**ADR 参考**：`docs/adr/2026-07-14-file-sync-conflict-resolution.md` v2.1 决策 1 + 职责分层

**表结构**：

```sql
CREATE TABLE file_sync_state (
    file_path     TEXT PRIMARY KEY,
    parent_hash   TEXT,
    current_hash  TEXT,
    updated_at    TEXT NOT NULL
);
```

- `file_path`：相对 lifeprism_data_path 的路径（如 `user/user.md`）
- `parent_hash`：上次同步成功时的 hash（NULL = 从未同步）
- `current_hash`：当前文件内容的 hash
- 不加入 SYNC_TABLES——它是同步元数据，通过 API 扩展字段传递，不在数据库同步链路中传输

**FileSyncStateProvider 职责边界**（只做 CRUD，不包含同步业务逻辑）：

- `get_state(file_path)` → 查单条记录（返回 parent_hash + current_hash）
- `get_all_states(directory)` → 查目录下所有文件的状态
- `upsert_state(file_path, parent_hash, current_hash)` → 插入或更新
- `delete_state(file_path)` → 删除记录

hash 刷新、11 状态矩阵判定、parent_hash 推进等同步业务逻辑**不放在 Provider 中**，由 SyncClient 内联实现（见 issue 33）。

**compute_file_hash() 工具函数**：

```python
def compute_file_hash(content: bytes) -> str:
    text = content.decode("utf-8", errors="replace")
    normalized = "".join(text.split())  # 去除所有空白字符
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

- 去除所有空白字符（空格、换行 `\n`、回车 `\r`、制表符 `\t` 等）
- 源文件不受影响，仅 hash 计算时做规范化
- 避免 OS 差异（Windows `\r\n` vs Linux `\n`）导致 hash 不一致

**compute_file_hash() 位置**：放在 `lifeprism/sync/` 目录下（如 `lifeprism/sync/hash_utils.py`），以便 SyncClient 和 sync_cloud_api 都能导入。

**TABLE_CONFIGS 注册**：`file_sync_state` 表必须在 `lifeprism/config/database.py` 的 TABLE_CONFIGS 中注册 DDL。注册后，本地和云端的 `init_database()` 均会自动创建此表（ADR 决策 1："本地和云端均需对称维护"）。`file_sync_state` **不加入 SYNC_TABLES**——它是同步元数据，不通过数据库同步链路传输。

## Acceptance criteria

- [ ] `file_sync_state` 表 DDL 在 `database.py` 的 TABLE_CONFIGS 中注册
- [ ] 本地和云端 `init_database()` 均自动创建 file_sync_state 表
- [ ] `file_sync_state` 不在 SYNC_TABLES 中（防御性测试）
- [ ] FileSyncStateProvider 继承 LWBaseDataProvider，定义 `_TABLE_NAME`、`_PRIMARY_KEY` 等元数据
- [ ] Provider 方法仅包含 get_state / get_all_states / upsert_state / delete_state（纯 CRUD）
- [ ] Provider 不包含 hash 计算、矩阵判定等同步业务逻辑
- [ ] `compute_file_hash()` 工具函数放在 `lifeprism/sync/` 目录下
- [ ] `compute_file_hash()` 实现：去除所有空白字符后计算 SHA-256
- [ ] 单元测试：compute_file_hash 对相同内容不同空白格式返回相同 hash
- [ ] 单元测试：compute_file_hash 对空文件、纯空白文件返回确定性 hash
- [ ] 单元测试：Provider CRUD 操作正确
- [ ] 单元测试：get_state 对不存在的 file_path 返回 None

## Blocked by

None - can start immediately
