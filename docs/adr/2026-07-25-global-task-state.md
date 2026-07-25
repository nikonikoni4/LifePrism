---
version: 1.1
created_at: 2026-07-25
updated_at: 2026-07-25
last_updated: 修订决策 5 超时降级策略，新增全局前提 3、4（文件/数据库同步的自我纠正能力）
abstract: 引入 GlobalTaskState 单例（IDLE/LOCAL_TASK/CLOUD_SYNC 三态），用 threading.Condition 跨线程协调本地定时任务（10点序列 + 4h 任务）与云端 sync_once 的互斥；backup_documents 从独立 03:00 cron 改为 10点任务子步骤以解决"凌晨3点未开机不补备份"问题；决策 5 超时降级策略依赖全局前提 3、4（文件/数据库同步的自我纠正能力）保证超时执行 dreaming 不会造成永久数据问题。
status: decided
---

# 全局任务状态互斥机制

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |
| 1.1 | 修订决策 5 超时降级策略（dreaming 在超时后仍执行）；新增全局前提 3（文件同步自我纠正）、4（数据库同步自我纠正）；引用 history-bugs/2026-07-25-sync-last-sync-time-update-point-data-loss.md |

## 问题界定

### 问题简述

审查备份功能时发现三类系统性风险，本质均为"本地定时任务与云端 sync_once 之间缺乏全局协调"：

1. **凌晨 3 点未开机不补备份**：`backup_documents` 任务 `skip_compensation=True`，启动时不补执行 → 长期夜间不开机等于永远无文档备份
2. **三类任务并发产生数据库/文件写冲突**：
   - `dreaming`（10点任务）调用 `SyncService.incremental_sync` 时可能与定时 `sync_once`（10分钟一次）并发，两者使用独立的锁（asyncio.Lock vs threading.Lock），无协调
   - `backup_documents`（03:00）复制文件时若 `sync_once` 正在写文件，备份可能不一致
   - `process_session_message`（4h）写 `behavior.md` / `chat_history.json` 时若 `sync_once` 在读，可能读到不一致状态
3. **三类锁完全独立**：ActivityWatch 同步用 asyncio.Lock、云端同步用 threading.Lock、backup/dreaming 无锁，三者无协调

### 讨论范围

- 本地定时任务（10点任务、4h 任务、03:00 backup、数据库 backup）与云端 sync_once 的互斥机制
- 跨线程通信方案选型（threading.Lock / threading.Condition / asyncio.Lock）
- `backup_documents` 是否保留独立 cron，还是并入 10点任务
- 任务超时降级策略
- `process_session_message` 是否纳入互斥

### 非讨论范围

- 数据库备份的互斥 —— 不参与（SQLite Online Backup API 不阻塞读写，详见 §决策 6）
- 备份格式与保留策略 —— 见 ADR [`2026-07-17-data-backup-strategy.md`](./2026-07-17-data-backup-strategy.md)
- 备份范围（哪些目录）—— 见 ADR [`2026-07-17-backup-sync-decoupled-scope.md`](./2026-07-17-backup-sync-decoupled-scope.md)
- sync_once 内部的冲突解决流程 —— 见 ADR [`2026-07-17-conflict-resolution-diff3-replaces-llm.md`](./2026-07-17-conflict-resolution-diff3-replaces-llm.md)

### 模糊信息的明确定义

- **全局任务状态**：跨任务/跨线程共享的"当前正在做什么"标志，用一个变量表示当前是 IDLE/LOCAL_TASK/CLOUD_SYNC
- **LOCAL_TASK**：本地任务合集，包括 10点任务（`incremental_sync` + `dreaming` + `backup_documents`）和 4h 任务（`process_session_message`）
- **CLOUD_SYNC**：云端同步任务（`SyncClient.sync_once`）
- **threading.Condition**：Python 标准库线程原语，提供 `wait/notify` 能力，内部包含一个 Lock，跨线程安全
- **try_acquire**：原子"检查 + 设置"操作，避免 check-then-set 竞态

