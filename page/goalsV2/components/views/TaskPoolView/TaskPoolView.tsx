import React, { useState, useMemo, useCallback } from 'react';
import { X, RefreshCw, Check, Loader2, ChevronRight, ChevronDown } from 'lucide-react';
import { useTaskPoolStore } from '../../../hooks/useTaskPoolStore';
import { useGoalStore } from '../../../hooks/useGoalStore';
import { usePlanDocStore } from '../../../hooks/usePlanDocStore';
import { useGoalPageContext } from '../../../context/GoalPageContext';
import { DropdownMenu, DropdownItem } from '../../shared/components/DropdownMenu';
import { TodoItem as TodoItemComponent, DraggableItem, DroppablePoolRoot } from '@my-ui-kit/core';
import { viewBackground } from '../../shared/backgroundStyles';
import type { TaskPoolViewProps, TodoItem } from '../../../types';

// State border colors for left accent
const STATE_BORDER_COLORS: Record<string, string> = {
    pool: '#6366f1',      // indigo-500
    scheduled: '#8b5cf6', // violet-500
    completed: '#10b981', // emerald-500
    shelved: '#9ca3af'    // gray-400
};

/**
 * 构建任务树：将扁平列表转换为树形结构
 */
const buildTaskTree = (tasks: TodoItem[]): TodoItem[] => {
    const taskMap = new Map<number, TodoItem>();
    const roots: TodoItem[] = [];

    // 先创建所有节点的副本
    tasks.forEach(task => {
        taskMap.set(task.id, { ...task, children: [] });
    });

    // 构建父子关系
    taskMap.forEach(task => {
        if (task.parentId) {
            const parent = taskMap.get(Number(task.parentId));
            if (parent) {
                parent.children = parent.children || [];
                parent.children.push(task);
            } else {
                roots.push(task);
            }
        } else {
            roots.push(task);
        }
    });

    return roots;
};

/**
 * 递归渲染任务树
 */
