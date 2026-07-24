---
version: 1.0
created_at: 2026-07-24
updated_at: 2026-07-24
last_updated: 初始版本，记录删除同步 Stage 3 代码审查中 4 个 P2 问题
abstract: 删除同步 Stage 3（墓碑同步流程）代码审查发现的 4 个 P2 问题：通用通道缺防御性过滤、墓碑端点缺 Pydantic 模型、DeletionLogProvider 方法重复、测试覆盖缺口。
---

# 删除同步 P2 问题：防御性过滤 + Pydantic 模型 + 方法重复 + 测试缺口

**优先级**: 中
**影响范围**: `lifeprism/sync/sync_client.py`、`lifeprism/server/api/sync_cloud_api.py`、`lifeprism/repository/providers/deletion_log_provider.py`

---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0  | 创建文档初稿，记录 Issue 4/7/8/9 四个 P2 问题 |

---

## 问题描述

删除同步 Stage 3（commit 99872455）代码审查发现 4 个 P2 问题，均不影响当前功能正确性，但影响可维护性和防御性。

### Issue 4: 通用通道缺防御性过滤（P1 架构）

`deletion_log` 已从 `SYNC_TABLES` 移除（`lifeprism/sync/constants.py:62-64`），墓碑仅通过专用通道（`_pull_deletion_log` / `_push_deletion_log` / `_cleanup_deletion_log`）同步。

但 `sync_once` 中构建 `tables` 列表时（`lifeprism/sync/sync_client.py:253`）：
```python
tables = list(set(SYNC_TABLES + dynamic_table_names))
```
没有显式过滤 `deletion_log`。如果未来有人误将 `deletion_log` 加回 `SYNC_TABLES`，会导致双重同步（通用 LWW 通道 + 专用墓碑通道），产生语义冲突。

### Issue 7: 墓碑端点使用 list[dict] 而非 Pydantic 模型（P2 最佳实践）

三个墓碑端点的请求/响应模型使用 `list[dict[str, Any]]` 而非 Pydantic 模型：

| 端点 | 文件位置 | 字段 |
|------|----------|------|
| `/push-deletion-log` | `lifeprism/server/api/sync_cloud_api.py:125` | `tombstones: list[dict[str, Any]]` |
| `/pull-deletion-log` 响应 | `lifeprism/server/api/sync_cloud_api.py:331` | `tombstones: [{...}]`（无模型） |
| `/cleanup-deletion-log` | `lifeprism/server/api/sync_cloud_api.py:408` | 响应无模型 |

缺少 Pydantic 模型导致：无请求体校验、无 OpenAPI schema 文档、字段名拼写错误不会在入口被拦截。

### Issue 8: DeletionLogProvider 三个写入方法重复代码（P2 代码质量）

`DeletionLogProvider` 的三个写入方法存在大量重复的 SQL 构建和执行逻辑：

| 方法 | 文件位置 | 行数 |
|------|----------|------|
| `create_tombstone` | `lifeprism/repository/providers/deletion_log_provider.py:59` | ~50 行 |
| `write_tombstone_with_cursor` | `lifeprism/repository/providers/deletion_log_provider.py:113` | ~70 行 |
| `create_tombstone_with_cursor` | `lifeprism/repository/providers/deletion_log_provider.py:191` | ~50 行 |

三个方法的核心逻辑相同（INSERT OR IGNORE + 冲突处理），仅在连接管理（自带连接 vs 接收 cursor）和参数处理上有差异。

### Issue 9: 测试覆盖缺口（P2 测试）

删除同步模块缺少以下测试：

| 缺口 | 说明 |
|------|------|
| 云侧端点 TestClient 集成测试 | 3 个墓碑端点无 FastAPI TestClient 集成测试，当前仅通过 mock httpx 测试客户端侧 |
| Push 失败路径测试 | `_push_deletion_log` HTTP 失败时的行为未测试 |
| cursor 变体方法单元测试 | `create_tombstone_with_cursor` / `write_tombstone_with_cursor` 无独立单元测试 |

---

## 当前影响

- **Issue 4**：当前无功能影响（`deletion_log` 不在 `SYNC_TABLES` 中），但缺少防御性过滤，未来误加回会导致双重同步
- **Issue 7**：无功能影响，但 API 文档不完整，字段错误只能在运行时发现
- **Issue 8**：无功能影响，但维护成本高（修改一个方法需要同步修改另外两个）
- **Issue 9**：云侧端点和失败路径无回归测试保障

---

## 优化方案

### Issue 4: 防御性过滤

在 `sync_once` 构建 `tables` 列表后添加显式过滤：
```python
tables = [t for t in tables if t != "deletion_log"]
```
或在 `SYNC_TABLES` 定义处添加注释 + 断言。

**推荐**：在 `sync_once` 中添加过滤（防御性编程，成本最低）。

### Issue 7: Pydantic 模型

创建 `TombstonePushRequest` / `TombstonePullResponse` / `TombstoneCleanupResponse` Pydantic 模型，替换 `list[dict[str, Any]]`。

**推荐**：在下次修改 `sync_cloud_api.py` 时顺便重构。

### Issue 8: 方法合并

提取公共 SQL 构建逻辑到 `_build_tombstone_insert_sql()` 私有方法，三个公开方法调用它并仅处理连接管理差异。

**推荐**：在下次修改 `DeletionLogProvider` 时顺便重构。

### Issue 9: 测试补充

- 添加 `TestClient` 集成测试（参考 `test/core/integration/api/test_sync_api.py`）
- 添加 Push 失败路径测试（mock httpx 抛异常）
- 添加 cursor 变体方法单元测试

**推荐**：与 Issue 7 重构一起完成（Pydantic 模型 + 集成测试）。

---

## 相关代码文件

- `lifeprism/sync/constants.py:25-65` — SYNC_TABLES 定义（deletion_log 已移除）
- `lifeprism/sync/sync_client.py:249-258` — sync_once 构建 tables 列表
- `lifeprism/server/api/sync_cloud_api.py:125,314,338,408` — 三个墓碑端点
- `lifeprism/repository/providers/deletion_log_provider.py:59,113,191` — 三个写入方法

## 相关文档

- 代码审查报告：`docs/generated/022/2026-07-24-code-review-deletion-sync-tombstone.md`
- ADR：[2026-07-22 墓碑同步流程架构](../adr/2026-07-22-deletion-sync-tombstone.md)
- PRD：`.scratch/deletion-sync-03-tombstone/prd.md`
