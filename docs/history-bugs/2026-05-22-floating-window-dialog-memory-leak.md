# 2026-05-22 浮窗对话框监听器内存泄露

## 基本信息

- **日期**: 2026-05-22
- **严重程度**: 高（内存泄露）
- **状态**: 已修复
- **影响范围**: `frontend/floating/what-am-i-doing`

## 问题描述

当用户在 What Am I Doing 浮窗中停止计时后，会弹出 `record-activity` 对话框让用户输入活动内容。如果用户直接关闭对话框窗口（点击 X 按钮或右键关闭），而不是点击对话框内的"确认"或"取消"按钮，会导致浮窗中注册的监听器无法被清理，造成内存泄露。

### 问题场景

1. 用户在浮窗中开始计时一个任务
2. 等待 60 秒以上后停止计时
3. `record-activity` 对话框弹出
4. **用户直接点击窗口 X 按钮关闭对话框**（而不是点击确认/取消）
5. 浮窗中的监听器未被清理，持续占用内存
6. 重复上述操作多次后，内存持续增长

### 根本原因

在修复前，`openRecordActivityDialog()` 函数只注册了 `activity-recorded` 监听器来等待用户确认，但没有监听对话框的 `closed` 事件。当用户直接关闭窗口时：

1. 对话框窗口被销毁
2. Electron 主进程广播 `dialog-closed` 消息
3. 但浮窗没有注册 `dialog-closed` 监听器，无法接收通知
4. `activity-recorded` 监听器永远不会被清理
5. Promise 永久挂起，无法 resolve
6. 每次重复操作都会泄露一个监听器

## 修复方案

### 修复内容

**文件**: `frontend/floating/what-am-i-doing/hooks/useWaidTimer.ts`

1. **注册 `dialog-closed` 监听器**（第 78 行）：
   ```typescript
   window.electronAPI?.onMessage?.('dialog-closed', handleDialogClosed);
   ```

2. **实现 `handleDialogClosed` 处理器**（第 68-74 行）：
   ```typescript
   const handleDialogClosed = (data: { dialogId: string }) => {
       if (data.dialogId === 'record-activity') {
           console.log('[openRecordActivityDialog] Dialog closed, cleaning up listeners');
           cleanupListeners();
           resolve(); // 对话框关闭时也 resolve，不创建 CustomBlock
       }
   };
   ```

3. **清理函数包含两个监听器**（第 31-34 行）：
   ```typescript
   const cleanupListeners = () => {
       window.electronAPI?.removeMessageListener?.('activity-recorded', handleActivityRecorded);
       window.electronAPI?.removeMessageListener?.('dialog-closed', handleDialogClosed);
   };
   ```

### Electron 主进程支持

**文件**: `frontend/electron/main.cjs:536-546`

Electron 主进程在对话框关闭时广播 `dialog-closed` 消息：

```javascript
win.on('closed', () => {
    delete dialogWindows[dialogId];
    
    // 向所有浮窗广播 dialog-closed 消息，用于清理监听器
    for (const [floatingId, floatingWin] of Object.entries(floatingWindows)) {
        if (floatingWin && !floatingWin.isDestroyed()) {
            floatingWin.webContents.send('dialog-closed', { dialogId });
        }
    }
});
```

## 修复后的工作流程

### 场景 A: 用户点击确认
1. 用户输入活动内容，点击确认
2. 对话框发送 `activity-recorded` 消息
3. `handleActivityRecorded` 触发
4. 创建 CustomBlock
5. 调用 `cleanupListeners()` 清理两个监听器
6. Promise resolve

### 场景 B: 用户直接关闭窗口
1. 用户点击窗口 X 按钮
2. Electron 主进程广播 `dialog-closed` 消息
3. `handleDialogClosed` 触发
4. 调用 `cleanupListeners()` 清理两个监听器
5. Promise resolve（不创建 CustomBlock）
6. 无内存泄露

## 验证方法

### 手动测试