const TaskTree: React.FC<{
    tasks: TodoItem[];
    onUpdate: (id: number, updates: Partial<TodoItem>) => void;
    onDelete: (id: number) => void;
    onComplete: (id: number) => void;
    disableInternalDnd?: boolean;
    expandedIds: Set<number>;
    onToggleExpand: (id: number) => void;
}> = ({ tasks, onUpdate, onDelete, onComplete, disableInternalDnd, expandedIds, onToggleExpand }) => {
    // 判断任务状态
    const isScheduled = (task: TodoItem) => task.state === 'scheduled';
    const isCompleted = (task: TodoItem) => task.state === 'completed';

    return (
        <>
            {tasks.map(task => {
                const scheduled = isScheduled(task);
                const completed = isCompleted(task);
                const hasChildren = task.children && task.children.length > 0;
                const isExpanded = expandedIds.has(task.id);

                // 任务样式类名
                const taskClassName = `${scheduled ? 'opacity-50' : ''} ${completed ? 'opacity-60' : ''}`;

                return (
                    <div key={task.id} className="mb-2">
                        {disableInternalDnd ? (
                            <DraggableItem
                                id={`pool-${task.id}`}
                                type="task"
                                source="task-pool"
                                data={task}
                                className={taskClassName}
                            >
                                <div
                                    className="flex items-stretch bg-white rounded-xl border-y border-r border-slate-200/80 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
                                    style={{ borderLeftWidth: '4px', borderLeftStyle: 'solid', borderLeftColor: '#6366f1' }}
                                >
                                    <div className="flex-1 flex items-start gap-2">
                                        {/* 展开/折叠按钮 */}
                                        <button
                                            onClick={() => hasChildren && onToggleExpand(task.id)}
                                            className={`flex-shrink-0 mt-3 ml-2 w-5 h-5 flex items-center justify-center transition-all rounded ${hasChildren ? 'text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer' : 'text-transparent cursor-default'
                                                }`}
                                        >
                                            {hasChildren && (isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />)}
                                        </button>

                                        <div className="flex-1 min-w-0">
                                            <TodoItemComponent
                                                item={task}
                                                onUpdate={onUpdate}
                                                onDelete={onDelete}
                                                showDate={true}
                                                disableSortable={true}
                                                disableCardStyle={true}
                                            />
                                        </div>
                                    </div>
                                </div>
                            </DraggableItem>
                        ) : (
                            <div
                                className={`flex items-stretch bg-white rounded-xl shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 ${taskClassName}`}
                                style={{
                                    border: '1px solid rgba(226, 232, 240, 0.8)',
                                    borderLeft: `4px solid ${STATE_BORDER_COLORS[task.state] || STATE_BORDER_COLORS.pool}`
                                }}
                            >
                                <div className="flex-1 flex items-start gap-2">
                                    {/* 展开/折叠按钮 */}
                                    <button
                                        onClick={() => hasChildren && onToggleExpand(task.id)}
                                        className={`flex-shrink-0 mt-3 ml-2 w-5 h-5 flex items-center justify-center transition-all rounded ${hasChildren ? 'text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer' : 'text-transparent cursor-default'
                                            }`}
                                    >
                                        {hasChildren && (isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />)}
                                    </button>

                                    <div className="flex-1 min-w-0">
                                        <TodoItemComponent
                                            item={task}
                                            onUpdate={onUpdate}
                                            onDelete={onDelete}
                                            disableCardStyle={true}
                                        />
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* 递归渲染子任务 */}
                        {hasChildren && isExpanded && (
                            <div className={`ml-6 mt-2 pl-4 border-l-2 border-dashed border-slate-200 ${scheduled || completed ? 'opacity-70' : ''}`}>
                                <TaskTree
                                    tasks={task.children!}
                                    onUpdate={onUpdate}
                                    onDelete={onDelete}
                                    onComplete={onComplete}
                                    disableInternalDnd={disableInternalDnd}
                                    expandedIds={expandedIds}
                                    onToggleExpand={onToggleExpand}
                                />
                            </div>
                        )}
                    </div>
                );
            })}
        </>
    );
};

export const TaskPoolView: React.FC<TaskPoolViewProps> = ({
    disableInternalDnd = false
}) => {
    const {
        tasks,
        loading,
        syncing,
        updateTask,
        deleteTask,
        syncFromPlanDoc,
        completeTask,
        loadTasks
    } = useTaskPoolStore();
    const { goals } = useGoalStore();
    const { planDocs } = usePlanDocStore();
    const { selectedGoalId, setSelectedGoalId, selectedPlanDocId, setSelectedPlanDocId } = useGoalPageContext();

    const [showCompleted, setShowCompleted] = useState(true);
    const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

    // 切换展开/折叠
    const handleToggleExpand = useCallback((id: number) => {
        setExpandedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    }, []);

    // 筛选任务
    const filteredTasks = useMemo(() => {
        let filtered = tasks.filter(t => {
            // 基础状态筛选
            if (showCompleted) {
                return t.state === 'pool' || t.state === 'scheduled' || t.state === 'completed';
            }
            return t.state === 'pool' || t.state === 'scheduled';
        });

        if (selectedGoalId) {
            filtered = filtered.filter(t => t.goalId === selectedGoalId);
        }

        if (selectedPlanDocId) {
            filtered = filtered.filter(t => t.planDocId === selectedPlanDocId);
        }

        return buildTaskTree(filtered);
    }, [tasks, selectedGoalId, selectedPlanDocId, showCompleted]);

    // 清空筛选
    const clearFilters = () => {
        setSelectedGoalId(null);
        setSelectedPlanDocId(null);
    };

    // 同步按钮点击处理
    const handleSync = useCallback(async () => {
        if (selectedPlanDocId) {
            await syncFromPlanDoc(selectedPlanDocId);
        } else {
            // 如果没有选择计划书，提示用户
            alert('请先选择要同步的计划书');
        }
    }, [selectedPlanDocId, syncFromPlanDoc]);

    // 刷新任务列表
    const handleRefresh = useCallback(async () => {
        await loadTasks(selectedGoalId, selectedPlanDocId);
    }, [loadTasks, selectedGoalId, selectedPlanDocId]);

    // 构建下拉菜单项
    const goalDropdownItems: DropdownItem[] = goals.map(goal => ({
        id: goal.id,
        label: goal.title,
        onClick: () => setSelectedGoalId(goal.id),
    }));

    const planDocDropdownItems: DropdownItem[] = useMemo(() => {
        const docs = selectedGoalId
            ? planDocs.filter(doc => doc.goalId === selectedGoalId)
            : planDocs;

        return docs.map(doc => ({
            id: doc.id,
            label: doc.id,
            onClick: () => setSelectedPlanDocId(doc.id),
        }));
    }, [planDocs, selectedGoalId]);

    const selectedGoal = goals.find(g => g.id === selectedGoalId);
    const selectedPlanDoc = planDocs.find(p => p.id === selectedPlanDocId);

    return (
        <div className={`h-full flex flex-col ${viewBackground.className}`} style={viewBackground.style}>
            {/* 筛选栏 */}
            <div className="flex-shrink-0 p-6 border-b border-slate-200/60 bg-white/50 backdrop-blur-sm">
                <div className="flex items-center gap-3 flex-wrap">
                    {/* Goal 筛选 */}
                    <DropdownMenu
                        trigger={
                            <button className="px-4 py-2 rounded-xl bg-white border border-slate-200 hover:border-indigo-300 text-sm font-medium text-slate-700 hover:text-indigo-600 transition-all shadow-sm hover:shadow-md">
                                {selectedGoal ? selectedGoal.title : '选择目标'}
                            </button>
                        }
                        items={goalDropdownItems}
                        width="w-64"
                    />

                    {/* 计划书筛选 */}
                    <DropdownMenu
                        trigger={
                            <button className="px-4 py-2 rounded-xl bg-white border border-slate-200 hover:border-violet-300 text-sm font-medium text-slate-700 hover:text-violet-600 transition-all shadow-sm hover:shadow-md">
                                {selectedPlanDoc ? selectedPlanDoc.id : '选择计划书'}
                            </button>
                        }
                        items={planDocDropdownItems}
                        width="w-64"
                    />

                    {/* 同步按钮 */}
                    {selectedPlanDocId && (
                        <button
                            onClick={handleSync}
                            disabled={syncing}
                            className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-300 text-white text-sm font-medium transition-all shadow-sm hover:shadow-md flex items-center gap-2"
                        >
                            {syncing ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <RefreshCw size={14} />
                            )}
                            {syncing ? '同步中...' : '同步'}
                        </button>
                    )}

                    {/* 清空筛选按钮 */}
                    {(selectedGoalId || selectedPlanDocId) && (
                        <button
                            onClick={clearFilters}
                            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-sm font-medium text-slate-600 hover:text-slate-800 transition-all flex items-center gap-2"
                        >
                            <X size={14} />
                            清空筛选
                        </button>
                    )}

                    {/* 显示已完成任务开关 */}
                    <button
                        onClick={() => setShowCompleted(!showCompleted)}
                        className={`px-4 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-2 ${showCompleted
                                ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                            }`}
                    >
                        <Check size={14} />
                        {showCompleted ? '隐藏已完成' : '显示已完成'}
                    </button>

                    {/* 任务计数 */}
                    <div className="ml-auto text-xs font-bold text-slate-400 tracking-wider">
                        {loading ? (
                            <Loader2 size={14} className="animate-spin" />
                        ) : (
                            `${filteredTasks.length} 个任务`
                        )}
                    </div>
                </div>
            </div>

            {/* 任务列表 */}
            <DroppablePoolRoot className="flex-1 overflow-y-auto scrollbar-hide">
                <div className="p-6 min-h-full">
                    {loading ? (
                        <div className="h-full flex items-center justify-center min-h-[200px]">
                            <div className="text-center">
                                <Loader2 size={32} className="animate-spin text-slate-400 mx-auto mb-4" />
                                <div className="text-sm font-medium text-slate-400">加载中...</div>
                            </div>
                        </div>
                    ) : filteredTasks.length === 0 ? (
                        <div className="h-full flex items-center justify-center min-h-[200px]">
                            <div className="text-center">
                                <div className="text-6xl mb-4 opacity-20">📋</div>
                                <div className="text-sm font-medium text-slate-400">暂无任务</div>
                                {selectedPlanDocId && (
                                    <button
                                        onClick={handleSync}
                                        className="mt-4 px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium transition-all"
                                    >
                                        从计划书同步任务
                                    </button>
                                )}
                            </div>
                        </div>
                    ) : (
                        <TaskTree
                            tasks={filteredTasks}
                            onUpdate={updateTask}
                            onDelete={deleteTask}
                            onComplete={completeTask}
                            disableInternalDnd={disableInternalDnd}
                            expandedIds={expandedIds}
                            onToggleExpand={handleToggleExpand}
                        />
                    )}
                </div>
            </DroppablePoolRoot>
        </div>
    );
};
