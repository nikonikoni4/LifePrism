# Code Review Report

**审查范围**: 当前工作目录变更（report AI summary 重构）
**审查时间**: 2026-07-01
**变更文件**:
- `lifeprism/server/services/report_service.py` — 删除旧 AI summary 函数，新增 behavior.md 读取
- `lifeprism/server/api/report_api.py` — 移除 3 个 POST AI summary 端点
- `frontend/apps/lifewatch/pages/reports/api.ts` — 清理旧 AI summary API 方法
- `frontend/apps/lifewatch/pages/reports/components/AISummaryCard.tsx` — 注释生成按钮，添加提示
- `frontend/apps/lifewatch/pages/reports/components/WeeklyReviewTab.tsx` — 移除 AI Summary 卡片
- `frontend/apps/lifewatch/pages/reports/components/MonthlyReviewTab.tsx` — 移除 AI Summary 卡片

## 架构上下文

### 相关 Spec
- 无正式 spec 关联此变更

### 相关 ADR
- 无正式 ADR 关联此变更（此为废弃功能的清理性变更）

### 决策覆盖
- 0/6 变更文件有 ADR 关联（纯功能废弃清理）

## 审查结果

Found 2 issues:

### Issue 1: Service 层捕获全部异常并静默返回默认值

- **类型**: Architecture
- **置信度**: 75
- **位置**: `lifeprism/server/services/report_service.py:39-42`
- **详情**: `_get_behavior_content()` 函数在 Service 层使用 `except Exception as e` 捕获所有异常并返回空字符串。根据 `docs/coding-rules/backend-core-rules.md` 第 5 节"错误处理分层"，Service 层应"让异常自然冒泡，不捕获异常"。即使是外部接口层也不应使用 `except Exception` 捕获全部错误。
- **依据**: `docs/coding-rules/backend-core-rules.md` Section 5:
  > Service 层（业务逻辑层）：让异常自然冒泡，不捕获异常
  > 外部接口层：不能使用`except Exception as e` 捕获全部错误
- **建议**: 改为只捕获预期的 I/O 异常（如 `FileNotFoundError`, `OSError`），或让异常向上传播。由于 AI 总结是非关键功能，也可以将此函数移到更合适的层级。

### Issue 2: AISummaryCard 组件中保留未使用的状态变量

- **类型**: Code Quality
- **置信度**: 85
- **位置**: `frontend/apps/lifewatch/pages/reports/components/AISummaryCard.tsx:43-50`
- **详情**: `handleGenerateSummary` 已注释掉，但 `isLoading`、`error`、`tokensUsage` 状态变量及其关联的 JSX 条件分支（LoadingSkeleton、error 显示、tokens 统计）仍然保留。这些状态永远不会被修改，对应的 UI 分支永远不会被渲染，形成死代码。
- **依据**: React 最佳实践 — 不应保留永远不会被触发的状态和条件渲染分支
- **建议**: 移除 `isLoading`、`error`、`tokensUsage` 状态声明，移除 `LoadingSkeleton` 组件、错误显示分支、tokens 统计显示，简化组件结构。

## 变更摘要

本次变更是对 Reports 页面 AI 总结功能的清理性重构：

1. **后端**: 删除 3 个引用已删除模块 (`lifeprism.llm.function.report_summary`) 的异步 AI summary 函数，新增 `_get_behavior_content()` 从 `behavior.md`（每天 10:00 由定时任务自动生成）读取日报 AI 总结。周报和月报的 `ai_summary` 字段设为 `None`。
2. **API**: 移除 `POST /report/daily/ai_summary`、`POST /report/weekly/ai_summary`、`POST /report/monthly/ai_summary` 三个端点。
3. **前端**: 注释主动生成 AI 总结的按钮，替换为"每天 10:00 自动更新"提示；周/月 Tab 移除 AISummaryCard 组件；清理 api.ts 中的旧 AI summary 方法。

变更整体风险低，主要是删除已失效的代码路径，并建立新的简化数据流：`定时任务 → behavior.md → GET /report/daily → 前端展示`。
