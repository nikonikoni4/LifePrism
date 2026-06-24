import React, { useState, useRef, useEffect } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { TodoItem } from '../../../apps/goals/types/todo';
import { formatElapsed, formatMinutes } from '../utils/formatTime';

interface WaidTodoItemProps {
    item: TodoItem;
    level: number;
    isTimerActive: boolean;
    elapsed: number;
    accumulatedMinutes: number;
    collapsed: boolean;
    hasChildren: boolean;
    isExpanded: boolean;
    onToggleComplete: (id: string) => void;
    onStartTimer: (item: TodoItem) => void;
    onStopTimer: () => void;
    onContentChange: (id: string, content: string) => void;
    onRemove: (id: string) => void;
    onToggleCollapse: (id: string) => void;
    onToggleExpand: (id: string) => void;
    children?: React.ReactNode;
}

export function WaidTodoItem({
    item,
    level,
    isTimerActive,
    elapsed,
    accumulatedMinutes,
    collapsed,
    hasChildren,
    isExpanded,
    onToggleComplete,
    onStartTimer,
    onStopTimer,
    onContentChange,
    onRemove,
    onToggleCollapse,
    onToggleExpand,
    children,
}: WaidTodoItemProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [editValue, setEditValue] = useState(item.content);
    const [showMenu, setShowMenu] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const isCompleted = item.state === 'completed';

    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: item.id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus();
            inputRef.current.select();
        }
    }, [isEditing]);

    // 点击外部关闭菜单
    useEffect(() => {
        if (!showMenu) return;
        const handleClick = (e: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setShowMenu(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [showMenu]);

    const handleBlur = () => {
        setIsEditing(false);
        const trimmed = editValue.trim();
        if (trimmed && trimmed !== item.content) {
            onContentChange(item.id, trimmed);
        } else {
            setEditValue(item.content);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            (e.target as HTMLInputElement).blur();
        } else if (e.key === 'Escape') {
            setEditValue(item.content);
            setIsEditing(false);
        }
    };

    return (
        <div ref={setNodeRef} style={style} className="relative">
            {/* 层级连接线 */}
            {level > 0 && (
                <div
                    className="absolute top-0 bottom-0 border-l border-white/10"
                    style={{ left: `${8 + (level - 1) * 20 + 10}px` }}
                />
            )}
            <div
                className="flex items-center gap-1.5 px-2 py-1.5 group hover:bg-white/5 rounded"
                style={{ paddingLeft: `${8 + level * 20}px` }}
            >
                {/* 拖拽手柄 */}
                <button
                    className="flex-shrink-0 w-4 h-4 flex items-center justify-center text-white/20 hover:text-white/50 cursor-grab active:cursor-grabbing"
                    {...attributes}
                    {...listeners}
                >
                    <svg className="w-3 h-3" viewBox="0 0 16 16" fill="currentColor">
                        <circle cx="5" cy="3" r="1.2" />
                        <circle cx="11" cy="3" r="1.2" />
                        <circle cx="5" cy="8" r="1.2" />
                        <circle cx="11" cy="8" r="1.2" />
                        <circle cx="5" cy="13" r="1.2" />
                        <circle cx="11" cy="13" r="1.2" />
                    </svg>
                </button>

                {/* 折叠箭头 */}
                {hasChildren ? (
                    <button
                        onClick={() => onToggleCollapse(item.id)}
                        className="flex-shrink-0 w-4 h-4 flex items-center justify-center text-white/40 hover:text-white/70"
                    >
                        <svg className={`w-3 h-3 transition-transform ${collapsed ? '' : 'rotate-90'}`} viewBox="0 0 12 12" fill="currentColor">
                            <path d="M4 2l4 4-4 4V2z" />
                        </svg>
                    </button>
                ) : (
                    <span className="flex-shrink-0 w-4" />
                )}

                {/* Checkbox */}
                <button
                    onClick={() => onToggleComplete(item.id)}
                    className={`flex-shrink-0 w-4 h-4 rounded border ${isCompleted
                        ? 'bg-green-500 border-green-500'
                        : 'border-white/40 hover:border-white/70'
                        } flex items-center justify-center transition-colors`}
                >
                    {isCompleted && (
                        <svg className="w-3 h-3 text-white" viewBox="0 0 12 12" fill="none">
                            <path d="M2.5 6L5 8.5L9.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    )}
                </button>

                {/* 任务名称 */}
                {isEditing ? (
                    <input
                        ref={inputRef}
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onBlur={handleBlur}
                        onKeyDown={handleKeyDown}
                        className="flex-1 min-w-0 bg-white/10 text-white text-sm px-1.5 py-0.5 rounded outline-none focus:ring-1 focus:ring-white/30"
                    />
                ) : (
                    <span
                        className={`flex-1 min-w-0 text-sm cursor-text ${
                            isExpanded ? 'whitespace-normal break-words' : 'truncate'
                        } ${isCompleted ? 'line-through text-white/40' : 'text-white/90'}`}
                        onDoubleClick={() => {
                            if (!isCompleted) {
                                setEditValue(item.content);
                                setIsEditing(true);
                            }
                        }}
                    >
                        {item.content}
                    </span>
                )}

                {/* 时长显示 */}
                <span className="flex-shrink-0 text-xs text-white/50 tabular-nums">
                    {isTimerActive ? (
                        <span className="text-green-400 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                            {formatElapsed(elapsed)}
                        </span>
                    ) : accumulatedMinutes > 0 ? (
                        formatMinutes(accumulatedMinutes)
                    ) : null}
                </span>

                {/* 计时按钮 */}
                {!isCompleted && (
                    <button
                        onClick={() => isTimerActive ? onStopTimer() : onStartTimer(item)}
                        className={`flex-shrink-0 w-6 h-6 rounded flex items-center justify-center transition-colors ${isTimerActive
                            ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                            : 'text-white/30 hover:text-white/70 hover:bg-white/10 opacity-0 group-hover:opacity-100'
                            }`}
                        title={isTimerActive ? 'Stop' : 'Start'}
                    >
                        {isTimerActive ? (
                            <svg className="w-3 h-3" viewBox="0 0 12 12" fill="currentColor">
                                <rect x="2" y="2" width="8" height="8" rx="1" />
                            </svg>
                        ) : (
                            <svg className="w-3 h-3" viewBox="0 0 12 12" fill="currentColor">
                                <path d="M3 1.5v9l7.5-4.5L3 1.5z" />
                            </svg>
                        )}
                    </button>
                )}

                {/* 展开/收缩按钮 */}
                <button
                    onClick={() => onToggleExpand(item.id)}
                    className="flex-shrink-0 w-6 h-6 rounded flex items-center justify-center text-white/30 hover:text-white/70 hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-all"
                    title={isExpanded ? 'Collapse' : 'Expand'}
                >
                    {isExpanded ? (
                        <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M6 2H3a1 1 0 0 0-1 1v3M10 2h3a1 1 0 0 1 1 1v3M6 14H3a1 1 0 0 1-1-1v-3M10 14h3a1 1 0 0 0 1-1v-3" />
                        </svg>
                    ) : (
                        <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M2 6V3a1 1 0 0 1 1-1h3M14 6V3a1 1 0 0 0-1-1h-3M2 10v3a1 1 0 0 0 1 1h3M14 10v3a1 1 0 0 1-1 1h-3" />
                        </svg>
                    )}
                </button>

                {/* 更多菜单 */}
                <div className="relative flex-shrink-0" ref={menuRef}>
                    <button
                        onClick={() => setShowMenu(!showMenu)}
                        className="w-6 h-6 rounded flex items-center justify-center text-white/30 hover:text-white/70 hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-all"
                    >
                        <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
                            <circle cx="8" cy="3" r="1.5" />
                            <circle cx="8" cy="8" r="1.5" />
                            <circle cx="8" cy="13" r="1.5" />
                        </svg>
                    </button>
                    {showMenu && (
                        <div className="absolute right-0 bottom-full mb-1 bg-[#2a2a2a] border border-white/10 rounded-md shadow-xl z-50 py-1 min-w-[100px]">
                            <button
                                onClick={() => {
                                    setShowMenu(false);
                                    onRemove(item.id);
                                }}
                                className="w-full text-left px-3 py-1.5 text-sm text-white/70 hover:bg-white/10 hover:text-white"
                            >
                                Remove
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* 子任务 */}
            {children}
        </div>
    );
}
