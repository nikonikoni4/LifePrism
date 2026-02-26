import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
    DndContext,
    closestCenter,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent,
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { TodoItem } from '../../apps/goals/types/todo';
import { WaidAPI } from './api/waidApi';
import { safeUpdateTodo, safeCreateTodo } from './api/safeTodoOps';
import { mapBackendTodoToFrontend } from '../../apps/goals/apis/todoApi';
import { useWaidTimer } from './hooks/useWaidTimer';
import { WaidTodoItem } from './components/WaidTodoItem';
import { AddTaskMenu } from './components/AddTaskMenu';
import { getTodayStr } from './utils/formatTime';
import { flatListToTree, treeToFlatList } from '../../my-ui-kit/ui-kit/todoItem/utils';

const TITLE_BAR_HEIGHT = 32;
const ADD_BUTTON_HEIGHT = 40;
const PADDING = 16;
const MAX_WINDOW_HEIGHT = 600;

export const WhatAmIDoingFloat: React.FC = () => {
    const [todos, setTodos] = useState<TodoItem[]>([]);
    const [accumulated, setAccumulated] = useState<Record<string, number>>({});
    const [loading, setLoading] = useState(true);
    const [isCreating, setIsCreating] = useState(false);
    const [newTaskContent, setNewTaskContent] = useState('');
    const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
    const contentRef = useRef<HTMLDivElement>(null);
    const newTaskInputRef = useRef<HTMLInputElement>(null);

    // dnd-kit sensors
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
    );

    const toggleCollapse = useCallback((id: string) => {
        setCollapsedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }, []);

    // 计时器
    const handleDurationAdded = useCallback((todoId: string, minutes: number) => {
        setAccumulated((prev) => ({
            ...prev,
            [todoId]: (prev[todoId] || 0) + minutes,
        }));
    }, []);

    const { activeTimerId, elapsed, startTimer, stopTimer, updateActiveTodoContent } = useWaidTimer(handleDurationAdded);

    // 加载数据
    const refreshWaidTodos = useCallback(async () => {
        try {
            const data = await WaidAPI.getWaidTodos();
            setTodos(data);
            if (data.length > 0) {
                const ids = data.map((t) => t.id);
                const durations = await WaidAPI.batchGetDuration(ids, getTodayStr());
                setAccumulated(durations);
            } else {
                setAccumulated({});
            }
        } catch (e) {
            console.error('[WAID] Failed to refresh:', e);
        }
    }, []);

    // 初始化
    useEffect(() => {
        refreshWaidTodos().finally(() => setLoading(false));
    }, [refreshWaidTodos]);

    // 监听来自主窗口/对话框的刷新消息
    useEffect(() => {
        if (!window.electronAPI?.onMessage) return;
        const callback = () => { refreshWaidTodos(); };
        const handler = window.electronAPI.onMessage('waid-refresh', callback);
        return () => {
            window.electronAPI?.removeMessageListener?.('waid-refresh', handler);
        };
    }, [refreshWaidTodos]);

    // 窗口自适应高度
    useEffect(() => {
        if (!contentRef.current) return;
        const observer = new ResizeObserver((entries) => {
            const contentHeight = entries[0].contentRect.height;
            const totalHeight = contentHeight + TITLE_BAR_HEIGHT + ADD_BUTTON_HEIGHT + PADDING;
            const clampedHeight = Math.max(120, Math.min(totalHeight, MAX_WINDOW_HEIGHT));
            window.electronAPI?.resizeFloatingWindow?.('what-am-i-doing', {
                height: Math.round(clampedHeight),
            });
        });
        observer.observe(contentRef.current);
        return () => observer.disconnect();
    }, []);

    // 操作回调
    const handleToggleComplete = useCallback(async (id: string) => {
        const todo = todos.find((t) => t.id === id);
        if (!todo) return;
        const newState = todo.state === 'completed' ? 'pool' : 'completed';
        try {
            await safeUpdateTodo(id, { state: newState });
            if (newState === 'completed') {
                if (activeTimerId === id) await stopTimer();
                await WaidAPI.removeFromWaid(id);
            }
            await refreshWaidTodos();
        } catch (e) {
            console.error('[WAID] Toggle complete failed:', e);
        }
    }, [todos, activeTimerId, stopTimer, refreshWaidTodos]);

    const handleContentChange = useCallback(async (id: string, content: string) => {
        try {
            await safeUpdateTodo(id, { content });
            setTodos((prev) => prev.map((t) => (t.id === id ? { ...t, content } : t)));
            updateActiveTodoContent(id, content);
        } catch (e) {
            console.error('[WAID] Content change failed:', e);
        }
    }, [updateActiveTodoContent]);

    const handleRemove = useCallback(async (id: string) => {
        try {
            if (activeTimerId === id) await stopTimer();
            await WaidAPI.removeFromWaid(id);
            await refreshWaidTodos();
        } catch (e) {
            console.error('[WAID] Remove failed:', e);
        }
    }, [activeTimerId, stopTimer, refreshWaidTodos]);

    const handleSelectExisting = useCallback(async () => {
        if (window.electronAPI?.openDialogWindow) {
            await window.electronAPI.openDialogWindow('todo-picker');
        }
    }, []);

    const handleCreateNew = useCallback(() => {
        setIsCreating(true);
        setNewTaskContent('');
        setTimeout(() => newTaskInputRef.current?.focus(), 50);
    }, []);

    const handleNewTaskConfirm = useCallback(async () => {
        const content = newTaskContent.trim();
        setIsCreating(false);
        setNewTaskContent('');
        if (!content) return;
        try {
            const result = await safeCreateTodo({ content, state: 'pool' });
            const newTodo = mapBackendTodoToFrontend(result.item);
            await WaidAPI.addToWaid(newTodo.id);
            await refreshWaidTodos();
        } catch (e) {
            console.error('[WAID] Create new task failed:', e);
        }
    }, [newTaskContent, refreshWaidTodos]);

    // 构建树形结构（用 waidOrder 覆盖 orderIndex 以确保排序一致）
    const tree = useMemo(() => {
        const todosForTree = todos.map((t) => ({
            ...t,
            orderIndex: t.waidOrder ?? t.orderIndex,
        }));
        return flatListToTree(todosForTree);
    }, [todos]);

    // 拖拽结束处理
    const handleDragEnd = useCallback(async (event: DragEndEvent) => {
        const { active, over } = event;
        if (!over || active.id === over.id) return;

        // 找到 active 和 over 所在的同级列表
        const findSiblings = (items: TodoItem[]): TodoItem[] | null => {
            const ids = items.map((i) => i.id);
            if (ids.includes(active.id as string) && ids.includes(over.id as string)) {
                return items;
            }
            for (const item of items) {
                if (item.children && item.children.length > 0) {
                    const found = findSiblings(item.children as TodoItem[]);
                    if (found) return found;
                }
            }
            return null;
        };

        const siblings = findSiblings(tree);
        if (!siblings) return;

        const oldIndex = siblings.findIndex((i) => i.id === active.id);
        const newIndex = siblings.findIndex((i) => i.id === over.id);
        if (oldIndex === -1 || newIndex === -1) return;

        // 在同级列表中移动
        const reordered = arrayMove(siblings, oldIndex, newIndex);
        // 替换 tree 中对应的同级列表，然后 DFS 扁平化
        const replaceInTree = (items: TodoItem[]): TodoItem[] => {
            if (items === siblings) return reordered;
            return items.map((item) => ({
                ...item,
                children: item.children && item.children.length > 0
                    ? replaceInTree(item.children as TodoItem[])
                    : item.children,
            }));
        };
        const newTree = replaceInTree(tree);
        const flatIds = treeToFlatList(newTree).map((t) => t.id);

        // 乐观更新本地状态（同步更新 waidOrder 以确保 flatListToTree 排序正确）
        const reorderedTodos = flatIds
            .map((id, idx) => {
                const t = todos.find((t) => t.id === id);
                return t ? { ...t, waidOrder: idx } : null;
            })
            .filter(Boolean) as TodoItem[];
        setTodos(reorderedTodos);

        // 持久化
        try {
            await WaidAPI.reorderWaid(flatIds);
        } catch (e) {
            console.error('[WAID] Reorder failed:', e);
            await refreshWaidTodos();
        }
    }, [tree, todos, refreshWaidTodos]);

    // 递归渲染 todo 树
    const renderTodoTree = (items: TodoItem[], level: number = 0): React.ReactNode => {
        const ids = items.map((i) => i.id);
        return (
            <SortableContext items={ids} strategy={verticalListSortingStrategy}>
                {items.map((item) => {
                    const hasChildren = !!(item.children && item.children.length > 0);
                    const isCollapsed = collapsedIds.has(item.id);
                    return (
                        <WaidTodoItem
                            key={item.id}
                            item={item}
                            level={level}
                            isTimerActive={activeTimerId === item.id}
                            elapsed={activeTimerId === item.id ? elapsed : 0}
                            accumulatedMinutes={accumulated[item.id] || 0}
                            collapsed={isCollapsed}
                            hasChildren={hasChildren}
                            onToggleComplete={handleToggleComplete}
                            onStartTimer={startTimer}
                            onStopTimer={stopTimer}
                            onContentChange={handleContentChange}
                            onRemove={handleRemove}
                            onToggleCollapse={toggleCollapse}
                        >
                            {hasChildren && !isCollapsed
                                ? renderTodoTree(item.children as TodoItem[], level + 1)
                                : null}
                        </WaidTodoItem>
                    );
                })}
            </SortableContext>
        );
    };

    return (
        <div className="h-screen flex flex-col bg-[#1e1e1e] text-white select-none overflow-hidden">
            {/* 拖拽标题栏 */}
            <div
                className="h-8 flex items-center px-3 bg-gradient-to-r from-emerald-600 to-teal-600 shrink-0"
                style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
            >
                <span className="text-xs font-medium text-white/90">What Am I Doing?</span>
            </div>

            {/* 内容区域 */}
            <div className="flex-1 overflow-y-auto py-1">
              <div ref={contentRef}>
                {loading ? (
                    <div className="flex items-center justify-center py-8 text-white/30 text-sm">
                        Loading...
                    </div>
                ) : tree.length === 0 && !isCreating ? (
                    <div className="flex flex-col items-center justify-center py-8 text-white/30">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8 mb-2 opacity-50">
                            <circle cx="12" cy="12" r="10" />
                            <path d="M12 6v6l4 2" />
                        </svg>
                        <p className="text-xs">No tasks yet</p>
                    </div>
                ) : (
                    <>
                        <DndContext
                            sensors={sensors}
                            collisionDetection={closestCenter}
                            onDragEnd={handleDragEnd}
                        >
                            {renderTodoTree(tree)}
                        </DndContext>
                        {/* 内联新建输入框 */}
                        {isCreating && (
                            <div className="px-2 py-1.5">
                                <input
                                    ref={newTaskInputRef}
                                    value={newTaskContent}
                                    onChange={(e) => setNewTaskContent(e.target.value)}
                                    onBlur={handleNewTaskConfirm}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') handleNewTaskConfirm();
                                        if (e.key === 'Escape') {
                                            setIsCreating(false);
                                            setNewTaskContent('');
                                        }
                                    }}
                                    placeholder="Task name..."
                                    className="w-full bg-white/10 text-white text-sm px-2 py-1.5 rounded outline-none focus:ring-1 focus:ring-emerald-500/50 placeholder-white/30"
                                />
                            </div>
                        )}
                    </>
                )}
              </div>
            </div>

            {/* 底部添加按钮 */}
            <div className="shrink-0 px-2 pb-2 border-t border-white/5">
                <AddTaskMenu
                    onCreateNew={handleCreateNew}
                    onSelectExisting={handleSelectExisting}
                />
            </div>
        </div>
    );
};
