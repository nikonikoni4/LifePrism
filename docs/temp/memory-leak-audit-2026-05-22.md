# 浮窗内存泄露审查报告

**日期**: 2026-05-22  
**审查范围**: `frontend/floating` 和 `frontend/electron`  
**问题描述**: 用户报告当对话框被直接关闭（非点击确认/取消按钮）时，浮窗中的监听器未被清理，导致内存泄露

## 审查结果

### ✅ 问题已修复

经过系统性审查，**内存泄露问题已经在之前的代码修改中被修复**。

## 详细分析

### 1. `record-activity` 对话框（已修复）

**文件**: `frontend/floating/what-am-i-doing/hooks/useWaidTimer.ts`

**修复内容**:
- **第 77-78 行**: 注册了两个监听器
  ```typescript
  window.electronAPI?.onMessage?.('activity-recorded', handleActivityRecorded);
  window.electronAPI?.onMessage?.('dialog-closed', handleDialogClosed);
  ```

- **第 31-34 行**: 清理函数
  ```typescript
  const cleanupListeners = () => {
      window.electronAPI?.removeMessageListener?.('activity-recorded', handleActivityRecorded);
      window.electronAPI?.removeMessageListener?.('dialog-closed', handleDialogClosed);
  };
  ```

- **第 68-74 行**: `dialog-closed` 处理器
  ```typescript
  const handleDialogClosed = (data: { dialogId: string }) => {
      if (data.dialogId === 'record-activity') {
          console.log('[openRecordActivityDialog] Dialog closed, cleaning up listeners');
          cleanupListeners();
          resolve(); // 对话框关闭时也 resolve，不创建 CustomBlock
      }
  };
  ```

**工作流程**:
1. 用户停止计时 → `stopTimer()` 被调用
2. `openRecordActivityDialog()` 打开对话框并注册监听器
3. **场景 A**: 用户点击确认 → `activity-recorded` 触发 → 清理监听器 → resolve
4. **场景 B**: 用户直接关闭窗口 → Electron 广播 `dialog-closed` → `handleDialogClosed` 触发 → 清理监听器 → resolve
5. Promise 正确结束，无内存泄露

### 2. `todo-picker` 对话框（无泄露风险）

**文件**: `frontend/dialogs/todo-picker/TodoPickerDialog.tsx`

**通信模式**: 主动推送（不是监听器等待）

**工作流程**:
1. 浮窗打开 `todo-picker` 对话框（`WhatAmIDoingFloat.tsx:174-178`）
2. 对话框完成操作后，主动调用 `sendToFloating('what-am-i-doing', 'waid-refresh')` （`TodoPickerDialog.tsx:177`）
3. 浮窗的 `waid-refresh` 监听器接收消息并刷新（`WhatAmIDoingFloat.tsx:86-94`）
4. 监听器在组件卸载时正确清理（第 91-93 行）

**为什么没有泄露**:
- `todo-picker` 不需要等待对话框返回值
- 浮窗的 `waid-refresh` 监听器是长期存在的，与对话框生命周期无关
- 监听器在组件卸载时正确清理

### 3. Electron 主进程（正确实现）

**文件**: `frontend/electron/main.cjs:536-546`

```javascript
// 关闭时清理引用，并通知所有浮窗对话框已关闭
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

**功能**:
- 对话框关闭时，向所有浮窗广播 `dialog-closed` 消息
- 确保即使用户直接关闭窗口，浮窗也能收到通知并清理监听器

## 验证清单

### ✅ 代码审查

- [x] `record-activity` 对话框注册了 `dialog-closed` 监听器
- [x] `handleDialogClosed` 正确清理所有监听器
- [x] Promise 在对话框关闭时正确 resolve
- [x] `todo-picker` 使用主动推送模式，无泄露风险
- [x] Electron 主进程正确广播 `dialog-closed` 消息
- [x] 浮窗的长期监听器在组件卸载时正确清理

### 🧪 建议的手动测试

为了确保修复有效，建议进行以下测试：

#### 测试 1: `record-activity` 对话框直接关闭
1. 打开 What Am I Doing 浮窗
2. 开始计时一个任务，等待 60 秒以上
3. 停止计时 → `record-activity` 对话框弹出
4. **直接点击窗口 X 按钮关闭**（不点击确认/取消）
5. 打开浏览器开发者工具，检查控制台是否有日志：
   ```
   [openRecordActivityDialog] Dialog closed, cleaning up listeners
   ```
6. 重复步骤 2-4 多次（至少 5 次）
7. 检查内存使用情况（Chrome DevTools → Memory → Take Heap Snapshot）
8. **预期结果**: 监听器数量不增长，无内存泄露

#### 测试 2: `record-activity` 对话框正常确认
1. 打开 What Am I Doing 浮窗
2. 开始计时一个任务，等待 60 秒以上
3. 停止计时 → `record-activity` 对话框弹出
4. 输入活动内容，点击确认
5. **预期结果**: CustomBlock 创建成功，对话框关闭，无错误

#### 测试 3: `todo-picker` 对话框
1. 打开 What Am I Doing 浮窗
2. 点击 "+" 按钮 → "Select Existing"
3. `todo-picker` 对话框弹出
4. 选择一些任务，点击 "Add"
5. **预期结果**: 任务添加到浮窗，对话框关闭
6. 重复步骤 2-3，但直接点击 X 关闭对话框
7. **预期结果**: 对话框关闭，浮窗无变化，无错误

#### 测试 4: 长时间运行测试
1. 打开 What Am I Doing 浮窗
2. 重复以下操作 20 次：
   - 开始计时 → 等待 60 秒 → 停止计时
   - 随机选择：点击确认 或 直接关闭对话框
3. 检查内存使用情况
4. **预期结果**: 内存使用稳定，无持续增长

## 结论

✅ **内存泄露问题已修复**

代码审查确认：
1. `record-activity` 对话框的监听器在对话框关闭时正确清理
2. `todo-picker` 对话框使用主动推送模式，无泄露风险
3. Electron 主进程正确广播 `dialog-closed` 消息

建议进行上述手动测试以验证修复的有效性。

## 相关文件

- `frontend/floating/what-am-i-doing/hooks/useWaidTimer.ts` (第 29-98 行)
- `frontend/floating/what-am-i-doing/WhatAmIDoingFloat.tsx` (第 86-94, 174-178 行)
- `frontend/dialogs/todo-picker/TodoPickerDialog.tsx` (第 167-183 行)
- `frontend/electron/main.cjs` (第 536-546 行)
- `frontend/electron/preload.cjs` (第 129-138 行)