### 问题深度

涉及跨线程协调的架构决策——主事件循环中的 asyncio 任务如何与线程池/独立线程中的 sync_once 互斥，且不能阻塞主事件循环。

## 现状

### 线程模型

| 组件 | 运行方式 | 所在线程/事件循环 |
|------|---------|------------------|
| FastAPI/uvicorn | asyncio | 主线程主事件循环 |
| ScheduleService (AsyncIOScheduler) | asyncio | 主线程主事件循环 |
| `backup` / `dreaming` / `process_session_message` 任务 | asyncio 协程 | 主线程主事件循环 |
| AgentLoop | asyncio task | 主线程主事件循环 |
| 启动同步 `sync_once` | `asyncio.to_thread` | anyio 线程池 |
| 定时同步循环 `_run_sync_loop` | asyncio task | 主线程主事件循环 |
| 定时同步循环内的 `sync_once` | `asyncio.to_thread` | anyio 线程池 |
| 手动 API 触发的 `sync_once` | `threading.Thread` | 独立 threading 线程（无事件循环） |

### 已有的锁机制

| 锁 | 类型 | 用途 | 局限 |
|----|------|------|------|
| `SyncClient._sync_lock` | threading.Lock | 保护 `_is_syncing` 原子 check-then-set | 仅保护 sync_once 自身并发，不保护 backup/dreaming |
| `SyncService._sync_lock` | asyncio.Lock | 保护 ActivityWatch 增量同步互斥 | 与 SyncClient._sync_lock 独立无协调；asyncio.Lock 跨线程不安全 |
| `HeartbeatManager._lock` | threading.Lock | 保护心跳状态 | 已验证 threading.Lock 跨线程模式可行 |

### 已有的"在线但不同步"端点

存在 `POST /api/sync/heartbeat` event=ping：仅更新心跳时间戳，不执行同步。可用于云端 sync 放弃时报告本地在线。

### 关键缺失

1. 无跨"本地任务 vs 云端同步"的全局互斥机制
2. `backup_documents` 独立 cron + `skip_compensation=True` → 不补备份
3. `dreaming` 与 `sync_once` 可能并发 → 数据库写冲突
4. `process_session_message` 与 `sync_once` 可能并发 → `behavior.md` 不一致

## 方案对比

### 方案 A：三态全局状态（采纳）

引入 `GlobalTaskState` 单例，三态枚举（IDLE / LOCAL_TASK / CLOUD_SYNC），用 `threading.Condition` 保护。

**互斥规则**：
- 本地任务启动前：`try_acquire(LOCAL_TASK, timeout=300s)`，超时降级
- 云端 sync 启动前：`try_acquire(CLOUD_SYNC, timeout=0)`，失败放弃本次 + 调 ping 端点
- `backup_documents` 从独立 cron 移除，作为 10点任务子步骤（解决不补备份问题）

**优点**：
- 显式三态，状态清晰
- `threading.Condition` 跨线程安全（已验证：HeartbeatManager 模式）
- 失败有降级路径，不死等
- `backup_documents` 并入 10点任务后，自动复用 dreaming 的 `skip_compensation=False` 补执行机制
- 可与现有 `SyncClient._is_syncing` 共存（后续可整合）

**缺点**：
- 引入新单例与新概念，需团队理解
- 三态之间存在状态转换的语义约束（需文档说明）

### 方案 B：扩展 SyncClient._is_syncing 为全局状态

复用现有 `SyncClient._is_syncing` 字段，新增"本地任务"状态。

**优点**：不引入新单例
**缺点**：
- SyncClient 职责扩散，违反单一职责
- `_is_syncing` 是 bool，扩展为多状态需要重设计
- backup/dreaming 需要反向依赖 SyncClient，耦合方向错误

### 方案 C：asyncio.Lock 跨线程

用 `asyncio.Lock` 保护全局状态。

