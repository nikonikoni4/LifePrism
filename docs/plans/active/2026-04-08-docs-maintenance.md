---
version: 1.0
created_at: 2026-04-08
updated_at: 2026-04-10
last_updated: 补充 frontmatter 与 abstract 字段
abstract: 文档治理计划草案，讨论 docs 分类、生命周期、冲突裁决与 CI 维护机制。
---

# Docs的维护

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 补充 frontmatter 与 abstract 字段 |

## 0. 待确认与待实现

以下内容尚未最终定稿,或后续可能通过工具/CI实现,暂不视为已采纳规则:

1. `QUALITY_SCORE.md`
   - 作为质量评分和 gap tracker 的占位文件
   - 暂不实现

2. `rules` 的生命周期
   - 当前按“无状态”处理
   - 后续可能引入由 AI 辅助判断的生命周期

3. `spec` 的正式进入门槛
   - 当前已确认: `brainstorm` 产生的高细节 `sourc_spec` 默认不是正式 `spec`
   - 当前已确认: 进入正式 `docs/specs/` 的应是从 `sourc_spec` 过滤得到的 `spec draft`
   - `sourc_spec -> spec draft` 的完整过滤规则后续单独定义

4. `spec` 的需求合并检测
   - 对所有 `accepted_unimplemented` / `unstable` / `stable` 状态的 `spec`,是否都要做需求合并检测,暂未最终确定

5. `design-decisions` 的创建阈值
   - 当前只有初步判断标准
   - 何时必须新建 ADR,后续还需收紧

6. 文档辐射代码范围
   - 后续考虑让正式文档尽可能标注其关联代码范围,便于 CI 检查

7. `spec` 的 CI 检查依据
   - 已确认: `spec` 的 CI 检查应分为 `Technical Contract` 检查与抽象内容检查两类
   - 已确认: `Technical Contract` 优先依据相关定义文件检查
   - 已确认: 抽象内容检查需要先声明文件范围,再由 AI 在范围内做语义检查
   - 具体 CI 实现方式后续再定义

8. 哪些 `brainstorm` 需要提升为正式 `spec draft`
   - 已确认: 并不是所有 `brainstorm` 都需要进入 `docs/specs/`
   - 已确认: 需要先判断当前计划是否涉及具体功能模块、新增、嵌入式改动、无关内容或长期低价值内容
   - 具体筛选规则已形成初版,后续仍可继续收紧

## 1. 当前已采纳的文档模型

### 1.1 权限说明

在无人工额外授权的情况下:

- `C`: 可创建
- `U`: 可修改
- `D`: 可删除

除 `docs/temp/` 外,其他文档默认不允许 AI 自主删除。

### 1.2 冲突裁决使用规则

1. 不再使用单一全局数字优先级处理所有文档冲突。
2. 文档冲突按“冲突类型”裁决,而不是按一个总序裁决。
3. `generated`、`ARCHITECTURE`、`RUN` 默认不参与规范类文档冲突排序:
   - `generated` 是代码镜像和检查基线
   - `ARCHITECTURE` 是系统地图
   - `RUN` 是操作说明
4. `CLAUDE.md` / `AGENTS.md` 需要区分内容类型:
   - 非路径类内容,如核心协作规则、工作流约束:在 AI 协作流程中高优先级
   - 路径、导航、文档入口类内容:不参与业务/实现事实裁决,主要起入口作用
5. 当前默认裁决方式:
   - 协作流程和 AI 行为约束冲突: `CLAUDE.md` / `AGENTS.md` 非路径内容优先
   - “必须怎么做”冲突: `rules` 优先
   - “系统现在怎么工作”冲突: `authority` 优先
   - “业务应该是什么”冲突: `stable spec` 优先
   - “为什么这样设计”冲突: `design-decisions` 优先
   - “这次任务当前怎么执行”冲突: `active plan` 只在执行层有效,且服从 `rules` / `authority` / `stable spec` / `design-decisions`
