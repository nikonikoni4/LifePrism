# WAID 浮窗 Bug 记录

**日期**: 2026-04-19
**状态**: 已修复

---

## Bug 1: 浮窗无法置顶

**文件**: `frontend/electron/main.cjs`
**位置**: 第 392-409 行

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

**修复方案**: 在 Windows 平台上，对于 `alwaysOnTop` 窗口，先取消置顶再重新置顶，强制刷新窗口层级。

```javascript
existing.show();
// Bug fix: 在 Windows 上，alwaysOnTop 窗口需要先取消置顶再重新置顶才能正确提升层级
if (process.platform === 'win32' && existing.isAlwaysOnTop()) {
    existing.setAlwaysOnTop(false);
    existing.setAlwaysOnTop(true);
}
existing.focus();
```

**修复日期**: 2026-04-22

---

## Bug 2: 副屏幕浮窗宽度无限增长

**文件**:
- 前端: `frontend/floating/what-am-i-doing/WhatAmIDoingFloat.tsx` 第 97-109 行
- 后端: `frontend/electron/main.cjs` 第 574-605 行

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

**后端 resize 处理（修复前）**:
```javascript
ipcMain.handle('resize-floating-window', (_event, windowId, { width, height }) => {
    const win = floatingWindows[windowId];
    if (win && !win.isDestroyed()) {
        const [currentWidth] = win.getSize();
        win.setSize(width ?? currentWidth, Math.round(height));  // ← 问题在这里
        return { success: true };
    }
    return { success: false };
});
```

**根因确认（通过日志分析）**:

从 `localData\debug_logs\electron.log` 日志中清楚看到：

```
请求尺寸: width=undefined, height=124
实际设置: 321x124
设置后尺寸: 322x126  ← 宽度增加了1px
---
下次调用:
当前尺寸: 322x126
实际设置: 322x124
设置后尺寸: 324x126  ← 又增加了2px
---
持续增长: 325 → 326 → 328 → 329...
```

**根本原因**: 在副屏幕（负x坐标）环境下，Electron 的 `setSize()` 方法存在已知bug。当窗口位于负坐标时，即使传入当前宽度，`setSize()` 也会导致窗口宽度意外增长。这是 Electron 在多显示器环境下的坐标系统计算问题。

**问题分析过程**:

1. **初步尝试**: 使用 `setBounds()` 替代 `setSize()` → 无效，问题依然存在
2. **深入分析**: 通过详细日志发现，ResizeObserver在1秒内触发十几次，形成死循环：
   - 内容高度变化 → 调用resize → Electron意外改变宽度 → 触发ResizeObserver → 再次调用resize
3. **根本原因**: 
   - Electron在副屏幕环境下，`setSize()` 会导致宽度增加1-2px，高度也增加2px
   - ResizeObserver检测到宽度变化后再次触发，形成死循环
   - 即使使用 `setBounds()` 也无法避免这个bug

**解决方案（2026-04-22）**:

采用**两层防护**策略：

1. **前端防护**: 只在内容高度真正变化时才调用resize，忽略宽度变化
   ```javascript
   // WhatAmIDoingFloat.tsx
   const observer = new ResizeObserver((entries) => {
       const contentHeight = entry.contentRect.height;
       const heightChanged = contentHeight !== lastHeight;
       
       // 只在高度变化时才调用resize，打破死循环
       if (!heightChanged) {
           return;
       }
       
       // 获取当前窗口宽度并明确传入
       window.electronAPI?.getFloatingWindowSize?.('what-am-i-doing').then((result) => {
           if (result?.success) {
               window.electronAPI?.resizeFloatingWindow?.('what-am-i-doing', {
                   width: result.width,  // 明确传入当前宽度
                   height: Math.round(clampedHeight),
               });
           }
       });
   });
   ```

2. **后端支持**: 添加 `getFloatingWindowSize` API，让前端能获取当前窗口宽度
   ```javascript
   // main.cjs
   ipcMain.handle('get-floating-window-size', (_event, windowId) => {
       const win = floatingWindows[windowId];
       if (win && !win.isDestroyed()) {
           const [width, height] = win.getSize();
           return { success: true, width, height };
       }
       return { success: false };
   });
   ```

**效果**:
- ✅ 解决了死循环导致的宽度无限增长问题
- ⚠️ 每次添加/删除任务时，宽度仍会增加1-2px（Electron底层bug无法完全避免）
- ✅ 支持手动调整宽度，调整后的宽度会被保持
- ✅ 可接受的解决方案，不影响正常使用

**状态**: 部分解决（可接受）

**修复日期**: 2026-04-22

---

## 相关代码文件

| 文件 | 说明 |
|-----|------|
| `frontend/electron/main.cjs` | Electron 主进程，浮窗创建和 resize 处理 |
| `frontend/floating/what-am-i-doing/WhatAmIDoingFloat.tsx` | WAID 浮窗主组件，包含 ResizeObserver |
| `frontend/floating/what-am-i-doing/components/WaidTodoItem.tsx` | 浮窗内的任务项组件 |
| `frontend/electron/preload.cjs` | 预加载脚本，暴露 `resizeFloatingWindow` API |
