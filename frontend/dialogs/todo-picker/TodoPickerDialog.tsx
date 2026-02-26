import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { TodoItem } from '../../apps/goals/types/todo';
import { PlanDoc } from '../../apps/goals/types/entities';
import { todoApi } from '../../apps/goals/apis/todoApi';
import { goalsV2Api } from '../../apps/goals/apis/goal';
import { planDocApi } from '../../apps/goals/apis/planDoc';
import { WaidAPI } from '../../floating/what-am-i-doing/api/waidApi';
import { getDescendantIds, findItemById } from '../../my-ui-kit/ui-kit/todoItem/utils';
import { getTodayStr } from '../../floating/what-am-i-doing/utils/formatTime';

type StateFilter = 'pool' | 'scheduled';
type TimeFilter = 'today' | 'all';

export const TodoPickerDialog: React.FC = () => {
    const [allTodos, setAllTodos] = useState<TodoItem[]>([]);
    const [goalNames, setGoalNames] = useState<Record<string, string>>({});
    const [planDocs, setPlanDocs] = useState<PlanDoc[]>([]);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [search, setSearch] = useState('');
    const [stateFilter, setStateFilter] = useState<StateFilter>('scheduled');
    const [timeFilter, setTimeFilter] = useState<TimeFilter>('today');
    const [planDocFilter, setPlanDocFilter] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());

    const toggleCollapse = useCallback((id: string) => {
        setCollapsedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }, []);

    // 加载数据
    useEffect(() => {
        const load = async () => {
            try {
                const [todos, goals, docs] = await Promise.all([
                    todoApi.fetchTaskPool(null, null, undefined),
                    goalsV2Api.getGoals(),
                    planDocApi.getPlanDocs(),
                ]);
                // 过滤：未完成 + 未在浮窗中
                const available = todos.filter(
                    (t) => t.state !== 'completed' && t.waidOrder === null
                );
                setAllTodos(available);

                const nameMap: Record<string, string> = {};
                goals.forEach((g) => { nameMap[g.id] = g.title; });
                setGoalNames(nameMap);

                // 只保留 active + completed 状态的 PlanDoc
                setPlanDocs(docs.filter((d) => d.status === 'active' || d.status === 'completed'));
            } catch (e) {
                console.error('[TodoPicker] Load failed:', e);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, []);

    // 过滤（保留匹配项的所有祖先节点以维持树结构）
    const filtered = useMemo(() => {
        const today = getTodayStr();

        // Step 1: 找到所有匹配过滤条件的 item ID
        const matchingIds = new Set<string>();
        allTodos.forEach((t) => {
            if (planDocFilter && t.planDocId !== planDocFilter) return;
            if (stateFilter === 'pool' && t.state !== 'pool') return;
            if (stateFilter === 'scheduled' && t.state !== 'scheduled') return;
            if (timeFilter === 'today') {
                if (t.state === 'pool') return;
                if (t.state === 'scheduled' && t.scheduledDate !== today) return;
            }
            if (search && !t.content.toLowerCase().includes(search.toLowerCase())) return;
            matchingIds.add(t.id);
        });

        // Step 2: 向上追溯所有祖先，确保树结构完整
        const idMap = new Map<string, TodoItem>();
        allTodos.forEach((t) => idMap.set(t.id, t));

        const keepIds = new Set<string>(matchingIds);
        matchingIds.forEach((id) => {
            let current = idMap.get(id);
            while (current?.parentId) {
                const parentId = current.parentId;
                if (keepIds.has(parentId)) break;
                keepIds.add(parentId);
                current = idMap.get(parentId);
            }
        });

        return allTodos.filter((t) => keepIds.has(t.id));
    }, [allTodos, stateFilter, timeFilter, planDocFilter, search]);

    // 构建树形结构（仿照 TaskPool 的 buildTaskTree，正确处理 parentId string→number 转换）
    const buildTaskTree = useCallback((tasks: TodoItem[]): TodoItem[] => {
        const taskMap = new Map<string, TodoItem>();
        const roots: TodoItem[] = [];

        tasks.forEach(task => {
            taskMap.set(task.id, { ...task, children: [] });
        });

        tasks.forEach(task => {
            const current = taskMap.get(task.id)!;
            if (task.parentId) {
                const parent = taskMap.get(task.parentId);
                if (parent) {
                    (parent.children as TodoItem[]).push(current);
                } else {
                    roots.push(current);
                }
            } else {
                roots.push(current);
            }
        });

        const sortItems = (items: TodoItem[]): TodoItem[] => {
            return items
                .sort((a, b) => (a.orderIndex ?? 0) - (b.orderIndex ?? 0))
                .map(item => ({
                    ...item,
                    children: item.children ? sortItems(item.children as TodoItem[]) : [],
                }));
        };
        return sortItems(roots);
    }, []);

    // 先建树，再按 goalId 分组根节点（避免分组拆散父子关系）
    const groups = useMemo(() => {
        const roots = buildTaskTree(filtered);
        const groupMap = new Map<string, TodoItem[]>();
        roots.forEach((root) => {
            const key = root.goalId || '__none__';
            if (!groupMap.has(key)) groupMap.set(key, []);
            groupMap.get(key)!.push(root);
        });
        return groupMap;
    }, [filtered, buildTaskTree]);

    // 构建树（用于父子联动选择）
    const tree = useMemo(() => buildTaskTree(allTodos), [allTodos, buildTaskTree]);

    // 选择/取消（父子联动：从树中查找节点以获取 children）
    const toggleSelect = useCallback((item: TodoItem) => {
        const treeNode = findItemById(tree, item.id);
        const target = treeNode || item;
        setSelectedIds((prev) => {
            const next = new Set(prev);
            const descendants = getDescendantIds(target);
            if (next.has(item.id)) {
                descendants.forEach((id) => next.delete(id as string));
            } else {
                descendants.forEach((id) => next.add(id as string));
            }
            return next;
        });
    }, [tree]);

    const handleClose = async () => {
        await window.electronAPI?.closeDialogWindow?.('todo-picker');
    };

    const handleConfirm = async () => {
        if (selectedIds.size === 0) return;
        setSubmitting(true);
        try {
            await WaidAPI.batchAddToWaid(Array.from(selectedIds));
            // 通知浮窗刷新
            await window.electronAPI?.sendToFloating?.('what-am-i-doing', 'waid-refresh', {});
            await handleClose();
        } catch (e) {
            console.error('[TodoPicker] Confirm failed:', e);
            setSubmitting(false);
        }
    };

    const stateFilters: { key: StateFilter; label: string }[] = [
        { key: 'scheduled', label: 'Scheduled' },
        { key: 'pool', label: 'Pool' },
    ];

    const timeFilters: { key: TimeFilter; label: string }[] = [
        { key: 'today', label: 'Today' },
        { key: 'all', label: 'All' },
    ];

    // 递归渲染树形 todo 列表
    const renderTodoTree = (items: TodoItem[], level: number = 0): React.ReactNode => {
        return items.map((item) => {
            const hasChildren = item.children && item.children.length > 0;
            const isCollapsed = collapsedIds.has(item.id);
            return (
                <div key={item.id}>
                    <button
                        onClick={() => toggleSelect(item)}
                        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors ${
                            selectedIds.has(item.id)
                                ? 'bg-emerald-600/20'
                                : 'hover:bg-white/5'
                        }`}
                        style={{ paddingLeft: `${8 + level * 20}px` }}
                    >
                        {/* 折叠箭头 */}
                        {hasChildren ? (
                            <span
                                onClick={(e) => { e.stopPropagation(); toggleCollapse(item.id); }}
                                className="flex-shrink-0 w-4 h-4 flex items-center justify-center text-white/40 hover:text-white/70 cursor-pointer"
                            >
                                <svg className={`w-3 h-3 transition-transform ${isCollapsed ? '' : 'rotate-90'}`} viewBox="0 0 12 12" fill="currentColor">
                                    <path d="M4 2l4 4-4 4V2z" />
                                </svg>
                            </span>
                        ) : (
                            <span className="flex-shrink-0 w-4" />
                        )}
                        {/* Checkbox */}
                        <div className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center transition-colors ${
                            selectedIds.has(item.id)
                                ? 'bg-emerald-500 border-emerald-500'
                                : 'border-white/30'
                        }`}>
                            {selectedIds.has(item.id) && (
                                <svg className="w-3 h-3 text-white" viewBox="0 0 12 12" fill="none">
                                    <path d="M2.5 6L5 8.5L9.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                            )}
                        </div>
                        <span
                            className="w-2 h-2 rounded-full flex-shrink-0"
                            style={{ backgroundColor: item.color || '#666' }}
                        />
                        <span className="text-sm text-white/80 truncate">{item.content}</span>
                        <span className="text-xs text-white/30 ml-auto flex-shrink-0">{item.state}</span>
                    </button>
                    {/* 子项 */}
                    {hasChildren && !isCollapsed && renderTodoTree(item.children as TodoItem[], level + 1)}
                </div>
            );
        });
    };

    return (
        <div className="h-screen flex flex-col bg-[#1e1e1e] text-white select-none overflow-hidden">
            {/* 标题栏 */}
            <div
                className="h-10 flex items-center justify-between px-4 bg-gradient-to-r from-emerald-600 to-teal-600 shrink-0"
                style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
            >
                <span className="text-sm font-medium text-white/90">Select Tasks</span>
                <button
                    onClick={handleClose}
                    className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-white/20 transition-colors"
                    style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                        <path d="M18 6L6 18M6 6l12 12" />
                    </svg>
                </button>
            </div>

            {/* 搜索 + 筛选 */}
            <div className="shrink-0 px-3 pt-3 pb-2 space-y-2 border-b border-white/5">
                <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search..."
                    className="w-full h-8 px-3 rounded bg-white/10 border border-white/10 focus:border-emerald-500/50 focus:outline-none text-sm text-white placeholder-white/30"
                />
                <div className="flex items-center gap-2 flex-wrap">
                    {/* PlanDoc 下拉 */}
                    <select
                        value={planDocFilter || ''}
                        onChange={(e) => setPlanDocFilter(e.target.value || null)}
                        className="h-7 px-2 rounded bg-[#2a2a2a] border border-white/10 text-xs text-white/70 focus:outline-none focus:border-emerald-500/50 cursor-pointer min-w-0 max-w-[130px] truncate flex-shrink"
                        style={{ colorScheme: 'dark' }}
                    >
                        <option value="">All PlanDocs</option>
                        {planDocs.map((d) => (
                            <option key={d.id} value={d.id}>{d.id}</option>
                        ))}
                    </select>
                    {/* 状态切换 */}
                    <div className="flex gap-0.5 bg-white/5 rounded p-0.5 flex-shrink-0">
                        {stateFilters.map((f) => (
                            <button
                                key={f.key}
                                onClick={() => setStateFilter(f.key)}
                                className={`px-2 py-0.5 rounded text-xs transition-colors ${
                                    stateFilter === f.key
                                        ? 'bg-emerald-600 text-white'
                                        : 'text-white/50 hover:text-white/70'
                                }`}
                            >
                                {f.label}
                            </button>
                        ))}
                    </div>
                    {/* 时间切换 */}
                    <div className="flex gap-0.5 bg-white/5 rounded p-0.5 flex-shrink-0">
                        {timeFilters.map((f) => (
                            <button
                                key={f.key}
                                onClick={() => setTimeFilter(f.key)}
                                className={`px-2 py-0.5 rounded text-xs transition-colors ${
                                    timeFilter === f.key
                                        ? 'bg-emerald-600 text-white'
                                        : 'text-white/50 hover:text-white/70'
                                }`}
                            >
                                {f.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* 任务列表 */}
            <div className="flex-1 overflow-y-auto px-3 py-2">
                {loading ? (
                    <div className="flex items-center justify-center py-8 text-white/30 text-sm">Loading...</div>
                ) : filtered.length === 0 ? (
                    <div className="flex items-center justify-center py-8 text-white/30 text-sm">No tasks available</div>
                ) : (
                    Array.from(groups.entries()).map(([goalId, treeItems]) => (
                        <div key={goalId} className="mb-3">
                            <div className="text-xs text-white/40 font-medium mb-1 px-1">
                                {goalId === '__none__' ? 'Uncategorized' : goalNames[goalId] || goalId}
                            </div>
                            <div className="space-y-0.5">
                                {renderTodoTree(treeItems)}
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* 底部按钮 */}
            <div className="shrink-0 px-3 py-2 border-t border-white/5 flex gap-2">
                <button
                    onClick={handleClose}
                    className="flex-1 py-2 rounded bg-white/5 hover:bg-white/10 text-white/70 text-sm transition-colors"
                >
                    Cancel
                </button>
                <button
                    onClick={handleConfirm}
                    disabled={selectedIds.size === 0 || submitting}
                    className={`flex-1 py-2 rounded text-sm font-medium transition-colors ${
                        selectedIds.size > 0 && !submitting
                            ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                            : 'bg-white/5 text-white/30 cursor-not-allowed'
                    }`}
                >
                    {submitting ? 'Adding...' : `Add ${selectedIds.size > 0 ? `(${selectedIds.size})` : ''}`}
                </button>
            </div>
        </div>
    );
};
