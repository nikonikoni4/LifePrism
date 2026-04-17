---
version: 1.3
created_at: 2026-04-09
updated_at: 2026-04-14
last_updated: 迁移 spec 规则到 docs/docs-rules
abstract: 正式 spec 写入规则，定义 spec 的筛选原则、状态、固定结构、frontmatter 和 CI 抓手。
---

# spec-write-rules.md

## 1. 目的

这份文档只负责正式 `spec` 的写入规则。

作用：

1. 定义什么情况下应该写正式 `spec`
2. 定义 `sourc_spec -> spec draft` 的过滤方式
3. 定义正式 `spec` 的固定结构
4. 定义 `spec` 为后续 CI 提供的最小检查抓手

说明：

- docs 总入口见 `docs/docs-rules/docs-write-rules.md`
- docs 的更细治理讨论见 `docs/plans/active/2026-04-08-docs-maintenance.md`
- 本文件只聚焦“正式 `spec` 应该怎么写”

## 2. spec 写入流程说明

`brainstorming` 产生的 `sourc_spec` 通常包含大量实现细节、执行细节和对话上下文。若直接把 `sourc_spec` 当成正式 `spec`，文档会快速腐化，长期无法维护。

因此，正式 `spec` 必须通过过滤生成，而不是直接复制：

1. 先确认是否真的需要创建正式 `spec`
2. 指定一个高细节输入源，通常是 `sourc_spec`
3. 根据本规则筛选长期有价值的内容
4. 写成结构稳定、可维护的正式 `spec draft`
5. 在实现完成后补全或修正 `code_scope` 与 `contract_refs`

## 3. spec 的状态流转

当前正式 `spec` 使用以下状态：

- `draft`
- `accepted_unimplemented`
- `unstable`
- `stable`
- `deprecated`

状态含义：

1. `draft`
   - 初稿
   - 已开始进入正式 `spec` 体系，但内容仍可能不完整或待采纳

2. `accepted_unimplemented`
   - 已被采纳
   - 但尚未落地实现

3. `unstable`
   - 已实现
   - 但仍可能变动，或 CI / AI / 人工仍可能发现问题

4. `stable`
   - 长期稳定
   - 可作为后续任务的正式约束

5. `deprecated`
   - 对应需求已弃用，或被新 `spec` 取代

## 4. 核心规则

<rules>

### 1. 先判断是否应该写正式 `spec`

并不是所有 `brainstorming` 或设计讨论都需要进入 `docs/specs/`。

适合写正式 `spec` 的情况：

1. 当前计划涉及具体功能模块
2. 属于新增功能
3. 属于现有功能模块的嵌入式改动，且会改变长期行为、接口、状态机或关键数据约束
4. 会形成长期复用的 API、schema、命名约束或交互规则
5. 3 个月后人或 AI 仍可能需要查阅

通常不写正式 `spec` 的情况：

1. 纯流程讨论、纯文档讨论、纯工具讨论
2. 与具体功能模块无关的泛化讨论
3. 一次性迁移、一次性试验或短期临时方案
4. 不形成长期约束，且长期复用价值低
5. 只服务于本次执行拆解，实现完成后主要剩历史价值

### 2. 正式 `spec` 必须来自过滤，不是直接复制

正式 `spec` 应从 `sourc_spec` 中筛选，不应直接复制原文。

筛选时默认保留两类内容：

1. 抽象内容
   - 主要功能
   - 范围与非目标
   - 状态流转
   - 算法抽象说明
   - 前端设计风格

2. 规范性技术契约
   - API 路径、方法与核心语义
   - request / response schemas
   - 关键状态机命名
   - 关键数据约束
   - 对后续实现与验收有约束力的固定编码名称

### 3. 正式 `spec` 默认不保留的内容

以下内容默认不进入正式 `spec`：

1. 组件树、文件路径、目录拆分
2. 具体实现优先级和阶段拆解
3. 迁移步骤、回填步骤、发布步骤
4. 大段代码片段、具体库用法、实现技巧
5. 只服务于本次执行的临时设计细节

### 4. 正式 `spec` 的固定结构

每个正式 `spec` 默认按以下结构编写：

1. `Overview`
2. `Scope`
3. `Core Behavior`
4. `Technical Contract`
5. `Interaction / UX Notes`
6. `Acceptance Notes`
7. `Out of Spec`