**优点**：与 asyncio 架构一致
**缺点**：
- **跨线程不安全**：手动 API 触发的 sync_once 在 `threading.Thread` 中运行，无法安全操作 asyncio.Lock
- 不能在非事件循环线程中 `acquire/release`
- 否决

### 选型理由

方案 A 采纳：
1. 跨线程安全（threading.Condition 是标准跨线程原语）
2. 三态清晰，与现有 `SyncClient._is_syncing` 解耦
3. 已有先例（HeartbeatManager 用 threading.Lock 保护全局状态）
4. 失败有降级路径，不死等

## 决策

### 决策 1：引入 GlobalTaskState 单例（三态枚举）

**状态定义**：

```python
class TaskState(Enum):
    IDLE = "idle"                    # 空闲
    LOCAL_TASK = "local_task"        # 本地任务（10点序列 / 4h 任务）
    CLOUD_SYNC = "cloud_sync"        # 云端 sync_once
```

**实现位置**：`lifeprism/server/services/global_task_state.py`，使用 `LazySingleton` 单例模式（与 `backup_service` 一致）

**锁机制**：`threading.Condition`（包含一个 Lock，额外提供 `wait/notify`）

**核心方法**：

```python
def try_acquire(target: TaskState, timeout: float) -> bool:
    """阻塞获取状态。可被 asyncio.to_thread 包裹避免阻塞主 loop"""
    with self._cond:
        deadline = time.monotonic() + timeout
        while self._state != TaskState.IDLE:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            self._cond.wait(timeout=remaining)
        self._state = target
        return True

def release() -> None:
    """释放状态，唤醒所有等待者"""
    with self._cond:
        self._state = TaskState.IDLE
        self._cond.notify_all()
```

### 决策 2：backup_documents 从独立 cron 移除，并入 10点任务子步骤

**改造内容**：
- 删除 `schedule_service.py:138-145` 中 `backup_documents` 的 cron 注册
- `backup_documents` 不再独立检查 `run_mode`（跟随 10点任务，10点任务本身有 `run_mode == "full"` 守卫）
- 在 `_dreaming` 函数末尾追加 `await backup_service.backup_documents()`

**10点任务执行序列**：

```
10:00 触发（cron="0 10 * * *", skip_compensation=False → 启动时若已过10点补执行）:
  acquired = try_acquire(LOCAL_TASK, timeout=300s)
    ├─ 超时降级（acquired=False，5min 内 CLOUD_SYNC 未释放）:
    │   - incremental_sync 跳过（依赖云端数据，受 if acquired: 守卫）
    │   - dreaming 仍执行（不依赖云端）
    │   - backup_documents 仍执行（备份本地数据）
    │   - 不调用 release()（关键守卫：if acquired: release()）
    │     理由：超时返回 False 时状态从未被设为 LOCAL_TASK，release() 会错误
    │     把可能已被其他线程获取的 CLOUD_SYNC 重置为 IDLE，破坏互斥语义
    └─ 成功获取（acquired=True）:
        1. incremental_sync      (ActivityWatch → 本地数据库)
        2. dreaming              (LLM 写 behavior.md/recent_state.md/user.md)
        3. backup_documents      (平铺备份文档，捕获 dreaming 写入的最新数据)
        4. release()              (受 if acquired: 守卫，acquired=True 时调用)
```

**关键守卫**：实际代码中 `finally` 块使用 `if acquired: global_task_state.release()` 守卫，确保超时降级路径不调用 release()。`release()` 实现是无条件重置状态为 IDLE 并 notify_all()，若超时后另一线程已获取 CLOUD_SYNC，错误调用 release() 会破坏互斥语义。

**为什么 backup 在 dreaming 后面**：dreaming 会写 `behavior.md` / `recent_state.md` / `user.md`，backup 必须在写完之后才能捕获最新数据。若在前面，备份的是过期数据。

**为什么 skip_compensation 保持默认 False（补执行）**：与 dreaming 一致，启动时若已过 10:00 则补执行一次。用户原方案要求"应该要补备份"，并入 10点任务后自动获得补执行能力。

