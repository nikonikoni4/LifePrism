import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { TodoItem } from '../../apps/goals/types/todo';
import { taskPoolApi } from '../../apps/goals/apis/taskPool';
import { goalsV2Api } from '../../apps/goals/apis/goal';
import { WaidAPI } from '../../floating/what-am-i-doing/api/waidApi';
import { flatListToTree, getDescendantIds, findItemById } from '../../my-ui-kit/ui-kit/todoItem/utils';

type StateFilter = 'all' | 'pool' | 'scheduled';

export const TodoPickerDialog: React.FC = () => {
    const [allTodos, setAllTodos] = useState<TodoItem[]>([]);
    const [goalNames, setGoalNames] = useState<Record<string, string>>({});
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
    const [search, setSearch] = useState('');
    const [stateFilter, setStateFilter] = useState<StateFilter>('all');
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    // 加载数据
    useEffect(() => {
        const load = async () => {
            try {
                const [todos, goals] = await Promise.all([
                    taskPoolApi.fetchTaskPool(null, null, undefined),
                    goalsV2Api.getGoals(),
                ]);
                // 过滤：未完成 + 未在浮窗中
                const available = todos.filter(
                    (t) => t.state !== 'completed' && t.waidOrder === null
                );
                setAllTodos(available);

                const nameMap: Record<string, string> = {};
                goals.forEach((g) => { nameMap[g.id] = g.title; });
                setGoalNames(nameMap);
            } catch (e) {
                console.error('[TodoPicker] Load failed:', e);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, []);

    // 过滤
    const filtered = useMemo(() => {
        return allTodos.filter((t) => {
            if (stateFilter === 'pool' && t.state !== 'pool') return false;
            if (stateFilter === 'scheduled' && t.state !== 'scheduled') return false;
            if (search && !t.content.toLowerCase().includes(search.toLowerCase())) return false;
            return true;
        });
    }, [allTodos, stateFilter, search]);

    // 按 goalId 分组
    const groups = useMemo(() => {
        const map = new Map<string, TodoItem[]>();
        filtered.forEach((t) => {
            const key = t.goalId || '__none__';
            if (!map.has(key)) map.set(key, []);
            map.get(key)!.push(t);
        });
        return map;
    }, [filtered]);

    // 构建树（用于父子联动）
    const tree = useMemo(() => flatListToTree(allTodos), [allTodos]);

    // 选择/取消（父子联动：从树中查找节点以获取 children）
    const toggleSelect = useCallback((item: TodoItem) => {
        const treeNode = findItemById(tree, item.id);
        const target = treeNode || item;
        setSelectedIds((prev) => {
            const next = new Set(prev);
            const descendants = getDescendantIds(target);
            if (next.has(item.id)) {
                descendants.forEach((id) => next.delete(id as number));
            } else {
                descendants.forEach((id) => next.add(id as number));
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
        { key: 'all', label: 'All' },
        { key: 'pool', label: 'Pool' },
        { key: 'scheduled', label: 'Scheduled' },
    ];

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
                <div className="flex gap-1">
                    {stateFilters.map((f) => (
                        <button
                            key={f.key}
                            onClick={() => setStateFilter(f.key)}
                            className={`px-2.5 py-1 rounded text-xs transition-colors ${
                                stateFilter === f.key
                                    ? 'bg-emerald-600 text-white'
                                    : 'bg-white/5 text-white/50 hover:text-white/70'
                            }`}
                        >
                            {f.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* 任务列表 */}
            <div className="flex-1 overflow-y-auto px-3 py-2">
                {loading ? (
                    <div className="flex items-center justify-center py-8 text-white/30 text-sm">Loading...</div>
                ) : filtered.length === 0 ? (
                    <div className="flex items-center justify-center py-8 text-white/30 text-sm">No tasks available</div>
                ) : (
                    Array.from(groups.entries()).map(([goalId, items]) => (
                        <div key={goalId} className="mb-3">
                            <div className="text-xs text-white/40 font-medium mb-1 px-1">
                                {goalId === '__none__' ? 'Uncategorized' : goalNames[goalId] || goalId}
                            </div>
                            <div className="space-y-0.5">
                                {items.map((item) => (
                                    <button
                                        key={item.id}
                                        onClick={() => toggleSelect(item)}
                                        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors ${
                                            selectedIds.has(item.id)
                                                ? 'bg-emerald-600/20'
                                                : 'hover:bg-white/5'
                                        }`}
                                    >
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
                                ))}
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
