# 日记组件架构重构

## 元信息
- **日期**: 2026-06-29
- **类型**: 架构重构
- **影响范围**: 日记界面全部逻辑
- **触发原因**: 滚动 bug 反复出现，说明原有架构存在深层问题

## 重构目标

彻底解决日历点击后滚动条自动跳到顶部的 bug，这个 bug 已经修复过多次但总会复现，说明需要从架构层面重新设计。

## 架构改进

### 核心问题分析

原有架构的根本问题：
1. **状态管理混乱**：大量 ref 和 state 混用，职责不清
2. **副作用耦合**：滚动逻辑、保存逻辑、编辑器水合逻辑相互耦合
3. **竞态条件易发**：多个异步状态更新导致不可预测的行为
4. **代码难以维护**：单文件 700+ 行，逻辑分散

### 新架构设计

采用 **关注点分离（Separation of Concerns）** 原则：

```
journal.tsx (549 行)
├── useDiaryData.ts (132 行) - 数据管理
│   ├── 加载日记
│   ├── 保存内容（防抖 + 立即保存）
│   ├── 更新 meta（心情、重要程度、标签）
│   └── flush 挂起保存
├── useCalendarScroll.ts (33 行) - 滚动控制
│   ├── 只在初始化时滚动一次
│   └── 提供 resetScroll 方法
└── useBackgroundColor.ts (35 行) - 背景色管理
    ├── localStorage 持久化
    └── HSL 调整
```

## 滚动问题的根本解决方案

### 旧方案（反复失败）

```tsx
// ❌ 错误：依赖 state/ref 的复杂追踪
const [shouldScrollToDate, setShouldScrollToDate] = useState(true);
// 或
const shouldScrollToDateRef = useRef(true);

useEffect(() => {
  if (!shouldScrollToDate) return;  // 竞态条件！
  // ... 滚动
}, [activeDate, shouldScrollToDate]);

onClick={() => {
  setActiveDate(date);
  setShouldScrollToDate(false);  // 可能太晚
}}
```

**问题**：即使用 useRef，逻辑仍然复杂，用户点击日历时需要手动设置标志位，容易遗漏或出错。

### 新方案（根本解决）

```tsx
// ✅ 正确：简单清晰的逻辑
export function useCalendarScroll(activeDate: Date, enabled: boolean) {
  const hasScrolledRef = useRef(false);

  useEffect(() => {
    // 只在启用且未滚动过的情况下执行
    if (!enabled || hasScrolledRef.current) return;
    
    // 滚动到日期
    // ...
    hasScrolledRef.current = true;  // 标记已滚动
  }, [activeDate, enabled]);

  return { resetScroll: () => { hasScrolledRef.current = false; } };
}

// 使用
const { resetScroll } = useCalendarScroll(activeDate, !settingsView);

// 用户点击日历 - 不需要任何特殊处理
onClick={() => setActiveDate(date)}

// 只有"回到今天"按钮需要滚动
handleBackToToday() {
  setActiveDate(new Date());
  resetScroll();  // 显式重置，触发滚动
}
```

**优势**：
1. **单一职责**：滚动逻辑完全封装在 hook 中
2. **默认行为正确**：用户点击日历不触发滚动（符合预期）
3. **显式重置**：只有需要滚动的场景（回到今天）才调用 resetScroll
4. **无竞态条件**：ref 追踪简单明确，不依赖外部状态同步

## 数据管理改进

### useDiaryData Hook

将日记数据的所有操作封装：

```tsx
const {
  diary,           // 日记数据
  content,         // 编辑器内容
  loading,         // 加载状态
  loadDiary,       // 加载日记
  saveContentDebounced,  // 防抖保存
  flushPendingSave,      // 立即 flush
  updateMood,            // 更新心情
  updateImportance,      // 更新重要程度
  updateCustomTags,      // 更新标签
} = useDiaryData({
  onSaveSuccess: () => toast.success('已保存'),
  onSaveError: (msg) => toast.error(msg),
});
```

**关键改进**：
1. **防抖逻辑封装**：定时器管理、跨日期保存保护全部在 hook 内部
2. **清晰的 API**：主组件只调用高层方法，不关心内部实现
3. **回调注入**：toast 通知通过回调注入，保持 hook 纯净

## 代码组织

### 文件结构

```
journal/
├── journal.tsx              - 主组件 UI 渲染
├── useDiaryData.ts          - 数据管理 hook
├── useCalendarScroll.ts     - 滚动控制 hook
├── useBackgroundColor.ts    - 背景色管理 hook
├── DiaryTagBar.tsx          - 标签栏组件
├── SettingsPopover.tsx      - 设置弹窗
├── TemplateManager.tsx      - 模板管理
├── RangeSummaryModal.tsx    - 范围总结
├── diaryApi.ts              - API 服务
├── diaryTypes.ts            - 类型定义
└── diaryConstants.ts        - 常量配置
```

