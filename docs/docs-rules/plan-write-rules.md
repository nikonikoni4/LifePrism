---
version: 1.3
created_at: 2026-04-09
updated_at: 2026-04-14
last_updated: 迁移 plan 规则到 docs/docs-rules
abstract: 正式 plan 写入规则，定义 plan 的最小 frontmatter、状态、正文保留原则和模板。
---

# plan-write-rules.md

## 1. 目的

这份文档只定义正式 `plan` 的最小写入规则。

当前原则：

1. `writing-plan` skill 产出的 `plan` 可以直接进入正式 `docs/plans/`
2. `plan` 正文默认不做二次重写
3. 只补最小 frontmatter、版本章节和状态说明

说明：

- docs 总入口见 `docs/docs-rules/docs-write-rules.md`
- docs 的更细治理讨论见 `docs/plans/active/2026-04-08-docs-maintenance.md`
- 本文件不讨论其他复杂 `plan` 场景，只处理当前主流程

## 2. plan 的状态流转

当前正式 `plan` 使用以下状态：

- `draft`
- `active`
- `completed`
- `archived`

状态说明：

1. `draft`
   - 初稿
   - 尚未正式采用或尚未开始执行

2. `active`
   - 当前执行中的计划
   - 默认放在 `docs/plans/active/`

3. `completed`
   - 已执行完成的计划
   - 默认放在 `docs/plans/completed/`

4. `archived`
   - 已归档的历史计划
   - 默认放在 `docs/plans/archived/`

补充规则：

1. `writing-plan` 产出的 `plan` 默认先进入 `docs/plans/active/`
2. 执行完成后移动到 `docs/plans/completed/`
3. `completed` 超过 7 天后进入 `docs/plans/archived/`
4. `plan` 是历史执行资产，默认保留，不主动删除

## 3. 核心规则

<rules>

### 1. 正式 `plan` 的处理原则

1. `writing-plan` skill 产出的 `plan` 可以直接移动到正式 `docs/plans/`
2. 默认保持正文内容不变
3. 只补必要的元数据和版本记录

### 2. 正式 `plan` 的 frontmatter

正式 `plan` 默认包含以下字段：

```yaml
version:
created_at:
updated_at:
last_updated:
abstract:
title:
status:
related_spec:
```

字段说明：

1. `version`、`created_at`、`updated_at`、`last_updated`、`abstract`
   - 继承通用 md 文档规则

2. `title`
   - 当前 `plan` 标题

3. `status`
   - 当前状态，取值为 `draft` / `active` / `completed` / `archived`

4. `related_spec`
   - 若存在对应正式 `spec`，在此标记

### 3. 正式 `plan` 的正文要求

1. 保留 `writing-plan` skill 原始正文结构
2. 在正文开头补一个 `版本` 章节
3. 不要求为了入库而重写正文结构

### 4. 版本章节要求

每个正式 `plan` 都应在正文开头包含：

```md
## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 plan 初稿 |
```

### 5. `docs/plans/index.md`

1. 不要求每个 `plan` 维护独立 `Decision Log`
2. 由 `docs/plans/index.md` 统一承担轻量导航职责
3. `index.md` 只需要简要记录每个 `plan` 做了什么

</rules>

<never_do>

你禁止做以下事情：

1. 为了进入正式 `docs/plans/`，大幅重写 `writing-plan` 产出的正文
2. 把 `plan` 当成正式 `spec` 来重写
3. 要求每个 `plan` 额外维护独立 `Decision Log`
4. 执行完成后直接删除正式 `plan`

</never_do>

## 4. 最小模板

```md
---
version: 1.0
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
last_updated:
abstract:
title:
status: active
related_spec:
---

# {title}

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 plan 初稿 |

{保留 writing-plan 产出的原始正文}
```
