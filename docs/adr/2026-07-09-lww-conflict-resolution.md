---
version: 1.0
created_at: 2026-07-09
updated_at: 2026-07-09
last_updated: 2026-07-09
abstract: 同步冲突解决采用 Last-Write-Wins 策略 + 三类表写入分类，否决 CRDT 和版本号方案。核心原因：主备模式下同步频率低、时间差大，冲突概率极低，不值得为 30+ 张表改 schema。
status: decided
---

# 冲突解决策略：LWW + 三类表分类 vs CRDT/版本号

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

LifeWatch-AI 的本地-云端双向同步需要冲突解决策略。当本地和云端同时修改了同一条记录时，需要决定保留哪个版本。

### 讨论范围

- 冲突解决的粒度和策略
- 三类表（TEXT 主键 / AUTOINCREMENT+UNIQUE / 补充约束）的写入策略
- 是否需要版本号或 CRDT 支持更复杂的冲突解决

### 非讨论范围

- 同步原子性（已在 `2026-07-09-sync-atomicity-strategy.md` 中决定）
- 通信架构（本文档不讨论传输方式）
- HTTP 层的容错（重试、超时）

### 模糊信息的明确定义

- `Last-Write-Wins (LWW)`：比较 `updated_at` 时间戳，谁更晚谁保留。不需要版本号或设备 ID。
- `CRDT (Conflict-free Replicated Data Type)`：无冲突复制数据类型，自动合并并发修改，适用于多端并发编辑场景。
- `主备模式`：同一时间只有一个端（本地或云端）在写入数据，另一个端是"备份"。不是 active-active 双写模式。

### 问题深度

涉及数据同步的核心架构决策。选择影响所有同步表的 schema 设计和写入逻辑，且后续切换策略成本高（需改 schema + 同步逻辑 + 迁移脚本）。

## 现状

- 用户使用模式：电脑开机时用本地，出门或关机时用手机访问云端
- 云端写入频率不高，本地和云端之间通常存在较大的时间差
- 13 张同步表中，9 张已有 `updated_at` 字段（Issue #01 添加）
- `timeline_custom_block` 原本无 UNIQUE 约束，已在 Issue #01 中补充 `UNIQUE(start_time)`

## 可选方案

### 方案 A：LWW + 三类表写入分类（已实现）

比较 `updated_at` 时间戳决定保留版本。按主键类型分三类处理写入。

**优势**

- 不需要改 schema（除已添加的 `updated_at` 字段外）
- 实现简单，逻辑清晰
- 适合主备模式的低频同步场景

**劣势**

- 无法处理真正的并发修改（同时编辑同一条记录时，后写入的覆盖先写入的）
- 依赖 NTP 时间同步保证时钟误差 < 1 秒
- 三类表分类增加了实现复杂度

### 方案 B：版本号 + device_id

每条记录增加 `version` 和 `device_id` 字段，同步时比较版本号解决冲突。

**优势**

- 不依赖时钟同步
- 可以检测并发修改

**劣势**

- 需要为 30+ 张表改 schema（添加 version 和 device_id 字段）
- 改动量大，风险高
- 主备模式下冲突概率极低，收益不明显

### 方案 C：CRDT (cr-sqlite)

使用 cr-sqlite 扩展，自动实现 CRDT 合并。

**优势**

- 自动处理并发修改，无需手动冲突解决
- 适用于多端并发编辑

**劣势**

- 过度设计：适用于多端 active-active 并发场景，而本项目是主备模式
- 需引入 cr-sqlite 扩展依赖
- 改动量大，学习成本高

## 最终决策

选择 **方案 A：LWW + 三类表写入分类**。

## 决策原因

- 原因 1：使用模式决定冲突概率极低。用户使用模式是"电脑开机时用本地，出门或关机时用手机访问云端"，云端和本地之间通常存在较大的时间差，不会同时编辑同一条记录。主备模式下冲突概率 < 0.1%，不值得为低概率事件引入复杂方案。
- 原因 2：改动成本。版本号方案需要为 30+ 张表改 schema，每张表都要添加 version 和 device_id 字段，还要编写迁移脚本。CRDT 需要引入 cr-sqlite 扩展。这些改动量和风险远超 LWW 方案。
- 原因 3：LWW 已满足需求。NTP 时间同步保证时钟误差 < 1 秒，`updated_at` 字段已在 Issue #01 中添加，冲突判断逻辑简单（比较时间戳即可）。三类表写入分类虽然增加了一些实现复杂度，但都是 SQLite 的标准操作（INSERT OR REPLACE + UNIQUE 约束）。

## 三类表写入策略

同步范围内的 13 张表按主键类型分为 3 类：

| 类别 | 主键类型 | 表 | 写入策略 |
|------|---------|-----|---------|
| A | TEXT 主键（跨实例稳定） | mood_entries, diary, todo_list, goal, habits, behavior_analysis, category, sub_category, multi_purpose_map_cache, single_purpose_map_cache | `INSERT OR REPLACE` 按主键判重 |
| B | AUTOINCREMENT + UNIQUE 约束 | user_app_behavior_log, category_map_cache | `INSERT OR REPLACE` 依赖 UNIQUE 约束判重（Code Review 后改为剥离远程 id，避免 sqlite_sequence 污染） |
| C | AUTOINCREMENT，原无 UNIQUE | timeline_custom_block | 补充 `UNIQUE(start_time)` 约束后归入 B 类策略 |

Category B 的特殊处理：Code Review 发现 `INSERT OR REPLACE` 传入远程 `id` 会污染本地 `sqlite_sequence`，修复方案是对 AUTOINCREMENT 表剥离远程 `id`，让 SQLite 自动分配本地 id，依赖 UNIQUE 约束判重。

## 后续影响

- 如果未来使用模式从主备变为 active-active（多端同时编辑），LWW 可能导致数据丢失，需要重新评估 CRDT 或版本号方案
- NTP 时间同步是 LWW 的前提，云端和本地都必须启用 NTP
- 新增同步表时需要确定其主键类型，选择对应的写入策略
- Category B 表的 `id` 在同步后会变化（本地自增），需确保无外键引用这些表的 `id`（已验证）
