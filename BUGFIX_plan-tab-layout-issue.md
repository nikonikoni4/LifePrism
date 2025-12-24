# Plan Tab 布局问题修复文档

## 问题描述

在 Goals 页面的 Plan Tab 中，周计划（Weekly Plan）和月计划（Monthly Plan）视图无法占满整个右侧界面区域，右侧存在一条竖线和空白区域。

### 问题表现
- 周/月计划内容区域被限制在固定宽度（约742px）
- 右侧出现明显的空白区域和竖线分隔
- 当 AI Assistant 面板关闭时，空白区域仍然存在
- 用户希望周/月计划布局占满整个右侧界面

## 问题原因

### 根本原因
`PlanTabView` 组件的根元素缺少 `flex-1` CSS 类。

### 技术分析
1. **父容器结构**：`GoalsPage.tsx` 的 `<main>` 元素使用了 `flex-1 flex` 布局
2. **子组件问题**：`PlanTabView` 的根 `<div>` 只有 `flex h-full overflow-hidden bg-transparent`，没有 `flex-1`
3. **结果**：由于缺少 `flex-1`，`PlanTabView` 组件只占用其子元素所需的最小宽度，而非扩展填满可用空间

```tsx
// 修复前
<div className="flex h-full overflow-hidden bg-transparent">

// 修复后
<div className="flex flex-1 h-full overflow-hidden bg-transparent">
```

## 解决方案

### 修改文件
`frontend/page/goals/components/PlanTabView.tsx`

### 修改内容
在第 222 行的根 `<div>` 元素上添加 `flex-1` 类：

```diff
return (
-   <div className="flex h-full overflow-hidden bg-transparent">
+   <div className="flex flex-1 h-full overflow-hidden bg-transparent">
        {/* Left: Sidebar */}
        ...
```

## 修复效果

- ✅ 周计划视图（Weekly Plan）现在占满整个右侧区域
- ✅ 月计划视图（Monthly Plan）现在占满整个右侧区域
- ✅ 不再有竖线或空白区域
- ✅ AI Assistant 面板打开/关闭时布局正确响应

## 相关知识

### Flexbox `flex-1` 解释
- `flex-1` 是 `flex: 1 1 0%` 的简写
- 表示元素可以自动扩展（grow）和收缩（shrink），基础大小为 0
- 在 flex 容器中，带有 `flex-1` 的子元素会自动填满剩余空间

### 相关文件
- `frontend/page/goals/GoalsPage.tsx` - 父容器，定义了 flex 布局
- `frontend/page/goals/components/PlanTabView.tsx` - 需要填满空间的子组件
- `frontend/page/goals/components/TodoTabView.tsx` - 类似结构，可作为参考

## 日期
2024-12-24
