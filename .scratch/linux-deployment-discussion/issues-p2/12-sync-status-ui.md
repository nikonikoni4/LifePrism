# 同步状态 UI（可选，P3）

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

在前端设置页面显示同步状态，包括上次同步时间、同步记录数、手动触发同步按钮。

**实现端到端**：
1. 后端 API：`GET /api/sync/status`
   - 返回上次同步时间（`last_sync_time`）
   - 返回同步记录数（按表统计）
   - 返回同步状态（`syncing` / `idle` / `error`）
2. 前端设置页面（`apps/settings/`）增加"同步状态"区域：
   - 显示上次同步时间（相对时间，如"5 分钟前"）
   - 显示同步记录数（按表展开）
   - "手动同步"按钮
   - 同步进度指示器（同步中显示）
3. 手动触发同步：
   - 调用后端 API `POST /api/sync/trigger`
   - 显示同步进度
   - 完成后更新状态
4. UI 测试

**注**：此切片为可选功能，优先级较低，可以放到 P3 实现。

---

## Acceptance criteria

- [ ] API 端点 `GET /api/sync/status` 已实现
- [ ] API 端点 `POST /api/sync/trigger` 已实现（手动触发同步）
- [ ] 前端显示同步状态：
  - 上次同步时间（相对时间）
  - 同步记录数（按表展开）
  - 同步状态（syncing/idle/error）
- [ ] "手动同步"按钮已实现
- [ ] 同步进度指示器已实现
- [ ] UI 测试通过：
  - 测试显示同步状态
  - 测试手动触发同步
  - 测试同步进度显示

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/05-sync-client-basic.md`
- `.scratch/linux-deployment-discussion/issues-p2/06-scheduled-sync.md`
