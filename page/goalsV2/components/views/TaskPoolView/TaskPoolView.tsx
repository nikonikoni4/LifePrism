import React, { useState, useMemo } from 'react';
import { X } from 'lucide-react';
import { DndContext, DragOverlay } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { useTaskPoolStore } from '../../../hooks/useTaskPoolStore';
import { useGoalStore } from '../../../hooks/useGoalStore';
import { usePlanDocStore } from '../../../hooks/usePlanDocStore';
import { DropdownMenu, DropdownItem } from '../../shared/components/DropdownMenu';
import { TodoItem as TodoItemComponent } from '../../shared/components/todoItem/TodoItem';
import { DraggableItem, DroppablePoolRoot } from '../../shared/components/dragDrop';
import { viewBackground } from '../../shared/backgroundStyles';
import type { TaskPoolViewProps, TodoItem } from './types';

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
    disableInternalDnd?: boolean;
}> = ({ tasks, onUpdate, onDelete, disableInternalDnd }) => {
    // 判断任务是否已安排（scheduled状态）
    const isScheduled = (task: TodoItem) => task.state === 'scheduled';

    return (
        <>
            {tasks.map(task => {
                const scheduled = isScheduled(task);

                return (
                    <div key={task.id}>
                        {disableInternalDnd ? (
                            <DraggableItem
                                id={`pool-${task.id}`}
                                type="task"
                                source="task-pool"
                                data={task}
                                className={scheduled ? 'opacity-50' : ''}
                            >
                                {/* 已安排任务的样式标记 */}
                                <div className="relative">
                                    {scheduled && (
                                        <div className="absolute -left-1 top-0 bottom-0 w-1 bg-violet-400 rounded-full" />
                                    )}
                                    <TodoItemComponent
                                        todo={task}
                                        onUpdate={onUpdate}
                                        onDelete={onDelete}
                                        showDate={true}
                                        disableSortable={true}
                                    />
                                </div>
                            </DraggableItem>
                        ) : (
                            <TodoItemComponent
                                todo={task}
                                onUpdate={onUpdate}
                                onDelete={onDelete}
                            />
                        )}

                        {/* 递归渲染子任务 - 子任务也继承父任务的scheduled样式 */}
                        {task.children && task.children.length > 0 && (
                            <div className={`ml-6 mt-1 ${scheduled ? 'opacity-50' : ''}`}>
                                <TaskTree
                                    tasks={task.children}
                                    onUpdate={onUpdate}
                                    onDelete={onDelete}
                                    disableInternalDnd={disableInternalDnd}
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
    const { tasks, updateTask, deleteTask } = useTaskPoolStore();
    const { goals } = useGoalStore();
    const { planDocs } = usePlanDocStore();

    const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);
    const [selectedPlanDocId, setSelectedPlanDocId] = useState<string | null>(null);

    // 筛选任务
    const filteredTasks = useMemo(() => {
        let filtered = tasks.filter(t => t.state === 'pool' || t.state === 'scheduled');

        if (selectedGoalId) {
            filtered = filtered.filter(t => t.goalId === selectedGoalId);
        }

        if (selectedPlanDocId) {
            filtered = filtered.filter(t => t.planDocId === selectedPlanDocId);
        }

        return buildTaskTree(filtered);
    }, [tasks, selectedGoalId, selectedPlanDocId]);

    // 清空筛选
    const clearFilters = () => {
        setSelectedGoalId(null);
        setSelectedPlanDocId(null);
    };

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
            label: doc.title,
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
                                {selectedPlanDoc ? selectedPlanDoc.title : '选择计划书'}
                            </button>
                        }
                        items={planDocDropdownItems}
                        width="w-64"
                    />

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

                    {/* 任务计数 */}
                    <div className="ml-auto text-xs font-bold text-slate-400 tracking-wider">
                        {filteredTasks.length} 个任务
                    </div>
                </div>
            </div>

            {/* 任务列表 - DroppablePoolRoot 需要覆盖整个滚动区域 */}
            <DroppablePoolRoot className="flex-1 overflow-y-auto scrollbar-hide">
                <div className="p-6 min-h-full">
                    {filteredTasks.length === 0 ? (
                        <div className="h-full flex items-center justify-center min-h-[200px]">
                            <div className="text-center">
                                <div className="text-6xl mb-4 opacity-20">📋</div>
                                <div className="text-sm font-medium text-slate-400">暂无任务</div>
                            </div>
                        </div>
                    ) : (
                        <TaskTree
                            tasks={filteredTasks}
                            onUpdate={updateTask}
                            onDelete={deleteTask}
                            disableInternalDnd={disableInternalDnd}
                        />
                    )}
                </div>
            </DroppablePoolRoot>
        </div>
    );
};
