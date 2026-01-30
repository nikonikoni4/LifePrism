import React, { useEffect, useRef, useState } from 'react';
import {
    Check,
    GripVertical,
    Trash2,
    Calendar,
    FileText,
    Clock,
    AlertCircle,
    Timer,
    Pencil,
    Palette,
    ChevronDown,
    ChevronUp
} from 'lucide-react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { TodoItem as TodoItemType } from './types';

// State color mappings based on Aurora Design
const STATE_COLORS = {
    pool: 'bg-indigo-500',      // #6366F1
    scheduled: 'bg-violet-500', // #8B5CF6
    completed: 'bg-emerald-500',// #10B981
    shelved: 'bg-gray-400'
};

// Available todo background colors
const TODO_COLORS = [
    '#FFFFFF', // White
    '#E0F2FE', // Blue
    '#DCFCE7', // Green
    '#FEF3C7', // Amber
    '#FAE8FF', // Purple
    '#FEE2E2', // Red
    '#F3F4F6'  // Grey
];

// Get random color from TODO_COLORS
const getRandomColor = () => TODO_COLORS[Math.floor(Math.random() * TODO_COLORS.length)];

interface TodoItemDetailedProps {
    todo: TodoItemType;
    isActive?: boolean;
    onUpdate: (id: number, updates: Partial<TodoItemType>) => void;
    onSelect?: (id: number) => void;
    onDelete: (id: number) => void;

    // Optional display flags
    showSource?: boolean;
    showDate?: boolean;
}

/**
 * TodoItemDetailed - 详细版本的 TodoItem 组件
 * 用于每日聚焦页面，展示更多时间相关信息：
 * - 开始时间 (scheduledDate)
 * - 预期完成时间 (expectedFinishAt)
 * - 拖延时间 (delayDays)
 * - 拖延原因 (delayReason)
 */
