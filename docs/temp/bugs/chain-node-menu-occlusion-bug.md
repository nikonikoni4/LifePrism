# Habit Chain 节点菜单遮挡 Bug 分析

## 1. 现象描述

在习惯链条 (Habit Chain) 的展示列表（涉及文件 `frontend/apps/habits/components/views/chains/ChainNode.tsx` 中），当点击某一个节点右侧的“更多”（MoreHorizontal）图标展开下拉菜单时，如果该节点在页面下方还有其他兄弟节点，下拉菜单的下半部分会被紧邻的兄弟节点遮盖。此时，单纯给这个菜单 DOM 设置高层级（如 `z-index: 50` 或更大）无法破除遮挡。

## 2. 深入成因分析

这是前端 CSS 中经典的**层叠上下文（Stacking Context）**引起的相互遮挡问题，结合项目的当前实现，具体由以下两个因素叠加导致：

### 2.1. 兄弟节点渲染的“后来居上”特性
在 HTML 正常的文档流和渲染机制中，同级关系的元素在层级属性相同时，排在后面的 DOM 节点会自然覆盖在排在前面的DOM节点之上。

### 2.2. dnd-kit 引入了破坏性的 `transform`
为了实现拖拽功能，代码中通过 `@dnd-kit/sortable` 注入了如下样式：

```tsx
const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 50 : 10,
    opacity: isDragging ? 0.8 : 1,
};
```

🚨 **关键冲突点**：根据 CSS 规范，当一个元素设置了任何非 `none` 的 `transform` 属性时，该节点就会被**强制创建一个全新的层叠上下文**。
这意味着，每一个 HabitChainNode，都是一个独立且完全封闭的透明小世界。节点内部的元素无论 `z-index` 设置多大，其比对范围只限于它自身所在的这一个节点。“菜单”是不能拿它的 `z-index` 跳出去和“其他外部节点”比的。由于当前这些节点在不拖拽时 `z-index` 皆为 10，下方的节点凭借天然渲染顺位盖住了上方节点构筑的世界，自然也盖住了躲在上方节点里的弹窗菜单。

## 3. 决定采用的解决策略

面对此问题，决定采用**最彻底、最能解决边界情况**的做法。虽然临时提升被点击节点的 `z-index`（方案一） 可以解决节点间的遮挡，但这种方案一旦遇到外层大列表容器有 `overflow: auto` 或 `overflow: hidden`（滚动裁剪）的限制时，底部弹出的菜单依然会被切刀截断。

为了健壮性，采用**业界标准化的 React Portals 方案（即此前讨论的“方案二”）**对下拉菜单进行重构：

### 实现要点
1. **彻底解绑 DOM 层级 (React Portals)**：
   不再将包含着“编辑”、“删除”的下拉菜单以嵌套子组件的形式，包裹在 `<div className="relative">` 这个物理父盒子里。而是利用 `ReactDOM.createPortal`，当菜单被唤起时，直接将其对应的 DOM 结构插入到底层 `document.body` 尾部。这样菜单将直接无视整个 HabitChain 组件甚至更上游弹窗的层叠限制。

2. **浮动精准定位计算**：
   既然剥离了 `relative` 外壳，菜单将失去参照物。好在项目里已安装 `package.json -> @floating-ui/dom` 工具包库能够提供精准计算。
   - 当点击 `MoreHorizontal` 时，系统捕获该按钮在当前屏幕（Viewport）里的真实物理坐标 (`BoundingClientRect`)。
   - 将计算得到的坐标或直接将触发节点引用传递给 Floating UI。它将帮助把被 Portal 穿梭出去的那一大块菜单自动挂在对应的物理坐标旁，并附带诸如碰撞检测、自动反转方向等实用特性。
