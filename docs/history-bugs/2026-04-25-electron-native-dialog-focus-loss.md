# Electron 原生对话框导致焦点丢失和 undefined 错误

## 基本信息

- **日期**: 2026-04-25
- **严重程度**: 高
- **影响范围**: 所有使用 `window.confirm()`, `window.alert()`, `window.prompt()` 的 Electron 应用
- **平台**: Windows (主要), macOS, Linux

## 问题描述

这是一个复合 bug，包含两个相关但独立的问题：

### 问题 1: Electron 原生对话框导致输入框焦点丢失

**症状**:
- 调用 `window.confirm()` 或 `window.alert()` 后，页面上的输入框（input/textarea）变得无法输入
- 用户必须点击窗口外部再点击回来才能恢复输入功能
- 输入框看起来正常，但键盘输入无响应

**根本原因**:
Electron 在 Windows 平台上使用原生对话框时存在焦点管理 bug。当原生对话框关闭后，焦点没有正确返回到 BrowserWindow，导致输入元素失去键盘焦点。

**相关 Electron Issues**:
- [#31917 - Input field becomes unresponsive after window.Alert() and window.confirm()](https://github.com/electron/electron/issues/31917)
- [#41602 - Confirm/Alert popups break focus](https://github.com/electron/electron/issues/41602)
- [#20821 - Keyboard focus is lost in input DOM elements when displaying alert or similar browser dialogs](https://github.com/electron/electron/issues/20821)
- [#22923 - Unable to type in input unless clicked outside and back into the window](https://github.com/electron/electron/issues/22923)

### 问题 2: window.electronAPI 未定义导致应用崩溃

**症状**:
```
CategorySettingsTab.tsx:65 Uncaught (in promise) TypeError: Cannot read properties of undefined (reading 'showConfirm')
```

**根本原因**:
- 代码直接调用 `window.electronAPI.showConfirm()` 而没有检查 `window.electronAPI` 是否存在
- 在非 Electron 环境（如浏览器开发模式）或 preload 脚本未正确加载时，`window.electronAPI` 为 `undefined`
- 部分代码还存在逻辑错误：`if (!(await window.electronAPI.showConfirm(...)))` 在用户点击"取消"时才执行删除操作

## 复现步骤

### 问题 1 复现:
1. 在 Electron 应用中打开任何包含输入框的页面
2. 点击触发 `window.confirm()` 或 `window.alert()` 的按钮
3. 在对话框中点击确定或取消
4. 尝试在输入框中输入内容 → **无法输入**

### 问题 2 复现:
1. 在浏览器开发模式下运行前端应用（不在 Electron 环境）
2. 点击任何触发确认对话框的操作（如删除分类）
3. 应用崩溃并显示 `Cannot read properties of undefined` 错误

## 影响范围

**受影响的文件** (18 个):
- `frontend/apps/lifewatch/pages/category/components/CategorySettingsTab.tsx`
- `frontend/apps/lifewatch/pages/category/components/DataReviewTab.tsx`
- `frontend/apps/lifewatch/pages/category/components/CategoryMapCacheTab.tsx`
- `frontend/apps/lifewatch/pages/home/components/ActivitySummaryHeader.tsx`
- `frontend/apps/lifewatch/pages/timeline/Timeline.tsx`
- `frontend/apps/lifewatch/pages/timeline/components/CustomBlockLayer.tsx`
- `frontend/apps/lifewatch/pages/timeline/components/CustomBlockPopover.tsx`
- `frontend/apps/goals/components/views/GoalListView/GoalListView.tsx`
- `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx`
- `frontend/apps/mindspace/components/being/components/ReinterpretPast.tsx`
- `frontend/apps/mindspace/components/commitment/commitment.tsx`
- `frontend/apps/mindspace/components/journal/TemplateManager.tsx`
- `frontend/apps/mindspace/components/mood/EmotionView.tsx`
- `frontend/apps/habits/components/views/habits/HabitCard.tsx`
- `frontend/apps/habits/components/views/habits/PausedHabitCard.tsx`
- `frontend/apps/habits/components/views/chains/ChainNode.tsx`
- `frontend/apps/habits/components/views/chains/ChainCard.tsx`
- `frontend/core/components/CacheManager.tsx`

**受影响的功能**:
- 所有需要用户确认的删除操作
- 所有需要显示提示信息的操作
- 分类管理、数据审查、时间轴编辑、目标管理、习惯管理等核心功能

## 解决方案

### 方案 1: 使用 Electron 自定义对话框（推荐）

通过 preload 脚本暴露自定义对话框 API，避免使用原生对话框：

**preload.cjs**:
```javascript
const { ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    showConfirm: async (options) => {
        return await ipcRenderer.invoke('show-confirm', options);
    },
    showAlert: async (options) => {
        return await ipcRenderer.invoke('show-alert', options);
    }
});
```

**main.cjs**:
```javascript
ipcMain.handle('show-confirm', async (event, options) => {
    const result = await dialog.showMessageBox({
        type: 'question',
        buttons: ['取消', '确定'],
        defaultId: 1,
        message: options.message,
        noLink: true
    });
    return result.response === 1;
});
```

### 方案 2: 添加可选链和降级方案（当前实现）

为所有 `window.electronAPI` 调用添加可选链操作符和降级到原生对话框：

**修复前**:
```typescript
// 错误 1: 没有检查 electronAPI 是否存在
window.electronAPI.showAlert({ message: '操作失败' });

// 错误 2: 逻辑错误 - 用户点击"取消"时才执行删除
if (!(await window.electronAPI.showConfirm({ message: '确定删除？' }))) {
    await deleteItem(id);
}
```

**修复后**:
```typescript
// 方式 1: 使用条件判断
if (window.electronAPI?.showAlert) {
    window.electronAPI.showAlert({ message: '操作失败' });
} else {
    alert('操作失败');
}

// 方式 2: 使用三元运算符
const confirmed = window.electronAPI?.showConfirm
    ? await window.electronAPI.showConfirm({ message: '确定删除？' })
    : confirm('确定删除？');

if (confirmed) {
    await deleteItem(id);
}
```

## 实施细节

### 修改统计
- 18 个文件被修改
- +297 行新增
- -78 行删除

### 修复内容
1. **添加可选链操作符**: 所有 `window.electronAPI` 调用改为 `window.electronAPI?.`
2. **添加降级方案**: 
   - `showConfirm` → 降级到原生 `confirm()`
   - `showAlert` → 降级到原生 `alert()`
3. **修复逻辑错误**: 将 `if (!(await ...))` 改为先获取结果再判断

### 兼容性改进
修复后应用可以在以下环境正常运行：
- ✅ Electron 打包环境
- ✅ Electron 开发环境
- ✅ 纯浏览器环境（开发调试）

## 注意事项

1. **降级方案的局限性**: 
   - 在 Electron 环境下降级到原生 `confirm()`/`alert()` 仍会触发焦点丢失问题
   - 这只是一个临时兼容方案，确保应用不会崩溃
   - 最终应该完全使用 Electron 自定义对话框

2. **preload 脚本加载**: 
   - 确保 `preload.cjs` 正确配置在 `BrowserWindow` 的 `webPreferences` 中
   - 检查 `contextIsolation` 和 `nodeIntegration` 设置

3. **测试覆盖**: 
   - 在 Electron 环境和浏览器环境下都要测试
   - 测试对话框关闭后输入框是否能正常输入

## 相关资源

- [Electron Issue #31917](https://github.com/electron/electron/issues/31917)
- [Electron Issue #41602](https://github.com/electron/electron/issues/41602)
- [Electron Issue #20821](https://github.com/electron/electron/issues/20821)
- [cordova-electron-dialogs-fix](https://github.com/cimatti/cordova-electron-dialogs-fix) - 社区修复方案

## 提交记录

- **Commit**: `9b461b8`
- **Message**: `fix: 修复所有 window.electronAPI 调用的可选链和降级方案`
- **Date**: 2026-04-25
