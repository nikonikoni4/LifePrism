# 分批同步机制 - Repository 层

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 通信架构

---

## What to build

为 `SyncRepository.query_incremental()` 增加分页参数（`offset`、`limit`），支持分批查询增量数据，避免首次同步大数据集时超时（httpx timeout=60s）。

**问题背景**：首次同步 16MB 数据（~10,000 条记录）时，一次性查询返回可能导致：
- 单次查询耗时过长
- HTTP 响应体过大
- 客户端超时（httpx timeout=60s）

**解决方案**：Repository 层支持分页查询（LIMIT + OFFSET），API 层和客户端配合实现分批传输。

**实现端到端**：

1. 修改 `lifeprism/repository/sync_repository.py::query_incremental()`：

```python
def query_incremental(self, table_name, last_sync_time, offset=0, limit=None):
    """查询增量数据（支持分页）
    
    Args:
        table_name: 表名
        last_sync_time: 上次同步时间（ISO 8601 格式）
        offset: 分页偏移量（默认 0）
        limit: 每页记录数（None 表示不分页）
    
    Returns:
        list[dict]: 增量记录列表
    """
    sql = f"SELECT * FROM {table_name} WHERE updated_at > ? ORDER BY updated_at ASC"
    params = [last_sync_time]
    
    if limit is not None:
        sql += f" LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    
    try:
        cursor = self.db.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DataAccessError(
            message=f"查询表 {table_name} 增量数据失败",
            details={"table": table_name, "last_sync_time": last_sync_time, "offset": offset, "limit": limit, "error": str(e)}
        ) from e
```

2. 修改 `lifeprism/server/api/sync_cloud_api.py::sync_pull()`：

```python
class SyncPullRequest(BaseModel):
    last_sync_time: str
    tables: list[str]
    offset: int = Field(default=0, description="分页偏移量")
    limit: int | None = Field(default=None, description="每页记录数（None 表示不分页）")

@router.post("/pull")
async def sync_pull(request: SyncPullRequest, _: None = Depends(verify_sync_api_key)):
    # ... 现有逻辑
    for table_name in request.tables:
        rows = sync_repository.query_incremental(
            table_name, 
            request.last_sync_time,
            offset=request.offset,
            limit=request.limit
        )
        if rows:
            changes[table_name] = rows
    # ...
```

3. 集成测试：
   - 测试分页查询（offset=0, limit=1000）
   - 测试跨页查询（offset=1000, limit=1000）
   - 测试不分页查询（limit=None）

---

## Acceptance criteria

- [ ] `query_incremental()` 支持 `offset` 和 `limit` 参数
- [ ] SQL 正确拼接 `LIMIT ? OFFSET ?`（只在 limit 不为 None 时）
- [ ] `sync_pull` API 接受分页参数
- [ ] 分页参数验证：offset >= 0，limit > 0 或 None
- [ ] 错误处理：sqlite3.Error 转换为 DataAccessError
- [ ] 日志记录：INFO 级别记录分页参数
- [ ] 集成测试通过：分页查询、跨页查询、不分页查询

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/03-sync-api-pull.md` - Pull API 基础实现
- `.scratch/linux-deployment-discussion/issues-p2/05-sync-client-basic.md` - SyncClient 基础逻辑
