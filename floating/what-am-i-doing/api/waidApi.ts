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
import { BackendTaskPoolItem } from '../../../apps/goals/types/backend';
import { mapBackendTaskItemToFrontend } from '../../../apps/goals/apis/taskPool';

const getApiBase = createApiV2UrlGetter();

export const WaidAPI = {
    /** 获取浮窗 todo 列表（waid_order IS NOT NULL，ASC 排序） */
    getWaidTodos: async (): Promise<TodoItem[]> => {
        const response = await fetch(`${getApiBase()}/todos/waid`);
        if (!response.ok) {
            throw new Error(`Failed to fetch WAID todos: ${response.statusText}`);
        }
        const data: { items: BackendTaskPoolItem[] } = await response.json();
        return data.items.map(mapBackendTaskItemToFrontend);
    },

    /** 添加 todo 到浮窗（自动追加到末尾） */
    addToWaid: async (todoId: number): Promise<void> => {
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
    batchAddToWaid: async (todoIds: number[]): Promise<void> => {
        // 后端没有批量添加端点，逐个调用
        for (const id of todoIds) {
            await WaidAPI.addToWaid(id);
        }
    },

    /** 从浮窗移除（设 waid_order = NULL） */
    removeFromWaid: async (todoId: number): Promise<void> => {
        const response = await fetch(`${getApiBase()}/todos/${todoId}/waid`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            throw new Error(`Failed to remove todo from WAID: ${response.statusText}`);
        }
    },

    /** 批量更新排序（按数组顺序赋值 waid_order 0,1,2...） */
    reorderWaid: async (todoIds: number[]): Promise<void> => {
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
    batchGetDuration: async (todoIds: number[], date: string): Promise<Record<number, number>> => {
        if (todoIds.length === 0) return {};
        const response = await fetch(`${getApiBase()}/timeline/custom-blocks/batch-duration`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ todo_ids: todoIds, date }),
        });
        if (!response.ok) {
            throw new Error(`Failed to get batch duration: ${response.statusText}`);
        }
        const result: { data: Record<string, number> } = await response.json();
        // 后端返回 string key，转为 number key
        const mapped: Record<number, number> = {};
        for (const [key, value] of Object.entries(result.data)) {
            mapped[Number(key)] = value;
        }
        return mapped;
    },
};
