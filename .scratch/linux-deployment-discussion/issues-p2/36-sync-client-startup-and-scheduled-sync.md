# SyncClient 启动同步 + 定时同步

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 文件同步冲突处理

## What to build

修复 Bug：main.py 中 SyncClient 未调用 start_scheduled_sync(600) 和启动时 sync_once()，导致除应用关闭和手动前端触发外无自动同步。

**Bug 记录参考**：`docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md`

**需要做的 2 件事**：

### 1. 启动时立即同步一次

main.py 启动 SyncClient 后立即调用 `sync_once()`：
- 在 `start_scheduled_sync()` 之前执行
- 使用 `asyncio.to_thread(self.sync_client.sync_once)` 在独立线程中执行
- 启动同步失败不阻塞应用启动（日志记录 ERROR，应用继续运行）
- 并发控制：main.py 中通过 `try_start_sync()` 原子锁判断是否可启动，`sync_once()` 完成后调用 `finish_sync()` 释放锁。若启动同步未完成时定时同步触发，`try_start_sync()` 返回 False，定时同步跳过

### 2. 定时同步

main.py 启动定时同步循环：
- 调用 `start_scheduled_sync(interval=600)`（10 分钟间隔）
- 定时同步在独立线程中运行
- 定时同步失败不阻塞下一次同步（日志记录 ERROR，继续循环）

**关键约束**：
- 仅在 `run_mode == "full"`（本地）时启动定时同步——云端不需要拉取自己
- 云端作为被动的同步服务端，由本地 SyncClient 主动发起同步
- 应用关闭时的同步逻辑保留（已有）

## Acceptance criteria

- [ ] main.py 启动时调用 sync_once()（通过 asyncio.to_thread 在独立线程中）
- [ ] main.py 启动 start_scheduled_sync(600)（10 分钟间隔）
- [ ] 仅在 run_mode == "full" 时启动定时同步
- [ ] 启动同步失败不阻塞应用启动
- [ ] 定时同步失败不阻塞下一次同步
- [ ] 启动同步与定时同步的并发控制：使用 try_start_sync() 原子锁，启动同步未完成时定时同步不重复触发
- [ ] 启动同步不阻塞应用启动（asyncio.to_thread 在独立线程中执行，应用继续初始化）
- [ ] main_agent_only.py 不需要类似改动（云端为被动服务端，不主动同步）
- [ ] 日志记录：每次同步开始/结束、成功/失败
- [ ] 集成测试：应用启动后自动执行一次同步
- [ ] 集成测试：定时同步按间隔执行
- [ ] 集成测试：run_mode != "full" 时不启动定时同步
- [ ] 集成测试：启动同步未完成时定时同步被跳过（并发控制）

**与 issue 34 的协调**：issue 34 在 main.py 创建 SyncClient 时传入 event_loop 引用，本 issue 在同一代码区域追加 sync_once() 和 start_scheduled_sync() 调用。34 先做 event_loop 传入，本 issue 在此基础上追加启动逻辑。

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/33-sync-client-file-sync-full-flow.md` - SyncClient 文件同步全流程必须先就绪（启动同步和定时同步调用的就是 sync_once()）