6. 同级或跨维度难以判断的冲突默认交由人工裁决,CI 负责报告,不自动决定。

### 1.3 文档分类

| 文档类型 | 路径 | 职责 | 资产类型 | AI权限 | 冲突裁决角色 | AI加载 | 主要面向对象 |
|---------|------|------|---------|---------|---------|---------|---------|
| **入口文件** | `CLAUDE.md` / `AGENTS.md` | 给 AI 提供最小入口和工作流程约束 | 长期资产 | `U` | 非路径内容: AI 协作流程高优先级<br>路径/导航内容: 不参与业务与实现事实裁决 | 默认加载 | AI |
| **架构地图** | `docs/ARCHITECTURE.md` | 顶层导航,说明主要模块、层级和依赖关系 | 长期资产 | `U` | 不参与统一排序,作为系统地图检查是否需同步更新 | 按需加载 | AI |
| **编码规则** | `docs/coding-rules/` | 必须遵守的规范、约束、触发场景 | 长期资产 | `U` | 在“必须怎么做”冲突中优先 | 按需加载 | AI |
| **文档规则** | `docs/docs-rules/` | 编写 docs 时必须遵守的写作与导航规则 | 长期资产 | `U` | 在文档写作与同步规则冲突中优先 | 按需加载 | AI |
| **权威参考** | `docs/authority/` | 系统中特定且关键的实现知识,用于承接不适合放在 `rules` 里的重要实现事实 | 长期资产 | `U` | 在“系统现在怎么工作”冲突中优先 | 按需加载 | AI和人 |
| **启动文档** | `docs/RUN.md` | 如何启动系统,包括启动指令、端口、运行前提 | 长期资产 | `U` | 不参与统一排序,作为操作说明检查是否需同步更新 | 按需加载 | AI和人 |
| **产品规格** | `docs/specs/` | 对于正式 `spec`,承载业务意图、业务规则、领域概念,以及规范性技术契约 | 长期资产 | `CU` | `stable spec` 在“业务应该是什么”冲突中优先<br>非稳定状态默认不参与正式裁决 | 按需加载 | AI和人 |
| **架构决策** | `docs/design-decisions/` | 记录为什么这样设计 | 长期资产 | `CU` | 在“为什么这样设计”与长期取舍冲突中优先 | 按需加载 | AI和人 |
| **自动生成** | `docs/generated/` | 代码镜像,不手工维护正文,用于快速了解当前实现事实及 CI 结果 | 长期资产 | `CU` | 作为代码镜像和检查基线,不参与普通排序 | 按需加载 | AI |
| **执行计划** | `docs/plans/` | 执行过程中的任务分解和执行记录,也是历史执行资产 | 长期资产 | `CU` | `active plan` 只在本次执行层有效,且服从上层正式文档<br>`completed` / `archived` 主要作为历史参考 | 按需加载 | AI |
| **临时内容** | `docs/temp/` | 暂时无法归类的内容、草稿、临时记录 | 短期资产 | `CUD` | 不参与正式裁决 | 按需加载 | AI |

### 1.4 具体文档说明

| 文档路径 | 包含内容 |
|---------|---------|
| `CLAUDE.md` / `AGENTS.md` | 1. 文档入口和加载指引:包括各类文档入口、触发条件、索引链接。2. 高层协作规则和工作流程。3. 不承担具体业务事实和系统实现细节的长期定义。 |
| `docs/ARCHITECTURE.md` | 项目主要模块、层级、依赖关系说明,作为系统地图使用。 |
| `docs/authority/index.md` | `authority` 目录导航。 |
| `docs/design-decisions/index.md` | ADR 目录导航。 |
| `docs/specs/index.md` | `spec` 目录导航,用于汇总正式 `spec draft` 及其后续状态。 |
| `docs/generated/index.md` | 生成文档目录导航。 |
| `docs/plans/index.md` | `plan` 目录导航,并简要记录每个 plan 主要做了什么。 |

## 2. 当前已采纳的生命周期

