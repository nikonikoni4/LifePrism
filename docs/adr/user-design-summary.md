---
version: 1.0
created_at: 2026-07-25
updated_at: 2026-07-25
last_updated: 初始化项目级用户设计原则摘要（迁移 2026-07-25 global-task-state ADR 的设计原则）
abstract: LifeWatch-AI 项目级用户设计原则聚合文档，记录用户在架构决策中的判断方式和设计偏好，供后续 agent 参考以保持决策一致性。
---

# 用户设计原则摘要（项目级）

本文档记录用户在 LifeWatch-AI 项目架构决策中的判断方式（而非决策内容本身），供后续 agent 参考以保持决策一致性。决策详情见 [../adr/index.md](./index.md)。

## 设计原则

- **决策前提与决策点必须显式映射**：写 ADR 时，每个决策必须明确标注它依赖的具体前提，以及前提失效时的备选方案。拒绝在文档末尾堆砌通用前提列表——通用前提与具体决策没有对应关系，读者无法回答"这个决策依赖哪个前提"。判断标准：能否用一句话说清"在什么前提下选这个方案，前提不成立时切换到哪个"。驱动 [2026-07-25-global-task-state.md](./2026-07-25-global-task-state.md) 引入"决策-前提映射表"
- **跨线程协调用 threading 原语而非 asyncio 原语**：当任务跨"主事件循环 asyncio + 线程池/独立 threading.Thread"时，互斥锁必须用 threading.Lock/threading.Condition，不能用 asyncio.Lock。asyncio.Lock 只在单事件循环内有效，跨线程 acquire/release 不安全。判断标准：参与互斥的任一方是否在非事件循环线程中执行。驱动 [2026-07-25-global-task-state.md](./2026-07-25-global-task-state.md) 否决 asyncio.Lock 方案
- **互斥状态设计优先三态枚举而非 bool 扩展**：当需要协调多类任务（如本地任务 vs 云端同步）时，引入显式的三态枚举（IDLE/LOCAL_TASK/CLOUD_SYNC），而非把现有 bool 字段（如 _is_syncing）扩展为多状态。bool 扩展需要重设计，且导致职责扩散。判断标准：现有 bool 字段是否仅为"自身并发保护"。驱动 [2026-07-25-global-task-state.md](./2026-07-25-global-task-state.md) 否决扩展 SyncClient._is_syncing 方案
- **任务冲突时稀缺方等待、高频方放弃**：当两类任务互斥冲突时，频率低/成本高的任务（如 10点 dreaming 含 LLM 调用）应有限等待（5 分钟超时降级），频率高/成本低的任务（如 10分钟一次的云端同步）应直接放弃本次。判断标准：周期长短 + 单次执行成本。放弃高频任务后通过 ping 端点保持心跳。驱动 [2026-07-25-global-task-state.md](./2026-07-25-global-task-state.md) 的"云端放弃 + 本地等待"不对称策略
- **backup 并入有补执行能力的任务以解决不补备份问题**：当独立 cron 任务因 skip_compensation=True 不补执行导致长期失效（如凌晨 3 点用户不开机），将其并入已有 skip_compensation=False 的任务（如 10点 dreaming）作为子步骤，自动获得补执行能力。判断标准：原 cron 触发时间是否与用户使用习惯冲突。驱动 [2026-07-25-global-task-state.md](./2026-07-25-global-task-state.md) 的 backup_documents 并入 10点任务
- **SQLite Online Backup API 不阻塞读写，可豁免互斥**：数据库备份用 sqlite3.Connection.backup() 时按 page 复制，不阻塞业务读写，无需参与全局任务状态互斥。判断标准：备份方式是否为 Online Backup API（shutil.copy2 则必须参与互斥）。驱动 [2026-07-25-global-task-state.md](./2026-07-25-global-task-state.md) 决策 6

## 给后续 agent 的参考

- **写 ADR 时先画决策-前提映射表**——不要在末尾堆砌通用前提。每个决策必须标注：① 依赖的具体前提；② 前提失效时的备选方案。通用全局前提单独列章节，但不超过 2-3 条
- **跨线程场景先画线程模型表**——标注每个任务"在哪线程/事件循环"。只要有任一方在非事件循环线程中，立即排除 asyncio.Lock，改用 threading.Lock/Condition
- **设计互斥状态时检查现有 bool 锁的职责**——如果现有 bool 锁（如 _is_syncing）仅保护"自身并发"，不要扩展它来承担"跨任务互斥"职责。引入独立的三态枚举单例
- **设计冲突处理策略时做不对称设计**——不要让双方都等待或都放弃。根据周期长短+单次成本，让稀缺方等待（带超时降级），高频方放弃（带心跳保持）
- **设计定时任务时检查用户使用习惯**——cron 触发时间是否与用户使用习惯冲突。冲突则并入其他任务，或改 skip_compensation=False 补执行
- **判断数据库备份是否参与互斥时检查备份方式**——sqlite3.Connection.backup() 可豁免；shutil.copy2 必须参与互斥（需 WAL checkpoint）
