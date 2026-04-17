---
version: 1.1
created_at: 2026-04-17
updated_at: 2026-04-17
last_updated: 修正日记 AI 总结响应契约，移除 tokens_usage
abstract: 定义 Mind Space 日记 AI 总结功能的设计，包括只读总结卡片、手动触发 API、LLM 调用、数据库覆盖写入、只返回内容的响应契约、错误处理和验证范围。
---

# Diary AI Summary Design

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建设计稿，定义日记 AI 总结手动触发、后端 API、前端卡片和测试边界 |
| 1.1 | 修正日记 AI 总结响应契约，`ai_diary_summary` 只返回内容，因此 API 不返回 `tokens_usage` |

## Overview

本设计为 Mind Space 日记界面增加 AI 总结能力。

目标是让用户在日记详情页中看到当前日期的 AI 总结，并可通过手动按钮触发重新生成。总结内容不可编辑，生成成功后覆盖保存到 `diary.ai_summary` 字段。

本功能不做自动触发。保存日记正文、修改心情、修改重要程度或修改自定义标签时，都不会自动刷新 AI 总结。

## Scope

本设计覆盖：

1. 日记界面标签栏下方新增 AI 总结只读卡片。
2. 卡片左上角新增 `AI 总结` 按钮。
3. 后端新增 `POST /diary/{date}/ai_summary`。
4. Service 层调用 `lifeprism.llm.function.diary_summary.ai_diary_summary(...)`。
5. 生成成功后覆盖写入 `diary.ai_summary`。
6. 空日记、LLM 失败和重复点击的处理方式。

本设计不覆盖：

1. 自动定时总结前一天日记。
2. 日记保存后自动刷新总结。
3. 总结历史版本管理。
4. 用户手动编辑 AI 总结。
5. `ai_diary_summary` 内部 prompt 和上下文读取策略调整。

## Decisions

### 1. API Shape

采用独立副作用端点：

```http
POST /api/v2/diary/{date}/ai_summary
```

选择该路径的原因：

1. `GET /diary/{date}` 继续只负责读取 diary，不承担生成副作用。
2. `PUT /diary/{date}/content` 继续只负责保存正文，不绑定重型 LLM 调用。
3. 该模式与 report 模块现有 `POST /report/*/ai_summary` 方向一致。

响应结构使用 diary 专用的简单内容响应，不返回 token 消耗：

```json
{
  "content": "AI 生成的总结内容"
}
```

原因是 `ai_diary_summary` 只提供 summary content，无法从该函数获取 token 消耗。实现时应新增 diary 专用响应模型，例如 `DiaryAISummaryResponse`，而不是复用 report 的 `AISummaryResponse`。

### 2. Backend Flow

`diary_service` 新增异步函数，例如 `get_diary_ai_summary(date: str)`。

处理流程：

1. 使用现有 diary 读取流程获取该日期日记，保持当前“选择日期后自动创建 diary 记录”的行为。
2. 从数据库记录读取 `mood`、`importance`、`custom_tags`。
3. 从 markdown 文件读取该日期正文。
4. 正文 `strip()` 后为空时，抛出业务错误，由 API 返回 `400`，错误含义为“日记为空，无法总结”。
5. 将数据库字段转换为适合 LLM 的参数后调用 `ai_diary_summary(date, mood, importance, custom_tags)`。
6. 如果 LLM 返回有效内容，调用 `diary_provider.update_diary(date, {"ai_summary": content})` 覆盖旧 summary。
7. 返回 `content` 给前端。

`ai_diary_summary` 内部已经负责读取它需要的其他上下文文件，例如用户信息、近况和历史行为记录。Service 层不复制这些逻辑，只负责提供数据库中已有的日记 meta 数据。

### 3. Overwrite Semantics

每次用户点击按钮并成功生成时，都覆盖 `diary.ai_summary`。

旧 summary 只在以下情况下保留：

1. 当前日记为空，后端拒绝生成。
2. LLM 调用失败。
3. LLM 返回值无法解析为有效 summary。
4. 数据库更新失败。

