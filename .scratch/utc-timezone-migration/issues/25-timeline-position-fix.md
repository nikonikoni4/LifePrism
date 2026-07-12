# Issue #25: timeline 模块时间轴定位端到端修复

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

修复 timeline 模块 6 处 `split('T')[1]` 直接取 UTC 时间部分用于时间轴定位的问题，改为使用本地时区时间定位。

**问题**：timeline 模块的多个组件直接对 UTC ISO 8601 字符串做 `split('T')[1]` 取时间部分，用于时间轴上的事件块定位。由于取的是 UTC 时间，事件块会出现在错误的时刻（UTC+8 用户看到的事件块偏移 8 小时）。

**架构原则**：
- 后端 API：保持 UTC ISO 8601 透传，不做转换
- 前端组件：就地转换为本地时区时间用于定位和显示

**需要修复的文件**（前端组件层）：

1. `Timeline.tsx`（约第 1436-1438 行）
   - 问题：`split('T')[1]` 直接取 UTC 时间部分用于时间轴定位
   - 修复：先用 `utcToLocalDisplay()` 转换，再取时间部分

2. `CustomBlockPopover.tsx`
   - 问题：同上
   - 修复：同上

3. `CustomBlockLayer.tsx`
   - 问题：同上
   - 修复：同上

4. `BehaviorBlockLayer.tsx`
   - 问题：同上
   - 修复：同上

5. `CustomBlockLabel.tsx`
   - 问题：同上
   - 修复：同上

6. `BehaviorDetailPanel.tsx`
   - 问题：同上
   - 修复：同上

### E2E 验证
7. 时间轴上事件块出现在正确的时刻（不偏移 8 小时）
8. 事件块的时间标签显示正确的本地时间
9. 自定义时间块定位正确

## Acceptance criteria

- [ ] `Timeline.tsx` 时间轴定位使用本地时区时间
- [ ] `CustomBlockPopover.tsx` 使用本地时区时间
- [ ] `CustomBlockLayer.tsx` 使用本地时区时间
- [ ] `BehaviorBlockLayer.tsx` 使用本地时区时间
- [ ] `CustomBlockLabel.tsx` 使用本地时区时间
- [ ] `BehaviorDetailPanel.tsx` 使用本地时区时间
- [ ] E2E 验证：时间轴事件块出现在正确时刻
- [ ] 相关测试通过

## Blocked by

- Issue #21 - 前端时间转换工具完善（需要 `utcToLocalDisplay` 函数）

## 注意事项

1. **后端 API 不做转换**：API 保持 UTC ISO 8601 透传
2. **只改前端组件**：所有转换在组件层就地完成
3. **时间轴定位精度**：确保事件块在时间轴上的位置与实际本地时间一致
4. **与 Issue #22 的关系**：Issue #22 修复 Timeline 筛选提交，本 issue 修复 Timeline 显示定位，两者互补
