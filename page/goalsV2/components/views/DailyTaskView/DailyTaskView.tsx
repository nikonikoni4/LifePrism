import React, { useState, useMemo, useCallback } from 'react';
import { viewBackground } from '../../shared/backgroundStyles';
import { useGoalPageContext } from '../../../context/GoalPageContext';
import { useTaskPoolStore } from '../../../hooks/useTaskPoolStore';
import { useGoalStore } from '../../../hooks/useGoalStore';
import { usePlanDocStore } from '../../../hooks/usePlanDocStore';
import { TodoItemTreeDetailed } from '@my-ui-kit/core';
import { TodoItem } from '../../../types/todo';
import { DailyTaskHeader, DailyTaskToolbar, TaskInputBox } from './components';

/**
 * 构建树形结构
 * 将扁平的任务列表转换为嵌套的树形结构
 */
const buildTaskTree = (tasks: TodoItem[]): TodoItem[] => {
    const taskMap = new Map<number, TodoItem>();
    const roots: TodoItem[] = [];

    // 首先创建所有任务的副本
    tasks.forEach(task => {
        taskMap.set(task.id, { ...task, children: [] });
    });

    // 构建树形结构
    tasks.forEach(task => {
        const taskWithChildren = taskMap.get(task.id)!;
        if (task.parentId) {
            const parentId = Number(task.parentId);
            const parent = taskMap.get(parentId);
            if (parent) {
                parent.children = parent.children || [];
                parent.children.push(taskWithChildren);
            } else {
                // 父任务不在当前列表中，作为根节点
                roots.push(taskWithChildren);
            }
        } else {
            roots.push(taskWithChildren);
        }
    });

    // 按 orderIndex 排序
    const sortByOrder = (items: TodoItem[]) => {
        items.sort((a, b) => a.orderIndex - b.orderIndex);
        items.forEach(item => {
            if (item.children && item.children.length > 0) {
                sortByOrder(item.children);
            }
        });
    };
    sortByOrder(roots);

    return roots;
};

/**
 * 收集所有任务ID（包括子任务）
 */
const collectAllIds = (tasks: TodoItem[]): Set<number> => {
    const ids = new Set<number>();
    const collect = (items: TodoItem[]) => {
        items.forEach(item => {
            ids.add(item.id);
            if (item.children && item.children.length > 0) {
                collect(item.children);
            }
        });
    };
    collect(tasks);
    return ids;
};

