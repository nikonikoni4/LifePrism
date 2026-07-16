# 打包环境退出绕过 FastAPI 优雅关闭流程 — taskkill /F 强制杀进程导致同步和心跳丢失

## 元信息

- **发生时间**: 2026-04-22（taskkill /T /F 短期修复引入）
- **发现时间**: 2026-07-16
- **修复状态**: ✅ 已修复（场景区分的优雅关闭 + powerMonitor 监听）
- **影响范围**: Windows 打包环境（Electron + PyInstaller）退出流程
- **bug 类型**: 回归 bug — 历史孤儿进程 bug（2026-04-22）的短期修复遗留，从"短期方案"晋升到"长期方案"
- **严重程度**: 严重（P0）— 打包环境退出时：(1) 关闭前同步不执行，本地最近改动无法推送 (2) offline 心跳不发送，云端不知道本地已离线，无法立即接管

## 触发规则

在以下场景时阅读此文档：
- 打包环境退出后云端未立即接管（本地状态仍显示 online）
- 打包环境退出后本地改动未同步到云端
- 修改 Electron `main.cjs` 中 `before-quit` 处理逻辑
- 修改后端 `lifespan` shutdown 函数
- 涉及 Windows 关机/重启/睡眠/唤醒等系统电源事件的业务处理
- 排查"为什么退出时的数据没有推送到云端"
- 参考思源笔记的 `Close(force=false) + syncData(true, false)` 退出同步设计

## Bug 简述

Windows 打包环境下，Electron `before-quit` 使用 `taskkill /pid X /T /F` 强制杀死后端进程树（含所有子进程）。`/F` 等同于 SIGKILL，**完全不触发 FastAPI 的 lifespan shutdown 流程**。导致关闭前同步（sync_once）和 offline 心跳（send_heartbeat）全部丢失，云端无法知道本地已离线并立即接管。

这与用户主动在托盘菜单退出的预期不符（参考思源笔记 `Close(force=false)` 的设计：退出时等待同步完成）。

## 复现场景

1. 打包 LifePrism 为 exe，启动并正常运行（产生一些本地改动，如日记、会话记录）
2. 通过托盘菜单"退出 LifePrism"
3. 观察 `electron.log`：无 `[Shutdown]` 日志链，直接 `taskkill`
4. 观察 `lifeprism.log`：无 `[SHUTDOWN] 关闭前同步完成`，无 `心跳事件已发送: event=offline`
5. 云端状态仍是 online（从未收到 offline 事件），延迟几分钟到几十分钟才因心跳超时判定离线
6. 本地改动未推送到云端

### 附加场景：Windows 关机

用户直接关机时，Windows 发送 `WM_QUERYENDSESSION`，Electron 触发 `before-quit`，走同样的 `taskkill /F` 流程。此时**更糟糕**：如果启动 sync_once 但被强杀 → parent_hash 不一致 → 下次启动走 AI 合并（600s 超时）。

## 复用场景

- 任何需要在进程退出前完成异步清理操作的设计 — 必须提供优雅关闭机制，不能仅依赖操作系统强杀
- 区分"用户主动退出"和"系统关机/重启"两种场景 — 前者有充足时间执行完整同步，后者只有 5 秒
- 系统睡眠/唤醒场景 — 唤醒时应主动触发同步以保证数据时效性

## 代码位置

### 问题代码（修复前）

