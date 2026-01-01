/**
 * TaskDetailPanel - 任务详情面板组件
 * 
 * 可复用的任务详情编辑面板，用于 TodoTabView 和 PlanTabView
 */

import React, { useState } from 'react';
import {
    Target,
    GripVertical,
    Calendar,
    Trash2,
    Palette,
    Activity,
    CheckCircle,
    RefreshCw,
    X
} from 'lucide-react';
import {
    DndContext,
    pointerWithin,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent,
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
    useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { TodoItem, SubTodoItem, ActiveGoalItem } from '../types';

// --- Constants ---
const TODO_COLORS = [
    '#FFFFFF', // White
    '#E0F2FE', // Blue
    '#DCFCE7', // Green
    '#FEF3C7', // Amber
    '#FAE8FF', // Purple
    '#FEE2E2', // Red
    '#F3F4F6'  // Grey
];

// --- Sortable Sub-Task Item ---
interface SortableSubTaskProps {
    subItem: SubTodoItem;
    onUpdate: (id: number, updates: Partial<SubTodoItem>) => void;
    onDelete: (id: number) => void;
}

const SortableSubTaskItem: React.FC<SortableSubTaskProps> = ({ subItem, onUpdate, onDelete }) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: subItem.id });

    const style: React.CSSProperties = {
        transform: CSS.Transform.toString(transform),
        transition: isDragging ? undefined : transition,
        opacity: isDragging ? 0.6 : 1,
        zIndex: isDragging ? 50 : 'auto',
        position: 'relative'
    };

    // Auto-resize textarea logic for subtask
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);
    React.useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
        }
    }, [subItem.content]);

    return (
        <div
            ref={setNodeRef}
            style={style}
            className={`group relative flex items-start gap-3 py-3 pr-3 pl-10 rounded-2xl border transition-colors duration-200 mb-2 cursor-pointer border-transparent hover:border-slate-200 hover:shadow-sm bg-white ${isDragging ? 'shadow-xl' : ''}`}
        >
            {/* Drag Handle */}
            <div
                {...attributes}
                {...listeners}
                className="absolute left-1 top-3 p-2 px-2.5 rounded-xl text-slate-300 hover:text-slate-600 hover:bg-slate-200/50 transition-all flex items-center justify-center z-10 cursor-grab active:cursor-grabbing mt-0.5"
            >
                <GripVertical size={18} />
            </div>

            {/* Checkbox */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onUpdate(subItem.id, { completed: !subItem.completed });
                }}
                className={`w-5 h-5 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-all mt-0.5 ${subItem.completed
                    ? 'bg-green-500 border-green-500 text-white shadow-md'
                    : 'border-slate-300 hover:border-green-400 text-transparent hover:text-green-300'
                    }`}
            >
                {subItem.completed && <CheckCircle size={12} />}
            </button>

            {/* Content Textarea */}
            <div className="flex-1 min-w-0">
                <textarea
                    ref={textareaRef}
                    rows={1}
                    value={subItem.content}
                    onChange={(e) => onUpdate(subItem.id, { content: e.target.value })}
                    onClick={(e) => e.stopPropagation()}
                    className={`w-full text-sm font-medium outline-none bg-transparent transition-colors resize-none overflow-hidden ${subItem.completed ? 'text-slate-400 line-through' : 'text-slate-700'
                        }`}
                    style={{ minHeight: '20px' }}
                />
            </div>

            {/* Delete Button */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onDelete(subItem.id);
                }}
                className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 transition-all mt-[-2px]"
            >
                <Trash2 size={14} />
            </button>
        </div>
    );
};

// --- Main Component Props ---
export interface TaskDetailPanelProps {
    task: TodoItem;
    activeGoals: ActiveGoalItem[];
    onUpdateTask: (id: number, updates: Partial<TodoItem>) => void;
    onCreateSubTask: (parentId: number, content: string) => void;
    onUpdateSubTask: (id: number, updates: Partial<SubTodoItem>) => void;
    onDeleteSubTask: (id: number) => void;
    onReorderSubTasks: (parentId: number, subTaskIds: number[]) => void;
    onClose?: () => void;
    showCloseButton?: boolean;
}

