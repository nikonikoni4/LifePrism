---
version: 1.0
created_at: 2026-04-19
updated_at: 2026-04-19
last_updated: 创建关于 Node 菜单遮挡的 bug 档案
abstract: 关于 Habit Chain 节点下拉菜单由于 dnd-kit 产生的 transform 层叠上下文引发的遮挡问题的分析与 React Portals 解决方案。
---

# Habit Chain 节点菜单遮挡 Bug 分析

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

1. **Bug简述**：在习惯链条（Habit Chain）列表中展开某一节点的下拉菜单时，菜单下方会被后续紧邻的兄弟节点遮挡，且单纯提高菜单的 `z-index` 无效。
2. **复用场景**：适用于解决具有拖拽功能、带有 `transform` 样式，或外层包裹了 `overflow: hidden/auto` 等情况下的子列表或复杂组件内的弹窗/菜单层叠渲染遮挡问题。
3. **代码位置**：`frontend/apps/habits/components/views/chains/ChainNode.tsx` 中与下拉菜单（MoreHorizontal）绑定的 DOM 节点。
4. **发生原因**：为实现拖拽功能，`@dnd-kit/sortable` 给节点元素注入了非 `none` 的 `transform` CSS属性。此行为会强制使得每个节点都构建出一个全新且封闭的“层叠上下文（Stacking Context）”。节点内部弹出的菜单其 `z-index` 的比较范围只限在其所属的这一个节点内，无法与下方节点进行直接比叠，致使后渲染的下方兄弟节点得以天然覆盖住了上方受限的弹窗。
5. **最佳方案**：解构脱离式方案（React Portals + Floating UI）。不要将菜单通过 `relative` + `absolute` 耦合在当前列表项的物理 DOM 层级中，而是利用 `ReactDOM.createPortal`，在唤起时将此菜单直接挂载到在最顶层的 `document.body` 尾部，从而跨越性逃逸一切内层元素的层叠限制。同时利用 `@floating-ui/dom` 在触发点击时做浮动精准的坐标定位和碰撞判定。
