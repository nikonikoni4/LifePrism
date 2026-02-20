import React, { useState, useMemo, useCallback, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { X, RefreshCw, Loader2, ChevronRight, ChevronDown, GripVertical } from 'lucide-react';
import { useTaskPoolStore } from '../../../hooks/useTaskPoolStore';
import { useGoalStore } from '../../../hooks/useGoalStore';
import { usePlanDocStore } from '../../../hooks/usePlanDocStore';
import { useGoalPageContext } from '../../../context/GoalPageContext';
import { DropdownMenu, DropdownItem } from '../../shared/components/DropdownMenu';
import { SyncDeleteConfirmDialog } from '../../shared/components/SyncDeleteConfirmDialog';
import { ConfirmDialog } from '../../shared/components/ConfirmDialog';
import { TodoItem as TodoItemComponent, DraggableItem, DroppablePoolRoot } from '@my-ui-kit/core';
import { viewBackground } from '../../shared/backgroundStyles';
import type { TaskPoolViewProps, TodoItem } from '../../../types';
import type { TodoDeletePreview } from '../../../types/backend';
import { todoApi } from '../../../apis/todoApi';
import { triggerPlanDocSave, triggerAllPlanDocRefreshes } from '../../../hooks/usePlanDocSaveHook';

// State border colors for left accent
const STATE_BORDER_COLORS: Record<string, string> = {
    pool: '#6366f1',      // indigo-500
    scheduled: '#8b5cf6', // violet-500
    completed: '#10b981', // emerald-500
    shelved: '#9ca3af'    // gray-400
};

// 状态筛选选项
type StateFilter = 'pool' | 'scheduled' | 'completed' | 'all';
const STATE_FILTER_OPTIONS: { value: StateFilter; label: string; color: string }[] = [
    { value: 'pool', label: '待处理', color: '#6366f1' },
    { value: 'scheduled', label: '已安排', color: '#8b5cf6' },
    { value: 'completed', label: '已完成', color: '#10b981' },
    { value: 'all', label: '全部', color: '#64748b' },
];

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

export const TaskPoolView: React.FC<TaskPoolViewProps> = ({
    disableInternalDnd = false
}) => {
    const {
        tasks,
        loading,
        syncing,
        updateTask,
        deleteTask,
        loadTasks
    } = useTaskPoolStore();
    const { goals } = useGoalStore();
    const { planDocs } = usePlanDocStore();
    const { selectedGoalId, setSelectedGoalId, selectedPlanDocId, setSelectedPlanDocId } = useGoalPageContext();

    // 默认筛选 pool 状态，减少初始渲染量
    const [stateFilter, setStateFilter] = useState<StateFilter>('pool');
    const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

    // 同步相关状态
    const [isSyncing, setIsSyncing] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [syncPreviewData, setSyncPreviewData] = useState<{
        toDelete: TodoDeletePreview[];
        created: number;
        updated: number;
    } | null>(null);
    const [showNoPlanDocAlert, setShowNoPlanDocAlert] = useState(false);
    const [syncResultMessage, setSyncResultMessage] = useState<string | null>(null);

    // 虚拟滚动容器引用
    const parentRef = useRef<HTMLDivElement>(null);

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

    // 筛选任务（构建树形结构）
    const filteredTasks = useMemo(() => {
        let filtered = tasks.filter(t => {
            // 状态筛选
            if (stateFilter === 'all') {
                return t.state === 'pool' || t.state === 'scheduled' || t.state === 'completed';
            }
            return t.state === stateFilter;
        });

        if (selectedGoalId) {
            filtered = filtered.filter(t => t.goalId === selectedGoalId);
        }

        if (selectedPlanDocId) {
            filtered = filtered.filter(t => t.planDocId === selectedPlanDocId);
        }

        return buildTaskTree(filtered);
    }, [tasks, selectedGoalId, selectedPlanDocId, stateFilter]);

    // 将树形结构展平为虚拟滚动列表（只包含可见节点）
    const flattenedTasks = useMemo(() => {
        const result: { task: TodoItem; depth: number }[] = [];

        const flatten = (items: TodoItem[], depth: number) => {
            items.forEach(task => {
                result.push({ task, depth });
                if (task.children && task.children.length > 0 && expandedIds.has(task.id)) {
                    flatten(task.children, depth + 1);
                }
            });
        };

        flatten(filteredTasks, 0);
        return result;
    }, [filteredTasks, expandedIds]);

    // 虚拟滚动配置
    const virtualizer = useVirtualizer({
        count: flattenedTasks.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 80, // 每个任务项估计高度（含间距）
        overscan: 5, // 预渲染额外的项目数
        measureElement: (element) => element.getBoundingClientRect().height, // 动态测量实际高度
    });

    // 清空筛选
    const clearFilters = () => {
        setSelectedGoalId(null);
        setSelectedPlanDocId(null);
    };

    // 同步按钮点击处理 - 新流程：先 dry_run 预检
    const handleSync = useCallback(async () => {
        if (!selectedPlanDocId) {
            setShowNoPlanDocAlert(true);
            return;
        }

        setIsSyncing(true);
        try {
            // 1. 先保存编辑器内容到 MD 文件，确保后端读取最新内容
            await triggerPlanDocSave(selectedPlanDocId);

            // 2. 执行 dry_run 预检
            const preview = await todoApi.syncPlanDoc(selectedPlanDocId, { dry_run: true });

            if (preview.to_delete && preview.to_delete.length > 0) {
                // 有待删除任务，显示确认对话框
                setSyncPreviewData({
                    toDelete: preview.to_delete,
                    created: preview.created,
                    updated: preview.updated,
                });
                setShowDeleteConfirm(true);
            } else {
                // 无待删除任务，直接执行同步
                const result = await todoApi.syncPlanDoc(selectedPlanDocId, { dry_run: false });
                await loadTasks();
                await triggerAllPlanDocRefreshes();
                setSyncResultMessage(`同步完成：新增 ${result.created}，更新 ${result.updated}`);
                setTimeout(() => setSyncResultMessage(null), 3000);
            }
        } catch (error) {
            console.error('Sync failed:', error);
            setSyncResultMessage('同步失败，请重试');
            setTimeout(() => setSyncResultMessage(null), 3000);
        } finally {
            setIsSyncing(false);
        }
    }, [selectedPlanDocId, loadTasks]);

    // 确认删除处理
    const handleConfirmDelete = useCallback(async () => {
        if (!selectedPlanDocId) return;

        setIsSyncing(true);
        try {
            const result = await todoApi.syncPlanDoc(selectedPlanDocId, { confirm_delete: true });
            await loadTasks();
            await triggerAllPlanDocRefreshes();
            setShowDeleteConfirm(false);
            setSyncPreviewData(null);
            setSyncResultMessage(`同步完成：新增 ${result.created}，更新 ${result.updated}，删除 ${result.deleted}`);
            setTimeout(() => setSyncResultMessage(null), 3000);
        } catch (error) {
            console.error('Sync with delete failed:', error);
            setSyncResultMessage('同步失败，请重试');
            setTimeout(() => setSyncResultMessage(null), 3000);
        } finally {
            setIsSyncing(false);
        }
    }, [selectedPlanDocId, loadTasks]);

    // 保留全部处理
    const handleKeepAll = useCallback(async () => {
        if (!selectedPlanDocId) return;

        setIsSyncing(true);
        try {
            const result = await todoApi.syncPlanDoc(selectedPlanDocId, { confirm_delete: false });
            await loadTasks();
            await triggerAllPlanDocRefreshes();
            setShowDeleteConfirm(false);
            setSyncPreviewData(null);
            setSyncResultMessage(`同步完成：新增 ${result.created}，更新 ${result.updated}（已保留 ${syncPreviewData?.toDelete.length || 0} 个任务）`);
            setTimeout(() => setSyncResultMessage(null), 3000);
        } catch (error) {
            console.error('Sync with keep failed:', error);
            setSyncResultMessage('同步失败，请重试');
            setTimeout(() => setSyncResultMessage(null), 3000);
        } finally {
            setIsSyncing(false);
        }
    }, [selectedPlanDocId, loadTasks, syncPreviewData]);

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
                            disabled={isSyncing || syncing}
                            className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-300 text-white text-sm font-medium transition-all shadow-sm hover:shadow-md flex items-center gap-2"
                        >
                            {(isSyncing || syncing) ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <RefreshCw size={14} />
                            )}
                            {(isSyncing || syncing) ? '同步中...' : '同步'}
                        </button>
                    )}

                    {/* 同步结果提示 */}
                    {syncResultMessage && (
                        <div className="px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-700">
                            {syncResultMessage}
                        </div>
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

                    {/* 状态筛选按钮组 */}
                    <div className="flex items-center gap-1 bg-slate-100 rounded-xl p-1">
                        {STATE_FILTER_OPTIONS.map(option => (
                            <button
                                key={option.value}
                                onClick={() => setStateFilter(option.value)}
                                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${stateFilter === option.value
                                    ? 'bg-white shadow-sm'
                                    : 'hover:bg-white/50'
                                    }`}
                                style={{
                                    color: stateFilter === option.value ? option.color : '#64748b'
                                }}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>

                    {/* 任务计数 */}
                    <div className="ml-auto text-xs font-bold text-slate-400 tracking-wider">
                        {loading ? (
                            <Loader2 size={14} className="animate-spin" />
                        ) : (
                            `${flattenedTasks.length} 个任务`
                        )}
                    </div>
                </div>
            </div>

            {/* 任务列表 - 虚拟滚动 */}
            <DroppablePoolRoot className="flex-1 overflow-hidden">
                <div
                    ref={parentRef}
                    className="h-full overflow-y-auto scrollbar-hide"
                >
                    <div className="p-6 min-h-full">
                        {loading ? (
                            <div className="h-full flex items-center justify-center min-h-[200px]">
                                <div className="text-center">
                                    <Loader2 size={32} className="animate-spin text-slate-400 mx-auto mb-4" />
                                    <div className="text-sm font-medium text-slate-400">加载中...</div>
                                </div>
                            </div>
                        ) : flattenedTasks.length === 0 ? (
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
                            <div
                                style={{
                                    height: `${virtualizer.getTotalSize()}px`,
                                    width: '100%',
                                    position: 'relative',
                                }}
                            >
                                {virtualizer.getVirtualItems().map(virtualRow => {
                                    const { task, depth } = flattenedTasks[virtualRow.index];
                                    const hasChildren = task.children && task.children.length > 0;
                                    const isExpanded = expandedIds.has(task.id);
                                    const isScheduled = task.state === 'scheduled';
                                    const isCompleted = task.state === 'completed';
                                    const taskClassName = `${isScheduled ? 'opacity-50' : ''} ${isCompleted ? 'opacity-60' : ''}`;

                                    return (
                                        <div
                                            key={task.id}
                                            data-index={virtualRow.index}
                                            ref={virtualizer.measureElement}
                                            style={{
                                                position: 'absolute',
                                                top: 0,
                                                left: 0,
                                                width: '100%',
                                                transform: `translateY(${virtualRow.start}px)`,
                                                paddingLeft: `${depth * 24}px`,
                                                paddingBottom: '8px', // 增加间距避免重叠
                                            }}
                                        >
                                            {disableInternalDnd ? (
                                                <DraggableItem
                                                    id={`pool-${task.id}`}
                                                    type="task"
                                                    source="task-pool"
                                                    data={task}
                                                    className={taskClassName}
                                                >
                                                    <div className="flex items-start gap-1">
                                                        {/* 展开/折叠按钮 - 放在卡片外部 */}
                                                        <button
                                                            onClick={() => hasChildren && handleToggleExpand(task.id)}
                                                            className={`flex-shrink-0 mt-3 w-5 h-5 flex items-center justify-center transition-all rounded ${hasChildren ? 'text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer' : 'text-transparent cursor-default'}`}
                                                        >
                                                            {hasChildren && (isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />)}
                                                        </button>
                                                        {/* 任务卡片 */}
                                                        <div
                                                            className="flex-1 bg-white rounded-xl border-y border-r border-slate-200/80 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
                                                            style={{ borderLeftWidth: '4px', borderLeftStyle: 'solid', borderLeftColor: STATE_BORDER_COLORS[task.state] || STATE_BORDER_COLORS.pool }}
                                                        >
                                                            <TodoItemComponent
                                                                item={task}
                                                                onUpdate={updateTask}
                                                                onDelete={deleteTask}
                                                                showDate={true}
                                                                disableSortable={true}
                                                                disableCardStyle={true}
                                                            />
                                                        </div>
                                                    </div>
                                                </DraggableItem>
                                            ) : (
                                                <div className="flex items-start gap-1">
                                                    {/* 展开/折叠按钮 - 放在卡片外部 */}
                                                    <button
                                                        onClick={() => hasChildren && handleToggleExpand(task.id)}
                                                        className={`flex-shrink-0 mt-3 w-5 h-5 flex items-center justify-center transition-all rounded ${hasChildren ? 'text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer' : 'text-transparent cursor-default'}`}
                                                    >
                                                        {hasChildren && (isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />)}
                                                    </button>
                                                    {/* 任务卡片 */}
                                                    <div
                                                        className={`flex-1 bg-white rounded-xl shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 ${taskClassName}`}
                                                        style={{
                                                            border: '1px solid rgba(226, 232, 240, 0.8)',
                                                            borderLeft: `4px solid ${STATE_BORDER_COLORS[task.state] || STATE_BORDER_COLORS.pool}`
                                                        }}
                                                    >
                                                        <TodoItemComponent
                                                            item={task}
                                                            onUpdate={updateTask}
                                                            onDelete={deleteTask}
                                                            disableCardStyle={true}
                                                        />
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>
            </DroppablePoolRoot>

            {/* 同步删除确认对话框 */}
            {syncPreviewData && (
                <SyncDeleteConfirmDialog
                    isOpen={showDeleteConfirm}
                    onClose={() => {
                        setShowDeleteConfirm(false);
                        setSyncPreviewData(null);
                    }}
                    onConfirmDelete={handleConfirmDelete}
                    onKeepAll={handleKeepAll}
                    toDelete={syncPreviewData.toDelete}
                    syncStats={{
                        created: syncPreviewData.created,
                        updated: syncPreviewData.updated,
                    }}
                    loading={isSyncing}
                />
            )}

            {/* 未选择计划书提示 */}
            <ConfirmDialog
                isOpen={showNoPlanDocAlert}
                onClose={() => setShowNoPlanDocAlert(false)}
                onConfirm={() => setShowNoPlanDocAlert(false)}
                title="提示"
                message="请先选择要同步的计划书"
                confirmText="确定"
                cancelText=""
            />
        </div>
    );
};
