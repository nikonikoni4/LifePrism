---
version: 1.0
created_at: 2026-04-18
updated_at: 2026-04-18
last_updated: 新增日记范围手动总结设计稿，定义 diary_source_hash、behavior.md 次级标题结构和批量更新策略
abstract: 定义 Mind Space 日记 AI 总结范围手动更新设计，包括 diary_source_hash 的语义、behavior.md 的次级标题结构、ai_diary_summary 的旧摘要入参和批量更新弹窗策略。
---

# Diary Range AI Summary Design

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建设计稿，定义范围手动总结、正文 hash 判断、behavior.md 次级标题和批量更新分支 |

## Overview

本设计在现有单日日记 AI 总结功能之上，增加“按日期范围手动更新总结”的能力。

目标是让用户在日记界面内选择日期范围后，批量为日记生成或更新 AI 总结，同时避免把 `behavior.md` 继续作为“正文是否变化”的判断来源。已有单日页面内的“重新生成”能力保持不变。

本设计将“摘要是否对应当前正文”收敛到 `diary` 表中的结构化字段 `diary_source_hash`，并将 `behavior.md` 改造成按日期和次级标题分块的聚合文档。

## Scope

本设计覆盖：

1. `diary` 表新增 `diary_source_hash` 字段。
2. 日记正文 hash 的计算规则和写入时机。
3. `behavior.md` 的日期块结构调整为 `## 日期` + `### 日记总结`。
4. `lifeprism/llm/utils/md_os.py` 的读写函数增加次级标题控制。
5. `ai_diary_summary` 改为接收外部传入的 `outdate_summary`。
6. 日记页面设置按钮内新增“日期范围手动更新总结”入口。
7. 批量更新弹窗的三种策略及对应筛选规则。

本设计不覆盖：

1. 单日页面现有“重新生成”按钮的交互改动。
2. `ai_diary_summary` 的 prompt 内容重写。
3. `behavior.md` 其他类型数据的次级标题设计。
4. 自动定时总结或保存后自动触发总结。
5. 摘要历史版本管理。

## Decisions

### 1. `diary_source_hash` 只表示当前摘要对应的正文版本

`diary` 表新增 `diary_source_hash` 字段。

该字段的含义不是“当前正文 hash”，而是“当前 `ai_summary` 对应的正文 hash”。这样可以直接回答一个具体问题：当前摘要是否仍然对应现在的正文。

正文 hash 只看日记正文内容，计算前先移除空格和换行符 `\n`，再计算 hash。

写入规则：

1. 保存日记正文时，不更新 `diary_source_hash`。
2. 只有当 AI 总结成功生成并保存到 `diary.ai_summary` 后，才同步写入当次正文的 hash 到 `diary_source_hash`。

判断规则：

1. `ai_summary` 为空时，视为“未总结”。
2. `ai_summary` 不为空且当前正文 hash 与 `diary_source_hash` 一致时，视为“已有总结且正文未变化”。
3. `ai_summary` 不为空但两者不一致时，视为“已有总结但正文已变化”。

该字段只用于批量更新时的 B 分支“仅重新生成日记变化了的总结”，不影响单日页面内现有的主动重生成逻辑。

### 2. `behavior.md` 改为日期块下的次级标题结构

`behavior.md` 的单日内容结构调整为：

```md
## 2026-04-18

### 日记总结
1. ...
2. ...
```

当前阶段只引入 `### 日记总结`，不预先增加其他次级标题。

这样做的原因是：

1. `behavior.md` 未来会混入其他类型内容，不能继续依赖“当天有内容”来判断日记总结是否过期。
2. 日记总结需要有稳定、可控的落点，避免和其他数据写在同一层级。
3. 后续新增别的数据时，只需要再添加新的 `###` 标题，不需要重构日期层级。

本次不做旧结构兼容。读取和写入都只认新结构。

### 3. `md_os.py` 的行为改为“必须写入某个次级标题”

`lifeprism/llm/utils/md_os.py` 中的 `behavior.md` 工具函数调整为更严格的结构化接口。

写入函数：

1. `write_date_md(...)` 增加必填参数 `subheading`。
2. `subheading` 不能为空。
3. 写入时必须落到 `## YYYY-MM-DD` 下的某个 `###` 次级标题内。
4. 不允许继续向日期块根部直接写内容。
5. 仍保留 `append` 和 `overwrite` 两种模式。

读取函数：

1. `extract_date_md(...)` 和 `extract_date_logs_from_file(...)` 增加 `subheading` 参数。
2. `subheading="all"` 时，返回该日期块下全部内容。
3. `subheading="日记总结"` 时，只返回该次级标题下内容。
4. 如果目标次级标题不存在，则返回空。

这样 `behavior.md` 可以作为聚合文档继续存在，但结构控制由工具函数强约束，不再依赖调用方手工拼接 markdown。

### 4. `ai_diary_summary` 保持 create / update 分支，只改旧摘要来源

`ai_diary_summary` 保留现有“无旧摘要走 create prompt，有旧摘要走 update prompt”的逻辑，不改 prompt 策略。

