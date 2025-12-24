# Plan 页面滚动问题修复文档

## 问题描述

**日期**: 2024-12-24

**问题现象**: 
在 Plan 页面中，当鼠标悬停在左侧日期选择区域（Week 1、Week 2、Week 3、Week 4 列表）时，滚动鼠标滚轮会导致整个页面向下滑动，包括左侧边栏本身也会被滚出视图。

**期望行为**: 
左侧边栏应该保持固定位置，滚轮事件不应该触发外层容器的滚动。

## 问题分析

### 根本原因

问题出在 `GoalsPage.tsx` 的布局结构中。`PlanTabView` 组件被包裹在一个具有 `overflow-y-auto` 属性的外层 div 中：

```tsx
// GoalsPage.tsx 修复前的代码结构
<main className="flex-1 flex min-h-0 overflow-hidden">
    {activeTab === 'todo' && <TodoTabView />}

    {activeTab !== 'todo' && (
        <div className="flex-1 overflow-y-auto p-0 no-scrollbar">  {/* 问题所在 */}
            {activeTab === 'plan' && <PlanTabView />}
            ...
        </div>
    )}
</main>
```

### 问题解析

1. `PlanTabView` 组件本身设计为 `h-full overflow-hidden`，有自己独立的滚动区域管理
2. 但它被错误地包裹在一个 `overflow-y-auto` 的外层容器中
3. 当鼠标在左侧边栏区域滚动时：
   - 左侧边栏的 Week List 区域内容不足以产生内部滚动
   - 滚轮事件冒泡到外层的 `overflow-y-auto` 容器
   - 导致整个 Plan 页面内容（包括左侧边栏）一起滚动

### 为什么 TodoTabView 没有这个问题？

观察代码可以发现，`TodoTabView` 是直接渲染在 `main` 容器中的，没有被 `overflow-y-auto` 的 div 包裹：

```tsx
{activeTab === 'todo' && <TodoTabView />}  // 直接渲染，不在 overflow-y-auto 容器内
```

## 解决方案

### 修复方法

将 `PlanTabView` 从 `overflow-y-auto` 容器中移出，让它与 `TodoTabView` 保持一致的渲染方式：

```tsx
// GoalsPage.tsx 修复后的代码结构
<main className="flex-1 flex min-h-0 overflow-hidden">
    {activeTab === 'todo' && <TodoTabView />}
    {activeTab === 'plan' && <PlanTabView />}  {/* 直接渲染，不在外层滚动容器内 */}

    {activeTab !== 'todo' && activeTab !== 'plan' && (
        <div className="flex-1 overflow-y-auto p-0 no-scrollbar">
            ...其他标签页内容
        </div>
    )}
</main>
```

### 修改的文件

| 文件路径 | 修改内容 |
|---------|---------|
| `frontend/page/goals/GoalsPage.tsx` | 将 `PlanTabView` 从 `overflow-y-auto` 容器中移出 |
| `frontend/page/goals/components/PlanTabView.tsx` | 为 Week List 区域添加 `onWheel` 事件处理器（辅助优化） |

### 详细代码变更

**GoalsPage.tsx**:
```diff
 <main className="flex-1 flex min-h-0 overflow-hidden">
     {activeTab === 'todo' && <TodoTabView />}
-
-    {activeTab !== 'todo' && (
+    {activeTab === 'plan' && <PlanTabView />}
+
+    {activeTab !== 'todo' && activeTab !== 'plan' && (
         <div className="flex-1 overflow-y-auto p-0 no-scrollbar">
-            {activeTab === 'plan' && <PlanTabView />}
-
             <div className="max-w-6xl mx-auto p-10 h-full">
```

**PlanTabView.tsx** (辅助优化):
```diff
 {/* Week List */}
-<div className="flex-1 space-y-1 overflow-y-auto scrollbar-light">
+<div 
+    className="flex-1 space-y-1 overflow-y-auto scrollbar-light"
+    onWheel={(e) => e.stopPropagation()}
+>
```

## 验证结果

修复后经浏览器测试验证：
- ✅ 鼠标悬停在左侧 Week 选择区域时，滚轮滚动不再导致页面滚动
- ✅ 左侧边栏（Week 1-4 和月总结按钮）保持固定位置
- ✅ 右侧主内容区域的滚动功能正常
- ✅ 页面整体布局稳定

## 经验总结

1. **组件独立性原则**: 具有独立滚动管理的组件（如 `PlanTabView`、`TodoTabView`）应该直接渲染，避免被外层滚动容器包裹
2. **事件冒泡防护**: 对于不需要传播滚轮事件的区域，可以使用 `onWheel={(e) => e.stopPropagation()}` 阻止事件冒泡
3. **布局一致性**: 相同类型的组件（如各个 Tab View）应该保持一致的渲染方式，便于维护和避免意外问题

## 相关链接

- 问题发现日期: 2024-12-24
- 修复提交: N/A (待提交)
- 相关组件: `GoalsPage.tsx`, `PlanTabView.tsx`