### 2.1 生命周期说明

- `——` 表示无状态
- 无状态不代表不维护,而是表示不使用显式状态机
- 长期资产默认保留,不由 AI 自主删除

### 2.2 生命周期总表

| 文档类型 | 路径 | 文档状态定义 | 状态变量 |
|---------|------|------|------|
| **入口文件** | `CLAUDE.md` / `AGENTS.md` | `——` | 协作规则变化、入口结构变化 |
| **架构地图** | `docs/ARCHITECTURE.md` | `——` | 模块结构变化、依赖关系变化 |
| **编码规则** | `docs/coding-rules/` | `——` | 当前阶段由人工决定创建与调整 |
| **文档规则** | `docs/docs-rules/` | `——` | 当前阶段由人工决定创建与调整 |
| **权威参考** | `docs/authority/` | `draft` / `stable` | 代码库情况、人工确认 |
| **产品规格** | `docs/specs/` | `draft` / `accepted_unimplemented` / `unstable` / `stable` / `deprecated` | 用户需求修改、实现状态、时间、专项检查结果 |
| **架构决策** | `docs/design-decisions/` | `stable` / `deprecated` | 新决定出现 |
| **自动生成** | `docs/generated/` | `——` | 代码结构变化、生成脚本执行 |
| **执行计划** | `docs/plans/` | `draft` / `active` / `completed` / `archived` | 人工确认、任务完成状态、时间 |
| **临时内容** | `docs/temp/` | `——` | 临时写入和清理 |

### 2.3 各类文档状态机

#### authority

状态流转:

`draft -> stable -> draft -> stable`

规则:

- 当用户决定将某些特定系统内容放入 `authority`,先进入 `draft`
- 用户确认后进入 `stable`
- 若 CI、AI 或人工发现问题,退回 `draft`
- 修复并再次经人工确认后回到 `stable`

#### specs

状态定义:

- `draft`: 初稿,未采纳或存在明显问题
- `accepted_unimplemented`: 已被采纳,但尚未落地实现
- `unstable`: 已采纳且已实现,但仍可能变动或存在问题
- `stable`: 长期稳定
- `deprecated`: 已弃用

状态流转:

`draft -> accepted_unimplemented -> unstable -> stable -> draft`

补充流转:

- 任意状态 -> `deprecated`: 当对应需求消失或被废弃

规则:

- 当前已确认的生成链路:
  - `brainstorm -> sourc_spec(高细节临时产物) -> spec draft(正式进入 docs/specs/)`
- `sourc_spec` 的定位:
  - 作为高细节设计草稿,服务于后续 `plan` 编写
  - 内容不要求固定结构,因为它高度依赖具体对话过程
  - 默认不直接作为正式 `spec` 长期保存
- `spec draft` 的定位:
  - 作为正式进入 `docs/specs/` 的长期资产初稿
  - 当前已确认应保留两类内容:
    - 抽象内容: 主要功能、范围、状态流转、算法抽象说明、前端设计风格等
    - 规范性技术契约: API、schemas、关键状态机命名、关键数据约束等
- `plan` 的关系:
  - `writing-plan` 可以主要依据 `sourc_spec` 编写
  - 不要求仅依赖过滤后的 `spec draft`
- `brainstorm -> spec draft` 采用两阶段筛选:
  - 第一阶段: 判断该 `brainstorm` 是否值得进入正式 `spec`
  - 第二阶段: 若值得进入,再从 `sourc_spec` 中筛选可长期保留的内容
- AI 创建初稿后进入 `draft`
- 当文档完成规定结构并经用户确认采纳,但尚未实现时,进入 `accepted_unimplemented`
- 当需求已被实现并具备可检查对象后,进入 `unstable`
- `unstable` 进入 `stable` 需要同时满足:
  - 长时间(一个月)未被改动
  - CI、AI、人工未检测出错误
  - 满足时间后进行一次专项检查
  - 专项检查通过
- 若 CI、AI、人工检测出错误,或用户需求发生修改,退回 `draft`