### 决策 3：4h process_session_message 纳入 LOCAL_TASK 互斥

**改造内容**：
- `_process_session_message` 入口加 `try_acquire(LOCAL_TASK, timeout=300s)`
- 超时（5min 内 CLOUD_SYNC 未释放）→ 跳过本次（4h 周期短，下次再处理）
- 执行完成后 `release()`

**为什么 4h 任务也持 LOCAL_TASK 状态（而非独立状态）**：
- 4h 任务写 `behavior.md` / `chat_history.json`，与 sync_once 读写冲突
- 持 LOCAL_TASK 后，sync_once 会放弃本次（成本低，10分钟周期）
- 避免引入更多状态枚举（LOCAL_LIGHT_TASK 等），保持三态简洁
- 4h 任务执行快（几分钟），阻塞 sync_once 的影响可控

**`chat_history.json` 本身不参与同步**（已在 `BACKUP_EXCLUDED_FILENAMES` 和同步白名单排除），但 4h 任务同时写 `behavior.md`（参与同步），所以仍需互斥。

### 决策 4：云端 sync_once 遇 LOCAL_TASK 放弃本次 + 调 ping 端点

**改造内容**：
- `SyncClient.sync_once` 入口加 `try_acquire(CLOUD_SYNC, timeout=0)`（不等待）
- 获取失败（LOCAL_TASK 在跑）→ 放弃本次 sync，调 `POST /api/sync/heartbeat` event=ping
- 获取成功 → 执行 sync_once，完成后 `release()`

**为什么云端 sync 不等待 LOCAL_TASK**：
- sync_once 周期短（10分钟），放弃一次成本低
- LOCAL_TASK 持锁时间长（dreaming 含 LLM 调用，可能 5-15 分钟），等待不划算
- ping 端点保持心跳，云端知道本地在线，下次 10 分钟会再 sync

**改造位置**（3 处触发入口都要改）：
- `lifeprism/server/main.py:309-356`（启动同步）
- `lifeprism/sync/sync_client.py:135-187`（定时同步循环）
- `lifeprism/server/api/sync_status_api.py:75-117`（手动 API 触发）

**ping 端点的复用**：[sync_cloud_api.py:507-546](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L507) 已有 `POST /api/sync/heartbeat` event=ping，仅更新心跳不执行同步。复用此端点报告本地在线。

### 决策 5：10点任务遇 CLOUD_SYNC 用有限等待 + 超时降级

**等待机制**：
- `try_acquire(LOCAL_TASK, timeout=300)` 限时 5 分钟
- 通过 `asyncio.to_thread(try_acquire, ...)` 包裹，避免阻塞主事件循环
- 内部用 `threading.Condition.wait(timeout=remaining)` 实现

**为什么 5 分钟**：
- sync_once 平均 1-3 分钟（数据库不大）
- 5 分钟覆盖 99% 的 sync 场景
- 超时降级比无限等待更可控

**超时降级策略**：

| 子任务 | 超时后行为 | 理由 |
|--------|----------|------|
| `incremental_sync` | 跳过 | 依赖云端数据，CLOUD_SYNC 期间数据不一致 |
| `dreaming` | 仍执行 | 不依赖云端，仅读本地数据库；LLM 写入本地文件和数据库的冲突在下次 sync 自动纠正（见下方全局前提 3、4） |
| `backup_documents` | 仍执行 | 备份本地数据，不依赖云端 |

**为什么不直接跳过整个 10点任务**：dreaming 和 backup 不依赖云端，跳过会丢失当日 AI 总结和备份，不划算。**且由于全局前提 3、4 的保证，超时降级执行 dreaming 引发的文件/数据库冲突会在下次 sync 自动纠正**，不会造成永久数据问题。

### 决策 6：数据库备份不参与互斥

