# 日记组件调试开关使用说明

## 文件位置
`frontend/apps/mindspace/components/journal/diaryDebug.ts`

## 如何启用调试日志

### 方法 1：启用所有日志（推荐排查问题时使用）

编辑 `diaryDebug.ts`：

```typescript
export const DIARY_DEBUG = {
  enabled: true,  // 改为 true
  scroll: true,
  dataLoad: true,
  userAction: true,
};
```

保存后重新构建前端：
```bash
cd frontend && npm run build
```

### 方法 2：只启用特定类型的日志

```typescript
export const DIARY_DEBUG = {
  enabled: true,
  scroll: true,      // 滚动相关日志
  dataLoad: false,   // 关闭数据加载日志
  userAction: false, // 关闭用户操作日志
};
```

## 日志类型说明

### `scroll` - 滚动相关日志
- useEffect 触发时机
- 滚动执行情况
- DOM 元素查找结果
- 滚动位置计算

**输出示例**：
```
[useCalendarScroll] useEffect triggered { enabled: true, hasScrolled: false, ... }
[useCalendarScroll] Attempting to scroll to: diary-date-2026-5-29
[useCalendarScroll] Scrolling calendar container { ... }
[useCalendarScroll] Scrolled successfully
```

### `dataLoad` - 数据加载相关日志
- 日期切换
- 日记加载

**输出示例**：
```
[JournalView] activeDate changed, loading diary: 2026-05-29T16:00:00.000Z
```

### `userAction` - 用户操作相关日志
- 点击日历日期

**输出示例**：
```
[MonthBlock] Date clicked: 2026-05-29T16:00:00.000Z
```

## 常见问题排查

### 问题：点击日历后滚动条跳到顶部

**启用日志**：
```typescript
enabled: true,
scroll: true,
userAction: true,
```

**观察**：
1. 点击日期后是否看到 `[MonthBlock] Date clicked`
2. 是否触发 `[useCalendarScroll] useEffect triggered`
3. `hasScrolled` 的值是 `true` 还是 `false`
4. 是否看到 `Skip scroll: already scrolled`

**诊断**：
- 如果 `hasScrolled: true` 但应该滚动 → 标志位被错误设置
- 如果看到 `Missing required elements` → DOM 渲染时机问题
- 如果完全没触发 useEffect → React 依赖问题

### 问题：初始加载不滚动

**启用日志**：
```typescript
enabled: true,
scroll: true,
dataLoad: true,
```

**观察**：
1. 是否看到 `[JournalView] Calling useCalendarScroll with: { enabled: true, ... }`
2. 是否触发 `[useCalendarScroll] useEffect triggered`
3. 是否看到 `Attempting to scroll to`

## 关闭调试日志

调试完成后，记得关闭日志：

```typescript
export const DIARY_DEBUG = {
  enabled: false,  // 改回 false
  scroll: true,
  dataLoad: true,
  userAction: true,
};
```

重新构建：
```bash
cd frontend && npm run build
```

## 注意事项

1. **生产环境**：确保 `enabled: false`，避免控制台日志泄露信息
2. **性能**：调试日志会略微影响性能，排查完问题后及时关闭
3. **版本控制**：提交代码前确认 `enabled: false`

## 快速命令

```bash
# 启用调试
sed -i 's/enabled: false/enabled: true/' frontend/apps/mindspace/components/journal/diaryDebug.ts
cd frontend && npm run build

# 关闭调试
sed -i 's/enabled: true/enabled: false/' frontend/apps/mindspace/components/journal/diaryDebug.ts
cd frontend && npm run build
```

## 添加新的调试日志

如果需要添加新的日志分类：

1. 在 `DIARY_DEBUG` 中添加新字段：
```typescript
export const DIARY_DEBUG = {
  enabled: false,
  scroll: true,
  dataLoad: true,
  userAction: true,
  newCategory: true,  // 新增
};
```

2. 使用 `debugLog` 记录：
```typescript
debugLog('newCategory', '[Component] Message', data);
```