export const DailyTaskView: React.FC = () => {
    // Context
    const { selectedDate } = useGoalPageContext();

    // Stores
    const { tasks, addTask, updateTask, deleteTask } = useTaskPoolStore();
    const { goals } = useGoalStore();
    const { planDocs } = usePlanDocStore();

    // Local state
    const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
    const [inputGoalId, setInputGoalId] = useState<string | null>(null);
    const [inputPlanDocId, setInputPlanDocId] = useState<string | null>(null);
    const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);

    // 格式化日期为 YYYY-MM-DD
    const dateStr = useMemo(() => {
        return selectedDate.toISOString().split('T')[0];
    }, [selectedDate]);

    // 过滤当天的任务
    const dailyTasks = useMemo(() => {
        return tasks.filter(t =>
            t.scheduledDate === dateStr &&
            (t.state === 'scheduled' || t.state === 'completed')
        );
    }, [tasks, dateStr]);

    // 构建树形结构
    const taskTree = useMemo(() => buildTaskTree(dailyTasks), [dailyTasks]);

    // 统计数据
    const stats = useMemo(() => {
        const total = dailyTasks.length;
        const completed = dailyTasks.filter(t => t.state === 'completed').length;
        const overdue = dailyTasks.filter(t => {
            if (!t.expectedFinishAt || t.state === 'completed') return false;
            return new Date(t.expectedFinishAt) < new Date();
        }).length;
        return { total, completed, overdue };
    }, [dailyTasks]);

    // 是否全部展开
    const isAllExpanded = useMemo(() => {
        const allIds = collectAllIds(taskTree);
        if (allIds.size === 0) return false;
        return Array.from(allIds).every(id => expandedIds.has(id));
    }, [taskTree, expandedIds]);

    // 目标选项
    const goalOptions = useMemo(() => {
        return goals.map(g => ({ id: g.id, label: g.title }));
    }, [goals]);

    // 计划书选项（根据选中的目标过滤）
    const planDocOptions = useMemo(() => {
        const filtered = inputGoalId
            ? planDocs.filter(p => p.goalId === inputGoalId)
            : planDocs;
        return filtered.map(p => ({ id: p.id, label: p.id }));
    }, [planDocs, inputGoalId]);

    // 获取目标名称
    const getGoalName = useCallback((goalId: string | null) => {
        if (!goalId) return undefined;
        return goals.find(g => g.id === goalId)?.title;
    }, [goals]);

    // 获取计划书名称
    const getPlanName = useCallback((planDocId: string | null) => {
        if (!planDocId) return undefined;
        return planDocs.find(p => p.id === planDocId)?.id;
    }, [planDocs]);

    // 切换全部展开/折叠
    const handleToggleExpandAll = useCallback(() => {
        if (isAllExpanded) {
            setExpandedIds(new Set());
        } else {
            setExpandedIds(collectAllIds(taskTree));
        }
    }, [isAllExpanded, taskTree]);

    // 重置
    const handleReset = useCallback(() => {
        setExpandedIds(new Set());
        setSelectedTaskId(null);
    }, []);

    // 添加任务
    const handleAddTask = useCallback((content: string) => {
        const newTask: TodoItem = {
            id: Date.now(),
            content,
            parentId: null,
            goalId: inputGoalId,
            planDocId: inputPlanDocId,
            sourceType: 'manual',
            sourceAnchorId: null,
            state: 'scheduled',
            scheduledDate: dateStr,
            expectedFinishAt: null,
            actualFinishAt: null,
            delayDays: null,
            delayReason: null,
            color: '#FFFFFF',
            orderIndex: dailyTasks.length,
            poolOrderIndex: null,
        };
        addTask(newTask);
    }, [addTask, inputGoalId, inputPlanDocId, dateStr, dailyTasks.length]);

    // 添加子任务
    const handleAddChild = useCallback((parentId: number) => {
        const parent = tasks.find(t => t.id === parentId);
        const siblings = tasks.filter(t => t.parentId === String(parentId));

        const newTask: TodoItem = {
            id: Date.now(),
            content: '新子任务',
            parentId: String(parentId),
            goalId: parent?.goalId || inputGoalId,
            planDocId: parent?.planDocId || inputPlanDocId,
            sourceType: 'manual',
            sourceAnchorId: null,
            state: 'scheduled',
            scheduledDate: dateStr,
            expectedFinishAt: null,
            actualFinishAt: null,
            delayDays: null,
            delayReason: null,
            color: '#FFFFFF',
            orderIndex: siblings.length,
            poolOrderIndex: null,
        };

        addTask(newTask);
        // 展开父任务
        setExpandedIds(prev => new Set([...prev, parentId]));
    }, [tasks, addTask, inputGoalId, inputPlanDocId, dateStr]);

    // 更新任务
    const handleUpdateTask = useCallback((id: number, updates: Partial<TodoItem>) => {
        updateTask(id, updates);
    }, [updateTask]);

    // 删除任务
    const handleDeleteTask = useCallback((id: number) => {
        deleteTask(id);
    }, [deleteTask]);

    // 选择任务
    const handleSelectTask = useCallback((id: number) => {
        setSelectedTaskId(id);
    }, []);

    // 展开/折叠变化
    const handleExpandChange = useCallback((id: number, expanded: boolean) => {
        setExpandedIds(prev => {
            const next = new Set(prev);
            if (expanded) {
                next.add(id);
            } else {
                next.delete(id);
            }
            return next;
        });
    }, []);

    return (
        <div className="h-full flex flex-col" style={viewBackground.style}>
            {/* 头部状态栏 */}
            <DailyTaskHeader
                selectedDate={selectedDate}
                completedCount={stats.completed}
                totalCount={stats.total}
                overdueCount={stats.overdue}
            />

            {/* 操作工具栏 */}
            <DailyTaskToolbar
                isAllExpanded={isAllExpanded}
                onToggleExpandAll={handleToggleExpandAll}
                onReset={handleReset}
            />

            {/* 任务输入框 */}
            <TaskInputBox
                goals={goalOptions}
                planDocs={planDocOptions}
                selectedGoalId={inputGoalId}
                selectedPlanDocId={inputPlanDocId}
                onGoalChange={setInputGoalId}
                onPlanDocChange={setInputPlanDocId}
                onAddTask={handleAddTask}
            />

            {/* 任务列表区域 */}
            <div className="flex-1 overflow-y-auto p-6">
                {taskTree.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                        <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mb-4">
                            <span className="text-3xl">📋</span>
                        </div>
                        <h3 className="text-lg font-semibold text-slate-700 mb-2">暂无任务</h3>
                        <p className="text-sm text-slate-500 max-w-xs">
                            在上方输入框添加任务，或从任务池拖拽任务到日历
                        </p>
                    </div>
                ) : (
                    <div className="bg-white rounded-2xl shadow-sm border border-slate-200/60 p-4">
                        <TodoItemTreeDetailed
                            items={taskTree}
                            collapsible={true}
                            defaultExpandedIds={expandedIds}
                            sortable={false}
                            selectedId={selectedTaskId}
                            onUpdate={handleUpdateTask}
                            onDelete={handleDeleteTask}
                            onSelect={handleSelectTask}
                            onExpandChange={handleExpandChange}
                            showSource={true}
                            showDate={true}
                            onAddChild={handleAddChild}
                            getGoalName={getGoalName}
                            getPlanName={getPlanName}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};
