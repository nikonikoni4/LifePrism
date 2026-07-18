---
version: 1.0
created_at: 2026-07-17
updated_at: 2026-07-17
last_updated: 2026-07-17
abstract: 冲突失败时不阻塞 sync_once（仅跳过冲突文件），不主动通知用户（仅日志 + sync_conflict 备份），与"不做 Agent 恢复通道"整体决策一致
status: decided
---

# 冲突失败处理策略：不阻塞 + 不主动通知

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

diff3 + LLM 辅助合并流程中，当冲突块 3 次重试都失败后，需要决策：
1. 是否阻塞整个 sync_once？（问题 2）
2. 是否主动通知用户？（问题 3）

这两个问题耦合——如果主动通知，需要某种用户介入通道；如果不主动通知，则不需要阻塞等待用户。

### 讨论范围

- 冲突失败后 sync_once 的行为（阻塞 vs 跳过）
- 用户通知机制（主动通知 vs 被动发现）
- sync_conflict/ 备份的修复（同时备份本地和云端）

### 非讨论范围

- 冲突解决机制本身（见 ADR `2026-07-17-conflict-resolution-diff3-replaces-llm.md`）
- 数据备份机制（见 ADR `2026-07-17-data-backup-strategy.md`）
- 数据库同步冲突失败（数据库仍走 row-level LWW，不涉及冲突解决）

### 问题深度

涉及 UX 设计原则——是否为低频冲突场景投入通知通道成本。

## 现状

**sync_client 的现有失败处理模式**：
- `sync_once` 是整体 try/except 包裹（[sync_client.py:176](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L176)）
- 单文件失败不中断整个 sync_once，记录 ERROR 后下次定时重试
- 已有"跳过失败文件继续其他"的行为模式

**sync_conflict/ 备份的当前 bug**：
- [sync_client.py:1610-1614](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1610-L1614) 只备份本地版本（`local_content`）
- 云端版本（`remote_content`）在降级 keep_ours 后永久丢失
- 用户无法对比本地与云端差异，无法判断 keep_ours 是否正确

## 决策前提

- 前提 1（事实）：sync_once 已有"跳过失败文件继续其他"的行为模式
- 前提 2（原则）：主备模式不需要实时性（用户不在线时同步仍可运行）
- 前提 3（用户判断）：当前主要面向对象是用户自己，可接受被动发现冲突
- 前提 4（用户判断）：冲突使用频率低，未来可能做主动通知，但当下不必要
- 前提 5（决策依据）：与"不做 Agent 恢复通道"整体决策一致（[ADR-2 数据备份策略](./2026-07-17-data-backup-strategy.md)）
- 前提 6（事实）：diff3 覆盖 90% 场景 + LLM 辅助覆盖剩余大部分 + 3 次重试，极端失败场景应该极罕见

## 可选方案

### 方案 A：阻塞整个 sync_once + 立即通知用户

**优势**

- 冲突立即被处理，不会累积
- 用户感知最强

**劣势**

- 一个文件失败导致所有其他文件也无法同步
- 用户不在线时同步永远阻塞
- 需要主动通知通道（与"不做 Agent 恢复通道"矛盾）

### 方案 B：仅跳过冲突文件 + 下次对话时 Agent 通知

**优势**

- 不阻塞其他文件同步
- 用户自然对话时被告知

**劣势**

- 需要维护 `pending_conflict_notifications` 表
- 与"不做 Agent 通道"决策矛盾
- 如果用户几天不对话，冲突一直未告知

### 方案 C：仅跳过冲突文件 + 不主动通知（当前选择）

**优势**

- 与"不做 Agent 恢复通道"整体决策一致
- 实现简单（仅日志 + sync_conflict/ 备份）
- 不阻塞 sync_once
- 符合现有 sync_client 失败处理模式

**劣势**

- 用户可能不会主动查看 sync_conflict/，可能永远不知道
- 如果用户发现 keep_ours 选错了，可能已经晚

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 不做 Agent 通道 + 用户是开发者 + 冲突频率低 | 方案 C（不阻塞 + 不通知） | 当前选择 |
| 未来面向终端用户 + 冲突频率显著提升 | 方案 B（Agent 通知） | 备选触发条件 |
| 冲突需要立即处理 + 用户实时在线 | 方案 A（阻塞 + 立即通知） | 不推荐 |

## 最终决策

当前成立的前提：
- 前提 3（用户是开发者，可接受被动发现）
- 前提 4（冲突频率低，未来可能做主动通知）
- 前提 5（与"不做 Agent 恢复通道"决策一致）

因此选择 **方案 C**，具体包括：

1. **冲突失败时不阻塞 sync_once**：仅跳过冲突文件，其他文件继续同步
2. **冲突文件降级 keep_ours**：保留本地版本
3. **不主动通知用户**：单个冲突块重试 3 次失败降级 keep_ours 时记录 WARNING 日志；整个文件冲突处理异常回退 LWW 时记录 ERROR 日志；均配合 sync_conflict/ 备份
4. **用户被动发现**：通过查看 sync_conflict/ 目录
5. **冲突文件下次 sync_once 重新尝试**：状态保持为 CONFLICT，下次同步会重新 diff3

**关键修复**：sync_conflict/ 必须同时备份本地和云端版本

当前 [sync_client.py:1610-1614](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1610-L1614) 只备份本地版本，需要修复为：

```
sync_conflict/
└── 20260717_154500/
    ├── agent__behavior.md.local.md    ← 本地版本
    └── agent__behavior.md.remote.md   ← 云端版本
```

**修复理由**：
1. 当前只备份本地版本，云端版本在降级 keep_ours 后永久丢失
2. 用户无法对比本地与云端差异，无法判断 keep_ours 是否正确
3. 如果用户发现 keep_ours 选错了，没有云端版本可恢复
4. 同时备份两份让用户有完整的对比和恢复能力

前提失效时的切换路径：
- 若未来面向终端用户或冲突频率显著提升 → 切换到方案 B（Agent 通知）
- 若冲突需要实时处理 → 切换到方案 A（阻塞 + 立即通知）

## 决策原因

- 原因 1：与"不做 Agent 恢复通道"整体决策一致，避免引入复杂度
- 原因 2：用户是开发者，可接受被动发现冲突
- 原因 3：冲突使用频率低，当下不必要做主动通知
- 原因 4：符合现有 sync_client "跳过失败文件继续其他"的行为模式
- 原因 5：sync_conflict/ 备份修复让用户有完整的对比和恢复能力

## 后续影响

**代码结构**：
- 修改 `lifeprism/sync/sync_client.py`（冲突失败时不阻塞 + 同时备份本地和云端）
- 日志记录冲突失败详情（含冲突块 ID、失败原因）

**测试**：
- 冲突失败时不阻塞 sync_once 集成测试
- sync_conflict/ 双向备份测试
- 冲突文件下次 sync_once 重试测试

**关联文档**：
- `docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md`（冲突解决 ADR）
- `docs/adr/2026-07-17-data-backup-strategy.md`（数据备份 ADR）
- `.scratch/file-conflict-resolution-redesign/prd.md`（完整 PRD）
- `docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md`（触发本次决策的 bug）
