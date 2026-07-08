# 前端状态与错误处理修复 — 双重请求 + 定时器泄漏 + 错误详情

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD.md`
**Code Review**: `docs/generated/003/code-review-2026-07-07-2145.md` Issues 7, 9, 13（置信度 80-90）

## What to build

修复前端 3 个状态管理和错误处理问题，提升用户体验和代码健壮性。

端到端行为：
1. 点击"筛选"按钮只发起一次 API 请求（当前页码正确为 1），不再产生双重请求和竞态条件
2. 组件卸载时 debounce 定时器被清理，不再触发已卸载组件的状态更新
3. API 错误时解析后端响应体中的 `message` 字段，用户看到具体错误原因而非模糊的 statusText

## Acceptance criteria

- [ ] `handleFilter` 移除手动 `loadData()` 调用，仅依赖 `setPage(1)` 触发 useEffect
- [ ] 或者改为 `loadData` 接收参数模式，避免闭包捕获旧 page 值
- [ ] `TypeDetailView` 添加 `useEffect` cleanup 清理 `debounceRef.current`
- [ ] 内层 1500ms 的 `setTimeout` 也在 cleanup 中清理（可用 ref 追踪）
- [ ] `api.ts` 所有方法的错误处理解析 `res.json()` 中的 `message` 字段
- [ ] 用户创建类型时 slug 冲突，错误提示显示"slug 已存在"而非"Bad Request"
- [ ] 用户录入数据时字段不存在，错误提示显示具体字段名
- [ ] 已有的 64 个前端测试无回归

## Blocked by

None - can start immediately
