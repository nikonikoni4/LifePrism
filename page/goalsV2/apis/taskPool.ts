/**
 * TaskPool API
 * /api/v2/taskpool
 * /api/v2/todos
 */

import { createApiV2UrlGetter } from '../../../services/apiConfig';
import { TodoItem } from '../types/todo';
import {
    BackendTaskPoolItem,
    BackendTaskPoolResponse,
    BackendSyncResponse,
    BackendUpdateTodoResponse,
    BackendCreateTodoResponse
} from '../types/backend';

// API base URL getter
// This points to /api/v2 (Default)
const getApiBase = createApiV2UrlGetter();

// ============================================================================
// Type Conversion Functions
// ============================================================================

export function mapBackendTaskItemToFrontend(item: BackendTaskPoolItem): TodoItem {
    return {
        id: item.id,
        content: item.content,
        parentId: item.parent_id ? String(item.parent_id) : null,
        goalId: item.link_to_goal_id,
        planDocId: item.plan_doc_id,
        sourceAnchorId: item.source_anchor_id,
        state: item.state as 'pool' | 'scheduled' | 'completed' | 'shelved',
        scheduledDate: item.date,
        expectedFinishAt: item.expected_finished_at,
        actualFinishAt: item.actual_finished_at,
        delayDays: item.delay_days,
        delayReason: item.delay_reason,
        color: item.color || '#FFFFFF',
        orderIndex: item.order_index,
        poolOrderIndex: item.pool_order_index,
        children: [],
    };
}

// ============================================================================
// API Functions
// ============================================================================

export const taskPoolApi = {
    /**
     * Get task pool items
     */
    fetchTaskPool: async (
        goalId?: string | null,
        planDocId?: string | null,
        state?: string
    ): Promise<TodoItem[]> => {
        const params = new URLSearchParams();
        if (goalId) params.append('goal_id', goalId);
        if (planDocId) params.append('plan_doc_id', planDocId);
        if (state) params.append('state', state);

        // Correct URL: /api/v2/taskpool
        const url = `${getApiBase()}/taskpool${params.toString() ? '?' + params.toString() : ''}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Failed to fetch taskpool: ${response.statusText}`);
        }

        const data: BackendTaskPoolResponse = await response.json();
        return data.items.map(mapBackendTaskItemToFrontend);
    },

    /**
     * Sync plan doc to task pool
     */
    syncPlanDoc: async (planDocId: string): Promise<BackendSyncResponse> => {
        // Correct URL: /api/v2/taskpool/sync
        const response = await fetch(`${getApiBase()}/taskpool/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan_doc_id: planDocId }),
        });

        if (!response.ok) {
            throw new Error(`Failed to sync plan doc: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Update a todo item
     */
    updateTodo: async (
        todoId: number,
        updates: Partial<{
            content: string;
            color: string;
            state: string;
            date: string | null;
            expected_finished_at: string | null;
            parent_id: number | null;
            delay_days: number | null;
            delay_reason: string | null;
        }>
    ): Promise<BackendUpdateTodoResponse> => {
        const response = await fetch(`${getApiBase()}/todos/${todoId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        });

        if (!response.ok) {
            throw new Error(`Failed to update todo: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Create a new todo item
     */
    createTodo: async (
        data: {
            content: string;
            state?: string;
            date?: string | null;
            color?: string;
            link_to_goal_id?: string | null;
            plan_doc_id?: string | null;
            parent_id?: number | null;
            expected_finished_at?: string | null;
            pool_order_index?: number | null;
        }
    ): Promise<BackendCreateTodoResponse> => {
        const response = await fetch(`${getApiBase()}/todos`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            throw new Error(`Failed to create todo: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Delete a todo item
     */
    deleteTodo: async (todoId: number): Promise<void> => {
        const response = await fetch(`${getApiBase()}/todos/${todoId}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to delete todo: ${response.statusText}`);
        }
    }
};
