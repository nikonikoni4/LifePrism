# Issue #24: custom-records 模块时间显示端到端修复

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

修复 custom-records 模块 4 处直接 `split('T')` 显示 UTC 时间的问题，改为前端组件就地转换为本地时区显示。

**问题**：custom-records 模块的多个组件直接对 UTC ISO 8601 字符串做 `split('T')` 或 `replace('T', ' ').slice(0, 16)`，显示的是 UTC 时间而非本地时间，用户看到的时间比实际早 8 小时。

**架构原则**：
- 后端 API：保持 UTC ISO 8601 透传，不做转换
- 前端组件：就地调用 `utcToLocalDisplay()` 转换为本地时区显示

**需要修复的文件**（前端组件层）：

1. `frontend/apps/custom-records/components/TypeListView.tsx`（约第 117 行）
   - 问题：直接 `split('T')` 显示 UTC 时间
   - 修复：改用 `utcToLocalDisplay()` 或 `utcToLocalDate()`

2. `frontend/apps/custom-records/components/TypeDetailView.tsx`（约第 40 行、第 429 行）
   - 问题：直接 `replace('T', ' ').slice(0, 16)` 显示 UTC 时间
   - 修复：改用 `utcToLocalDisplay()`

3. `frontend/apps/custom-records/components/EntryCard.tsx`（约第 28-32 行）
   - 问题：直接 `split('T')` 显示 UTC 时间
   - 修复：改用 `utcToLocalDisplay()` 或 `utcToLocalDate()`

4. 检查 custom-records 模块其他组件是否有类似问题

### E2E 验证
5. 创建自定义记录类型 → 列表显示正确的本地时间
6. 创建自定义记录 → 详情页显示正确的本地时间
7. 记录卡片显示正确的本地时间

## Acceptance criteria

- [ ] `TypeListView.tsx` 使用 `utcToLocalDisplay()` 显示时间
- [ ] `TypeDetailView.tsx` 使用 `utcToLocalDisplay()` 显示时间
- [ ] `EntryCard.tsx` 使用 `utcToLocalDisplay()` 显示时间
- [ ] custom-records 模块其他组件检查并修复（如有）
- [ ] E2E 验证：所有时间显示为本地时区
- [ ] 相关测试通过

## Blocked by

- Issue #21 - 前端时间转换工具完善（需要 `utcToLocalDisplay` 函数）

## 注意事项

1. **后端 API 不做转换**：API 保持 UTC ISO 8601 透传
2. **只改前端组件**：所有转换在组件层就地完成
3. **统一使用 dateUtils**：不要在组件内自己实现转换逻辑
