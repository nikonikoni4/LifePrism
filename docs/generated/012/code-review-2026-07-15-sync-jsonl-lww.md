# Code Review Report

**审查范围**: 当前未提交的修改（git diff HEAD）
**审查时间**: 2026-07-15
**变更文件**:
- `lifeprism/sync/sync_client.py`（+31/-14，Phase 2c-1 冲突解决分流逻辑）
- `docs/adr/2026-07-14-file-sync-conflict-resolution.md`（+27/-4，ADR v2.1→v2.2）

## 架构上下文

### 相关 ADR
- `docs/adr/2026-07-14-file-sync-conflict-resolution.md` v2.2 (decided) — 本次变更直接对应的 ADR，决策 3 补充 JSONL LWW 实现细节
- `docs/adr/2026-07-09-lww-conflict-resolution.md` — LWW 冲突解决通用策略
- `docs/adr/2026-07-14-sync-full-sync-strategy.md` — 全量同步策略

### 相关 Spec
- `docs/specs/2026-07-11-data-sync-spec.md` — 数据同步模块规格，定义 LWW 冲突解决策略、文件同步（gzip+base64）

### 决策覆盖
- 2/2 变更文件均有 ADR 关联
- 代码实现与 ADR v2.2 决策 3 描述一致（JSONL→LWW，MD→AI 合并）

## 审查结果

Found 4 issues（置信度 ≥ 80）:

### Issue 1: ADR v2.2 决策 5 hash 规范化描述与代码实现冲突

- **类型**: Architecture / Documentation
- **置信度**: 85
- **位置**:
  - ADR: `docs/adr/2026-07-14-file-sync-conflict-resolution.md` 第 6 行（abstract）、第 430-444 行（决策 5 hash 规范化策略）、第 616 行（方案优点汇总 #10）
  - 代码: `lifeprism/sync/hash_utils.py` 第 9-30 行
- **详情**: ADR v2.2 仍保留 v2.1 的过度规范化描述："hash 计算去除所有空白字符"，决策 5 代码示例为 `normalized = "".join(text.split())`，这会移除词语间空格（`"hello world"` 与 `"helloworld"` 产生相同 hash）。但实际代码 `hash_utils.py` 实现的是"统一行尾符（\r\n→\n）+ 去除每行行尾空白，保留词语间空格"，代码注释明确说明"保留词语间的空格（避免 'hello world' 与 'helloworld' 产生相同 hash）"。

  v2.2 版本更新了 ADR 的 abstract（本次修改行），但未修正其中遗留的 hash 描述。由于 ADR 状态为 `decided`，后续开发者若按决策 5 重新实现 `compute_file_hash`，会引入"内容变更被忽略"的严重 bug（Markdown 中 `"# 标题"` 与 `"#标题"` 被视为相同内容，导致 11 态矩阵误判为 SKIP）。
- **依据**:
  - 项目记忆明确记录："compute_file_hash 过度规范化（移除所有空格）会导致内容变更被忽略，需仅保留行尾符规范化和行尾去空格"
  - CLAUDE.md 核心规则 3："列出风险"
  - `docs/docs-rules/docs-write-rules.md:43-52`：abstract 应准确反映文档内容

### Issue 2: JSONL LWW 分流逻辑完全无测试覆盖

- **类型**: Testing
- **置信度**: 90
- **位置**: `lifeprism/sync/sync_client.py` 第 1394-1406 行
- **详情**: 本次变更新增的核心行为——`.jsonl` 后缀文件冲突时直接加入 `push_paths` 保留本地版本（LWW），没有任何测试覆盖。审查所有相关测试文件（`test_sync_conflict_resolve.py`、`test_sync_files_full_flow.py`、`test_sync_client_files.py`）后发现：所有现有冲突测试均使用 `.md` 文件路径作为冲突对象（如 `conflict_test/diary/2026-07-14.md`、`diary/conflict.md`），没有任何测试使用 `.jsonl` 文件。

  缺失的验证点：
  1. JSONL 冲突文件被加入 `push_paths` 推送（而非送 `_resolve_conflicts`）
  2. JSONL 冲突文件不调用 `_resolve_conflicts`
  3. JSONL 文件本地内容不被修改（不经过 AI 合并）
  4. JSONL 文件不创建 `sync_conflict/` 备份
