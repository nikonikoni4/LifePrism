---
version: 1.0
created_at: 2026-07-17
updated_at: 2026-07-17
last_updated: 初始版本，记录首次同步全清覆盖关键路径测试覆盖缺失
abstract: 首次同步全清流程的 8 个核心方法（query_all/delete_all_rows/3个API端点/_initial_push_db/_initial_push_files/_advance_local_parent_after_initial_sync/_full_sync_to_cloud）当前无单元测试和集成测试覆盖。
---

# 首次同步全清覆盖流程：测试覆盖缺失

**优先级**: 中
**影响范围**: `lifeprism/sync/sync_client.py`、`lifeprism/server/api/sync_cloud_api.py`、`lifeprism/repository/sync_repository.py`

---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0  | 创建文档初稿 |

---

## 问题描述

云端首次同步全清覆盖方案（替代黑名单）实施后，以下 8 个核心方法无单元测试和集成测试覆盖：

### 无覆盖的方法

| # | 方法 | 文件 | 行数 |
|---|------|------|------|
| 1 | `query_all` | `lifeprism/repository/sync_repository.py` | ~126 行 |
| 2 | `delete_all_rows` | `lifeprism/repository/sync_repository.py` | ~23 行 |
| 3 | `GET /api/sync/initialization-status` | `lifeprism/server/api/sync_cloud_api.py` | ~17 行 |
| 4 | `POST /api/sync/full-clear` | `lifeprism/server/api/sync_cloud_api.py` | ~83 行 |
| 5 | `POST /api/sync/mark-initialized` | `lifeprism/server/api/sync_cloud_api.py` | ~12 行 |
| 6 | `_initial_push_db` | `lifeprism/sync/sync_client.py` | ~78 行 |
| 7 | `_initial_push_files` | `lifeprism/sync/sync_client.py` | ~43 行 |
| 8 | `_advance_local_parent_after_initial_sync` | `lifeprism/sync/sync_client.py` | ~52 行 |
| 9 | `_full_sync_to_cloud` | `lifeprism/sync/sync_client.py` | ~59 行 |

### 涉及的测试场景

1. **首次同步完整流程**：sync_once 检测未初始化 → full-clear → 全量推送 DB → 全量推送文件 → mark-initialized → parent_hash 推进
2. **幂等重试**：full-clear 后推送中断 → 下次 sync_once 重新 full-clear + 推送
3. **空数据场景**：无种子数据 / 空文件目录的首次同步
4. **动态表场景**：存在自定义表的首次同步
5. **full-clear 路径安全检查**：`full-clear` 端点对 SYNC_DIRECTORIES 的 `relative_to` 路径逃逸检测
6. **Row 3 矩阵判定陷阱回归**：验证 `_advance_local_parent_after_initial_sync` 后 parent_hash 正确设置，不会误判 CONFLICT（P0 修复）
7. **N+1 查询回归**：验证 `batch_get_states` + `batch_upsert_states` 的批量行为（P0 修复）
8. **非首次同步回归**：首次同步后，后续 sync_once 走原有增量流程，不受影响

---

## 根因分析

| 根因 | 说明 |
|------|------|
| 首次同步方案实施时间紧张 | 核心流程在一天内完成编码和审查修复，测试作为非阻塞项延后 |
| 测试基础设施依赖 | 首次同步涉及本地+云端两端交互，需要 Mock HTTP 服务端 + 本地 DB 测试夹具 |

---

## 当前影响

- **部署风险**：首次同步流程无法在 CI 中自动化验证，依赖手动测试
- **回归风险**：后续修改 sync_client 或 sync_cloud_api 时，首次同步分支易被无意破坏
- **P0 修复无测试固化**：`_advance_local_parent_after_initial_sync` 的批量操作和矩阵判定已手工修复，但无回归测试

---

## 清理计划

| 步骤 | 内容 | 依赖 |
|------|------|------|
| 1 | 编写 `TestInitialSyncFullClear` 测试类，Mock `httpx.AsyncClient` 模拟云端 3 个 API 端点 | 无 |
| 2 | 测试 `_full_sync_to_cloud` 完整路径（full-clear → push DB → push files → mark-initialized） | 步骤 1 |
| 3 | 测试幂等重试（full-clear 后 mock 推送失败 → 下次重试） | 步骤 1 |
| 4 | 测试 `_advance_local_parent_after_initial_sync` 批量操作和空路径边界 | 无 |
| 5 | 测试 `full-clear` 端点的路径安全检查（路径逃逸攻击向量） | 无 |
| 6 | 集成测试：真实 SQLite DB + Mock HTTP 的首次同步端到端流程 | 步骤 1-5 |

---

## 相关代码文件

- `lifeprism/sync/sync_client.py:223-231` — sync_once 首次同步分支
- `lifeprism/sync/sync_client.py:269-536` — 5 个首次同步方法
- `lifeprism/server/api/sync_cloud_api.py:934-1049` — 3 个 API 端点
- `lifeprism/repository/sync_repository.py` — query_all / delete_all_rows

## 相关文档

- ADR：[2026-07-17 云端初始化与首次同步策略：全清覆盖替代黑名单过滤](../adr/2026-07-17-cloud-init-first-sync-full-clear.md)
- 代码审查报告：`docs/generated/014/2026-07-17-code-review-cloud-init-first-sync.md`
