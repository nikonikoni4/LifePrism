# 定时同步

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

实现定时同步机制，每 10 分钟自动执行一次同步，支持失败重试和日志记录。

**实现端到端**：
1. 在 `SyncClient` 添加 `start_scheduled_sync()` 方法
2. 使用 `asyncio.create_task()` 创建后台任务
3. 每 10 分钟调用 `sync_once()`
4. **并发控制**：
   - 增加同步状态标志：`_is_syncing: bool = False`
   - 定时触发时检查：如果 `_is_syncing == True`，跳过本次同步并记录 WARNING
   - 同步开始时设置 `_is_syncing = True`，完成后设置为 `False`
   - 使用 `try...finally` 确保异常时也能重置标志
5. 失败重试逻辑：
   - 同步失败时记录 ERROR 日志
   - 下次定时触发时自动重试
6. 日志记录：
   - INFO 级别：同步开始/完成、同步记录数
   - WARNING 级别：跳过同步（上次未完成）
   - ERROR 级别：同步失败原因
7. 集成到 `main.py` 启动流程

---

## Acceptance criteria

- [ ] `SyncClient.start_scheduled_sync()` 已实现
- [ ] 每 10 分钟自动同步（使用 `asyncio` 后台任务）
- [ ] **并发控制生效**：
  - 增加 `_is_syncing: bool` 标志
  - 定时触发时检查，如果正在同步则跳过并记录 WARNING
  - 使用 `try...finally` 确保异常时也能重置标志
- [ ] 失败重试逻辑生效（下次定时触发时自动重试）
- [ ] 日志记录完整：
  - INFO：同步开始时间、完成时间、同步记录数
  - WARNING：跳过同步（上次未完成）
  - ERROR：同步失败原因
- [ ] 集成测试通过：
  - 测试定时触发（Mock 时间）
  - **测试并发控制（上次同步未完成时跳过）**
  - 测试失败重试
  - 测试日志记录

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/05-sync-client-basic.md`