**理由**：
- SQLite Online Backup API（`sqlite3.Connection.backup()`）按 page 复制，不阻塞业务读写
- 数据库备份有自己的独立 cron（`0 0,8,16 * * *`，每 8 小时），与 10点任务和 sync_once 时间错开
- 即使同时执行也不会产生数据不一致（Online Backup 保证原子快照）

**不改造**：`backup_database` 保留独立 cron，不纳入 LOCAL_TASK，不参与互斥。

### 决策 7：跨线程通信用 threading.Condition

**选型对比**：

| 选项 | 跨线程安全 | 等待能力 | 适合场景 |
|------|----------|---------|---------|
| `asyncio.Lock` | ❌ 只在单事件循环内 | 是 | 同 loop 内协程互斥 |
| `threading.Lock` | ✅ | 否（只能加锁/解锁） | 简单互斥，无等待需求 |
| `threading.Condition` | ✅ | ✅ `wait/notify` | 需要等待状态变化（本场景） |
| `asyncio.Event` + `threading.Event` 混用 | ⚠️ 复杂 | 是 | 双重事件循环，过度设计 |

**选 `threading.Condition` 的理由**：
1. 10点任务需要"等待 CLOUD_SYNC 释放"——这是条件等待，不是简单互斥
2. `threading.Condition` 内部包含 `Lock`，提供 `wait/notify` 跨线程能力
3. 已有先例：项目已大量使用 `threading.Lock`（6 处），团队熟悉
4. 10点任务通过 `asyncio.to_thread(try_acquire, timeout)` 包裹，等待在线程池不阻塞主 loop

### 决策 8：与现有 SyncClient._is_syncing 的关系

**当前**：`SyncClient._is_syncing` 是 bool，用 `threading.Lock` 保护，仅防止 sync_once 自身并发（启动同步 vs 定时同步 vs 手动触发）。

**改造后**：
- `SyncClient._is_syncing` 保留不变，继续保护 sync_once 内部并发
- 新增 `GlobalTaskState` 保护"本地任务 vs 云端同步"的全局互斥
- `sync_once` 入口顺序：先 `try_start_sync()`（防 sync 自身并发）→ 再 `try_acquire(CLOUD_SYNC, timeout=0)`（防与 LOCAL_TASK 冲突）

**为什么不直接整合**：
- `SyncClient._is_syncing` 是 bool，扩展为三态需重设计，影响面大
- 拆分关注点：`_is_syncing` 管 sync 内部并发，`GlobalTaskState` 管跨任务互斥
- 后续如需整合，可在 `GlobalTaskState` 稳定后再做（不在本次范围）

## 影响范围

### 新增

- `lifeprism/server/services/global_task_state.py`：`GlobalTaskState` 单例 + `TaskState` 枚举

### 修改

- `lifeprism/server/services/schedule_service.py`：
  - 删除 `backup_documents` 的 cron 注册（138-145 行）
  - `_dreaming` 函数末尾追加 `await backup_service.backup_documents()`
  - `_dreaming` 入口加 `try_acquire(LOCAL_TASK)` + 末尾 `release()`
  - `_process_session_message` 入口加 `try_acquire(LOCAL_TASK)` + 末尾 `release()`
- `lifeprism/server/main.py`：启动同步 `_start_sync_on_startup` 加 `try_acquire(CLOUD_SYNC, timeout=0)`
- `lifeprism/sync/sync_client.py`：`_run_sync_loop` 内 sync_once 前加 `try_acquire(CLOUD_SYNC, timeout=0)` + 失败调 ping
- `lifeprism/server/api/sync_status_api.py`：手动 API 触发的 sync_once 前加 `try_acquire(CLOUD_SYNC, timeout=0)`

### 不变

- `backup_database`：独立 cron 不变
- `SyncClient._is_syncing`：保留不变
- 备份格式、保留策略、完整性校验：不变

## 已知限制