##### brainstorm 提升为 spec 的第一阶段筛选

目标:

- 先判断某次 `brainstorm` 是否值得进入正式 `docs/specs/`
- 避免把所有讨论结果都沉淀为长期资产

适合提升为正式 `spec draft` 的情况:

1. 当前计划涉及具体功能模块
2. 属于新增功能
3. 属于现有功能模块的嵌入式改动,且会改变长期行为、接口、状态机或关键数据约束
4. 会形成长期复用的 API、schema、命名约束或交互规则
5. 3 个月后人或 AI 仍可能需要查阅

通常不提升为正式 `spec draft` 的情况:

1. 纯流程讨论、纯文档讨论、纯工具讨论
2. 与具体功能模块无关的泛化讨论
3. 一次性迁移、一次性试验或短期临时方案
4. 不形成长期约束,且长期复用价值低
5. 只服务于本次执行拆解,实现完成后主要剩历史价值

说明:

- 第一阶段的核心不是判断内容是否详细,而是判断它是否值得成为长期规格资产
- 只要总体判断为“不值得长期保留”,则该次 `brainstorm` 可以只保留为临时设计资产或执行输入,不进入正式 `spec`

##### sourc_spec 到 spec draft 的第二阶段筛选

目标:

- 从高细节、强对话依赖的 `sourc_spec` 中筛出适合长期保存的规格内容

默认应保留的内容:

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

按模块复杂度决定是否保留的内容:

1. 错误语义与异常场景
2. 空状态与边界状态
3. 响应式规则
4. 关键交互反馈

默认不进入正式 `spec draft` 的内容:

1. 组件树、文件路径、目录拆分
2. 具体实现优先级和阶段拆解
3. 迁移步骤、回填步骤、发布步骤
4. 大段代码片段、具体库用法、实现技巧
5. 只服务于本次执行的临时设计细节

说明:

- 第二阶段的核心不是“尽量保留更多”,而是“只保留实现前必须明确、实现后仍有参考或约束价值的内容”
- 来自真实 `sourc_spec` 的内容结构通常不固定,因此筛选应按内容类型进行,而不是按原文档章节机械复制

##### spec draft 固定模板 v1

目标:

- 为 `sourc_spec -> spec draft` 提供稳定落地模板
- 降低每次过滤时的主观性

建议结构:

1. `Overview`
   - 功能名称
   - 当前状态
   - 关联模块
   - 一句话目标

2. `Scope`
   - 当前功能要解决什么
   - 当前功能不解决什么

3. `Core Behavior`
   - 主要功能说明
   - 用户或调用方可观察到的行为
   - 关键状态流转

4. `Technical Contract`
   - API 路径、方法、核心语义
   - request / response schemas
   - 关键数据约束
   - 关键状态机命名
   - 关键固定编码名称

5. `Interaction / UX Notes`
   - 仅在前端功能或交互能力中需要
   - 保留长期有效的交互规则和设计风格
   - 不保留具体组件拆分与局部实现技巧

6. `Acceptance Notes`
   - 至少记录若干关键验收点
   - 用于说明什么情况下算实现正确

7. `Out of Spec`
   - 明确哪些内容不在本 `spec` 中长期维护
   - 例如阶段拆解、迁移步骤、代码组织方式、临时实现细节

模板说明:

- `Overview`、`Scope`、`Core Behavior`、`Technical Contract` 为默认必需章节
- `Interaction / UX Notes` 按功能类型决定是否保留
- `Acceptance Notes` 当前建议保留轻量版本,不展开为完整测试设计
- `Out of Spec` 用于主动控制文档膨胀

建议 frontmatter:

```yaml
id:
title:
status:
module:
last_updated:
sourc_spec:
related_plan:
code_scope:
contract_refs:
```

frontmatter 说明:

