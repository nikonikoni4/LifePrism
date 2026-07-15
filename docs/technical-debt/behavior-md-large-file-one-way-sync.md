---
version: 1.0
created_at: 2026-07-15
updated_at: 2026-07-15
last_updated: 初始版本，记录 behavior.md 大文件同步优化需求——文件拆分 + 单向同步白名单
abstract: behavior.md（约 130KB）仅由本地 dreaming task 写入，云端永不修改，但当前 CONFLICT_RESOLVE 流程会将其纳入 AI 合并，造成不必要的 token 消耗（实测 85K+ tokens/次）。需要：(1) 按月份拆分大文件减少单次传输量；(2) 增加单向同步白名单，名单内文件只走 本地→云端 方向，跳过冲突检测和 AI 合并。
---

# behavior.md 大文件同步优化：拆分 + 单向同步白名单

**优先级**: 中
**影响范围**: `lifeprism/sync/sync_client.py`（冲突判定逻辑）、dreaming task 写入逻辑、behavior.md 文件结构

---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0  | 创建文档初稿，记录问题和优化方向 |

---

## 问题描述

### 问题 1：behavior.md 文件过大

`user/daily_data/behavior.md` 当前约 **130KB**，包含从 2026-03-05 至今的全部日记总结。每次冲突解决时，两份内容（本地 + 云端）内联在 `InboundMessage.content` 中，导致：
- 单次 CONFLICT_RESOLVE 消息 content 长度约 **270KB**（两份 behavior.md 的内容）
- 实测 token 消耗：**85K+ prompt tokens**（仅 behavior.md 一个文件）
- LLM 处理耗时：**44.6s**（日志实测）

### 问题 2：behavior.md 本不应触发冲突

`behavior.md` 的写入来源只有 **dreaming task**（`MessageType.DREAM_TASK`），云端 agent_only 模式不启动 dreaming task（ADR 前提 4）。因此：

| 端 | 会写入 behavior.md？ |
|----|---------------------|
| 本地 dreaming task | ✅ 定时写入 |
| 云端 agent_only | ❌ 永不写入 |

**behavior.md 的变更永远是单向的（本地 → 云端），根本不存在真正的"双方都改"冲突。** 当前触发 CONFLICT_RESOLVE 的原因只能是同步链路异常（如 parent_hash 不一致），这种情况下完全不需要 AI 合并，直接推送本地版本即可。

### 问题 3：同类型文件不止 behavior.md 一个

以下文件同样仅由本地 dreaming task 写入，云端永不修改：

| 文件 | 写入来源 | 预估大小 |
|------|---------|---------|
| `user/daily_data/behavior.md` | dreaming task 聚合 | ~130KB（持续增长） |
| `user/daily_data/recent_state.md` | dreaming task 聚合 | ~5KB |
| `user/chat_history.json` | dreaming task 写入 | 已排除同步（ADR 决策 2） |

这些文件如果触发 CONFLICT_RESOLVE，都应该跳过 AI 合并，直接走本地 → 云端推送。

---

## 当前影响

- **token 浪费**：behavior.md 单文件冲突消耗 85K+ prompt tokens，实际不需要 AI 处理
- **时间浪费**：实测 behavior.md 合并耗时 44.6s（有效工作为 0，因为云端版本为空）
- **垃圾文件**：结合 [[conflict-resolve-ai-merged-garbage]]，还会产生 `behavior_merged.md` 垃圾文件
- **随数据增长恶化**：behavior.md 持续追加，越大概率越大

---

## 两种场景分析

### 场景 A：正常同步（单向推送）

本地 dreaming task 更新 behavior.md → local current_hash 变化 → 同步时检测到仅本地改 → **PUSH**（不会触发 CONFLICT）

✅ 当前流程已经正确。

### 场景 B：异常触发冲突（需要修复的场景）

云端因部署/迁移等原因导致 parent_hash 不一致 → 同步时 11 状态矩阵判定为 CONFLICT → 触发 AI 合并

❌ 此时应直接推送本地版本，不需要 AI 合并。

---

## 优化方案

### 方案 A：单向同步白名单（推荐优先实现）

新增配置 `ONE_WAY_SYNC_FILES`，名单内的文件：
1. 同步时**跳过冲突检测**：即使 parent_hash 不一致，也不判 CONFLICT，直接按本地 current_hash 推送
2. 不进入 `_resolve_conflicts()` 流程
3. 不在 `InboundMessage.content` 中内联内容

```python
# sync_client.py 或 sync_config.py
ONE_WAY_SYNC_FILES = [
    "user/daily_data/behavior.md",
    "user/daily_data/recent_state.md",
]
```

**优势**：
- 改动范围小：只需在 `_sync_files_full_flow()` 的 11 状态矩阵判定前加一层过滤
- 立即消除 behavior.md 的 AI 合并开销
- 为后续新增单向文件提供配置入口

**劣势**：
- 不解决 behavior.md 文件本身过大的问题（传输量仍大）
- 白名单需要手动维护

### 方案 B：按月份拆分 behavior.md（中期优化）

将 `behavior.md` 拆分为按月文件：

```
user/daily_data/
├── behavior/
│   ├── 2026-03.md
│   ├── 2026-04.md
│   ├── 2026-05.md
│   ├── 2026-06.md
│   └── 2026-07.md
```

**优势**：
- 单文件大小可控，增量同步只传输当月文件
- 即使触发冲突，AI 处理的数据量也大幅降低
- 便于按时间范围查询和管理

**劣势**：
- 改动范围大：dreaming task 写入逻辑 + 读取 behavior.md 的所有下游
- 需要处理跨月查询的合并逻辑
- 历史数据迁移

### 推荐实施顺序

1. **先实施方案 A**（单向白名单）：立即止血，消除 behavior.md 的不必要 AI 合并
2. **后实施方案 B**（按月拆分）：在 dreaming task 重构时同步进行，降低单文件传输量

---

## 相关代码文件

- `lifeprism/sync/sync_client.py:1120-1264` — `_resolve_conflicts()` 冲突解决流程
- `lifeprism/sync/sync_client.py` — `_sync_files_full_flow()` 11 状态矩阵判定
- `lifeprism/sync/sync_config.py` — 同步配置（白名单可放此处）
- `lifeprism/llm/agent/context.py` — dreaming task 触发逻辑

## 相关文档

- ADR：[2026-07-14 文件同步冲突处理方案](../adr/2026-07-14-file-sync-conflict-resolution.md)（决策 2 白名单、决策 3 分流策略）
- 技术债：[CONFLICT_RESOLVE AI _merged 垃圾文件 + token 浪费](conflict-resolve-ai-merged-garbage.md)
