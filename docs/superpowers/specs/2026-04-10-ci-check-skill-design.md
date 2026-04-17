---
version: 1.1
created_at: 2026-04-10
updated_at: 2026-04-10
last_updated: 对齐 baseline 回退顺序、运行时状态路径与报告契约表述
abstract: 定义 CI-check skill 的检查时序、基线策略、并行子 agent 方案、状态持久化结构与报告格式。
---

# CI-check Skill Design

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建设计稿，明确提交前检查与提交后状态更新流程 |
| 1.1 | 对齐 baseline 回退顺序、运行时状态路径与报告契约表述 |

## Overview

本设计稿定义 `CI-check` skill 的第一版流程，目标是在每次 `git commit` 前建立“代码编写 -> CI 检查 -> 修复 -> 提交 -> 记录检查基线”的闭环。

当前版本暂不包含静态检查、类型检查、测试执行等代码类脚本检查，重点放在：

1. 用稳定 prompt 约束主 agent 的行为。
2. 先根据 Git 变更范围决定检查任务，再并行分派子 agent。
3. 将检查结果统一写入 `docs/generated/ci-report.md`。
4. 在提交成功后持久化 `check_history[current_branch]`。

## Scope

本设计解决以下问题：

1. `CI-check` skill 何时触发、按什么顺序执行。
2. 主 agent 如何选择检查基线与本次检查范围。
3. 哪些子 agent 需要执行，它们分别检查什么。
4. 检查结果和历史状态如何保存。

本设计不解决以下问题：

1. `lint`、类型检查、测试框架接入。
2. 自动修复文档冲突或代码冲突。
3. Git hook 或外部脚本的最终接入方式。
4. 文档冲突的自动裁决。

## Core Workflow

### 1. Two-Phase Execution

`CI-check` 分为两个阶段：

1. `pre-commit check`
   - 在提交前执行。
   - 读取基线、分析变更、分派检查任务、生成报告。
2. `post-commit finalize`
   - 在提交成功后执行。
   - 将新的 `HEAD` 写入 `check_history[current_branch]`。

### 2. Baseline Resolution

主 agent 必须按以下顺序解析基线：

1. 读取当前分支名 `current_branch`。
2. 读取配置中的 `check_history[current_branch].last_checked_commit`。
3. 若该值存在且在仓库中可解析，则作为 `baseline_commit`。
4. 若不存在或失效，则回退到 `git merge-base HEAD main`。
5. 若 `main` 不存在或无法解析，则允许先尝试对远端跟踪主分支求 merge-base（例如 `origin/main`），再回退到仓库初始提交。

报告中必须说明本次 `baseline_commit` 的来源，避免检查结果不可解释。

### 3. Change Collection

主 agent 必须同时收集两类变更：

1. `git diff <baseline_commit> HEAD --name-only`
   - 用于理解自上次已记录检查点以来，这个分支累计改动了哪些文件。
   - 该结果用于决定需要关注哪些长期文档域。
2. `git diff --cached --name-only`
   - 用于确定本次真正要提交的暂存区范围。
   - 该结果是本次检查的主对象。

如果暂存区为空，主 agent 必须停止并提示当前没有可检查的提交内容。

### 4. Dispatch Rule

主 agent 不允许无条件全量检查，必须先根据变更范围做任务选择。

推荐分派规则：

1. 命中 `docs/` 相关变更时，派发 `docs-structure-checker`。
2. 命中代码、规则或正式文档变更时，派发 `rules-compliance-checker`。
3. 命中会影响正文事实、契约或架构描述的变更时，派发 `docs-code-consistency-checker`。
4. 只要暂存区非空，最后都执行 `report-writer` 汇总结果；如果没有 checker 被派发，也要明确记录本次没有命中需要检查的子任务。

## Agent Model

### Main Agent Responsibilities

主 agent 负责：

1. 读取分支、配置和 Git 变更信息。
2. 决定基线。
3. 按变更范围选择子 agent。
4. 向每个子 agent 传入有限输入与检查边界。
5. 汇总结果并形成最终报告。
6. 在提交成功后更新状态文件。

主 agent 不负责：

1. 自动裁决文档冲突。
2. 在证据不足时强行给出 blocker。
3. 在 pre-commit 阶段提前更新 `check_history`。

### Child Agents

#### docs-structure-checker

职责：

1. 检查 `docs/` 内新增或修改的正式文档是否需要同步更新对应 `index.md`。
2. 检查相关文档是否违反 `docs/docs-rules/index.md` 中声明的 docs-write 规则入口。
3. 只关注文档结构和导航，不判断业务实现正确性。

#### rules-compliance-checker

职责：

1. 先读取 `docs/coding-rules/index.md`。
2. 根据当前变更加载相关规则文件。
3. 判断本次暂存修改是否违反“必须怎么做”的规则。

