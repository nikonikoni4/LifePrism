---
version: 1.0
created_at: 2026-07-15
updated_at: 2026-07-15
last_updated: 初始版本，记录 CONFLICT_RESOLVE 流程中 AI 产生 _merged 垃圾文件 + token 浪费问题
abstract: CONFLICT_RESOLVE 流程中 AI 被注册了 WriteFileTool，但提示词要求"直接输出内容"。AI 倾向于先 write_file 写 _merged 文件再输出文本，产生垃圾文件（xx_merged.md）和大量无效 token 消耗（权限错误重试）。提示词硬编码在 sync_client.py 中，未纳入 lifeprism prompt 系统。
---

# CONFLICT_RESOLVE AI 合并流程：_merged 垃圾文件 + token 浪费

**优先级**: 中
**影响范围**: `lifeprism/sync/sync_client.py`（提示词 + 流程）、`lifeprism/llm/agent/loop.py`（工具注册）

---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0  | 创建文档初稿，记录问题和清理计划 |

---

## 问题描述

文件同步冲突解决（CONFLICT_RESOLVE）流程存在三个关联问题：

### 问题 1：AI 自行创建 `xx_merged.md` 垃圾文件

AI 被注册了 `WriteFileTool`（`loop.py:465`），但提示词说"直接输出合并后的文档内容，不要解释"。AI 的行为是：

1. 先用 `write_file` 写一个 `{原文件名}_merged.md`（如 `user/user_merged.md`、`user/daily_data/recent_state_merged.md`）
2. 再用 `read_file` 读回刚写的文件
3. 最后在文本回复中输出合并内容

系统只使用 `result.response.content`（第 3 步的文本输出）写入原文件路径（`sync_client.py:1226`）。**`_merged` 文件完全被忽略，留存在磁盘成为垃圾文件。**

### 问题 2：大量 token 浪费在权限错误重试上

AI 在"找到正确文件路径"的过程中反复用无效路径尝试：
- 用相对路径 `user/user.md` → 权限拒绝（`_check_workspace_permission` 要求绝对路径）
- 用 `localData` 根目录 → 权限拒绝（不在 `ALLOWED_DIRS` 中）
- 用 `localData/user` 子目录 → 才成功

实测数据（`user/user.md` 冲突）：
- **9 轮 LLM 调用**，总消耗约 **30K+ tokens**
- 前 3 轮全部是权限错误
- 真正做合并只需要 1-2 轮

### 问题 3：提示词硬编码在 sync_client.py 中

`system_prompt`（`sync_client.py:1190-1194`）和 `content` 合并指令（`:1180-1187`）都是字符串硬编码，未纳入 lifeprism 的 prompt 系统（`templates/agent/`），不利于统一管理和后续优化。

---

## 根因分析

| 根因 | 对应问题 |
|------|---------|
| CONFLICT_RESOLVE 注册了 WriteFileTool/EditFileTool，但提示词期望 AI 直接输出文本——工具能力与指令矛盾 | 问题 1 |
| `_check_workspace_permission` 对相对路径直接拒绝，AI 不知道允许的绝对路径列表 | 问题 2 |
| 提示词在设计时未考虑纳入 prompt 模板系统，作为快速实现直接硬编码 | 问题 3 |

---

## 当前影响

- **磁盘污染**：每次 CONFLICT_RESOLVE 产生 1 个 `_merged.md` 垃圾文件
- **token 浪费**：每个冲突文件额外消耗约 60-80% 的 token（权限探索 + 写读 _merged）
- **时间浪费**：实测 `user/user.md` 合并耗时 78.9s，其中有效工作不足 20s
- **维护困难**：提示词散落在 sync_client.py 中，修改需要改代码而非 prompt 文件

---

## 清理计划

| 步骤 | 内容 | 依赖 |
|------|------|------|
| 1 | 从 CONFLICT_RESOLVE 工具列表中移除 WriteFileTool 和 EditFileTool（只保留只读工具） | 无 |
| 2 | 在 system_prompt 或 user message 中注入 `ALLOWED_DIRS` 的绝对路径列表，减少权限探索 | 步骤 1 |
| 3 | 将 CONFLICT_RESOLVE 的 system_prompt 迁移到 `templates/agent/` prompt 系统 | 步骤 1 |
| 4 | 增加 agent 工具调用评估指标（写文件次数、权限错误次数、有效轮次占比），用于回归检测 | 无，可并行 |

---

## 相关代码文件

- `lifeprism/sync/sync_client.py:1177-1226` — 冲突消息构建 + 合并结果写入
- `lifeprism/llm/agent/loop.py:464-471` — CONFLICT_RESOLVE 工具注册
- `lifeprism/llm/agent/context.py:82-85` — system_prompt 分发（else 分支）
- `lifeprism/llm/agent/tools/filesystem.py:22-48` — `_check_workspace_permission` 权限检查

## 相关文档

- ADR：[2026-07-14 文件同步冲突处理方案](../adr/2026-07-14-file-sync-conflict-resolution.md)（决策 3）
- 测试：`test/core/integration/llm/agent/test_conflict_resolve_loop.py`
- 测试：`test/core/unit/llm/test_conflict_message.py`