其中：

1. `Overview`、`Scope`、`Core Behavior`、`Technical Contract`
   - 默认必需

2. `Interaction / UX Notes`
   - 仅在前端功能或交互功能需要时保留

3. `Acceptance Notes`
   - 保留轻量关键验收点
   - 当前不要求展开为完整测试设计

4. `Out of Spec`
   - 用于明确哪些内容不在本 `spec` 中长期维护

### 5. 正式 `spec` 的 frontmatter

正式 `spec` 默认包含以下 frontmatter 字段：

```yaml
version:
created_at:
updated_at:
last_updated:
abstract:
id:
title:
status:
module:
sourc_spec:
related_plan:
code_scope:
contract_refs:
```

字段说明：

1. `version`、`created_at`、`updated_at`、`last_updated`、`abstract`
   - 继承通用 md 文档规则

2. `id`
   - `spec` 的稳定标识

3. `title`
   - `spec` 标题

4. `status`
   - 当前状态

5. `module`
   - 关联功能模块

6. `sourc_spec`
   - 该 `spec draft` 来源于哪份高细节设计稿

7. `related_plan`
   - 当前主要执行计划

8. `code_scope`
   - 抽象内容的语义检查范围

9. `contract_refs`
   - `Technical Contract` 对应的定义文件

### 6. `code_scope` 与 `contract_refs` 的写法

`code_scope` 写法：

1. 允许文件路径与目录路径混用
2. 当相关实现只涉及少量离散文件时，直接写文件路径
3. 当同一功能目录下有较多相关文件，且边界稳定时，可直接写目录路径
4. 目录路径应尽量指向功能边界明确的目录，避免直接给过大的根目录

`contract_refs` 写法：

1. 默认写文件路径
2. 只有当某个目录本身就是稳定的契约定义目录，且其中大部分文件都属于该契约时，才允许写目录路径
3. 不建议仅因文件数量多就把 `contract_refs` 退化为目录路径

当前建议阈值：

1. 对 `code_scope`
   - 当相关文件 `<= 4` 个时，优先直接写文件
   - 当相关文件 `>= 5` 个且集中在同一功能目录时，可直接写目录

2. 对 `contract_refs`
   - 默认不按数量阈值切换
   - 仍以是否为稳定定义目录为主判断是否可写目录

### 7. `code_scope` 与 `contract_refs` 的时间线

1. `code_scope` 与 `contract_refs` 可以在 `plan` 执行完成后补全或修正
2. 当 `spec` 进入 `unstable` 时，二者应成为正式 CI 检查依据
3. 对 `draft` / `accepted_unimplemented` 状态，可以只做弱检查：
   - 字段是否存在
   - 是否缺少明显必要的范围或引用

### 8. 正式 `spec` 与 `plan` 的关系

1. `writing-plan` 可以主要依据 `sourc_spec` 编写
2. 不要求 `plan` 只能依赖过滤后的正式 `spec`
3. 正式 `spec` 更偏长期规格资产
4. `plan` 更偏本次执行资产

### 9. 正式 `spec` 的最小质量要求

1. 不允许只有抽象描述而没有 `Technical Contract`
2. 不允许只有技术细节而没有功能与行为说明
3. 不允许把本次执行步骤直接写成长期 `spec`
4. 不允许缺少 `sourc_spec`、`related_plan`、`code_scope`、`contract_refs`

</rules>

<never_do>

你禁止做以下事情：

1. 直接将 `brainstorming` 或其他技能产出的高细节 `sourc_spec` 原样写入 `docs/specs`
2. 把执行步骤、迁移步骤、阶段拆解直接写成正式 `spec`
3. 把组件树、目录结构、局部实现技巧当作正式 `spec` 的主体内容
4. 在缺少 `Technical Contract` 的情况下，将文档标记为正式 `spec`
5. 在未确认其长期价值前，把泛化讨论或低价值内容写入 `docs/specs`

</never_do>

## 5. 写入模板

```md
---
version: 1.0
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
last_updated:
abstract:
id:
title:
status: draft
module:
sourc_spec:
related_plan:
code_scope:
contract_refs:
---

# {title}

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |

## Overview

## Scope

## Core Behavior

## Technical Contract

## Interaction / UX Notes

## Acceptance Notes

## Out of Spec
```
