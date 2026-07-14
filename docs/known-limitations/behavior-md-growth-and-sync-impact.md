# behavior.md 持续增长与同步影响

- **状态**: `acknowledged`（已确认，当前阶段不处理）
- **严重程度**: 低（当前）→ 中（未来文件增长到 1MB+ 时）
- **影响范围**: 文件同步（传输大小 + AI 冲突合并 token 消耗）

## 问题描述

`user/behavior.md` 由 dreaming task 追加式写入，持续记录用户行为模式。当前文件已约 300KB，随使用时间线性增长。

同步影响：
- **传输大小**：当前 300KB gzip 压缩后约 100KB，单次 HTTP 请求完全可接受
- **AI 冲突合并**：CONFLICT 时两份文档内联在 InboundMessage content 中交给 AI 合并。当前 300KB×2 = 600KB 文本，AI 可处理。若增长到 1MB+，两份 2MB 文本可能超出 LLM token 限制

## 当前假设

- behavior.md 增长速度可控（当前约 300KB，估算 6 个月后约 1MB）
- 当前文件大小不构成传输瓶颈
- CONFLICT 场景频率低（主备模式下双方同时修改 behavior.md 的概率小）

## 触发条件

满足以下任一条件时需处理：
- behavior.md 超过 1MB
- AI 冲突合并因 token 限制失败

## 计划改进

按月拆分 behavior.md：

```
user/
├── behavior.md                    # 当前月的行为记录（活跃写入）
├── behavior_archive/
│   ├── 2026-01.md                  # 历史归档（不再修改）
│   ├── 2026-02.md
│   └── ...
```

- dreaming task 每月初将上月 behavior.md 移入 `behavior_archive/`，新建当月文件
- 历史归档不再修改 → 同步时 hash 不变 → Phase 1 check 直接 SKIP
- 当前月文件体积可控（约 50KB/月），AI 合并无压力
- 需修改 dreaming task 的写入逻辑 + AI 读取 behavior 的逻辑（读当前月或历史归档）

## 相关文档

- 文件同步冲突处理方案: [2026-07-14-file-sync-conflict-resolution.md](../adr/2026-07-14-file-sync-conflict-resolution.md) 决策 3（AI 冲突解决）
- 同步 API 协议: 同上 ADR 决策 5（三阶段 check/fetch/push/verify）
