# 日记界面日历点击自动滚动到顶部 Bug

## 元信息
- **updated_at**: 2026-06-29
- **severity**: HIGH（影响用户体验，反复出现）
- **触发规则**: 在排查日记界面日历点击后自动滚动、滚动条跳到顶部、React 状态更新竞态条件、useEffect 依赖竞态问题时阅读

## 问题描述

### 症状
在日记界面右侧栏的日历中，点击任意日期后，**左侧日历滚动条会自动跳回到最顶部**，而不是保持在当前位置。

### 反复出现的原因
此 bug **已修复过多次但反复出现**，本质是一个 **React 状态更新的竞态条件（Race Condition）**问题。

## 根本原因

### 代码位置
`frontend/apps/mindspace/components/journal/journal.tsx`

### 问题机制

1. **之前的错误修复尝试**（使用 state）：
   ```tsx
   const [shouldScrollToDate, setShouldScrollToDate] = useState(true);
   
   // useEffect 依赖 shouldScrollToDate
   useEffect(() => {
     if (settingsView || !shouldScrollToDate) return;
     // ... 滚动逻辑
   }, [activeDate, settingsView, shouldScrollToDate]);
   
   // 点击日期
   onClick={() => {
     setActiveDate(currentDate);
     setShouldScrollToDate(false);  // ← 异步更新，竞态条件！
   }}
   ```

2. **竞态条件触发流程**：
   - 用户点击日历某个日期
   - `setActiveDate(currentDate)` 被调用
   - `setShouldScrollToDate(false)` 被调用
   - **但两个 setState 都是异步的，执行顺序不确定**
   - `activeDate` 变化触发 useEffect
   - **此时 `shouldScrollToDate` 可能还没更新为 false**
   - 条件检查 `!shouldScrollToDate` 失败
   - 滚动逻辑执行 → 日历跳到顶部

3. **为什么反复出现**：
   - React 状态更新的批处理（batching）机制在不同渲染时机下表现不一致
   - 有时更新够快，看起来"修好了"
   - 有时渲染慢一点，竞态就复现了
   - 这种不确定性让开发者误以为已修复，实际只是"碰巧没触发"

## 正确解决方案

### 核心原理
**使用 `useRef` 替代 `useState`**，因为：
- `ref.current = value` 是**同步修改**，立即生效
- 不触发重新渲染
- 完全避免竞态条件

### 修复代码

```tsx
// ❌ 错误：使用 state（异步）
const [shouldScrollToDate, setShouldScrollToDate] = useState(true);

// ✅ 正确：使用 ref（同步）
const shouldScrollToDateRef = useRef(true);

// useEffect 读取 ref
useEffect(() => {
  if (settingsView || !shouldScrollToDateRef.current) return;
  const timer = setTimeout(() => {
    const scrollId = `diary-date-${activeDate.getFullYear()}-${activeDate.getMonth()}-${activeDate.getDate()}`;
    const el = document.getElementById(scrollId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    shouldScrollToDateRef.current = false;  // 同步修改
  }, 100);
  return () => clearTimeout(timer);
}, [activeDate, settingsView]);  // 移除 shouldScrollToDate 依赖

// 点击日期
onClick={() => {
  setActiveDate(currentDate);
  shouldScrollToDateRef.current = false;  // 同步修改，立即生效
}}

// 回到今天
const handleBackToToday = () => {
  setActiveDate(new Date());
  setSettingsView(false);
  shouldScrollToDateRef.current = true;  // 此时需要滚动
};
```

## 修复要点

1. **同步性**：`ref.current` 修改是同步的，`setActiveDate` 触发 useEffect 时，ref 已经是最新值
2. **移除依赖**：useEffect 依赖数组中**不需要包含 ref**，因为 ref 变化不触发重渲染
3. **适用场景**：
   - 点击日期：不需要滚动 → `shouldScrollToDateRef.current = false`
   - 回到今天：需要滚动 → `shouldScrollToDateRef.current = true`

## 关键教训

### 🚨 重要原则

**当需要在事件处理器中修改值，并在 useEffect 中立即读取最新值时，使用 useRef 而非 useState**

### 适用场景识别

使用 `useRef` 的信号：
- ✅ 需要在 onClick/onChange 等事件中修改标志位
- ✅ useEffect 需要根据这个标志位决定是否执行
- ✅ 标志位不需要触发 UI 重渲染
- ✅ 需要避免竞态条件

使用 `useState` 的场景：
- 需要触发 UI 重渲染
- 值的变化需要反映到界面上
- 不存在事件处理器和 useEffect 的竞态关系

## 相关提交

- `f99d4fb` - 之前的错误修复尝试（使用 setShouldScrollToDate(false)）
- 本次修复 - 使用 useRef 彻底解决竞态条件

## 测试验证

### 复现步骤
1. 打开日记界面
2. 在左侧日历滚动到任意位置（非顶部）
3. 点击日历中的任意日期
4. **预期**：滚动条保持在当前位置
5. **Bug 表现**：滚动条跳回顶部

### 验证方法
- 快速连续点击不同日期，观察滚动条是否保持稳定
- 在不同浏览器和不同渲染性能下测试（慢设备更容易触发竞态）
- 多次刷新页面测试（偶发性问题）

### 调试工具

如果问题复现，可以启用调试日志排查：

**启用方法**：编辑 `frontend/apps/mindspace/components/journal/diaryDebug.ts`

```typescript
export const DIARY_DEBUG = {
  enabled: true,  // 改为 true
  scroll: true,      // 滚动相关日志
  dataLoad: true,    // 数据加载日志
  userAction: true,  // 用户操作日志
};
```

重新构建后，控制台会显示详细的调试日志，方便定位问题。

详细使用说明见：`docs/temp/diary-debug-guide.md`

## 相关文件
- `frontend/apps/mindspace/components/journal/journal.tsx` - 日记主组件

## 标签
`race-condition` `react-hooks` `useEffect` `useRef` `scroll-behavior` `diary` `calendar`