这些失败情况都不清空旧 summary。

### 4. Frontend Card

日记页面在 `DiaryTagBar` 下方、Markdown 编辑器上方增加只读卡片。

卡片结构：

1. 左上角：`AI 总结` 按钮。
2. 右上角：轻量状态文字，例如 `只读` 或生成中状态。
3. 下方：summary 正文。

显示规则：

1. 初次加载 diary 时，显示 `diary.ai_summary`。
2. 若 `diary.ai_summary` 为空，显示占位文案：`暂无 AI 总结，点击左上角按钮生成`。
3. 正文区域不可编辑。
4. 卡片高度由内容自然撑开，不设置固定高度。
5. 生成成功后立即将返回的 `content` 写入当前页面状态。

按钮交互：

1. 点击前，如果当前正文为空或全空白，前端直接 toast 提示，不发请求。
2. 请求进行中时，按钮 disabled，并显示 loading 状态。
3. 请求成功后 toast 提示生成成功。
4. 请求失败后 toast 提示生成失败，并保留当前展示内容。
5. 生成 summary 不参与现有正文自动保存防抖链路。

### 5. Error Handling

错误语义：

1. 空日记：后端返回 `400`，前端提示“日记为空，无法总结”。
2. LLM 调用失败：后端返回 `500`，前端提示“AI 总结生成失败”。
3. 数据库写入失败：后端返回 `500`，前端提示“AI 总结保存失败”。
4. 重复点击：前端通过 loading 状态禁用按钮，避免并发请求。

API 层只做 HTTP 状态转换，Service 层负责业务判断和数据编排，Provider 层继续只负责数据库更新。

## Data Flow

```text
JournalView
-> DiaryAPI.generateAiSummary(date)
-> POST /api/v2/diary/{date}/ai_summary
-> diary_service.get_diary_ai_summary(date)
-> diary_provider.get_diary_by_date(date)
-> diary_service reads diary/YYYY/MM/YYYY-MM-DD.md
-> ai_diary_summary(date, mood, importance, custom_tags)
-> diary_provider.update_diary(date, {"ai_summary": content})
-> DiaryAISummaryResponse
-> JournalView updates diary.ai_summary
```

## Test Plan

后端测试：

1. 空日记调用 `POST /diary/{date}/ai_summary` 返回 `400`。
2. 有正文时，Service 会调用 `ai_diary_summary`。
3. LLM 成功返回后，`diary.ai_summary` 被新内容覆盖。
4. 已存在旧 summary 时，再次生成成功会覆盖旧值。
5. LLM 失败时，不覆盖旧 summary。

前端验证：

1. `diary.ai_summary` 为空时显示占位文案。
2. 点击按钮时进入 loading/disabled 状态。
3. 当前正文为空时前端不发请求并提示。
4. 生成成功后卡片内容更新为新 summary。
5. 生成失败时保留旧 summary。

## Documentation Follow-up

实现计划阶段需要更新正式 spec：

1. 修改 `docs/specs/2026-04-15-mind-space-diary.md`，移除“AI 总结功能（保留字段，未实现）”的表述。
2. 在正式 spec 的 API 路由表中加入 `POST /diary/{date}/ai_summary`。
3. 在正式 spec 的交互说明中加入 AI 总结只读卡片。

该功能属于局部功能实现，不构成长期架构取舍，因此不需要新增 `docs/design-decisions/` 文档。

## Acceptance Notes

本设计可进入实现计划，当满足以下条件：

1. 用户已确认采用独立 `POST /diary/{date}/ai_summary` 端点。
2. 用户已确认只做手动触发。
3. 用户已确认生成成功后覆盖 `diary.ai_summary`。
4. 用户已确认空日记不调用 LLM，并提示无法总结。
5. 用户已确认卡片位于标签栏下方、编辑器上方。

## Out of Spec

以下内容不在本设计中实现：

1. 自动按日期生成 summary。
2. 保存正文后自动刷新 summary。
3. summary 版本历史。
4. summary 手动编辑。
5. LLM prompt 重写。
