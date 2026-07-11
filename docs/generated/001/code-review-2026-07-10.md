# Code Review Report

**审查范围**: `frontend/shell/ModuleDock.tsx` — 移动端触屏适配修改
**审查时间**: 2026-07-10
**变更文件**: `frontend/shell/ModuleDock.tsx`（+62 行 / -5 行）

## 架构上下文

### 相关 Spec
- 无直接相关的 spec（ModuleDock 是前端 Shell 层导航组件，暂无独立 spec）

### 相关 ADR
- 无直接相关的 ADR

### 变更意图
解决手机端访问时导航栏（ModuleDock）无法显示的问题。原因为 ModuleDock 完全依赖鼠标事件（`mousemove`、`onMouseEnter`、`onMouseLeave`）触发显示/隐藏，触屏设备无这些事件。

## 审查结果

### 审查过程中发现并修复的问题

#### Issue 1: 🔴 全屏遮罩层阻止所有用户交互（已修复）
- **类型**: Code Quality / Bug
- **置信度**: 100
- **位置**: `ModuleDock.tsx:210-216`（原代码）
- **详情**: 使用 `fixed inset-0 z-[9997]` 全屏遮罩作为触屏设备的"点击空白处隐藏"机制。该遮罩会覆盖整个视口，导致用户无法滚动页面、无法与遮罩下方任何内容交互，相当于冻结了整个应用。
- **修复**: 去掉全屏遮罩。触屏设备上 Dock 默认始终可见，通过顶部 44px 触发区域唤出。

#### Issue 2: 🟡 混合设备误检测风险（已修复）
- **类型**: Code Quality
- **置信度**: 75
- **位置**: `ModuleDock.tsx:89-92`（原代码）
- **详情**: 原检测逻辑 `hasCoarsePointer || hasTouchEvents` 中，`'ontouchstart' in window` 和 `navigator.maxTouchPoints > 0` 会在带触摸屏的笔记本电脑（如 Surface）上返回 true，即使当前使用鼠标作为主输入设备。这会导致此类设备的鼠标悬停 Dock 行为被禁用。
- **修复**: 改用 `(pointer: coarse)` 媒体查询作为唯一检测手段（检测**主指针设备**类型），仅在浏览器不支持 matchMedia 时回退到 `'ontouchstart' in window`。

#### Issue 3: 🟡 注释过时（未修复，低优先级）
- **类型**: Documentation
- **置信度**: 25
- **位置**: `ModuleDock.tsx:193`
- **详情**: `handleDockTouchStart` 的注释写"触屏设备点击 Dock 外部时隐藏"，但该函数实际只更新 `mouseX` 以支持放大效果。
- **建议**: 后续修正注释为"触摸时更新 mouseX 以支持放大效果"。

### 验证通过项

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 桌面端行为不变 | ✅ | `isTouchDevice=false` 时所有代码路径与修改前完全一致 |
| 内存泄漏 | ✅ | 所有 useEffect 返回 cleanup 函数，matchMedia listener 正确移除 |
| TypeScript 类型 | ✅ | 无类型错误 |
| 安全风险 | ✅ | 纯 UI 交互逻辑，不涉及数据或认证 |
| 依赖数组正确 | ✅ | mousemove useEffect 正确添加 `isTouchDevice` 依赖 |
| 事件清理 | ✅ | 定时器清理、事件监听移除均正确 |

### 桌面端行为确认

修改对桌面端（非触屏设备）**零影响**，关键路径验证：

1. `isTouchDevice` 初始 `false` → 检测后保持 `false`
2. `isVisible` 初始 `false` → 检测后保持 `false`（桌面端不默认显示）
3. mousemove 监听器正常注册（`isTouchDevice=false` 时不跳过）
4. `handleDockMouseEnter`/`handleDockMouseLeave` 正常执行（`isTouchDevice=false` 时不 return early）
5. 触发区域高度保持 20px（`isTouchDevice ? 44 : TRIGGER_ZONE_HEIGHT` → 20）
6. `onMouseEnter` 绑定 `showDock`（`isTouchDevice ? undefined : showDock` → showDock）
7. 无全屏遮罩（`isTouchDevice && isVisible` → `false`）

## 变更摘要

1. **新增触屏设备检测** — `useEffect` 中使用 `matchMedia('(pointer: coarse)')` 检测主指针设备类型
2. **触屏默认显示 Dock** — 检测到触屏设备时 `isVisible` 初始化为 `true`
3. **跳过鼠标事件** — 触屏设备上三个关键路径跳过鼠标逻辑：全局 mousemove、onMouseEnter、onMouseLeave
4. **新增触摸事件** — `onTouchStart` 处理器支持触摸位置驱动的图标放大动效
5. **触发区域适配** — 触屏设备触发区域高度从 20px 增加到 44px（手指友好尺寸）
6. **设备切换监听** — 监听 `(pointer: coarse)` 变化（如平板接入键盘/鼠标）