- `sourc_spec` 用于标记该 `spec draft` 来源于哪份 `sourc_spec`
- `related_plan` 用于标记当前主要执行计划
- `code_scope` 用于声明抽象内容的语义检查范围
- `contract_refs` 用于声明 `Technical Contract` 对应的定义文件
- 当前只保留最小必要字段,避免 metadata 先行膨胀

最小正文骨架:

```md
# {title}

## Overview

## Scope

## Core Behavior

## Technical Contract

## Interaction / UX Notes

## Acceptance Notes

## Out of Spec
```

使用规则:

1. 不要求 `sourc_spec` 中每个章节都能映射到模板中的一个章节
2. 允许多个离散片段合并整理后再写入一个正式章节
3. 若某部分内容只在本次执行中有价值,则不强行塞入模板
4. 如果 `Technical Contract` 为空,应重新判断该文档是否真的需要进入正式 `spec`

##### spec 的 CI 检查依据 v1

目标:

- 为正式 `spec` 提供最小可落地的 CI 检查抓手
- 区分结构化可检查内容与需要 AI 语义判断的内容

检查模型:

1. `Technical Contract` 检查
2. 抽象内容检查

###### 1. Technical Contract 检查

原则:

- `Technical Contract` 的核心检查依据不是全文语义理解,而是相关定义文件
- 只有难以结构化判断的部分,才交给 AI 做补充判断

当前检查抓手:

- API 路由定义
- request / response schema 定义
- DTO / interface / type / validator 定义
- 状态机 enum、常量或关键命名定义
- 关键数据约束定义

检查方式:

1. 读取 `contract_refs`
2. 判断相关定义文件是否仍存在
3. 判断关键名称、路径、字段、枚举值、约束是否与 `Technical Contract` 一致
4. 若无法通过结构化方式完全判断,再由 AI 结合定义文件做补充审查

###### 2. 抽象内容检查

原则:

- 抽象内容不应由 AI 对全仓进行无范围检查
- 必须先声明文件范围,再在范围内做语义一致性判断

当前检查抓手:

- `Overview`
- `Scope`
- `Core Behavior`
- 状态流转
- 算法抽象说明
- 交互规则与长期设计风格

检查方式:

1. 读取 `code_scope`
2. 当代码变更命中 `code_scope` 时,触发抽象内容检查
3. 由 AI 仅在该范围内加载相关文件
4. 判断当前实现是否改变了 `spec` 所描述的行为、边界、状态流转或关键交互规则
5. 若存在不一致,报告“应修改代码”或“应修改 `spec`”,但不自动裁决

###### code_scope 与 contract_refs 的时间线

规则:

1. `code_scope` 与 `contract_refs` 可以在 `plan` 执行完成后补全或修正
2. 当 `spec` 进入 `unstable` 时,二者应成为正式 CI 检查依据
3. 对 `draft` / `accepted_unimplemented` 状态,可以只做弱检查:
   - 字段是否存在
   - 是否缺少明显必要的范围或引用

当前最小写法:

- `code_scope`: 文件或目录列表
- `contract_refs`: 定义文件列表

说明:

- 当前先不要求更细粒度到符号级引用
- 先保证有范围和有定义文件可追踪,再决定是否继续细化

###### code_scope 与 contract_refs 的路径写法

原则:

- 当前阶段直接使用文件路径或目录路径,不引入更复杂的符号级定位
- `code_scope` 可以比 `contract_refs` 更粗粒度
- `contract_refs` 默认应比 `code_scope` 更精确

`code_scope` 写法:

1. 允许文件路径与目录路径混用
2. 当相关实现只涉及少量离散文件时,直接写文件路径
3. 当同一功能目录下有较多相关文件,且边界稳定时,可直接写目录路径
4. 目录路径应尽量指向功能边界明确的目录,避免直接给过大的根目录

`contract_refs` 写法:

1. 默认写文件路径
2. 只有当某个目录本身就是稳定的契约定义目录,且其中大部分文件都属于该契约时,才允许写目录路径
3. 不建议仅因“文件数量多”就把 `contract_refs` 退化为目录路径

当前建议阈值:

1. 对 `code_scope`
   - 当相关文件 `<= 4` 个时,优先直接写文件
   - 当相关文件 `>= 5` 个且集中在同一功能目录时,可直接写目录
2. 对 `contract_refs`
   - 默认不按数量阈值切换
   - 仍以“是否为稳定定义目录”为主判断是否可写目录

示例:

```yaml
code_scope:
  - frontend/apps/mindspace/components/value/
  - frontend/apps/mindspace/hooks/useValueView.ts
  - backend/services/value/

contract_refs:
  - frontend/apps/mindspace/apis/valueApi.ts
  - frontend/apps/mindspace/types/value.ts
  - backend/schemas/value_schema.py
```

说明:

- `git diff` 命中 `contract_refs` 时,优先触发 `Technical Contract` 检查
- `git diff` 命中 `code_scope` 时,触发抽象内容检查

#### design-decisions

状态流转:

`stable -> deprecated`


适合进入 `design-decisions` 的特征:

- 3 个月后还会被问“为什么当时这么做”
- 它不是当前事实,而是长期取舍和原则
- 未来多个 agent 任务都需要知道
- 不写下来 agent 很难保持一致
- 它影响多个模块或多个任务

说明:

- 当一个内容满足上面多条特征时,就非常适合进入 `design-decisions`
- 其中前两条权重最高

通常不应写入 `design-decisions` 的内容:

1. 一次性执行步骤
   - 这应该放在 `plan`
2. 当前实现事实
   - 这应该放在 `authority` 或 `generated`
3. 纯业务需求
   - 这应该放在 `spec`
4. 任务过程中临时改主意的细节
   - 先留在 `plan`
   - 只有稳定后才考虑提升
5. 小范围修补或局部 bugfix
   - 除非它暴露了长期设计缺陷,并形成了新的长期原则

规则:

- 创建后默认视为 `stable`
- 当新决定推翻或修改旧决定时,旧文档进入 `deprecated`

#### plans

状态流转:

`draft -> active -> completed -> archived`

规则:

- AI 创建后进入 `draft`
- 被采用后进入 `active`
- 执行完成后进入 `completed`
- `completed` 7 天后进入 `archived`
- `plan` 是历史执行资产,即使归档也默认保留
- 不要求为每个 `plan` 额外维护 `Decision Log`
- 由 `docs/plans/index.md` 统一承担轻量导航职责,简要记录每个 `plan` 的主题和主要工作

## 3. Docs在CI中维护

### 3.1 维护目标

每次 `git commit` 之前执行 CI 检查,识别代码和文档之间的冲突或缺失同步。

### 3.2 CI 维护流程

1. 通过 `git diff` 确认修改内容
2. 判断修改内容与需要维护的文档是否有重叠
3. 若有重叠或存在潜在冲突,则进行分类检查
4. 判断当前修改是否触发新的 `design-decisions`

### 3.3 分类检查

1. 对于 `rules`
   - 判断当前修改是否违反 `rules`
   - 若不符合,在报告中提出
   - 由人工决定是修改 `rules` 还是修改代码

2. 对于 `spec`
   - 判断当前修改是否与 `spec` 冲突
   - 若不符合,在报告中提出
   - 由人工决定是修改 `spec` 还是修改代码

3. 对于 `authority`
   - 判断当前修改是否与 `authority` 冲突
   - 若不符合,在报告中提出
   - 由人工决定是修改 `authority` 还是修改代码

4. 对于 `design-decisions`
   - 判断当前修改是否与既有决策相悖
   - 若相悖,在报告中提出
   - 由人工决定是否推翻既有决定,并创建新的 ADR

5. 对于 `ARCHITECTURE`
   - 判断架构是否发生变化
   - 如果发生变化,在报告中提出需要更新 `docs/ARCHITECTURE.md`

### 3.4 CI 不负责的事项

- CI 负责发现和报告,不自动替代人工做冲突裁决
- CI 不自动删除长期文档
- CI 不自动决定 `authority` 的创建