1. **GLOBAL_TASK_STATE 是进程内状态**：不支持多进程协调（如未来 multiprocessing.Process 需要参与互斥时需引入进程间通信机制）
2. **5 分钟超时是经验值**：sync_once 实际耗时受数据库大小、网络状况影响，超时可能误判
3. **LOCAL_TASK 持锁时间较长**：dreaming 含 LLM 调用，可能持锁 5-15 分钟，期间 sync 放弃多次
4. **手动触发的 sync_once 不在事件循环中**：通过 `threading.Thread` 执行，调用 `try_acquire` 时若失败需通过同步 HTTP 调用 ping 端点（不能用 `asyncio` 客户端）
5. **状态不持久化**：进程崩溃重启后状态重置为 IDLE，不影响功能（重启时无任务在跑）

## 决策前提与映射

每个决策依赖各自的具体前提，前提失效时切换到备选方案。

### 决策-前提映射表

| 决策 | 依赖的具体前提 | 前提失效时的备选方案 |
|------|--------------|-------------------|
| 决策 1（三态枚举 + threading.Condition） | ① 多线程模型存在（主 loop + 线程池 + 独立 threading.Thread）；② 已有 `SyncClient._is_syncing` 仅保护 sync_once 自身并发，不保护与本地任务的冲突 | 若是单线程架构则不需要 GlobalTaskState；若 `_is_syncing` 已扩展为多态可直接复用 |
| 决策 2（backup 并入 10点任务） | ① **用户夜间确实不开机**（凌晨 3 点 cron 实际不会触发）；② 10点任务 `skip_compensation=False` 会补执行；③ dreaming 会写文件，backup 必须在 dreaming 后面才能捕获最新数据 | 若用户夜间常运行，保留独立 03:00 cron + 改 `skip_compensation=False` 补执行 |
| 决策 3（4h 持 LOCAL_TASK） | ① **4h 任务写 `behavior.md`**（参与同步，与 sync_once 读写冲突） | 若 `process_session_message` 不写参与同步的文件，就不需要持 LOCAL_TASK 状态 |
| 决策 4（云端遇冲突放弃 + ping） | ① **云端同步周期短（10 分钟），跳过一次成本低**；② 存在 ping 端点可报告在线 | 若同步周期变长（如 1 小时），跳过会丢失过多数据，应改为云端等待 LOCAL_TASK 释放 |
| 决策 5（5 分钟超时） | ① **sync_once 实际耗时一般在 1-3 分钟**（数据库几 MB + 局域网）；② 5 分钟覆盖大多数场景 | **注意：5 分钟是经验估计，无实测统计支持**。若实际耗时经常超 5 分钟，需调大超时或改为动态调整 |
| 决策 6（数据库备份不参与互斥） | ① SQLite Online Backup API 不阻塞业务读写；② 数据库备份独立 cron（00/08/16 点）与 10点任务和 sync_once 时间错开 | 若 SQLite 改用其他备份方式（如 `shutil.copy2`）则必须参与互斥 |
| 决策 7（threading.Condition） | ① 10点任务在主 loop（asyncio）；② sync_once 在线程池/独立线程中；③ 需要等待状态变化（不是简单互斥） | 若所有任务同 loop 则 asyncio.Lock 即可；若不需要等待则 threading.Lock 即可 |
| 决策 8（与 _is_syncing 共存） | ① `_is_syncing` 是 bool，扩展为三态需重设计；② 拆分关注点更清晰 | 若 `_is_syncing` 本来就是枚举，可直接扩展复用 |

### 全局前提（适用于整个 ADR）

