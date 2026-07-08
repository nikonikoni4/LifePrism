---
version: 1.0
created_at: 2026-07-09
updated_at: 2026-07-09
last_updated: 2026-07-09
abstract: 同步系统采用全局 last_sync_time 整体原子性策略（任一表失败则不更新时间戳），否决 row-level best-effort 方案，核心原因是后者会导致失败行数据永久丢失。
status: decided
---

# 同步原子性策略：整体原子 vs Row-level Best-effort

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

LifeWatch-AI 的本地-云端双向同步系统中，`sync_once()` 需要在 Pull（13 张表）和 Push（13 张表）完成后更新 `last_sync_time`。Code Review 指出当前实现是"整体原子性"（任一表失败则不更新时间戳），质疑是否应改为 row-level best-effort（逐行同步、失败行跳过、成功行推进时间戳）。

### 讨论范围

- `sync_once()` 的错误处理粒度：table-level atomic vs row-level best-effort
- `last_sync_time` 的更新策略：全局一个时间戳 vs per-table / per-row 时间戳
- 同步失败后的重试行为：哪些数据会在下次同步中被重新拉取

### 非讨论范围

- 单表内部的行级冲突解决（已由 Last-Write-Wins 策略覆盖）
- HTTP 通信的容错策略（重试、超时等）
- 同步调度的频率和时机

### 模糊信息的明确定义

- `整体原子性`：指 `last_sync_time` 的更新是原子的——Pull 和 Push 全部成功才更新，任一步骤失败则保持旧时间戳。不指数据库事务级别的原子性。
- `row-level best-effort`：指逐行同步、逐行推进同步进度。失败的行被跳过，成功的行更新对应的时间戳。

### 问题深度

这是涉及数据安全性和同步正确性的架构原则决策，不是浅层方案选择。错误的策略会导致数据永久丢失，且问题在正常运行中不易察觉。

## 现状

- `sync_once()` 依次执行 `pull_from_remote()` 和 `push_to_remote()`，两者均遍历 13 张同步表
- 只有一个全局 `last_sync_time`，存储在 `settings_manager` 的 `sync.last_sync_time` 字段
- 任一步骤抛异常时，`set_setting("sync.last_sync_time", current_time)` 不会执行
- 下次同步使用旧的 `last_sync_time`，`query_incremental` 会重新查询到上次失败的所有变更

## 可选方案

### 方案 A：整体原子性（当前实现）

Pull 和 Push 全部成功后才更新 `last_sync_time`。任一表失败则整个 `sync_once()` 抛异常，时间戳不变。

**优势**

- 失败的表下次同步时会用旧时间戳重新查询，数据不会丢失
- 实现简单，只有一个全局时间戳，无需维护 per-table 或 per-row 状态
- 语义清晰：`last_sync_time` 代表"截至此时间点，所有表已成功同步"

**劣势**

- 成功的表下次同步时会重复同步（幂等，无副作用，但有性能开销）
- 单表失败会阻塞整个同步进度

### 方案 B：Row-level Best-effort

逐行同步，成功的行推进时间戳，失败的行跳过并记录。

**优势**

- 失败的行不影响其他行的同步进度
- 理论上更细粒度的错误处理

**劣势**

- **致命缺陷**：如果失败的行 `updated_at <= last_sync_time`（因为时间戳已被成功的行推进），下次 `query_incremental` 查询不到该行，数据永久丢失
- 需要 per-row 或 per-table 时间戳，实现复杂度高
- `last_sync_time` 语义模糊：不再代表"所有数据已同步至此"

## 最终决策

选择 **方案 A：整体原子性**。

## 决策原因

- 原因 1：数据安全优先。用户明确指出 row-level best-effort 的致命缺陷——"如果是 row 原子性，设定了 last_sync_time，下一次失败的就不会再被更新了"。失败的行会因为时间戳已被推进而无法被下次同步查询到，导致数据永久丢失。这是不可接受的。
- 原因 2：幂等重试的代价可接受。方案 A 下成功表会重复同步，但 `INSERT OR REPLACE` 是幂等操作，重复同步不会产生副作用，仅有网络和 CPU 开销。对于 10 分钟一次的定时同步，这个开销可以忽略。
- 原因 3：实现简单且语义清晰。全局一个 `last_sync_time`，成功才更新，失败就重试。不需要维护复杂的时间戳状态，且 `last_sync_time` 的语义明确——"截至此时间点，所有表已成功同步"。

## 后续影响

- 单表失败时，所有表会在下次同步中重复处理（幂等，无副作用）
- 如果某张表持续失败，会阻塞整个同步进度——需要监控同步失败频率，持续失败时告警
- 未来可优化为"table-level 容错 + last_sync_time 整体原子"：单表失败时记录错误并继续其他表，但 `last_sync_time` 仍在任一表失败时不更新。这样成功的表不需要重复同步，失败的表仍能用旧时间戳重试。当前阶段不实施此优化，因为收益有限且增加复杂度。
