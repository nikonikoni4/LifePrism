# 分页功能修复 — total 返回真实总记录数

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD.md`
**Code Review**: `docs/generated/002/code-review-2026-07-07-2145.md` Issue 1（置信度 100）

## What to build

修复自定义记录模块的分页功能。当前 `query_entries` 只返回当前页记录，Service 层用 `len(items)` 填充 `total` 字段，导致前端 `totalPages` 永远为 1，分页按钮不显示，用户无法翻页。

端到端行为：
1. 后端 Repository 的 `query_entries` 增加一次 `SELECT COUNT(*)` 查询，返回 `(items, total_count)` 元组
2. Service 层用真实总记录数填充 `CustomRecordEntryListResponse.total`
3. 前端 `TypeDetailView` 的分页按钮正确显示，用户可以翻到第 2 页及之后
4. 当记录数超过 pageSize（20）时，分页按钮可见且可操作

## Acceptance criteria

- [ ] Repository `query_entries` 返回 `(list[dict], int)` 元组，第二个元素为满足筛选条件的总记录数
- [ ] Service `get_entries` 用真实总数填充 `total` 字段
- [ ] 前端在有 25 条记录、pageSize=20 时，显示 2 页分页按钮
- [ ] 点击"下一页"能正确加载第 2 页数据
- [ ] 日期筛选后 total 正确反映筛选结果总数
- [ ] 已有的 31 个后端测试 + 64 个前端测试无回归

## Blocked by

None - can start immediately