唯一改动是：

1. 删除函数内部自己从 `behavior.md` 提取旧摘要的逻辑。
2. 将 `outdate_summary` 改为外部传入的参数。

判断规则：

1. `outdate_summary` 有值时，走 update prompt。
2. `outdate_summary` 为空时，走 create prompt。

写回 `behavior.md` 时固定写到 `### 日记总结`：

1. 有 `outdate_summary` 时使用 `overwrite`。
2. 无 `outdate_summary` 时使用 `append`。

这样改动最小，同时把“是否要更新旧总结”的判断责任交给调用方。

### 5. 范围手动更新入口使用三种覆盖策略

日记页面在设置按钮内新增“范围更新 AI 总结”入口。用户选择日期范围后，弹出更新策略选择。

单日页面现有“重新生成”按钮保持不变：

1. 用户点击后必须调用 `ai_diary_summary`。
2. 保持当前行为，传入旧摘要作为 `outdate_summary`。
3. 不引入 `diary_source_hash` 判断。

批量更新只处理满足以下前置条件的日期：

1. 日期在用户选择的时间范围内。
2. 日记正文不为空。

对于无 `ai_summary` 的日期：

1. 直接调用 `ai_diary_summary`。
2. 不传 `outdate_summary`。

对于已有 `ai_summary` 的日期，弹窗提供三种策略：

1. `重新生成全部内容`
   - 该日期直接调用 `ai_diary_summary`
   - 传入当前 `ai_summary` 作为 `outdate_summary`

2. `仅重新生成日记变化了的总结`
   - 先计算当前正文 hash，并与 `diary_source_hash` 比较
   - 只有不一致时才调用 `ai_diary_summary`
   - 调用时传入当前 `ai_summary` 作为 `outdate_summary`

3. `不覆盖已有的总结`
   - 该日期直接跳过
   - 不做任何额外判断

### 6. 生成成功后的更新闭环

每次 AI 总结成功后，需要完成三个写入动作：

1. 覆盖 `diary.ai_summary`
2. 写入新的 `diary_source_hash`
3. 覆盖 `behavior.md` 对应日期下的 `### 日记总结`

如果 LLM 调用失败、数据库写入失败或正文为空，则保持旧摘要和旧 `diary_source_hash` 不变。

## Data Flow

```text
Journal Settings
-> select date range
-> select strategy
-> fetch diary list / diary details needed for range
-> filter by date range and non-empty content
-> branch by ai_summary existence
-> branch by strategy for existing summaries
-> ai_diary_summary(date, mood, importance, custom_tags, outdate_summary?)
-> update diary.ai_summary
-> update diary.diary_source_hash
-> write behavior.md -> ## date -> ### 日记总结
```

## Test Plan

后端验证：

1. 保存正文时不会更新 `diary_source_hash`。
2. 首次生成 summary 成功后会写入 `ai_summary` 和 `diary_source_hash`。
3. 批量更新 B 分支下，只有正文 hash 与 `diary_source_hash` 不一致时才调用 `ai_diary_summary`。
4. `ai_diary_summary` 在 `outdate_summary` 有值时走 update 分支，无值时走 create 分支。
5. `write_date_md` 只能写入某个 `###` 次级标题，缺少 `subheading` 时抛错。
6. 读取 `subheading="日记总结"` 时，只返回对应内容。

前端验证：

1. 设置按钮内出现范围更新 AI 总结入口。
2. 用户可选择开始和结束日期。
3. 策略 A 会更新所有已有摘要的日期。
4. 策略 B 只更新正文变化过的已有摘要日期。
5. 策略 C 会跳过已有摘要日期。
6. 无摘要且正文非空的日期，在三种策略下都能首次生成 summary。

## Documentation Follow-up

实现计划阶段需要同步正式文档：

1. 更新 `docs/specs/2026-04-15-mind-space-diary.md`，补充范围手动更新入口和 `diary_source_hash` 字段。
2. 如 `behavior.md` 的结构约束需要长期维护，可评估是否沉淀到 `docs/authority/`。

本设计目前属于功能级设计稿，不构成长期架构原则，因此暂不新增 `docs/design-decisions/`。

## Acceptance Notes

本设计可进入实现计划，当满足以下条件：

1. 用户确认 `diary_source_hash` 只基于正文内容计算。
2. 用户确认 `behavior.md` 改为 `## 日期` + `### 日记总结` 结构。
3. 用户确认 `md_os.py` 写入必须指定次级标题，读取支持指定标题和 `all`。
4. 用户确认 `ai_diary_summary` 改为接收外部传入的 `outdate_summary`。
5. 用户确认范围手动更新使用三种策略：全部重生成、只更新正文变化的已有摘要、跳过已有摘要。
6. 用户确认单日页面现有“重新生成”功能保持不变。

## Out of Spec

以下内容不在本设计中实现：

1. 自动定时批量更新总结。
2. `behavior.md` 其他数据块的标题体系。
3. `ai_diary_summary` prompt 重写。
4. 摘要历史版本管理。
5. 已有旧 `behavior.md` 内容的兼容迁移。
