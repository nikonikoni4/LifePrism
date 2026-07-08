# 同步 API - Pull 接口

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

实现从云端拉取增量数据的 REST API 端点，支持 API Key 认证和增量查询。

**API 端点**：`POST /api/sync/pull`

**请求格式**：
```json
{
  "last_sync_time": "2026-07-08T10:00:00",
  "tables": ["mood_entries", "todo_list", ...],
  "api_key": "lifeprism_sync_..."
}
```

**响应格式**：
```json
{
  "changes": {
    "mood_entries": [
      {"id": "...", "content": "...", "updated_at": "..."}
    ],
    "todo_list": [...]
  },
  "sync_time": "2026-07-08T10:15:00"
}
```

**实现端到端**：
1. 新增 `lifeprism/repository/sync_repository.py`（SyncRepository），封装同步相关的动态多表查询
   - **编码规范要求**：不得在非 repository 的任何位置直接编写 SQL
   - `query_incremental(table_name, last_sync_time)` - 执行 `SELECT * FROM {table} WHERE updated_at > ? ORDER BY updated_at ASC`
   - 捕获 `sqlite3.Error` 并转换为 `DataAccessError` 抛出（不用 `except Exception`）
   - 在 `lifeprism/repository/__init__.py` 中导出
2. 新增 `lifeprism/server/routes/sync_api.py`（API 层，不直接写 SQL）
3. API Key 认证：
   - 从请求读取 `api_key`
   - 与配置中的 `sync_api_key` 比较（通过 `sync_config.get_sync_api_key()`）
   - **认证失败时抛出 `ValidationError(message="无效的同步 API Key", code="INVALID_SYNC_API_KEY")`**
   - **不使用 try/except**，让异常自然冒泡到全局异常处理器（符合 API 层规范）
4. 调用 `sync_repository.query_incremental()` 对每个表执行增量查询
   - **查询失败时由 Repository 层抛出 `DataAccessError`**
5. 返回 JSON 格式的变更数据
6. **日志记录**（INFO 级别）：
   - 同步请求开始：`last_sync_time`、请求的表列表
   - 同步完成：每个表的记录数、总耗时
7. 集成测试（Mock HTTP 请求，验证增量查询逻辑）

---

## Acceptance criteria

- [ ] API 端点 `POST /api/sync/pull` 已实现
- [ ] **API Key 认证生效**：
  - 错误的 Key 抛出 `ValidationError(code="INVALID_SYNC_API_KEY")`
  - 不使用 try/except，让异常自然冒泡到全局异常处理器
- [ ] 增量查询使用 `updated_at` 索引
- [ ] 返回数据格式正确（包含 `changes` 和 `sync_time`）
- [ ] **日志记录完整**（INFO 级别）：
  - 同步请求开始：`last_sync_time`、请求的表列表
  - 同步完成：每个表的记录数、总耗时
- [ ] 集成测试通过：
  - 测试正常拉取增量数据
  - 测试 API Key 认证失败（抛出 ValidationError）
  - 测试空查询（无增量数据）
  - 测试日志记录

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/01-database-schema-updated-at.md`
