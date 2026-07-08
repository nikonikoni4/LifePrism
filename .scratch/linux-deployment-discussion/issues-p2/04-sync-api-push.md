# 同步 API - Push 接口

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

实现推送本地变更到云端的 REST API 端点，支持 API Key 认证和批量写入。

**API 端点**：`POST /api/sync/push`

**请求格式**：
```json
{
  "changes": {
    "mood_entries": [
      {"id": "...", "content": "...", "updated_at": "..."}
    ],
    "todo_list": [...]
  },
  "api_key": "lifeprism_sync_..."
}
```

**响应格式**：
```json
{
  "status": "ok",
  "sync_time": "2026-07-08T10:15:00"
}
```

**实现端到端**：
1. 在 `lifeprism/repository/sync_repository.py`（Issue #03 创建的 SyncRepository）中添加批量写入方法
   - `upsert_rows(table_name, rows)` - 执行 `INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})`
   - **写入策略遵循 Issue #05 的三类表分类**：Category A 按主键判重，Category B/C 按 UNIQUE 约束判重
   - 捕获 `sqlite3.Error` 并转换为 `DataAccessError` 抛出（不用 `except Exception`）
   - 捕获 `sqlite3.IntegrityError`（UNIQUE 约束冲突）同样转换为 `DataAccessError`
2. 在 `lifeprism/server/routes/sync_api.py` 添加 Push 端点（API 层，不直接写 SQL）
3. API Key 认证：
   - 从请求读取 `api_key`
   - 与配置中的 `sync_api_key` 比较（通过 `sync_config.get_sync_api_key()`）
   - **认证失败时抛出 `ValidationError(message="无效的同步 API Key", code="INVALID_SYNC_API_KEY")`**
   - **不使用 try/except**，让异常自然冒泡到全局异常处理器（符合 API 层规范）
4. 调用 `sync_repository.upsert_rows()` 对每个表批量写入
   - **写入失败时由 Repository 层抛出 `DataAccessError`**
5. 返回同步状态
6. **日志记录**（INFO 级别）：
   - 同步请求开始：每个表的记录数
   - 同步完成：总耗时
7. 集成测试（Mock HTTP 请求，验证批量写入逻辑）

---

## Acceptance criteria

- [ ] API 端点 `POST /api/sync/push` 已实现
- [ ] **API Key 认证生效**：
  - 错误的 Key 抛出 `ValidationError(code="INVALID_SYNC_API_KEY")`
  - 不使用 try/except，让异常自然冒泡到全局异常处理器
- [ ] 批量写入使用 `INSERT OR REPLACE`，动态构建列名和占位符（不使用 `VALUES (?)` 简写）
- [ ] 返回数据格式正确（包含 `status` 和 `sync_time`）
- [ ] **日志记录完整**（INFO 级别）：
  - 同步请求开始：每个表的记录数
  - 同步完成：总耗时
- [ ] 集成测试通过：
  - 测试正常推送数据
  - 测试 API Key 认证失败（抛出 ValidationError）
  - 测试空推送（无变更数据）
  - 测试覆盖现有记录
  - 测试日志记录

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/01-database-schema-updated-at.md`
