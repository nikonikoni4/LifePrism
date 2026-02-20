/**
 * PlanDoc 安全的 Todo 操作包装
 *
 * 浮窗是独立 BrowserWindow，无法使用主窗口的 useTaskPoolStore Context。
 * 但 todo CRUD 操作前后必须通知主窗口做 PlanDoc 同步：
 *   - 操作前：triggerAllPlanDocSaves()（防止主窗口未保存内容被覆盖）
 *   - 操作后：triggerAllPlanDocRefreshes()（刷新编辑器显示最新内容）
 *
 * 注意：waid_order 的更新（添加/移除/排序）不涉及 MD 同步，
 * 直接调用 WaidAPI 即可，不需要 safe* 包装。
 */

import { todoApi } from '../../../apps/goals/apis/todoApi';
import { BackendUpdateTodoResponse, BackendCreateTodoResponse } from '../../../apps/goals/types/backend';

const PLANDOC_SAVE_TIMEOUT = 2000; // 2s 超时兜底

/**
 * 通知主窗口保存所有 PlanDoc 编辑器内容
 * 必须在 todo 操作前调用，防止主窗口未保存内容被覆盖
 */
async function requestPlanDocSave(): Promise<void> {
    if (!window.electronAPI?.sendToMain) return;

    return new Promise<void>((resolve) => {
        let ipcHandler: ReturnType<typeof window.electronAPI.onMessage> | null = null;

        const timeout = setTimeout(() => {
            if (ipcHandler) window.electronAPI?.removeMessageListener?.('plandoc-save-done', ipcHandler);
            resolve();
        }, PLANDOC_SAVE_TIMEOUT);

        const callback = () => {
            clearTimeout(timeout);
            if (ipcHandler) window.electronAPI?.removeMessageListener?.('plandoc-save-done', ipcHandler);
            resolve();
        };

        ipcHandler = window.electronAPI!.onMessage('plandoc-save-done', callback);
        window.electronAPI!.sendToMain('plandoc-save-request');
    });
}

/** 通知主窗口刷新所有 PlanDoc 编辑器 */
async function requestPlanDocRefresh(): Promise<void> {
    await window.electronAPI?.sendToMain?.('plandoc-refresh-request');
}

/** PlanDoc 安全的 todo 更新 */
export async function safeUpdateTodo(
    todoId: number,
    updates: Record<string, unknown>
): Promise<BackendUpdateTodoResponse> {
    await requestPlanDocSave();
    const result = await todoApi.updateTodo(todoId, updates as any);
    await requestPlanDocRefresh();
    return result;
}

/** PlanDoc 安全的 todo 创建 */
export async function safeCreateTodo(
    data: Record<string, unknown>
): Promise<BackendCreateTodoResponse> {
    await requestPlanDocSave();
    const result = await todoApi.createTodo(data as any);
    await requestPlanDocRefresh();
    return result;
}

/** PlanDoc 安全的 todo 删除 */
export async function safeDeleteTodo(todoId: number): Promise<void> {
    await requestPlanDocSave();
    await todoApi.deleteTodo(todoId);
    await requestPlanDocRefresh();
}