- **依据**:
  - CLAUDE.md 核心规则 5："Bug 先测试"（功能行为变更需测试覆盖）
  - `docs/coding-rules/test-rules.md` 规则 1：核心功能必须测试，分流逻辑属于核心功能分支
  - 本次变更是功能行为变更（从统一 AI 合并改为按后缀分流），属于需要测试覆盖的场景

### Issue 3: md_conflicts 变量命名与实际语义不符

- **类型**: Code Quality / Best Practices
- **置信度**: 80
- **位置**: `lifeprism/sync/sync_client.py` 第 1396 行
- **详情**:
  ```python
  md_conflicts = [p for p in conflict_paths if not p.endswith(".jsonl")]
  ```
  变量名为 `md_conflicts`，暗示只包含 Markdown（.md）文件。但实际过滤条件是 `not p.endswith(".jsonl")`，捕获的是**所有非 JSONL 文件**（包括 .txt、.json、.yaml、无扩展名文件等）。

  ADR v2.2 决策 3 自身措辞更严谨："其他后缀（`.md` 等）→ 送 `_resolve_conflicts` 走 AI 合并"，而代码变量名窄化为"md"。此命名问题同时影响：
  - 第 1411 行日志消息 `"MD 冲突走 AI 合并"`
  - 第 1422 行日志消息 `"MD CONFLICT 解决完成"`
  - 第 1390、1408 行注释 `"MD 走 AI 合并"`

  若未来 `SYNC_DIRECTORIES` 扩展出现非 .md 非 .jsonl 文件冲突，命名会误导维护者。
- **依据**:
  - `docs/coding-rules/backend-core-rules.md` 命名约定要求命名准确反映语义
  - ADR v2.2 决策 3（第 249 行）措辞比代码变量更严谨
  - 建议重命名为 `non_jsonl_conflicts` 或 `ai_merge_conflicts`

### Issue 4: 混合冲突场景测试缺失

- **类型**: Testing
- **置信度**: 80
- **位置**: `lifeprism/sync/sync_client.py` 第 1393-1425 行
- **详情**: 缺少混合冲突场景测试——同一批次中同时存在 `.jsonl` 和 `.md` 冲突文件时，是否正确分流到两条处理路径（JSONL→push_paths，MD→_resolve_conflicts），且两条路径互不干扰。当前测试要么纯 `.md`（如 `test_full_flow_calls_resolve_conflicts_for_conflict_files`），要么无冲突（`test_full_flow_skips_resolve_when_no_conflicts`），完全缺少混合场景。混合分流是 v2.2 决策的核心新增逻辑，无测试覆盖。
- **依据**:
  - `docs/coding-rules/test-rules.md` 规则 3：验证关键业务逻辑分支
  - 混合分流是 v2.2 决策 3 的核心新增逻辑

## 变更摘要

本次变更实现 ADR v2.2 决策 3 的 JSONL LWW 分流逻辑：

**代码变更**（`sync_client.py` Phase 2c-1）：
- 原逻辑：所有 CONFLICT 文件统一走 `_resolve_conflicts`（AI 合并，每文件超时 600s）
- 新逻辑：按 `.jsonl` 后缀分流——JSONL 文件直接加入 `push_paths`（保留本地版本覆盖云端，LWW），非 JSONL 文件（.md 等）走 `_resolve_conflicts` AI 合并

**文档变更**（ADR v2.1→v2.2）：
- 版本号升级，更新 abstract
- 新增版本记录条目（v2.2）
- 决策 3 表格修改 session/*.jsonl 策略描述
- 新增"JSONL LWW 实现细节"、"为什么选择保留本地而非比较 mtime"、"数据丢失风险评估"三个章节

**整体评价**：代码实现与 ADR v2.2 决策 3 描述一致，分流逻辑正确，JSONL 冲突绕过了 600s 超时的 AI 合并是性能优化。主要问题集中在测试覆盖缺失（Issue 2、4）和文档/命名一致性（Issue 1、3）。建议补充测试后合入，并同步修正 ADR 决策 5 的 hash 规范化描述。