### 主组件职责

重构后的 `journal.tsx` 只负责：
1. **状态管理**：UI 状态（侧边栏、弹窗）
2. **事件处理**：用户交互（点击、快捷键）
3. **组件组合**：组装子组件和 hooks
4. **UI 渲染**：JSX 结构

**不再负责**：
- ❌ 数据保存逻辑
- ❌ 滚动控制逻辑
- ❌ 背景色持久化逻辑

## 关键改进点

### 1. 编辑器水合处理

```tsx
const isEditorHydratingRef = useRef(false);

// 同步编辑器内容
useEffect(() => {
  if (editorRef.current && !loading) {
    isEditorHydratingRef.current = true;
    editorRef.current.setMarkdown(content);
    setTimeout(() => {
      isEditorHydratingRef.current = false;
    }, 0);
  }
}, [content, loading]);

// 内容变化处理
const handleContentChange = useCallback((md: string) => {
  if (isEditorHydratingRef.current) return;  // 忽略水合期间的变化
  saveContentDebounced(md);
}, [saveContentDebounced]);
```

**优势**：水合保护逻辑清晰，不与其他逻辑耦合。

### 2. 防抖保存

```tsx
// useDiaryData.ts
const saveContentDebounced = useCallback((newContent: string, delay: number = 1500) => {
  setContent(newContent);
  const targetDate = currentDateRef.current;  // 锁定当前日期

  if (saveTimerRef.current) {
    clearTimeout(saveTimerRef.current);
  }

  saveTimerRef.current = setTimeout(() => {
    saveTimerRef.current = null;
    saveContentNow(targetDate, newContent);  // 使用锁定的日期
  }, delay);
}, [saveContentNow]);
```

**优势**：日期锁定机制防止跨日期保存。

### 3. 月历渲染

```tsx
// MonthBlock 组件内联，访问父组件状态
const MonthBlock = ({ date }: { date: Date }) => {
  // ...
  return (
    <button
      onClick={() => setActiveDate(currentDate)}  // 简单直接
      // ...
    >
      {day}
    </button>
  );
};
```

**优势**：点击处理极简，不需要任何滚动控制代码。

## 测试验证

### 验证步骤

1. **基本功能**：
   - ✅ 加载日记
   - ✅ 编辑内容自动保存
   - ✅ 切换日期正常加载
   - ✅ 手动保存（Ctrl+S）
   - ✅ AI 总结生成

2. **滚动行为**：
   - ✅ 初始加载时滚动到当天
   - ✅ 点击其他日期**不触发滚动**
   - ✅ "回到今天"按钮触发滚动
   - ✅ 快速连续点击日期不闪烁

3. **边界情况**：
   - ✅ 编辑中切换日期，保存正确日期
   - ✅ 编辑器初始化不触发保存
   - ✅ 组件卸载时保存挂起内容

## 迁移指南

### 对外接口不变

```tsx
<JournalView 
  onBack={() => {}}
  onOpenGuide={() => {}}
/>
```

### 行为变化

1. **滚动行为**：用户点击日历后，滚动条保持在当前位置（修复bug的目标）
2. **其他行为**：完全一致

## 性能影响

- **代码体积**：716 行 → 749 行（+33 行），但模块化更好
- **运行时性能**：无影响，hooks 不增加额外开销
- **可维护性**：显著提升

## 后续优化建议

1. **测试覆盖**：为 hooks 编写单元测试
2. **类型安全**：添加更严格的 TypeScript 类型
3. **错误处理**：统一错误边界处理
4. **状态持久化**：考虑将编辑中的内容保存到 localStorage（防止意外关闭）

## 相关文件

- `frontend/apps/mindspace/components/journal/journal.tsx` - 主组件（重写）
- `frontend/apps/mindspace/components/journal/useDiaryData.ts` - 新增
- `frontend/apps/mindspace/components/journal/useCalendarScroll.ts` - 新增
- `frontend/apps/mindspace/components/journal/useBackgroundColor.ts` - 新增
- `frontend/apps/mindspace/components/journal/journal.tsx.backup` - 原文件备份

## 回滚方案

如果出现问题，可以快速回滚：

```bash
cd frontend/apps/mindspace/components/journal
cp journal.tsx.backup journal.tsx
rm useDiaryData.ts useCalendarScroll.ts useBackgroundColor.ts
```

## 标签

`refactoring` `architecture` `hooks` `separation-of-concerns` `diary` `bug-fix`