const TaskDetailPanel: React.FC<TaskDetailPanelProps> = ({
    task,
    activeGoals,
    onUpdateTask,
    onCreateSubTask,
    onUpdateSubTask,
    onDeleteSubTask,
    onReorderSubTasks,
    onClose,
    showCloseButton = false
}) => {
    const [subTaskInput, setSubTaskInput] = useState('');
    const [showDateRangePicker, setShowDateRangePicker] = useState(false);

    // Auto-resize textarea logic for Task Name
    const taskNameRef = React.useRef<HTMLTextAreaElement>(null);
    React.useEffect(() => {
        if (taskNameRef.current) {
            taskNameRef.current.style.height = 'auto';
            taskNameRef.current.style.height = taskNameRef.current.scrollHeight + 'px';
        }
    }, [task.content]);

    // DnD sensors for sub-tasks
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    const handleDragEndSubTasks = (event: DragEndEvent) => {
        const { active, over } = event;
        if (!over || active.id === over.id || !task.subItems) return;

        const oldIndex = task.subItems.findIndex(s => s.id === active.id);
        const newIndex = task.subItems.findIndex(s => s.id === over.id);

        if (oldIndex !== -1 && newIndex !== -1) {
            const newOrder = arrayMove(task.subItems, oldIndex, newIndex);
            onReorderSubTasks(task.id, newOrder.map(s => s.id));
        }
    };

    const handleCreateSubTask = () => {
        if (!subTaskInput.trim()) return;
        onCreateSubTask(task.id, subTaskInput.trim());
        setSubTaskInput('');
    };

    return (
        <div className="w-full max-w-2xl animate-in fade-in slide-in-from-right-4 duration-300">
            {/* Close Button (optional) */}
            {showCloseButton && onClose && (
                <div className="flex justify-end mb-4">
                    <button
                        onClick={onClose}
                        className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>
            )}

            {/* Task Name (Header) */}
            <div className="mb-6">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 block">Task Name</label>
                <textarea
                    ref={taskNameRef}
                    rows={1}
                    value={task.content}
                    onChange={(e) => onUpdateTask(task.id, { content: e.target.value })}
                    className="w-full text-2xl font-bold text-slate-800 outline-none bg-transparent border-b border-transparent focus:border-slate-200 transition-all pb-1 placeholder-slate-300 resize-none overflow-hidden"
                />
            </div>

            {/* 5-column Grid for Metadata */}
            <div className="grid grid-cols-5 gap-2 mb-6">
                {/* 1. Date Range */}
                <div
                    className="bg-slate-50/50 p-2.5 rounded-xl border border-slate-100 flex flex-col gap-1 hover:bg-white hover:shadow-sm transition-all group cursor-pointer relative"
                    onClick={() => setShowDateRangePicker(!showDateRangePicker)}
                >
                    <div className="flex items-center gap-1.5 text-slate-400">
                        <Calendar size={11} className="group-hover:text-blue-500 transition-colors" />
                        <span className="text-[8px] font-bold uppercase tracking-wider">日期</span>
                    </div>
                    <div className="flex items-center gap-1 text-[10px] font-bold text-slate-700">
                        <span className="truncate">{task.date?.slice(5) || '--'}</span>
                        <span className="text-slate-400">→</span>
                        <span className="truncate">{task.expectedFinishedAt?.slice(5) || '--'}</span>
                    </div>

                    {/* Date Range Picker Popup */}
                    {showDateRangePicker && (
                        <div
                            className="absolute top-full left-0 mt-2 bg-white rounded-xl shadow-xl border border-slate-200 p-4 z-50 w-64"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="space-y-3">
                                <div>
                                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">开始日期</label>
                                    <input
                                        type="date"
                                        value={task.date || ''}
                                        onChange={(e) => onUpdateTask(task.id, { date: e.target.value })}
                                        className="w-full px-3 py-2 text-sm font-semibold text-slate-700 bg-slate-50 border border-slate-200 rounded-lg outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                                    />
                                </div>
                                <div>
                                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">结束日期</label>
                                    <input
                                        type="date"
                                        value={task.expectedFinishedAt || ''}
                                        onChange={(e) => onUpdateTask(task.id, { expectedFinishedAt: e.target.value || null })}
                                        className="w-full px-3 py-2 text-sm font-semibold text-slate-700 bg-slate-50 border border-slate-200 rounded-lg outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                                    />
                                </div>
                                <button
                                    onClick={() => setShowDateRangePicker(false)}
                                    className="w-full py-2 bg-blue-500 text-white text-sm font-bold rounded-lg hover:bg-blue-600 transition-colors"
                                >
                                    确定
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                {/* 2. Cross-Day Toggle */}
                <div
                    onClick={() => onUpdateTask(task.id, { crossDay: !task.crossDay })}
                    className={`p-2.5 rounded-xl border flex flex-col gap-1 cursor-pointer transition-all group ${task.crossDay
                        ? 'bg-amber-50/50 border-amber-200 hover:bg-amber-100'
                        : 'bg-slate-50/50 border-slate-100 hover:bg-white hover:shadow-sm'
                        }`}
                    title="长期任务：每天都会出现直至完成"
                >
                    <div className={`flex items-center gap-1.5 ${task.crossDay ? 'text-amber-600' : 'text-slate-400'}`}>
                        <RefreshCw size={11} className="group-hover:text-amber-500 transition-colors" />
                        <span className="text-[8px] font-bold uppercase tracking-wider">跨日</span>
                    </div>
                    <span className={`text-[10px] font-bold truncate ${task.crossDay ? 'text-amber-700' : 'text-slate-500'}`}>
                        {task.crossDay ? '长期' : '单日'}
                    </span>
                </div>

                {/* 3. Goal Link */}
                <div className="bg-slate-50/50 p-2.5 rounded-xl border border-slate-100 flex flex-col gap-1 hover:bg-white hover:shadow-sm transition-all group">
                    <div className="flex items-center gap-1.5 text-slate-400">
                        <Target size={11} className="group-hover:text-orange-500 transition-colors" />
                        <span className="text-[8px] font-bold uppercase tracking-wider">目标</span>
                    </div>
                    <select
                        value={task.linkToGoalId || ''}
                        onChange={(e) => onUpdateTask(task.id, { linkToGoalId: e.target.value || null })}
                        className="bg-transparent text-[10px] font-bold text-slate-700 w-full outline-none cursor-pointer truncate"
                    >
                        <option value="">无</option>
                        {activeGoals.map(g => (
                            <option key={g.id} value={g.id}>{g.name}</option>
                        ))}
                    </select>
                </div>

                {/* 4. Color Selection */}
                <div className="bg-slate-50/50 p-2.5 rounded-xl border border-slate-100 flex flex-col gap-1 hover:bg-white hover:shadow-sm transition-all group">
                    <div className="flex items-center gap-1.5 text-slate-400">
                        <Palette size={11} className="group-hover:text-purple-500 transition-colors" />
                        <span className="text-[8px] font-bold uppercase tracking-wider">颜色</span>
                    </div>
                    <div className="flex gap-1">
                        {TODO_COLORS.map(c => (
                            <button
                                key={c}
                                onClick={() => onUpdateTask(task.id, { color: c })}
                                className={`w-3.5 h-3.5 rounded-full border border-slate-200 shadow-sm transition-transform hover:scale-110 ${task.color === c ? 'ring-2 ring-slate-400 scale-110' : ''}`}
                                style={{ backgroundColor: c }}
                            />
                        ))}
                    </div>
                </div>

                {/* 5. Status Toggle */}
                <div
                    onClick={() => onUpdateTask(task.id, {
                        state: task.state === 'completed' ? 'active' : 'completed'
                    } as any)}
                    className={`p-2.5 rounded-xl border flex flex-col gap-1 cursor-pointer transition-all ${task.state === 'completed'
                        ? 'bg-green-50/50 border-green-200 hover:bg-green-100'
                        : 'bg-slate-50/50 border-slate-100 hover:bg-white hover:shadow-sm hover:border-blue-200'
                        }`}
                >
                    <div className={`flex items-center gap-1.5 ${task.state === 'completed' ? 'text-green-600' : 'text-slate-400'}`}>
                        {task.state === 'completed' ? <CheckCircle size={11} /> : <Activity size={11} />}
                        <span className="text-[8px] font-bold uppercase tracking-wider">状态</span>
                    </div>
                    <span className={`text-[10px] font-bold truncate ${task.state === 'completed' ? 'text-green-700' : 'text-slate-700'}`}>
                        {task.state === 'completed' ? '完成' : '进行中'}
                    </span>
                </div>
            </div>

            {/* Separator */}
            <div className="h-px bg-slate-100 w-full mb-8 relative">
                <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-white px-3 text-[10px] font-black text-slate-300 uppercase tracking-widest">
                    Sub-tasks
                </span>
            </div>

            {/* Sub-tasks Input */}
            <div className="mb-4">
                <input
                    type="text"
                    value={subTaskInput}
                    onChange={(e) => setSubTaskInput(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                            handleCreateSubTask();
                        }
                    }}
                    placeholder="Create a sub-task..."
                    className="w-full bg-slate-50 border border-transparent rounded-xl px-4 py-3 text-sm font-medium outline-none focus:bg-white focus:border-blue-200 focus:ring-4 focus:ring-blue-50 transition-all placeholder-slate-400"
                />
            </div>

            {/* Sub-Task List */}
            <DndContext
                id="dnd-subtasks"
                sensors={sensors}
                collisionDetection={pointerWithin}
                onDragEnd={handleDragEndSubTasks}
            >
                <SortableContext items={(task.subItems || []).map(s => s.id)} strategy={verticalListSortingStrategy}>
                    <div className="space-y-2">
                        {(task.subItems || []).map(sub => (
                            <SortableSubTaskItem
                                key={sub.id}
                                subItem={sub}
                                onUpdate={onUpdateSubTask}
                                onDelete={onDeleteSubTask}
                            />
                        ))}
                        {(!task.subItems || task.subItems.length === 0) && (
                            <div className="text-center py-10 text-slate-300 text-xs font-bold italic">
                                No sub-tasks yet. Break it down!
                            </div>
                        )}
                    </div>
                </SortableContext>
            </DndContext>
        </div>
    );
};

export default TaskDetailPanel;
