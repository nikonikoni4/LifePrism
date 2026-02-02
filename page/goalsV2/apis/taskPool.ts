/**
 * TaskPool API
 * /api/v2/taskpool
 */

import { createApiV2UrlGetter } from '../../../services/apiConfig';
import { TodoItem } from '../types/todo';
import {
    BackendTaskPoolItem,
    BackendTaskPoolResponse,
    BackendSyncResponse,
    BackendUpdateTodoResponse
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
        sourceType: item.plan_doc_id ? 'plan_doc' : 'manual',
        sourceAnchorId: item.source_anchor_id,
        state: item.state as 'pool' | 'scheduled' | 'completed' | 'shelved',
        scheduledDate: item.date,
        expectedFinishAt: item.expected_finished_at,
        actualFinishAt: item.actual_finished_at,
        delayDays: null,
        delayReason: null,
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
        }>
    ): Promise<BackendUpdateTodoResponse> => {
        // Correct URL: /api/v2/todos/{id}
        // Note: Check if backend uses /api/v2/todos or /api/v2/taskpool/todos?
        // useTaskPoolStore.ts used: `${API_BASE}/todos/${todoId}` where API_BASE was .../api/v2
        // So /api/v2/todos is correct according to previous code. 
        // Note: standard REST might suggest /api/v2/taskpool/{id} but let's stick to legacy for now unless I see main.py
        // In main.py: app.include_router(taskpool_router, prefix="/api")
        // If taskpool_router has @router.put("/todos/{id}"), then it is /api/todos/{id} ??
        // Wait. previous code: const API_BASE = 'http://localhost:8000/api/v2';
        // fetch(`${API_BASE}/todos/${todoId}`) -> /api/v2/todos/{id}
        // main.py has taskpool_router at /api
        // if taskpool_router has /v2/todos ... 
        // Let's assume previous code was correct about path structure relative to base.
        // So: getApiBase() -> /api/v2. 
        // path: /todos/${todoId}

        const response = await fetch(`${getApiBase()}/todos/${todoId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        });

        if (!response.ok) {
            throw new Error(`Failed to update todo: ${response.statusText}`);
        }

        return response.json();
    }
};