export const TodoItemDetailed: React.FC<TodoItemDetailedProps> = ({
    todo,
    isActive,
    onUpdate,
    onSelect,
    onDelete,
    showSource = true,
    showDate = true
}) => {
    const [showColorPicker, setShowColorPicker] = useState(false);
    const [isExpanded, setIsExpanded] = useState(false);
    const [isEditingReason, setIsEditingReason] = useState(false);
    const colorPickerRef = useRef<HTMLDivElement>(null);

    // Editable fields state
    const [editScheduledDate, setEditScheduledDate] = useState(todo.scheduledDate || '');
    const [editExpectedDate, setEditExpectedDate] = useState(todo.expectedFinishAt || '');
    const [editActualDate, setEditActualDate] = useState(todo.actualFinishAt || '');
    const [editDelayReason, setEditDelayReason] = useState(todo.delayReason || '');

    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: todo.id });

    const style: React.CSSProperties = {
        transform: CSS.Transform.toString(transform),
        transition: isDragging ? undefined : transition,
        opacity: isDragging ? 0.6 : 1,
        zIndex: isDragging ? 50 : 'auto',
        position: 'relative',
        backgroundColor: todo.color || '#FFFFFF',
    };

    // Auto-resize for textarea
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const reasonTextareaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
        }
    }, [todo.content]);

    useEffect(() => {
        if (reasonTextareaRef.current) {
            reasonTextareaRef.current.style.height = 'auto';
            reasonTextareaRef.current.style.height = reasonTextareaRef.current.scrollHeight + 'px';
        }
    }, [editDelayReason]);

    // Close dropdowns when clicking outside
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

    // Sync form state when todo changes
    useEffect(() => {
        setEditScheduledDate(todo.scheduledDate || '');
        setEditExpectedDate(todo.expectedFinishAt || '');
        setEditActualDate(todo.actualFinishAt || '');
        setEditDelayReason(todo.delayReason || '');
    }, [todo.scheduledDate, todo.expectedFinishAt, todo.actualFinishAt, todo.delayReason]);

    // Handle State Toggling (Checkbox)
    const toggleComplete = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (todo.state === 'completed') {
            const restoreState = todo.scheduledDate ? 'scheduled' : 'pool';
            onUpdate(todo.id, { state: restoreState });
        } else {
            onUpdate(todo.id, {
                state: 'completed',
                actualFinishAt: new Date().toISOString().split('T')[0]
            });
        }
    };

    // Handle color selection
    const handleColorSelect = (color: string) => {
        onUpdate(todo.id, { color });
        setShowColorPicker(false);
    };

    // Handle date changes
    const handleScheduledDateChange = (value: string) => {
        setEditScheduledDate(value);
        onUpdate(todo.id, { scheduledDate: value || null });
    };

    const handleExpectedDateChange = (value: string) => {
        setEditExpectedDate(value);
        onUpdate(todo.id, { expectedFinishAt: value || null });
    };

    const handleActualDateChange = (value: string) => {
        setEditActualDate(value);
        onUpdate(todo.id, { actualFinishAt: value || null });
    };

    // Handle delay reason blur (save when focus lost)
    const handleDelayReasonBlur = () => {
        setIsEditingReason(false);
        onUpdate(todo.id, { delayReason: editDelayReason || null });
    };

    // Calculate delay status
    const getDelayStatus = () => {
        if (!todo.expectedFinishAt) return null;

        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const expected = new Date(todo.expectedFinishAt);
        expected.setHours(0, 0, 0, 0);

        if (todo.state === 'completed' && todo.actualFinishAt) {
            const actual = new Date(todo.actualFinishAt);
            actual.setHours(0, 0, 0, 0);
            const diffDays = Math.floor((actual.getTime() - expected.getTime()) / (1000 * 60 * 60 * 24));
            if (diffDays > 0) {
                return { type: 'delayed', days: diffDays };
            } else if (diffDays < 0) {
                return { type: 'early', days: Math.abs(diffDays) };
            }
            return { type: 'ontime', days: 0 };
        }

        // Not completed yet
        const diffDays = Math.floor((today.getTime() - expected.getTime()) / (1000 * 60 * 60 * 24));
        if (diffDays > 0) {
            return { type: 'overdue', days: diffDays };
        } else if (diffDays === 0) {
            return { type: 'duetoday', days: 0 };
        }
        return { type: 'upcoming', days: Math.abs(diffDays) };
    };

    const delayStatus = getDelayStatus();
    const isCompleted = todo.state === 'completed';

    // Format date for display
    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return '未设置';
        const date = new Date(dateStr);
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    };

    return (
        <div
            ref={setNodeRef}
            style={style}
            onClick={() => onSelect && onSelect(todo.id)}
            className={`
                group relative rounded-2xl border transition-all duration-200 mb-3 cursor-pointer overflow-hidden
                ${isActive
                    ? 'ring-2 ring-blue-400 border-blue-400 shadow-md z-10'
                    : 'border-slate-200/80 hover:border-slate-300 hover:shadow-sm'
                }
                ${isDragging ? 'shadow-xl' : ''}
                ${isCompleted ? 'opacity-70' : ''}
            `}
        >
            {/* Main Content Row */}
            <div className="flex items-start gap-3 py-3 pr-3 pl-10">
                {/* Drag Handle - Floating on left */}
                <div
                    {...attributes}
                    {...listeners}
                    onClick={(e) => e.stopPropagation()}
                    className="absolute left-1 top-1 p-2 px-2.5 text-slate-300 opacity-0 group-hover:opacity-100 cursor-grab active:cursor-grabbing hover:text-slate-600 hover:bg-slate-200/50 rounded-xl transition-all z-20 flex items-center justify-center mt-0.5"
                >
                    <GripVertical size={18} />
                </div>

                {/* Checkbox */}
                <button
                    onClick={toggleComplete}
                    className={`
                        w-5 h-5 rounded-lg border-[1.5px] flex items-center justify-center transition-all flex-shrink-0 mt-0.5
                        ${isCompleted
                            ? 'bg-emerald-500 border-emerald-500'
                            : 'border-slate-300 bg-white/50 hover:border-blue-400'
                        }
                    `}
                >
                    {isCompleted && <Check size={12} className="text-white" strokeWidth={3} />}
                </button>

                {/* Content Area */}
                <div className="flex-1 min-w-0">
                    {/* Task Content */}
                    <textarea
                        ref={textareaRef}
                        value={todo.content}
                        rows={1}
                        onChange={(e) => onUpdate(todo.id, { content: e.target.value })}
                        onClick={(e) => e.stopPropagation()}
                        className={`
                            w-full bg-transparent border-none outline-none text-sm font-medium p-0 resize-none overflow-hidden
                            ${isCompleted ? 'text-slate-400 line-through decoration-slate-300' : 'text-slate-700'}
                        `}
                        style={{ minHeight: '20px' }}
                        placeholder="Type a task..."
                    />

                    {/* Time Info Row - Always Visible */}
                    <div className="flex items-center gap-3 flex-wrap mt-2">
                        {/* Scheduled Date (开始时间) */}
                        {/* Scheduled Date (开始时间) */}
                        {todo.scheduledDate && (
                            <div className="flex items-center gap-1.5 text-xs relative z-30">
                                <Calendar size={12} className="text-violet-500" />
                                <span className="text-slate-500">开始:</span>
                                <input
                                    type="date"
                                    value={editScheduledDate}
                                    onChange={(e) => handleScheduledDateChange(e.target.value)}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        e.preventDefault(); // Prevent standard behavior to force picker? No, preventDefault stops focus often.
                                        // Just stop propagation and show picker
                                        try {
                                            if (typeof (e.currentTarget as any).showPicker === 'function') {
                                                (e.currentTarget as any).showPicker();
                                            }
                                        } catch (err) {
                                            // Fallback or ignore
                                        }
                                    }}
                                    onMouseDown={(e) => e.stopPropagation()}
                                    className="font-medium text-violet-600 bg-transparent border-none outline-none cursor-pointer text-xs p-0 w-[90px]"
                                />
                            </div>
                        )}

                        {/* Expected Finish Date (预期完成时间) */}
                        <div className="flex items-center gap-1.5 text-xs relative z-30">
                            <Timer size={12} className="text-blue-500" />
                            <span className="text-slate-500">预期:</span>
                            <input
                                type="date"
                                value={editExpectedDate}
                                onChange={(e) => handleExpectedDateChange(e.target.value)}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    try {
                                        if (typeof (e.currentTarget as any).showPicker === 'function') {
                                            (e.currentTarget as any).showPicker();
                                        }
                                    } catch (err) { }
                                }}
                                onMouseDown={(e) => e.stopPropagation()}
                                className="font-medium text-blue-600 bg-transparent border-none outline-none cursor-pointer text-xs p-0 w-[90px]"
                            />
                        </div>

                        {/* Actual Finish Date - Only show if completed */}
                        {isCompleted && (
                            <div className="flex items-center gap-1.5 text-xs relative z-30">
                                <Check size={12} className="text-emerald-500" />
                                <span className="text-slate-500">完成:</span>
                                <input
                                    type="date"
                                    value={editActualDate}
                                    onChange={(e) => handleActualDateChange(e.target.value)}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        try {
                                            if (typeof (e.currentTarget as any).showPicker === 'function') {
                                                (e.currentTarget as any).showPicker();
                                            }
                                        } catch (err) { }
                                    }}
                                    onMouseDown={(e) => e.stopPropagation()}
                                    className="font-medium text-emerald-600 bg-transparent border-none outline-none cursor-pointer text-xs p-0 w-[90px]"
                                />
                            </div>
                        )}

                        {/* Delay Status Badge */}
                        {delayStatus && (
                            <div className={`
                                flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold
                                ${delayStatus.type === 'overdue' ? 'bg-red-100 text-red-600 border border-red-200' : ''}
                                ${delayStatus.type === 'delayed' ? 'bg-amber-100 text-amber-600 border border-amber-200' : ''}
                                ${delayStatus.type === 'duetoday' ? 'bg-orange-100 text-orange-600 border border-orange-200' : ''}
                                ${delayStatus.type === 'upcoming' ? 'bg-blue-50 text-blue-500 border border-blue-100' : ''}
                                ${delayStatus.type === 'ontime' ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' : ''}
                                ${delayStatus.type === 'early' ? 'bg-green-50 text-green-600 border border-green-100' : ''}
                            `}>
                                {delayStatus.type === 'overdue' && <AlertCircle size={10} />}
                                {delayStatus.type === 'delayed' && <Clock size={10} />}
                                {delayStatus.type === 'duetoday' && <Timer size={10} />}
                                <span>
                                    {delayStatus.type === 'overdue' && `已逾期 ${delayStatus.days} 天`}
                                    {delayStatus.type === 'delayed' && `延迟 ${delayStatus.days} 天`}
                                    {delayStatus.type === 'duetoday' && '今日截止'}
                                    {delayStatus.type === 'upcoming' && `剩余 ${delayStatus.days} 天`}
                                    {delayStatus.type === 'ontime' && '按时完成'}
                                    {delayStatus.type === 'early' && `提前 ${delayStatus.days} 天`}
                                </span>
                            </div>
                        )}

                        {/* Source Pill */}
                        {todo.sourceType === 'plan_doc' && showSource && (
                            <div className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 font-semibold border border-blue-100">
                                <FileText size={10} />
                                <span>Plan</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Expand/Collapse Button */}
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        setIsExpanded(!isExpanded);
                    }}
                    className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-all"
                    title={isExpanded ? "收起详情" : "展开详情"}
                >
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>

                {/* Hover Actions */}
                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-all duration-200">
                    {/* Color Picker Button */}
                    <div className="relative" ref={colorPickerRef}>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowColorPicker(!showColorPicker);
                            }}
                            className={`p-1.5 rounded-xl transition-all ${showColorPicker ? 'text-purple-500 bg-purple-50' : 'text-slate-300 hover:text-purple-500 hover:bg-slate-100'}`}
                            title="选择颜色"
                        >
                            <Palette size={14} />
                        </button>

                        {/* Color Picker Dropdown */}
                        {showColorPicker && (
                            <div
                                className="absolute right-0 top-full mt-2 p-2.5 bg-white rounded-xl shadow-xl border border-slate-200 flex gap-1.5"
                                style={{ zIndex: 9999 }}
                                onClick={(e) => e.stopPropagation()}
                            >
                                {TODO_COLORS.map((color) => (
                                    <button
                                        key={color}
                                        onClick={() => handleColorSelect(color)}
                                        className={`
                                            w-5 h-5 rounded-full border border-slate-200 shadow-sm transition-transform hover:scale-110
                                            ${todo.color === color ? 'ring-2 ring-slate-400 scale-110' : ''}
                                        `}
                                        style={{ backgroundColor: color }}
                                    />
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Delete Button */}
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onDelete(todo.id);
                        }}
                        className="p-1.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all"
                        title="删除任务"
                    >
                        <Trash2 size={14} />
                    </button>
                </div>
            </div>

            {/* Expandable Detail Section - 拖延原因 */}
            {isExpanded && (
                <div
                    className="px-4 pb-4 pt-2 border-t border-slate-100 bg-slate-50/50"
                    onClick={(e) => e.stopPropagation()}
                >
                    <div className="space-y-3">
                        {/* Delay Reason */}
                        <div>
                            <label className="flex items-center gap-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                                <AlertCircle size={10} />
                                拖延/未完成原因
                            </label>
                            <textarea
                                ref={reasonTextareaRef}
                                value={editDelayReason}
                                onChange={(e) => setEditDelayReason(e.target.value)}
                                onFocus={() => setIsEditingReason(true)}
                                onBlur={handleDelayReasonBlur}
                                placeholder="记录原因，帮助复盘改进..."
                                rows={2}
                                className={`
                                    w-full px-3 py-2 text-sm text-slate-700 bg-white border rounded-lg outline-none resize-none placeholder-slate-400 transition-all
                                    ${isEditingReason
                                        ? 'border-blue-300 ring-2 ring-blue-100'
                                        : 'border-slate-200 hover:border-slate-300'
                                    }
                                `}
                            />
                        </div>

                        {/* Quick Time Summary */}
                        {(todo.scheduledDate || todo.expectedFinishAt || todo.actualFinishAt) && (
                            <div className="flex items-center gap-4 text-xs text-slate-500 pt-1">
                                {todo.scheduledDate && (
                                    <span>📅 开始: <strong className="text-slate-600">{formatDate(todo.scheduledDate)}</strong></span>
                                )}
                                {todo.expectedFinishAt && (
                                    <span>⏱️ 预期: <strong className="text-slate-600">{formatDate(todo.expectedFinishAt)}</strong></span>
                                )}
                                {todo.actualFinishAt && (
                                    <span>✅ 完成: <strong className="text-slate-600">{formatDate(todo.actualFinishAt)}</strong></span>
                                )}
                                {todo.delayDays !== null && todo.delayDays > 0 && (
                                    <span className="text-red-500">🔴 拖延: <strong>{todo.delayDays} 天</strong></span>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

// Export TODO_COLORS and getRandomColor for external use
export { TODO_COLORS, getRandomColor };
