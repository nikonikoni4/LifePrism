import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Calendar, Timer, Palette } from 'lucide-react';
import { viewBackground } from '../../shared/backgroundStyles';
import { useGoalPageContext } from '../../../context/GoalPageContext';
import { useTaskPoolStore } from '../../../hooks/useTaskPoolStore';
import { useGoalStore } from '../../../hooks/useGoalStore';
import { usePlanDocStore } from '../../../hooks/usePlanDocStore';
import { TodoItemTreeDetailed, TODO_COLORS, getRandomColor } from '@my-ui-kit/core';
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

/**
 * 子任务创建弹窗的状态
 */
interface AddChildModalState {
    isOpen: boolean;
    parentId: number | null;
    parentGoalId: string | null;
    parentPlanDocId: string | null;
}

/**
 * 子任务创建弹窗组件
 */
const AddChildModal: React.FC<{
    isOpen: boolean;
    parentId: number | null;
    defaultGoalId: string | null;
    defaultPlanDocId: string | null;
    defaultDate: string;
    onClose: () => void;
    onSubmit: (data: {
        content: string;
        color: string;
        scheduledDate: string;
        expectedFinishAt: string | null;
        parentId: number;
        goalId: string | null;
        planDocId: string | null;
    }) => void;
}> = ({ isOpen, parentId, defaultGoalId, defaultPlanDocId, defaultDate, onClose, onSubmit }) => {
    const [content, setContent] = useState('');
    const [color, setColor] = useState(() => getRandomColor());
    const [scheduledDate, setScheduledDate] = useState(defaultDate);
    const [expectedFinishAt, setExpectedFinishAt] = useState('');
    const [showColorPicker, setShowColorPicker] = useState(false);
    const colorPickerRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // 重置表单
    useEffect(() => {
        if (isOpen) {
            setContent('');
            setColor(getRandomColor());
            setScheduledDate(defaultDate);
            setExpectedFinishAt('');
            setShowColorPicker(false);
            // 聚焦输入框
            setTimeout(() => inputRef.current?.focus(), 100);
        }
    }, [isOpen, defaultDate]);

    // 点击外部关闭颜色选择器
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (colorPickerRef.current && !colorPickerRef.current.contains(event.target as Node)) {
                setShowColorPicker(false);
            }
        };
        if (showColorPicker) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [showColorPicker]);

    const handleSubmit = () => {
        if (!content.trim() || parentId === null) return;
        onSubmit({
            content: content.trim(),
            color,
            scheduledDate,
            expectedFinishAt: expectedFinishAt || null,
            parentId,
            goalId: defaultGoalId,
            planDocId: defaultPlanDocId,
        });
        onClose();
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && content.trim()) {
            handleSubmit();
        } else if (e.key === 'Escape') {
            onClose();
        }
    };

    if (!isOpen) return null;

    return createPortal(
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/30 backdrop-blur-sm"
                onClick={onClose}
            >
                <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: 10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: 10 }}
                    transition={{ duration: 0.15 }}
                    className="bg-white rounded-2xl shadow-xl border border-slate-200 w-[400px] overflow-hidden"
                    style={{ backgroundColor: color }}
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* 头部 */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200/60 bg-white/80">
                        <h3 className="text-sm font-semibold text-slate-700">添加子任务</h3>
                        <button
                            onClick={onClose}
                            className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                        >
                            <X size={16} />
                        </button>
                    </div>

                    {/* 内容 */}
                    <div className="p-4 space-y-4">
                        {/* 任务内容输入 */}
                        <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1.5">
                                任务内容 <span className="text-red-400">*</span>
                            </label>
                            <input
                                ref={inputRef}
                                type="text"
                                value={content}
                                onChange={(e) => setContent(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="输入任务内容..."
                                className="w-full px-3 py-2 text-sm text-slate-700 bg-white/80 border border-slate-200 rounded-lg outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 transition-all"
                            />
                        </div>

                        {/* 颜色选择 */}
                        <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1.5">
                                卡片颜色
                            </label>
                            <div className="relative" ref={colorPickerRef}>
                                <button
                                    onClick={() => setShowColorPicker(!showColorPicker)}
                                    className="flex items-center gap-2 px-3 py-2 bg-white/80 border border-slate-200 rounded-lg hover:border-slate-300 transition-colors"
                                >
                                    <div
                                        className="w-5 h-5 rounded-full border border-slate-300 shadow-sm"
                                        style={{ backgroundColor: color }}
                                    />
                                    <Palette size={14} className="text-slate-400" />
                                    <span className="text-xs text-slate-500">选择颜色</span>
                                </button>
                                {showColorPicker && (
                                    <div className="absolute left-0 top-full mt-2 p-2.5 bg-white rounded-xl shadow-xl border border-slate-200 flex gap-1.5 z-10">
                                        {TODO_COLORS.map((c) => (
                                            <button
                                                key={c}
                                                onClick={() => {
                                                    setColor(c);
                                                    setShowColorPicker(false);
                                                }}
                                                className={`w-6 h-6 rounded-full border border-slate-200 shadow-sm transition-transform hover:scale-110 ${color === c ? 'ring-2 ring-slate-400 scale-110' : ''}`}
                                                style={{ backgroundColor: c }}
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* 日期选择 */}
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="block text-xs font-medium text-slate-500 mb-1.5">
                                    <Calendar size={12} className="inline mr-1" />
                                    开始日期
                                </label>
                                <input
                                    type="date"
                                    value={scheduledDate}
                                    onChange={(e) => setScheduledDate(e.target.value)}
                                    className="w-full px-3 py-2 text-sm text-slate-700 bg-white/80 border border-slate-200 rounded-lg outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 transition-all"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-slate-500 mb-1.5">
                                    <Timer size={12} className="inline mr-1" />
                                    预期完成
                                </label>
                                <input
                                    type="date"
                                    value={expectedFinishAt}
                                    onChange={(e) => setExpectedFinishAt(e.target.value)}
                                    className="w-full px-3 py-2 text-sm text-slate-700 bg-white/80 border border-slate-200 rounded-lg outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 transition-all"
                                />
                            </div>
                        </div>
                    </div>

                    {/* 底部按钮 */}
                    <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-slate-200/60 bg-white/80">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                        >
                            取消
                        </button>
                        <button
                            onClick={handleSubmit}
                            disabled={!content.trim()}
                            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${content.trim()
                                    ? 'bg-blue-500 text-white hover:bg-blue-600'
                                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                                }`}
                        >
                            创建
                        </button>
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>,
        document.body
    );
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

    // 子任务创建弹窗状态
    const [addChildModal, setAddChildModal] = useState<AddChildModalState>({
        isOpen: false,
        parentId: null,
        parentGoalId: null,
        parentPlanDocId: null,
    });

    // 视图模式 state
    const [viewMode, setViewMode] = useState<'daily' | 'all_uncompleted'>('daily');

    // 格式化日期为 YYYY-MM-DD
    const dateStr = useMemo(() => {
        return selectedDate.toISOString().split('T')[0];
    }, [selectedDate]);

    // 过滤任务
    const dailyTasks = useMemo(() => {
        return tasks.filter(t => {
            // 基本条件：只要是当天任务，无论状态如何都显示
            const isTodayTask = t.scheduledDate === dateStr;

            if (viewMode === 'all_uncompleted') {
                // 如果是"全部未完成"模式：显示 (未完成的任务) OR (今天的任务)
                // 未完成定义: state != 'completed'
                // 注意：shelved 状态通常也不算"待办"，但这里用户只说了"未完成"。
                // 假设 shelved 也不显示除非是今天。
                // 若用户意图是 "Database backlog + Today"，则只要不是 completed 都可以算未完成。
                // 这里暂定: state != 'completed'
                return (t.state !== 'completed') || isTodayTask;
            } else {
                // 默认模式：仅显示当天的 scheduled 或 completed
                return isTodayTask && (t.state === 'scheduled' || t.state === 'completed');
            }
        });
    }, [tasks, dateStr, viewMode]);

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

    // 切换视图模式
    const handleToggleViewMode = useCallback(() => {
        setViewMode(prev => prev === 'daily' ? 'all_uncompleted' : 'daily');
    }, []);

    // 重置
    const handleReset = useCallback(() => {
        setExpandedIds(new Set());
        setSelectedTaskId(null);
        setViewMode('daily'); // 重置时也重置视图模式
    }, []);

    // 添加任务（顶级任务，通过输入框）
    const handleAddTask = useCallback((content: string) => {
        // 直接调用 addTask，由 store 发送到后端创建
        const newTask: TodoItem = {
            id: 0, // 临时 ID，后端会返回真实 ID
            content,
            parentId: null,
            goalId: inputGoalId,
            planDocId: inputPlanDocId,
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

    // 打开添加子任务弹窗
    const handleAddChild = useCallback((parentId: number) => {
        const parent = tasks.find(t => t.id === parentId);
        setAddChildModal({
            isOpen: true,
            parentId,
            parentGoalId: parent?.goalId || inputGoalId,
            parentPlanDocId: parent?.planDocId || inputPlanDocId,
        });
    }, [tasks, inputGoalId, inputPlanDocId]);

    // 关闭添加子任务弹窗
    const handleCloseAddChildModal = useCallback(() => {
        setAddChildModal({
            isOpen: false,
            parentId: null,
            parentGoalId: null,
            parentPlanDocId: null,
        });
    }, []);

    // 提交添加子任务
    const handleSubmitAddChild = useCallback((data: {
        content: string;
        color: string;
        scheduledDate: string;
        expectedFinishAt: string | null;
        parentId: number;
        goalId: string | null;
        planDocId: string | null;
    }) => {
        const siblings = tasks.filter(t => t.parentId === String(data.parentId));

        const newTask: TodoItem = {
            id: 0, // 临时 ID，后端会返回真实 ID
            content: data.content,
            parentId: String(data.parentId),
            goalId: data.goalId,
            planDocId: data.planDocId,
            sourceAnchorId: null,
            state: 'scheduled',
            scheduledDate: data.scheduledDate,
            expectedFinishAt: data.expectedFinishAt,
            actualFinishAt: null,
            delayDays: null,
            delayReason: null,
            color: data.color,
            orderIndex: siblings.length,
            poolOrderIndex: null,
        };

        addTask(newTask);
        // 展开父任务
        setExpandedIds(prev => new Set([...prev, data.parentId]));
    }, [tasks, addTask]);

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
                viewMode={viewMode}
                onToggleExpandAll={handleToggleExpandAll}
                onReset={handleReset}
                onToggleViewMode={handleToggleViewMode}
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

                            showDate={true}
                            onAddChild={handleAddChild}
                            getGoalName={getGoalName}
                            getPlanName={getPlanName}
                        />
                    </div>
                )}
            </div>

            {/* 添加子任务弹窗 */}
            <AddChildModal
                isOpen={addChildModal.isOpen}
                parentId={addChildModal.parentId}
                defaultGoalId={addChildModal.parentGoalId}
                defaultPlanDocId={addChildModal.parentPlanDocId}
                defaultDate={dateStr}
                onClose={handleCloseAddChildModal}
                onSubmit={handleSubmitAddChild}
            />
        </div>
    );
};