#### docs-code-consistency-checker

职责：

1. 检查暂存代码是否与 `authority`、`spec`、`design-decisions`、`ARCHITECTURE` 冲突。
2. 按既定冲突类型规则报告问题。
3. 对证据不足的情况输出 `warning`，交由人工裁决。

#### report-writer

职责：

1. 汇总所有 checker 的结果。
2. 生成统一结构的 `docs/generated/ci-report.md`。
3. 区分 blocker、warning、info。

## Prompt Contracts

### Main Agent Contract

主 agent prompt 必须强调：

1. 先读取基线与暂存区，再决定分派。
2. 只按变更范围加载文档，不允许无界全仓扫描。
3. `git diff <baseline_commit> HEAD --name-only` 用于理解累计改动。
4. `git diff --cached --name-only` 用于确定本次提交检查对象。
5. `check_history` 只在 `git commit` 成功后更新。
6. CI 只负责发现与报告，不自动裁决。

### Child Agent Template

所有子 agent 使用统一模板：

```md
你是 <agent_name>。

输入:
- staged_files
- branch_diff_files
- related_paths
- required_docs

你的任务:
1. 只在分配范围内检查。
2. 只加载必要入口文档和必要目标文件。
3. 基于证据输出 findings。

你禁止:
1. 扩张检查范围。
2. 自动修改文件。
3. 在证据不足时给出确定性结论。

按以下结构输出:
## Agent Result
- agent_name:
- scope:
- status: pass | warn | fail
- summary:

## Findings
- severity: blocker | warning | info
- file:
- reason:
- suggested_action:

## Evidence
- checked_files:
- loaded_docs:
- notes:
```

### Specialized Prompt Notes

在上述统一模板基础上：

1. `docs-structure-checker` 必须显式要求检查 `index.md` 同步与 docs 写作规则。
2. `rules-compliance-checker` 必须显式要求先读 `docs/coding-rules/index.md` 再加载具体规则。
3. `docs-code-consistency-checker` 必须显式要求区分“应改代码”与“应改文档”，但不能自动裁决。
4. `report-writer` 必须显式要求先写运行上下文，再汇总 findings。

## State File

建议为 `CI-check` 单独保存状态文件，例如：

- `docs/temp/ci-check-state.json`

说明：

1. 运行时状态属于“提交后 finalize 写入”的临时数据，应保持 gitignored，避免本 skill 自己制造新的 tracked changes。
2. `docs/temp/` 默认不纳入导航索引同步，适合承载运行时临时产物。

推荐结构：

```json
{
  "version": 1,
  "check_history": {
    "branch_name": {
      "last_checked_commit": "abc123",
      "last_report_path": "docs/generated/ci-report.md",
      "last_checked_at": "2026-04-10T13:20:00Z"
    }
  }
}
```

字段语义：

1. `last_checked_commit`
   - 最近一次“已完成检查且已成功提交”的提交点。
2. `last_report_path`
   - 最近一次报告位置。
3. `last_checked_at`
   - 最近一次成功更新状态的时间。

## Report Contract

`docs/generated/ci-report.md` 建议使用固定结构：

```md
# CI Report

## Run Context
- branch:
- baseline_commit:
- baseline_source:
- head_commit_before_commit:
- staged_files_count:

## Dispatch Summary
- dispatched_agents:
- skipped_agents:
- skip_reasons:

## Findings Summary
- blocker:
- warning:
- info:

## Detailed Findings
### blocker
...
### warning
...
### info
...

## Suggested Follow-up
- code changes needed:
- docs changes needed:
- manual decisions needed:
```

报告必须明确：

1. 本次基线来源。
2. 本次检查只覆盖暂存区。
3. 哪些问题阻塞提交，哪些只是提醒。

## Finalization Rule

提交成功后，主 agent 才能执行：

1. `git rev-parse HEAD` 获取新提交哈希。
2. 写入 `check_history[current_branch].last_checked_commit = new_head`。
3. 同步写入 `last_checked_at` 与 `last_report_path`。

如果提交未成功，则禁止更新状态文件。

## Acceptance Notes

本设计被视为可实现，当满足以下条件：

1. `CI-check` skill 能在提交前识别暂存区和累计变更范围。
2. 主 agent 会按范围分派子 agent，而不是固定全量检查。
3. 所有子 agent 使用统一输出契约。
4. 报告能区分 blocker、warning、info。
5. 状态文件只在提交成功后更新。

## Out of Spec

以下内容不在本设计稿中长期维护：

1. 实际 Git hook 脚本细节。
2. 静态检查、类型检查、测试执行的具体命令。
3. 各类规则的结构化解析器实现。
4. 子 agent 的运行器底层实现差异。
