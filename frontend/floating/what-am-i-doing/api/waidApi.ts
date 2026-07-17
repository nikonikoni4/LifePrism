/**
 * WAID (What Am I Doing) 浮窗专用 API
 *
 * 后端端点：
 *   GET    /api/v2/todos/waid              - 获取浮窗 todo 列表
 *   PUT    /api/v2/todos/waid/reorder      - 批量重排序
 *   PUT    /api/v2/todos/{id}/waid         - 添加到浮窗
 *   DELETE /api/v2/todos/{id}/waid         - 从浮窗移除
 *   POST   /api/v2/timeline/custom-blocks/batch-duration - 批量查询累计时长
 */

import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { TodoItem } from '../../../apps/goals/types/todo';
import { BackendTodoItem } from '../../../apps/goals/types/backend';
import { mapBackendTodoToFrontend } from '../../../apps/goals/apis/todoApi';
import { toISOStringUTC } from '../../../core/utils/dateUtils';

const getApiBase = createApiV2UrlGetter();

export const WaidAPI = {
    /** 获取浮窗 todo 列表（waid_order IS NOT NULL，ASC 排序） */
    getWaidTodos: async (): Promise<TodoItem[]> => {
        const response = await fetch(`${getApiBase()}/todos/waid`);
        if (!response.ok) {
            throw new Error(`Failed to fetch WAID todos: ${response.statusText}`);
        }
        const data: { items: BackendTodoItem[] } = await response.json();
        return data.items.map(mapBackendTodoToFrontend);
    },

    /** 添加 todo 到浮窗（自动追加到末尾） */
    addToWaid: async (todoId: string): Promise<void> => {
        const response = await fetch(`${getApiBase()}/todos/${todoId}/waid`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        if (!response.ok) {
            throw new Error(`Failed to add todo to WAID: ${response.statusText}`);
        }
    },

    /** 批量添加 todo 到浮窗 */
    batchAddToWaid: async (todoIds: string[]): Promise<void> => {
        // 后端没有批量添加端点，逐个调用
        for (const id of todoIds) {
            await WaidAPI.addToWaid(id);
        }
    },

    /** 从浮窗移除（设 waid_order = NULL） */
    removeFromWaid: async (todoId: string): Promise<void> => {
        const response = await fetch(`${getApiBase()}/todos/${todoId}/waid`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            throw new Error(`Failed to remove todo from WAID: ${response.statusText}`);
        }
    },

    /** 批量更新排序（按数组顺序赋值 waid_order 0,1,2...） */
    reorderWaid: async (todoIds: string[]): Promise<void> => {
        const response = await fetch(`${getApiBase()}/todos/waid/reorder`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ todo_ids: todoIds }),
        });
        if (!response.ok) {
            throw new Error(`Failed to reorder WAID: ${response.statusText}`);
        }
    },

    /** 批量获取今日累计时长（返回 todoId → 分钟数） */
    batchGetDuration: async (todoIds: string[], date: string): Promise<Record<string, number>> => {
        if (todoIds.length === 0) return {};
        const startOfDay = new Date(`${date}T00:00:00`);
        const endOfDay = new Date(`${date}T23:59:59.999`);
        const start_time = toISOStringUTC(startOfDay);
        const end_time = toISOStringUTC(endOfDay);
        const response = await fetch(`${getApiBase()}/timeline/custom-blocks/batch-duration`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ todo_ids: todoIds, start_time, end_time }),
        });
        if (!response.ok) {
            throw new Error(`Failed to get batch duration: ${response.statusText}`);
        }
        const result: { data: Record<string, number> } = await response.json();
        return result.data;
    },
};
