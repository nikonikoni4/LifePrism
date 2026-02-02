/**
 * Task Pool Store - 任务池状态管理
 * 
 * 提供任务池的状态管理和 API 调用：
 * - 从后端获取任务列表
 * - 同步计划书任务
 * - 更新任务状态
 */

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { TodoItemType as TodoItem } from '@my-ui-kit/core';

// Re-export type for consumers
export type { TodoItem };

// API Base URL
const API_BASE = 'http://localhost:8000/api/v2';

// ============================================================================
// API Types
// ============================================================================

interface TaskPoolResponse {
    items: TaskPoolApiItem[];
}

interface TaskPoolApiItem {
    id: number;
    content: string;
    parent_id: number | null;
    link_to_goal_id: string | null;
    plan_doc_id: string | null;
    source_anchor_id: string | null;
    state: string;
    date: string | null;
    expected_finished_at: string | null;
    actual_finished_at: string | null;
    color: string;
    order_index: number;
    pool_order_index: number | null;
    created_at: string | null;
}

interface SyncResponse {
    created: number;
    updated: number;
    cleaned: number;
    total: number;
}

interface UpdateTodoResponse {
    item: TaskPoolApiItem;
    md_synced: boolean;
}

// ============================================================================
// API Functions
// ============================================================================

async function fetchTaskPool(
    goalId?: string | null,
    planDocId?: string | null,
    state?: string
): Promise<TodoItem[]> {
    const params = new URLSearchParams();
    if (goalId) params.append('goal_id', goalId);
    if (planDocId) params.append('plan_doc_id', planDocId);
    if (state) params.append('state', state);

    const url = `${API_BASE}/taskpool${params.toString() ? '?' + params.toString() : ''}`;
    const response = await fetch(url);

    if (!response.ok) {
        throw new Error(`Failed to fetch taskpool: ${response.statusText}`);
    }

    const data: TaskPoolResponse = await response.json();
    return data.items.map(apiItemToTodoItem);
}

async function syncPlanDocApi(planDocId: string): Promise<SyncResponse> {
    const response = await fetch(`${API_BASE}/taskpool/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_doc_id: planDocId }),
    });

    if (!response.ok) {
        throw new Error(`Failed to sync plan doc: ${response.statusText}`);
    }

    return response.json();
}

async function updateTodoApi(
    todoId: number,
    updates: Partial<{
        content: string;
        color: string;
        state: string;
        date: string | null;
        expected_finished_at: string | null;
        parent_id: number | null;
    }>
): Promise<UpdateTodoResponse> {
    const response = await fetch(`${API_BASE}/todos/${todoId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
    });

    if (!response.ok) {
        throw new Error(`Failed to update todo: ${response.statusText}`);
    }

    return response.json();
}

// ============================================================================
// Data Transform
// ============================================================================

function apiItemToTodoItem(item: TaskPoolApiItem): TodoItem {
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
// Store Context
// ============================================================================

interface TaskPoolStoreContextType {
    // State
    tasks: TodoItem[];
    loading: boolean;
    syncing: boolean;
    error: string | null;

    // Actions
    loadTasks: (goalId?: string | null, planDocId?: string | null, state?: string) => Promise<void>;
    syncFromPlanDoc: (planDocId: string) => Promise<SyncResponse | null>;
    addTask: (task: TodoItem) => void;
    updateTask: (id: number, updates: Partial<TodoItem>) => Promise<void>;
    deleteTask: (id: number) => void;
    moveTaskToPool: (id: number) => Promise<void>;
    scheduleTask: (id: number, date: string) => Promise<void>;
    completeTask: (id: number) => Promise<void>;
}

const TaskPoolStoreContext = createContext<TaskPoolStoreContextType | undefined>(undefined);

export const TaskPoolProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [tasks, setTasks] = useState<TodoItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Load tasks from API
    const loadTasks = useCallback(async (
        goalId?: string | null,
        planDocId?: string | null,
        state?: string
    ) => {
        setLoading(true);
        setError(null);
        try {
            const data = await fetchTaskPool(goalId, planDocId, state);
            setTasks(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load tasks');
            console.error('Failed to load tasks:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    // Sync plan doc
    const syncFromPlanDoc = useCallback(async (planDocId: string): Promise<SyncResponse | null> => {
        setSyncing(true);
        setError(null);
        try {
            const result = await syncPlanDocApi(planDocId);
            // Reload tasks after sync
            await loadTasks(null, planDocId);
            return result;
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to sync');
            console.error('Failed to sync plan doc:', err);
            return null;
        } finally {
            setSyncing(false);
        }
    }, [loadTasks]);

    // Add task (local only for now)
    const addTask = useCallback((task: TodoItem) => {
        setTasks(prev => [...prev, task]);
    }, []);

    // Update task via API
    const updateTask = useCallback(async (id: number, updates: Partial<TodoItem>) => {
        try {
            // Transform updates to API format
            const apiUpdates: Record<string, unknown> = {};
            if (updates.content !== undefined) apiUpdates.content = updates.content;
            if (updates.color !== undefined) apiUpdates.color = updates.color;
            if (updates.state !== undefined) apiUpdates.state = updates.state;
            if (updates.scheduledDate !== undefined) apiUpdates.date = updates.scheduledDate;
            if (updates.expectedFinishAt !== undefined) apiUpdates.expected_finished_at = updates.expectedFinishAt;

            const response = await updateTodoApi(id, apiUpdates);

            // Update local state with response
            const updatedItem = apiItemToTodoItem(response.item);
            setTasks(prev => prev.map(t => t.id === id ? { ...t, ...updatedItem } : t));
        } catch (err) {
            console.error('Failed to update task:', err);
            // Optimistic update fallback
            setTasks(prev => prev.map(t => t.id === id ? { ...t, ...updates } : t));
        }
    }, []);

    // Delete task (local only for now)
    const deleteTask = useCallback((id: number) => {
        setTasks(prev => prev.filter(t => t.id !== id));
    }, []);

    // Move task to pool
    const moveTaskToPool = useCallback(async (id: number) => {
        await updateTask(id, { state: 'pool', scheduledDate: null });
    }, [updateTask]);

    // Schedule task
    const scheduleTask = useCallback(async (id: number, date: string) => {
        await updateTask(id, { state: 'scheduled', scheduledDate: date });
    }, [updateTask]);

    // Complete task
    const completeTask = useCallback(async (id: number) => {
        await updateTask(id, { state: 'completed' });
    }, [updateTask]);

    // Initial load
    useEffect(() => {
        loadTasks();
    }, [loadTasks]);

    const value: TaskPoolStoreContextType = {
        tasks,
        loading,
        syncing,
        error,
        loadTasks,
        syncFromPlanDoc,
        addTask,
        updateTask,
        deleteTask,
        moveTaskToPool,
        scheduleTask,
        completeTask,
    };

    return React.createElement(
        TaskPoolStoreContext.Provider,
        { value },
        children
    );
};

export const useTaskPoolStore = () => {
    const context = useContext(TaskPoolStoreContext);
    if (!context) {
        throw new Error("useTaskPoolStore must be used within a TaskPoolProvider");
    }
    return context;
};