1. 打开 What Am I Doing 浮窗
2. 开始计时一个任务，等待 60 秒以上
3. 停止计时 → `record-activity` 对话框弹出
4. **直接点击窗口 X 按钮关闭**（不点击确认/取消）
5. 打开浏览器开发者工具，检查控制台是否有日志：
   ```
   [openRecordActivityDialog] Dialog closed, cleaning up listeners
   ```
6. 重复步骤 2-4 多次（至少 10 次）
7. 检查内存使用情况（Chrome DevTools → Memory → Take Heap Snapshot）
8. **预期结果**: 监听器数量不增长，内存使用稳定

### 长时间运行测试

1. 重复以下操作 20 次：
   - 开始计时 → 等待 60 秒 → 停止计时
   - 随机选择：点击确认 或 直接关闭对话框
2. 检查内存使用情况
3. **预期结果**: 内存使用稳定，无持续增长

## 相关文件

- `frontend/floating/what-am-i-doing/hooks/useWaidTimer.ts` (第 29-98 行)
- `frontend/electron/main.cjs` (第 536-546 行)
- `frontend/electron/preload.cjs` (第 129-138 行)

## 相关模式

### `todo-picker` 对话框（无泄露风险）

`todo-picker` 对话框使用不同的通信模式，不存在内存泄露风险：

- **模式**: 主动推送（不是监听器等待）
- **工作流程**:
  1. 浮窗打开 `todo-picker` 对话框
  2. 对话框完成操作后，主动调用 `sendToFloating('what-am-i-doing', 'waid-refresh')`
  3. 浮窗的 `waid-refresh` 监听器接收消息并刷新
  4. 监听器在组件卸载时正确清理

- **为什么没有泄露**:
  - `todo-picker` 不需要等待对话框返回值
  - 浮窗的 `waid-refresh` 监听器是长期存在的，与对话框生命周期无关
  - 监听器在组件卸载时正确清理

## 经验教训

### 1. 对话框通信模式选择

**模式 A: 监听器等待模式**（`record-activity`）
- 适用场景：需要等待对话框返回值
- 要求：必须监听 `dialog-closed` 事件以清理监听器
- 优点：可以获取用户输入的数据
- 缺点：需要手动管理监听器生命周期

**模式 B: 主动推送模式**（`todo-picker`）
- 适用场景：对话框完成操作后主动通知
- 要求：对话框主动调用 `sendToFloating`
- 优点：无需等待，无内存泄露风险
- 缺点：需要对话框知道目标窗口 ID

### 2. 监听器清理原则

**必须清理的场景**：
- 对话框关闭（无论是确认还是取消）
- 组件卸载
- 窗口关闭

**清理检查清单**：
- [ ] 是否注册了 `dialog-closed` 监听器？
- [ ] 是否在所有退出路径都调用了清理函数？
- [ ] Promise 是否在所有场景下都能 resolve/reject？
- [ ] 是否在组件卸载时清理长期监听器？

### 3. Electron 窗口间通信最佳实践

**主进程职责**：
- 在窗口关闭时广播 `dialog-closed` 消息
- 确保消息发送到所有相关窗口
- 清理窗口引用

**渲染进程职责**：
- 注册必要的监听器
- 在所有退出路径清理监听器
- 避免监听器泄露

### 4. 调试内存泄露的方法

1. **Chrome DevTools Memory Profiler**:
   - Take Heap Snapshot
   - 比较多次快照，查找持续增长的对象
   - 搜索 "Detached" 节点

2. **Console 日志**:
   - 在监听器注册/清理时打印日志
   - 验证清理函数是否被调用

3. **重复操作测试**:
   - 重复触发问题场景 10-20 次
   - 观察内存使用趋势

## 触发规则

在以下场景时阅读此文档：

- 排查浮窗或对话框相关的内存泄露问题
- 实现新的对话框通信机制
- 发现监听器未被清理的问题
- 排查 Promise 永久挂起的问题
- 实现窗口间通信时需要参考最佳实践
