---
version: 1.1
created_at: 2026-04-10
updated_at: 2026-04-10
last_updated: 对齐 baseline 回退顺序与报告契约表述
abstract: 规划 CI-check skill 的实现步骤，包括主流程改写、子 agent 模板落盘、运行时状态设计与验证场景。
title: CI-check Skill Implementation Plan
status: active
related_spec: docs/superpowers/specs/2026-04-10-ci-check-skill-design.md
---

# CI-check Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `CI-check` skill so it performs staged-file-aware pre-commit checks, dispatches scoped child agents in parallel, and records the successful post-commit baseline without dirtying the repo.

**Architecture:** Keep orchestration in `skills/ci-check/skill.md`, move child-agent prompts into companion markdown files, and persist runtime state in an ignored file under `docs/temp/` so post-commit updates do not create tracked changes. Validate the skill with explicit scenario documents that exercise baseline resolution, dispatch decisions, and finalize behavior.

**Tech Stack:** Markdown skill files, Git diff commands, ignored JSON runtime state, repository docs conventions

---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建实施计划 |
| 1.1 | 对齐 baseline 回退顺序与报告契约表述 |

## File Structure

- Modify: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\skills\ci-check\skill.md`
- Create: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\skills\ci-check\prompts\main-agent.md`
- Create: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\skills\ci-check\prompts\docs-structure-checker.md`
- Create: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\skills\ci-check\prompts\rules-compliance-checker.md`
- Create: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\skills\ci-check\prompts\docs-code-consistency-checker.md`
- Create: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\skills\ci-check\prompts\report-writer.md`
- Create: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\skills\ci-check\validation-scenarios.md`
- Create: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\docs\temp\ci-check-state.json`
- Modify: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\docs\superpowers\index.md`
- Create: `D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_lifeprism_tool_use\docs\superpowers\plans\index.md`

### Responsibility Notes

- `skills/ci-check/skill.md` 持有触发条件、主流程、状态机、分派规则和输出契约。
- `skills/ci-check/prompts/*.md` 持有可复用的子 agent prompt 模板，避免把所有内容塞回主 skill。
- `skills/ci-check/validation-scenarios.md` 持有 skill 的验证场景和期望行为。
- `docs/temp/ci-check-state.json` 是运行时状态，不应进入 git 历史。

### Task 1: Replace the main skill contract

**Files:**
- Modify: `skills/ci-check/skill.md`
- Test: `skills/ci-check/validation-scenarios.md`

- [ ] **Step 1: Rewrite the frontmatter and overview so the skill is discoverable and enforceable**

```md
---
name: CI-check
description: Use when preparing to commit code or docs changes and a staged-file-aware CI consistency check must run before commit, with baseline tracking completed after a successful commit.
---

# CI-check

## Overview

This skill governs the pre-commit and post-commit CI loop for repository consistency checks.

Core principles:
1. Check only staged content for the current commit.
2. Use `git diff <baseline> HEAD --name-only` only to understand accumulated branch impact.
3. Update `check_history` only after a successful commit.
4. Report conflicts and missing sync, but do not auto-adjudicate them.
```

- [ ] **Step 2: Replace the current serial procedure with an explicit two-phase state machine**

```md
## Execution Flow

### Phase 1: pre-commit check
1. Resolve `current_branch`.
2. Resolve `baseline_commit` from runtime state, then fallback to `git merge-base HEAD main`; if `main` is unavailable, try a remote-tracking primary branch (for example `origin/main`) before falling back to the initial commit.
3. Read `git diff <baseline_commit> HEAD --name-only`.
4. Read `git diff --cached --name-only`.
5. Stop immediately if the staged set is empty.
6. Select child agents from the changed-file sets.
7. Run child agents in parallel.
8. Synthesize `docs/generated/ci-report.md`.

### Phase 2: post-commit finalize
1. Confirm `git commit` succeeded.
2. Read `git rev-parse HEAD`.
3. Write `check_history[current_branch].last_checked_commit = new_head`.
4. Update timestamp and report path.
```

- [ ] **Step 3: Add hard dispatch rules and runtime-state path rules**

```md
## Required Dispatch Rules

1. Never dispatch child agents before reading both diff sets.
2. Never run a full-repo scan when file-driven scoping is possible.
3. Treat `git diff --cached --name-only` as the authoritative scope for this commit.
4. Treat `docs/temp/ci-check-state.json` as runtime state because `docs/temp/**` is gitignored.
5. Never store post-commit state in a tracked file under `skills/` or `docs/generated/`.
```

- [ ] **Step 4: Add the child-agent output contract and finalize constraints**

```md
## Child Agent Output Contract

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

- [ ] **Step 5: Run a placeholder scan to ensure the old draft content is gone**

Run: `rg -n "decription|commit_A|占位|暂时不实现" skills/ci-check/skill.md`
Expected: no matches

- [ ] **Step 6: Commit**

```bash
git add skills/ci-check/skill.md
git commit -m "docs(skill): rewrite ci-check orchestration contract"
```

### Task 2: Create reusable prompt templates for the main agent and child agents

**Files:**
- Create: `skills/ci-check/prompts/main-agent.md`
- Create: `skills/ci-check/prompts/docs-structure-checker.md`
- Create: `skills/ci-check/prompts/rules-compliance-checker.md`
- Create: `skills/ci-check/prompts/docs-code-consistency-checker.md`
- Create: `skills/ci-check/prompts/report-writer.md`
- Test: `skills/ci-check/validation-scenarios.md`

- [ ] **Step 1: Create the main-agent prompt template with bounded orchestration instructions**

```md
# Main Agent Prompt Template

You are the CI-check main agent.

Inputs:
- current_branch
- baseline_commit
- branch_diff_files
- staged_files
- runtime_state_path

You must:
1. Read both diff sets before dispatch.
2. Dispatch only the child agents justified by changed files.
3. Pass only scoped files and required docs to each child agent.
4. Synthesize a single report.

You must not:
1. Update runtime state before commit succeeds.
2. Perform unbounded repository scans.
3. Auto-resolve document conflicts.
```

- [ ] **Step 2: Create the docs-structure-checker template**

```md
# docs-structure-checker

You are checking docs structure only.

You must:
1. Verify whether changed docs require `index.md` updates.
2. Read the docs-write rule file resolved from `docs/docs-rules/index.md`.
3. Report only structural and navigation issues.

You must not:
1. Judge implementation correctness.
2. Read unrelated code directories.
```

- [ ] **Step 3: Create the rules-compliance-checker and docs-code-consistency-checker templates**

```md
# rules-compliance-checker

You must read `docs/coding-rules/index.md` first, then only the rule files triggered by the staged scope.

# docs-code-consistency-checker

You must compare staged changes against relevant `authority`, `spec`, `design-decisions`, and `ARCHITECTURE` docs without auto-adjudicating ambiguous conflicts.
```

- [ ] **Step 4: Create the report-writer template with fixed report sections**

```md
# report-writer

The report must contain:
1. Run Context
2. Dispatch Summary
3. Findings Summary
4. Detailed Findings
5. Suggested Follow-up
```

- [ ] **Step 5: Verify the prompt files cover every agent named in the skill**

Run: `rg -n "docs-structure-checker|rules-compliance-checker|docs-code-consistency-checker|report-writer" skills/ci-check`
Expected: one skill definition section and one prompt template file per agent

- [ ] **Step 6: Commit**

```bash
git add skills/ci-check/prompts
git commit -m "docs(skill): add ci-check agent prompt templates"
```

### Task 3: Add runtime state contract and validation scenarios

**Files:**
- Create: `docs/temp/ci-check-state.json`
- Create: `skills/ci-check/validation-scenarios.md`
- Modify: `skills/ci-check/skill.md`

- [ ] **Step 1: Create the initial ignored runtime state file**

```json
{
  "version": 1,
  "check_history": {}
}
```

- [ ] **Step 2: Add state-file guidance to the skill so first-run behavior is explicit**

```md
## Runtime State

Path: `docs/temp/ci-check-state.json`

If the current branch has no recorded baseline:
1. Try `git merge-base HEAD main`.
2. If `main` is unavailable, try a remote-tracking primary branch (for example `origin/main`) before falling back to the repository initial commit.
3. Record the baseline source in the report.
```

- [ ] **Step 3: Create validation scenarios that pressure the skill’s edge cases**

```md
# CI-check Validation Scenarios

## Scenario 1: first run on a feature branch
- runtime state has no entry for the branch
- staged files include `docs/docs-rules/index.md`
- expected baseline source: `merge-base`

## Scenario 2: staged scope is empty
- `git diff --cached --name-only` returns nothing
- expected behavior: stop without dispatch

## Scenario 3: commit succeeds after warnings only
- report contains warnings but no blockers
- expected behavior: allow finalize and update runtime state
```

- [ ] **Step 4: Verify the runtime state path is ignored by git**

Run: `git check-ignore docs/temp/ci-check-state.json`
Expected: prints `docs/temp/ci-check-state.json`

- [ ] **Step 5: Verify the skill and scenarios agree on baseline fallback and finalize timing**

Run: `rg -n "merge-base HEAD main|origin/main|post-commit finalize|docs/temp/ci-check-state.json" skills/ci-check`
Expected: matching references in the skill and validation scenarios

- [ ] **Step 6: Commit**

```bash
git add skills/ci-check/skill.md skills/ci-check/validation-scenarios.md
git commit -m "docs(skill): add ci-check runtime state and validation scenarios"
```

### Task 4: Update superpowers navigation and verify docs integrity

**Files:**
- Modify: `docs/superpowers/index.md`
- Create: `docs/superpowers/plans/index.md`
- Modify: `docs/superpowers/plans/2026-04-10-ci-check-skill-implementation.md`

- [ ] **Step 1: Ensure the superpowers root index links both specs and plans**

```md
## 子目录

| 目录 | 说明 |
| ---- | ---- |
| [specs](specs/index.md) | superpowers 相关设计稿与方案文档 |
| [plans](plans/index.md) | superpowers 相关执行计划 |
```

- [ ] **Step 2: Keep the plans index minimal and navigation-only**

```md
# Superpowers Plans Index

## 文档列表

| 文件 | 简要说明 |
| ---- | -------- |
| [2026-04-10-ci-check-skill-implementation.md](2026-04-10-ci-check-skill-implementation.md) | CI-check skill 实施计划，覆盖主 skill 改写、子 agent 模板、运行时状态与验证场景。 |
```

- [ ] **Step 3: Run doc sanity checks for the new planning docs**

Run: `Select-String -Path docs/superpowers/index.md,docs/superpowers/plans/index.md -Pattern 'TODO|TBD|占位|implement later'`
Expected: no output

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/index.md docs/superpowers/plans/index.md docs/superpowers/plans/2026-04-10-ci-check-skill-implementation.md
git commit -m "docs(superpowers): add ci-check implementation plan"
```

## Self-Review

### Spec coverage

- `pre-commit check` 流程已覆盖在 Task 1 和 Task 3。
- 子 agent 并行与 prompt 模板已覆盖在 Task 2。
- `check_history` 与提交后 finalize 已覆盖在 Task 1 和 Task 3。
- 运行时状态改为忽略路径是对设计稿的实现收紧，用于避免 post-commit 自己制造新的 tracked changes。

### Placeholder scan

- 计划正文未使用 `TODO`、`TBD`、`implement later` 等占位词。
- 运行时状态文件保持忽略，不进入提交步骤。
- 每个涉及代码或文档修改的步骤都给出了具体片段或命令。

### Type consistency

- 统一使用 `baseline_commit`、`staged_files`、`branch_diff_files`、`check_history`。
- 统一使用 `pre-commit check` 与 `post-commit finalize` 作为阶段命名。
