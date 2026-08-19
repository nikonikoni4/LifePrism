---
version: 1.0
created_at: 2026-08-19
updated_at: 2026-08-19
last_updated: 创建文档，记录"分阶段执行启动优化、问题 2 暂不修改只记录"的决策
abstract: LifePrism 后端启动慢的优化采用分阶段策略：先执行低风险的方案 1（删除微信 token 测试段）和方案 3（send_heartbeat 改 fire-and-forget），暂不执行方案 2（启动同步改 fire-and-forget），仅以 ADR 形式记录。决策基于风险分级——方案 2 涉及锁释放时机变更、违反 ADR 2026-07-25-global-task-state 第 4 条契约、shutdown 冲突、task 引用丢失等多重风险，方案 1+3 风险极低且可能已足够解决问题。备选触发条件明确：1+3 修复后启动仍慢则启动方案 2。
status: decided
---

# 启动慢优化的分阶段执行策略

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档，记录"先 1+3、暂不 2 只记录"的分阶段策略 |

## 问题界定

### 问题简述

LifePrism 桌面端启动后，前端长时间无法连接后端。代码调研定位 3 个阻塞点，全部位于 [`lifeprism/server/main.py`](../lifeprism/server/main.py) 的 `lifespan` 函数内顺序 await：

1. **微信 token 测试段**（[`channel.py#L290-L297`](../lifeprism/llm/channel/wechat/channel.py#L290-L297)）：每次启动调用 `api_post("ilink/bot/getupdates")` 验证 token，失败仅记日志无补救动作，紧接着 `_poll_loop` 仍用同一 token 调用同一接口——预检结果对后续行为完全无影响，纯负价值
2. **启动同步阻塞 lifespan**（[`main.py#L368`](../lifeprism/server/main.py#L368)）：`await asyncio.to_thread(sync_client.sync_once)` 走线程不阻塞事件循环，但 lifespan 仍 await 等它完成；sync_once 需 1-3 分钟（29 表 Pull/Push + 文件三阶段），期间 FastAPI 不接受请求
3. **send_heartbeat("online") 阻塞 10s**（[`main.py#L398`](../lifeprism/server/main.py#L398)）：未配置 remote_url 时直接 return 不阻塞，但配置了云端不可达时卡满 10s 超时

### 讨论范围

- 三个阻塞点的修改方案选型
- 修改顺序与执行边界
- 哪些方案先执行、哪些方案暂缓及其判断依据
- 暂缓方案的记录形式（ADR）

### 非讨论范围

- sync_once 内部性能优化（属于同步模块独立决策）
- lifespan 中本地 IO 步骤（init_database / run_migrations / initialize_default_data 等，<1s 不是瓶颈）
- schedule_service.start / AgentLoop create_task（已异步无阻塞）
- `_start_ssh_tunnel` 是否也异步化（属于方案 2 的衍生决策，随方案 2 一并评估）

### 模糊信息的明确定义

- **方案 1**：删除微信 channel 的 token 测试段（channel.py 第 290-297 行整段 try/except）
- **方案 2**：将 `_start_sync_on_startup` 中的 `await asyncio.to_thread(sync_once)` 改为 `asyncio.create_task(asyncio.to_thread(sync_once))` 不 await
- **方案 3**：将 lifespan 第 398 行 `await send_heartbeat("online")` 改为 `asyncio.create_task(send_heartbeat("online"))` 不 await
- **fire-and-forget**：创建后台任务但不等待完成，立即继续后续流程
- **锁内移**：把 try_start_sync/finish_sync/global_task_state.acquire/release 全部包裹在后台 task 内部，让锁随 task 完成才释放

### 问题深度

涉及启动流程重构——lifespan 中的 await 阻塞顺序累积导致前端长时间连不上后端。三个修改方案的"风险-收益"不对称：方案 1+3 风险极低且可能已足够；方案 2 风险高但收益最大。需要在"风险可控"和"问题彻底解决"之间做分阶段取舍。

## 决策前提

### 前提 1：方案 1+3 可能已足够解决启动慢问题

- 启动慢的最长阻塞是方案 2 的 sync_once（1-3 分钟）
- 但方案 1（微信 token 测试网络往返）和方案 3（10s 心跳超时）也是累积时延的一部分
- 1+3 修复后，lifespan 只剩本地 IO（<1s）+ SSH 隧道建立（如有）+ sync_once 阻塞
- 若 sync_once 通常较快（数据量小、网络好），1+3 修复后启动可能已可接受
- **失效场景**：sync_once 本身就是主要瓶颈（数据量大、网络差、首次全量同步），1+3 修复后启动仍慢

### 前提 2：方案 2 的多重风险暂时不可接受

- **锁释放时机变更**：原 `finish_sync()` 和 `global_task_state.release()` 在 sync_once 完成后执行；改 fire-and-forget 后若立即释放，10 分钟定时同步会撞上仍在跑的启动同步
- **违反 ADR 契约**：[`2026-07-25-global-task-state.md`](./2026-07-25-global-task-state.md) 决策 4 明确"启动同步完成后才 release 全局状态"
- **shutdown 冲突**：lifespan 末尾第 570 行 `await asyncio.to_thread(sync_once)` 会和仍在跑的启动 sync_once 撞车
- **task 引用丢失**：asyncio.create_task 不持引用会被 GC（Python 文档明确警告）
- **SSH 隧道时序**：`await sync_client._start_ssh_tunnel()` 仍是 await，单独异步化会让 sync_once 在隧道未就绪时启动
- **前提失效条件**：用户判断"风险可控" → 若 1+3 修复后仍慢，则风险让位于效果

### 前提 3：分阶段执行可降低决策风险

- 1+3 风险低，先做不影响 2 的决策路径
- 1+3 修复后实测启动效果，是 2 是否必要的最直接判据
- 避免一次性改 3 项后无法判断"哪一项真正起了作用"

## 可选方案

### 方案 A：1+2+3 全部一次执行（被否决）

- 优点：一次性彻底解决启动慢
- 缺点：方案 2 风险大且未经效果验证就要承担所有副作用；若 1+3 已足够，方案 2 的风险就是无谓承担
- 否决理由：风险-收益不对称，且无法事后判断方案 2 是否必要

### 方案 B：1+3 先执行，2 暂不修改只记录（**当前选择**）

- 优点：先解决低风险问题，观察效果再决定是否承担方案 2 的风险
- 缺点：若 1+3 不足够，需要二次开发周期处理方案 2
- 选择理由：风险控制驱动方案收缩——与"修改不能影响正常运行"原则一致

### 方案 C：只做方案 2（被否决）

- 优点：直接解决最长阻塞点
- 缺点：方案 2 风险最高，且不解决 1+3 的累积时延；保留 1 的"无价值预检"和 3 的 10s 超时
- 否决理由：选择最高风险方案不符合"先低后高"的风险递进原则

## 决策逻辑

| 决策点 | 前提 | 选择 | 备选触发 |
|--------|------|------|----------|
| 是否一次执行全部 3 项 | 前提 1 + 前提 3 | 否（方案 B） | 1+3 修复后启动仍慢 → 启动方案 2 |
| 方案 2 暂缓的处理形式 | 前提 2 | ADR 记录锁内移/ shutdown 处理/task 引用等关键约束 | — |
| 方案 2 重新启动的判据 | 前提 1 失效 | 1+3 修复后实测启动仍慢 | — |

## 已知限制

### 当前接受的限制

- 方案 2 暂不执行，启动同步仍会阻塞 lifespan 1-3 分钟
- 若 sync_once 是主要瓶颈，1+3 修复后启动慢问题可能未完全解决
- 方案 2 的所有风险（锁释放时机、ADR 契约违反、shutdown 冲突、task GC）保留在原代码中

### 方案 2 重新启动时必须解决的关键约束

下列约束在方案 2 实际启动时**必须满足**，否则会引入新 bug：

1. **锁内移**：try_start_sync / finish_sync / global_task_state.acquire / release 必须包裹在后台 task 内部，让锁随 task 完成才释放，不能在 create_task 后立即释放
2. **task 引用持有**：`app.state.startup_sync_task = asyncio.create_task(...)`，防止 GC 回收
3. **shutdown 处理未完成任务**：lifespan 末尾 shutdown 流程（line 566-594）需判断 `app.state.startup_sync_task` 是否仍在跑，先 await（带超时）或 cancel，再走原 shutdown sync_once
4. **SSH 隧道时序**：`await sync_client._start_ssh_tunnel()` 保持 await 不动（隧道是 sync_once 的前置条件），单独异步化会让 sync_once 在隧道未就绪时启动
5. **task 内部异常处理**：完整 try/except 包裹，避免 "Task exception was never retrieved" 警告
6. **ADR 同步更新**：[`2026-07-25-global-task-state.md`](./2026-07-25-global-task-state.md) 决策 4 需追加说明"启动同步改为后台任务，锁随任务完成释放"

## 后续触发条件

| 条件 | 触发动作 |
|------|----------|
| 方案 1+3 修复后启动仍慢（sync_once 是主要瓶颈） | 启动方案 2 的实现，按"已知限制"小节中的 6 条约束执行 |
| 方案 1+3 修复后启动可接受 | 关闭本 ADR 的待办，将方案 2 标注为"暂不执行，效果验证通过" |
| sync_once 内部性能优化完成（如分批增量优化） | 重新评估方案 2 是否仍必要 |

## 参考资料

- 启动慢分析对话（本次会话）
- [`docs/adr/2026-07-25-global-task-state.md`](./2026-07-25-global-task-state.md) 决策 4（启动同步全局互斥）
- [`lifeprism/server/main.py`](../lifeprism/server/main.py) lifespan 函数
- [`lifeprism/llm/channel/wechat/channel.py`](../lifeprism/llm/channel/wechat/channel.py) start 方法
- [`lifeprism/sync/sync_client.py`](../lifeprism/sync/sync_client.py) try_start_sync / finish_sync / sync_once