**Electron 主进程**：[frontend/electron/main.cjs:727-749](file:///d:/desktop/软件开发/LifeWatch-AI/frontend/electron/main.cjs#L727-L749)

```javascript
// 修复前：直接 taskkill /T /F 杀死后端进程树
if (backendProcess) {
    if (process.platform === 'win32') {
        const { exec } = require('child_process');
        exec(`taskkill /pid ${backendProcess.pid} /T /F`, (error) => { ... });
    } else {
        backendProcess.kill();
    }
}
```

**后端 shutdown 流程**：[lifeprism/server/main.py:411-459](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/main.py#L411-L459)

以下 lifespan shutdown 中的步骤全部不执行（因为从未到达）：

```python
# 全部被 taskkill /F 跳过：
proc.terminate()          # 清理监控进程
wechat_channel.stop()     # 关闭微信渠道
loop_task.cancel()        # 取消 AgentLoop
schedule_service.shutdown()  # 停止定时任务
chatbot_service.shutdown()   # 清理 ChatBot
sync_client.sync_once()   # 关闭前同步 ← 关键：数据推送
send_heartbeat("offline") # offline 心跳 ← 关键：云端接管
```

## 发生原因

### 时间线

1. **最初设计**：使用 `backendProcess.kill()` 只杀直接子进程
2. **发现孤儿进程 bug（2026-04-22）**：`backendProcess.kill()` 只杀直接子进程（LifePrism-Server），导致 python 监控子进程（LifePrism-Monitor）变成孤儿
3. **短期修复**：改用 `taskkill /pid X /T /F` 杀死整个进程树，解决孤儿进程问题
4. **遗留问题**：`/F` 是 force kill，不触发任何信号处理，lifespan shutdown 完全跳过
5. **文档标记**：[docs/temp/bugs/2026-04-22-backend-orphan-process.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/temp/bugs/2026-04-22-backend-orphan-process.md) 明确写了"方案1（进程树杀死）是短期修复"，"方案2（优雅关闭）+ 方案4（监控进程心跳检测）是长期方案"

### 根因分析

```
用户退出 → before-quit
  ┌─────────────────────────────────────────────────┐
  │ taskkill /pid X /T /F                            │
  │   ↓ SIGKILL（无法捕获、无法拒绝）                   │
  │   ↓ 进程立即终止                                  │
  │   ↓ 不管当前在做什么                              │
  │   ↓ lifespan shutdown 全部跳过                   │
  └─────────────────────────────────────────────────┘

期望流程：
用户退出 → before-quit
  ┌─────────────────────────────────────────────────┐
  │ POST /shutdown → 后端收到 SIGINT                  │
  │   ↓ uvicorn 进入 lifespan shutdown               │
  │   ↓ sync_once（1-3 分钟）                        │
  │   ↓ send_heartbeat("offline")（~1 秒）          │
  │   ↓ 清理资源 → 进程退出                          │
  │   ↓ Electron 监听 exit 事件 → app.quit()        │
  └─────────────────────────────────────────────────┘
```

### Windows 关机的附加约束

Windows 关机流程：
1. 系统发送 `WM_QUERYENDSESSION` → Electron 触发 `before-quit`
2. **应用只有 5 秒响应时间**（Windows 默认，除非调用 `ShutdownBlockReasonCreate` 注册关机原因）
3. 5 秒内未响应 → 系统发送 `WM_ENDSESSION` → 强制杀死进程
4. sync_once 需要 1-3 分钟，5 秒内根本不可能完成

如果在关机时启动 sync_once 但被 5 秒强杀 → parent_hash 不一致 → 下次启动走 AI 合并 → 600s 超时卡住。

## 解决方案：参考思源的三场景区分设计

### 方案概述

参考思源笔记的退出/关机/睡眠设计：
- **退出**：[conf.go:815-839](file:///D:/desktop/软件开发/siyuan/kernel/model/conf.go#L815-L839) `Close(force=false)`：阻塞等待 `syncData(true, false)` 完成
- **关机**：[main.js:1660-1666](file:///D:/desktop/软件开发/siyuan/app/electron/main.js#L1660-L1666) `powerMonitor.on('shutdown')`：调用 `/api/system/exit`
- **睡眠/唤醒**：[main.js:1627-1658](file:///D:/desktop/软件开发/siyuan/app/electron/main.js#L1627-L1658) `powerMonitor.on('suspend')` / `resume`：唤醒后检查网络 → 触发同步

### 具体改动

**1. 后端新增两个关闭端点**（[system_api.py:23-136](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/system_api.py#L23-L136)）

- `POST /api/v2/system/shutdown`：用户主动退出专用，完整优雅关闭（含 sync_once，5 分钟超时兜底）
- `POST /api/v2/system/quick-shutdown`：Windows 关机专用，跳过 sync_once，只发 offline 心跳（~1 秒完成）

**2. 后端 lifespan shutdown 支持跳过同步**（[main.py:450-470](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/main.py#L450-L470)）

```python
skip_sync = getattr(app.state, "skip_sync_on_shutdown", False)
if skip_sync:
    # 关机场景：跳过 sync_once，只发 offline 心跳
    logger.info("[SHUTDOWN] 跳过关闭前同步（关机场景，只发 offline 心跳）")
elif hasattr(app.state, "sync_client") and app.state.sync_client:
    await asyncio.to_thread(app.state.sync_client.sync_once)
    logger.info("[SHUTDOWN] 关闭前同步完成")

try:
    await send_heartbeat("offline")
except Exception as e:
    logger.warning("[SHUTDOWN] 发送 offline 心跳失败: error=%s", e)
```

**3. Electron 三场景区分**（[main.cjs:236-339](file:///d:/desktop/软件开发/LifeWatch-AI/frontend/electron/main.cjs#L236-L339)）

| 场景 | 触发方式 | 调用端点 | sync_once | offline 心跳 | 超时兜底 |
|------|---------|---------|-----------|-------------|---------|
| 用户主动退出 | 托盘菜单/窗口关闭 | `/shutdown` | ✅ 执行 | ✅ 发送 | 5 分钟强杀 |
| Windows 关机/重启 | `powerMonitor.on('shutdown')` → `before-quit` | `/quick-shutdown` | ❌ 跳过 | ✅ 发送 | 4 秒强杀 |
| 系统唤醒 | `powerMonitor.on('resume')` | `/api/sync/trigger` | ✅ 后台触发 | 不影响 | - |

**4. 系统唤醒后同步**（[main.cjs:924-981](file:///d:/desktop/软件开发/LifeWatch-AI/frontend/electron/main.cjs#L924-L981)）

```javascript
powerMonitor.on('resume', async () => {
    // 唤醒后检查网络连通性，再触发同步
    // 参考：https://github.com/siyuan-note/siyuan/issues/6687
    await new Promise(resolve => setTimeout(resolve, 2000));
    const online = await net.isOnline();
    if (online && backendPort) {
        // 调用 /api/sync/trigger 触发后台同步
    }
});
```

**5. 前端遮罩提示**（[App.tsx](file:///d:/desktop/软件开发/LifeWatch-AI/frontend/App.tsx)）

用户主动退出时显示全屏遮罩"正在同步并退出"（参考思源 `util.PushMsg` 设计）。关机场景跳过 UI（无时间等渲染）。

### 关机场景为什么不执行 sync_once

1. **Windows 只给 5 秒**：sync_once 需要 1-3 分钟，绝对无法完成
2. **中途强杀风险更大**：启动 sync_once 但被杀 → parent_hash 不一致 → 下次启动走 AI 合并（600s 超时）
3. **数据补齐有保障**：每 10 分钟定时同步 + 下次启动同步保证数据延迟 ≤10 分钟
4. **offline 心跳是关键**：让云端立即接管只需 1 秒（HTTP POST），不受关机时限影响

### 修复前后对比

| 行为 | 修复前 | 修复后（主动退出） | 修复后（关机） |
|------|--------|-------------------|---------------|
| sync_once | ❌ 不执行 | ✅ 1-3 分钟完成后退出 | ❌ 跳过（依赖定时同步） |
| offline 心跳 | ❌ 不发送 | ✅ 发送 | ✅ 发送 |
| CPU/内存清理 | ❌ 遗留 | ✅ 完整清理 | ✅ 完整清理 |
| 孤儿进程 | ✅ taskkill /T 解决 | ✅ lifespan shutdown 解决 | ✅ lifespan shutdown 解决 |
| UI 提示 | ❌ 无 | ✅ 全屏遮罩 | ❌ 跳过（无时间） |
| 关闭耗时 | 瞬间（强杀） | 1-3 分钟 | 1-2 秒（跳过同步） |

## 设计教训

1. **短期修复不能永久化** — taskkill /T /F 在 2026-04-22 明确标记为短期修复，应定期审视"是否到了实施长期方案的时间"
2. **系统电源事件是真实高频场景** — 关机、睡眠、唤醒在用户日常使用中高频发生，必须纳入业务流程设计
3. **清理操作和业务操作需要区分** — 关机时"清理资源 + 发心跳"必须完成，"完整同步"可以跳过（有兜底机制）
4. **Windows 关机只有 5 秒** — 关机时不应启动任何耗时超过 5 秒的操作
5. **参考思源是正确选择** — 思源作为成熟的笔记同步工具，其电源事件处理模式经过生产验证，直接复用降低设计风险

## 相关文档

- 前序文档：[docs/temp/bugs/2026-04-22-backend-orphan-process.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/temp/bugs/2026-04-22-backend-orphan-process.md) — 孤儿进程 bug（taskkill /T /F 的来源）
- 参考设计：思源笔记 [main.js:1626-1666](file:///D:/desktop/软件开发/siyuan/app/electron/main.js#L1626-L1666) — powerMonitor 事件监听
- 参考设计：思源笔记 [conf.go:815-839](file:///D:/desktop/软件开发/siyuan/kernel/model/conf.go#L815-L839) — Close(force=false) 退出同步
- 同步设计：[docs/design-decisions/2026-07-14-file-sync-conflict-resolution.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/design-decisions/2026-07-14-file-sync-conflict-resolution.md) — per-file version tracking
