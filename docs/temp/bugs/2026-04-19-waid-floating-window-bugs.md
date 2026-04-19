# WAID 浮窗 Bug 记录

**日期**: 2026-04-19
**状态**: 仅发现根因，未修复

---

## Bug 1: 浮窗无法置顶

**文件**: `frontend/electron/main.cjs`
**位置**: 第 322-326 行

```javascript
const existing = floatingWindows[windowId];
if (existing && !existing.isDestroyed()) {
    existing.show();
    existing.focus();  // ← 问题在这里
    return { success: true, action: 'focused' };
}
```

**根因**: 当浮窗已经存在时，代码仅调用 `show()` + `focus()` 来恢复窗口。但对于设置了 `alwaysOnTop: true` 的窗口，在 Windows 上 `focus()` 可能无法正确将窗口提升到所有窗口之上。特别是在有其他 `alwaysOnTop` 窗口（如对话框）存在时，`focus()` 的提升效果会被削弱。

**对比**: 主窗口创建时没有设置 `alwaysOnTop`，但浮窗和对话框都设置了。如果对话框和浮窗同时存在，`focus()` 可能只会聚焦到对话框而非浮窗。

---

## Bug 2: 副屏幕浮窗宽度无限增长

**文件**:
- 前端: `frontend/floating/what-am-i-doing/WhatAmIDoingFloat.tsx` 第 97-109 行
- 后端: `frontend/electron/main.cjs` 第 486-494 行

**复现条件**: 双屏环境，副屏幕在左侧，将浮窗放在副屏幕上，对浮窗内项目进行操作后触发

**前端 ResizeObserver**:
```javascript
const observer = new ResizeObserver((entries) => {
    const contentHeight = entries[0].contentRect.height;
    const totalHeight = contentHeight + TITLE_BAR_HEIGHT + ADD_BUTTON_HEIGHT + PADDING;
    const clampedHeight = Math.max(120, Math.min(totalHeight, MAX_WINDOW_HEIGHT));
    window.electronAPI?.resizeFloatingWindow?.('what-am-i-doing', {
        height: Math.round(clampedHeight),  // 只传 height
    });
});
```

**后端 resize 处理**:
```javascript
ipcMain.handle('resize-floating-window', (_event, windowId, { width, height }) => {
    const win = floatingWindows[windowId];
    if (win && !win.isDestroyed()) {
        const [currentWidth] = win.getSize();
        win.setSize(width ?? currentWidth, Math.round(height));  // ← 问题嫌疑
        return { success: true };
    }
    return { success: false };
});
```

**根因推测**:

当浮窗在**副屏幕（左侧）**时，存在多 monitor 坐标系统问题：

1. 副屏幕在 Windows 中有**负的 x 坐标**
2. 当 `setSize(width, height)` 被调用时，Electron 内部可能在某种情况下把 **width 值误解为 x 方向的偏移量**
3. 每次 `resizeFloatingWindow` 被调用时，窗口的 x 坐标被累加偏移，导致窗口不断向右延展

另一种可能性：多 monitor 环境下，`getSize()` 和 `setSize()` 之间存在坐标系的微小差异累积，导致每次 resize 后窗口位置发生微小偏移。

**触发流程**: 操作浮窗内项目 → `refreshWaidTodos()` → React 重新渲染 → ResizeObserver 触发 → `setSize` 被调用 → 问题复现

---

## 相关代码文件

| 文件 | 说明 |
|-----|------|
| `frontend/electron/main.cjs` | Electron 主进程，浮窗创建和 resize 处理 |
| `frontend/floating/what-am-i-doing/WhatAmIDoingFloat.tsx` | WAID 浮窗主组件，包含 ResizeObserver |
| `frontend/floating/what-am-i-doing/components/WaidTodoItem.tsx` | 浮窗内的任务项组件 |
| `frontend/electron/preload.cjs` | 预加载脚本，暴露 `resizeFloatingWindow` API |
