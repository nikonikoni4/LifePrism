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
import { todoApi, mapBackendTodoToFrontend } from '../apis/todoApi';
import { BackendSyncResponse } from '../types/backend';
import { triggerAllPlanDocSaves, triggerAllPlanDocRefreshes } from './usePlanDocSaveHook';

// Re-export type for consumers
export type { TodoItem };

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
    syncFromPlanDoc: (planDocId: string) => Promise<BackendSyncResponse | null>;
    addTask: (task: TodoItem) => Promise<void>;
    updateTask: (id: string, updates: Partial<TodoItem>) => Promise<void>;
    deleteTask: (id: string) => Promise<void>;
    moveTaskToPool: (id: string) => Promise<void>;
    scheduleTask: (id: string, date: string) => Promise<void>;
    completeTask: (id: string) => Promise<void>;
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
            const data = await todoApi.fetchTaskPool(goalId, planDocId, state);
            setTasks(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load tasks');
            console.error('Failed to load tasks:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    // Sync plan doc
    const syncFromPlanDoc = useCallback(async (planDocId: string): Promise<BackendSyncResponse | null> => {
        setSyncing(true);
        setError(null);
        try {
            const result = await todoApi.syncPlanDoc(planDocId);
            // Reload tasks after sync
            await loadTasks();
            return result;
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to sync');
            console.error('Failed to sync plan doc:', err);
            return null;
        } finally {
            setSyncing(false);
        }
    }, [loadTasks]);

    // Add task via API
    const addTask = useCallback(async (task: TodoItem) => {
        try {
            // 在添加 todo 前，先触发所有 PlanDoc 保存
            await triggerAllPlanDocSaves();

            // Transform to API format
            const apiData = {
                content: task.content,
                state: task.state,
                date: task.scheduledDate,
                color: task.color,
                link_to_goal_id: task.goalId,
                plan_doc_id: task.planDocId,
                parent_id: task.parentId,
                expected_finished_at: task.expectedFinishAt,
                pool_order_index: task.poolOrderIndex,
            };

            const response = await todoApi.createTodo(apiData);
            const createdItem = mapBackendTodoToFrontend(response.item);
            setTasks(prev => [...prev, createdItem]);
            // 刷新 PlanDoc 编辑器内容
            await triggerAllPlanDocRefreshes();
        } catch (err) {
            console.error('Failed to create task:', err);
            // Fallback: add locally with temp ID (for offline support)
            setTasks(prev => [...prev, task]);
        }
    }, []);

    // Update task via API
    const updateTask = useCallback(async (id: string, updates: Partial<TodoItem>) => {
        try {
            // 在更新 todo 前，先触发所有 PlanDoc 保存
            // 确保编辑器中的未保存内容先同步到 MD 文件
            await triggerAllPlanDocSaves();

            // Transform updates to API format
            const apiUpdates: Record<string, unknown> = {};
            if (updates.content !== undefined) apiUpdates.content = updates.content;
            if (updates.color !== undefined) apiUpdates.color = updates.color;
            if (updates.state !== undefined) apiUpdates.state = updates.state;
            if (updates.scheduledDate !== undefined) apiUpdates.date = updates.scheduledDate;
            if (updates.expectedFinishAt !== undefined) apiUpdates.expected_finished_at = updates.expectedFinishAt;
            // parentId needs to be number or null
            if (updates.parentId !== undefined) apiUpdates.parent_id = updates.parentId;

            const response = await todoApi.updateTodo(id, apiUpdates);

            // Update local state with response
            const updatedItem = mapBackendTodoToFrontend(response.item);
            setTasks(prev => prev.map(t => t.id === id ? { ...t, ...updatedItem } : t));
            // 刷新 PlanDoc 编辑器内容
            await triggerAllPlanDocRefreshes();
        } catch (err) {
            console.error('Failed to update task:', err);
            // Optimistic update fallback ? 
            // Ideally we should rollback or show error.
            // For now keeping simple optimistic update logic from before, 
            // but the original code had a mix: it did state update AFTER success, with a fallback catch that did optimistic?
            // Actually original code catch block:
            // setTasks(prev => prev.map(t => t.id === id ? { ...t, ...updates } : t));
            // This is strange ("optimistic update fallback" usually means "revert", or "apply optimistic before"). 
            // The comment said "Optimistic update fallback". I'll keep it to minimize behavior change.
            setTasks(prev => prev.map(t => t.id === id ? { ...t, ...updates } : t));
        }
    }, []);

    // Delete task via API
    const deleteTask = useCallback(async (id: string) => {
        try {
            // 在删除 todo 前，先触发所有 PlanDoc 保存
            await triggerAllPlanDocSaves();

            await todoApi.deleteTodo(id);
            setTasks(prev => prev.filter(t => t.id !== id));
            // 刷新 PlanDoc 编辑器内容
            await triggerAllPlanDocRefreshes();
        } catch (err) {
            console.error('Failed to delete task:', err);
            // Fallback: remove locally anyway
            setTasks(prev => prev.filter(t => t.id !== id));
        }
    }, []);

    // Move task to pool
    const moveTaskToPool = useCallback(async (id: string) => {
        await updateTask(id, { state: 'pool', scheduledDate: null });
    }, [updateTask]);

    // Schedule task
    const scheduleTask = useCallback(async (id: string, date: string) => {
        await updateTask(id, { state: 'scheduled', scheduledDate: date });
    }, [updateTask]);

    // Complete task
    const completeTask = useCallback(async (id: string) => {
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