1. **单客户端模式**：同一时间只有一端（本地或云端）在主动写入（与 [sync-full-sync-strategy](./2026-07-14-sync-full-sync-strategy.md) 前提一致）。多客户端场景出现时整个互斥机制需重新评估
2. **dreaming 不依赖云端数据**：超时降级时 dreaming 仍执行的前提。若未来 dreaming 需要读取云端数据，超时降级策略需调整
3. **文件同步的自我纠正能力**：即使在 sync_once 文件同步期间 dreaming 修改了文件（如 `behavior.md`），下次 sync_once 时 Pre-sync 阶段会重新计算文件 hash，矩阵判定会重新 PUSH 完整 content，云端自动纠正半写入状态。**此前提支持决策 5 的超时降级策略：dreaming 仍执行不会造成永久文件冲突**。
4. **数据库同步的自我纠正能力**：sync_once 用"开始时间 T0"作为 `last_sync_time` 更新值（参考 [history-bugs/2026-07-25-sync-last-sync-time-update-point-data-loss.md](../history-bugs/2026-07-25-sync-last-sync-time-update-point-data-loss.md)），保证 sync 期间其他任务写入的数据 `updated_at > T0`，下次 sync 的 `WHERE updated_at > T0` 会包含这些数据并 Push。**此前提支持决策 5 的超时降级策略：dreaming 写入数据库的数据下次 sync 会被 Push，不会丢失**。

**前提 3、4 的共同结论**：sync_once 与 dreaming（或其他任务）并发执行产生的文件/数据库冲突，在下次 sync 都会自动纠正。这是决策 5"超时降级时仍执行 dreaming"的根本依据。若未来任一前提失效（如文件同步改为非 hash 矩阵机制、或 `last_sync_time` 改回结束时间），决策 5 必须重新评估为"超时跳过整个 10点任务"。

## 备选触发

- **多客户端场景出现**：GLOBAL_TASK_STATE 跨进程方案失效，需引入 Redis/DB 全局锁（影响决策 1）
- **用户夜间使用习惯改变**：保留独立 03:00 cron + 改 `skip_compensation=False`（影响决策 2）
- **`process_session_message` 不再写 `behavior.md`**：4h 任务退出 LOCAL_TASK 互斥（影响决策 3）
- **云端同步周期变长（>30 分钟）**：云端改为等待 LOCAL_TASK 释放，不放弃（影响决策 4）
- **sync_once 实际耗时经常超 5 分钟**：调大超时或改为动态调整（影响决策 5）
- **SQLite 改用 `shutil.copy2` 备份**：必须参与互斥（影响决策 6）
- **`_is_syncing` 重构为枚举**：可整合进 GlobalTaskState（影响决策 8）

## 相关 ADR / 文档

- [2026-07-17-data-backup-strategy.md](./2026-07-17-data-backup-strategy.md)：数据备份策略（平铺存储 + 复用调度器 + 不做恢复 API），本 ADR 修改其中"文档每天 03:00 备份一次"的决策
- [2026-07-17-backup-sync-decoupled-scope.md](./2026-07-17-backup-sync-decoupled-scope.md)：备份范围与同步范围解耦，本 ADR 不影响备份范围
- [2026-07-17-conflict-failure-policy.md](./2026-07-17-conflict-failure-policy.md)：冲突失败处理，本 ADR 不影响冲突解决流程
- [2026-07-14-sync-full-sync-strategy.md](./2026-07-14-sync-full-sync-strategy.md)：全量同步策略，本 ADR 不影响全量同步触发机制
- [2026-07-14-file-sync-conflict-resolution.md](./2026-07-14-file-sync-conflict-resolution.md)：文件同步冲突解决，本 ADR 不影响冲突解决算法
- Spec: [2026-07-17-data-backup-spec.md](../specs/2026-07-17-data-backup-spec.md)：数据备份模块规格，本 ADR 决策 2 修改 backup_documents 的触发方式

## 评审记录

- 2026-07-25：用户确认方案要点
  - 全局状态可行（参考 HeartbeatManager 模式）
  - 跨线程通信用 threading.Lock/Condition
  - 10点任务遇 CLOUD_SYNC 用有限等待 + 超时降级（5分钟）
  - 4h 任务纳入 LOCAL_TASK 互斥
  - chat_history 处理理由写入 ADR
  - 文档归属：写在新 ADR 中
  - 10点任务 skip_compensation 保持默认 False（补执行）
  - 4h 任务直接获取 LOCAL_TASK 状态
  - 文档备份在 dreaming 后面（捕获最新数据）
