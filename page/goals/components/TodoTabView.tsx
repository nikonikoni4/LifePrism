
import React, { useState, useMemo, useEffect, useCallback } from 'react';
import {
    Check,
    Target,
    Plus,
    GripVertical,
    Calendar,
    Trash2,
    Palette,
    Activity,
    CheckCircle,
    Loader2,
    RefreshCw,
    ChevronDown
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
import { todoApi, goalApi } from '../api';
import WeekDayTreeSelector from './WeekDayTreeSelector';

// --- Types & Constants ---
const TODO_COLORS = [
    '#FFFFFF', // White
    '#E0F2FE', // Blue
    '#DCFCE7', // Green
    '#FEF3C7', // Amber
    '#FAE8FF', // Purple
    '#FEE2E2', // Red
    '#F3F4F6'  // Grey
];

// --- Sortable Task Item Component ---
interface SortableTaskItemProps {
    todo: TodoItem | SubTodoItem;
    isActive?: boolean;
    isSubItem?: boolean;
    onUpdate: (id: number, updates: Partial<TodoItem | SubTodoItem>) => void;
    onSelect?: (id: number) => void;
    onDelete: (id: number) => void;
}

const SortableTaskItem: React.FC<SortableTaskItemProps> = ({
    todo,
    isActive,
    isSubItem = false,
    onUpdate,
    onSelect,
    onDelete
}) => {
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
        backgroundColor: 'color' in todo ? (todo.color || '#FFFFFF') : '#FFFFFF'
    };

    const content = 'content' in todo ? todo.content : '';

    return (
        <div
            ref={setNodeRef}
            style={style}
            onClick={() => onSelect && onSelect(todo.id)}
            className={`group relative flex items-center gap-3 py-3 pr-3 pl-10 rounded-2xl border transition-colors duration-200 mb-2 cursor-pointer ${isActive
                ? 'ring-2 ring-blue-400 border-blue-400 shadow-md z-10'
                : 'border-transparent hover:border-slate-200 hover:shadow-sm'
                } ${isSubItem ? 'bg-white' : ''} ${isDragging ? 'shadow-xl' : ''}`}
        >
            {/* Drag Handle */}
            <div
                {...attributes}
                {...listeners}
                className="absolute left-1 top-1/2 -translate-y-1/2 p-2 px-2.5 text-slate-300 opacity-0 group-hover:opacity-100 cursor-grab active:cursor-grabbing hover:text-slate-600 hover:bg-slate-200/50 rounded-xl transition-all z-20 flex items-center justify-center"
            >
                <GripVertical size={18} />
            </div>

            {/* Completion Checkbox */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    const currentState = 'state' in todo ? (todo as any).state : 'active';
                    const newState = currentState === 'completed' ? 'active' : 'completed';
                    onUpdate(todo.id, { state: newState } as any);
                }}
                className={`w-5 h-5 rounded-lg border-[1.5px] flex items-center justify-center transition-all flex-shrink-0 ${'state' in todo && (todo as any).state === 'completed'
                    ? 'bg-slate-800 border-slate-800'
                    : 'border-slate-300 bg-white/50 hover:border-blue-400'
                    }`}
            >
                {'state' in todo && (todo as any).state === 'completed' && <Check size={12} className="text-white" strokeWidth={3} />}
            </button>

            {/* Text Input - Direct Edit */}
            <div className="flex-1 min-w-0">
                <input
                    type="text"
                    value={content}
                    onChange={(e) => onUpdate(todo.id, { content: e.target.value })}
                    className={`w-full bg-transparent border-none outline-none text-sm font-medium p-0 ${'state' in todo && (todo as any).state === 'completed'
                        ? 'text-slate-400 line-through decoration-slate-300'
                        : 'text-slate-700'
                        }`}
                />
            </div>

            {/* Trash Icon */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onDelete(todo.id);
                }}
                className="opacity-0 group-hover:opacity-100 p-1 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded transition-all"
            >
                <Trash2 size={14} />
            </button>
        </div>
    );
};

// --- Main Three-Pane Component ---

interface TodoTabViewProps {
    initialDate?: string | null;
    onDateUsed?: () => void;
}

const TodoTabView: React.FC<TodoTabViewProps> = ({ initialDate, onDateUsed }) => {
    // 使用今天的日期作为默认值
    const today = new Date().toISOString().split('T')[0];
    const [selectedDate, setSelectedDate] = useState(initialDate || today);

    const [items, setItems] = useState<TodoItem[]>([]);
    const [dailyFocusContent, setDailyFocusContent] = useState<string | null>(null);
    const [selectedL1Id, setSelectedL1Id] = useState<number | null>(null);
    const [loading, setLoading] = useState(false);
    const [activeGoals, setActiveGoals] = useState<ActiveGoalItem[]>([]);

    // Handle external date navigation from PlanTabView
    useEffect(() => {
        if (initialDate) {
            setSelectedDate(initialDate);
            setSelectedL1Id(null);
            // Notify parent that the date has been used
            onDateUsed?.();
        }
    }, [initialDate, onDateUsed]);

    // Handle date change from WeekDayTreeSelector
    const handleDateChange = (date: string) => {
        setSelectedDate(date);
        setSelectedL1Id(null);
    };

    // 加载任务数据
    const loadTodos = useCallback(async () => {
        setLoading(true);
        try {
            const response = await todoApi.getTodos(selectedDate, true);
            setItems(response.items || []);
            setDailyFocusContent(response.dailyFocusContent);
        } catch (error) {
            console.error('Failed to load todos:', error);
        } finally {
            setLoading(false);
        }
    }, [selectedDate]);

    useEffect(() => {
        loadTodos();
    }, [loadTodos]);

    // 加载活跃目标列表
    useEffect(() => {
        const loadActiveGoals = async () => {
            try {
                const response = await goalApi.getActiveGoalNames();
                setActiveGoals(response.items || []);
            } catch (error) {
                console.error('Failed to load active goals:', error);
            }
        };
        loadActiveGoals();
    }, []);

    // Filter items based on Date
    const filteredL1Items = useMemo(() => {
        return items.filter(t => t.date === selectedDate || (t.crossDay && t.state !== 'completed'));
    }, [items, selectedDate]);

    const selectedL1Item = useMemo(() => {
        return items.find(t => t.id === selectedL1Id) || null;
    }, [items, selectedL1Id]);

    // --- Handlers ---

    const handleUpdateL1 = async (id: number, updates: Partial<TodoItem>) => {
        // Build final updates including side effects (sync with backend logic)
        const finalUpdates = { ...updates };
        if (updates.expectedFinishedAt) {
            finalUpdates.crossDay = true;
        }
        if (updates.crossDay === false) {
            finalUpdates.expectedFinishedAt = null;
        }

        // 乐观更新
        setItems(prev => prev.map(item =>
            item.id === id ? { ...item, ...finalUpdates } : item
        ));
        try {
            await todoApi.updateTodo(id, updates);
        } catch (error) {
            console.error('Failed to update todo:', error);
            loadTodos(); // 回滚
        }
    };

    const handleDeleteL1 = async (id: number) => {
        if (selectedL1Id === id) setSelectedL1Id(null);
        // 乐观更新
        setItems(prev => prev.filter(item => item.id !== id));
        try {
            await todoApi.deleteTodo(id);
        } catch (error) {
            console.error('Failed to delete todo:', error);
            loadTodos(); // 回滚
        }
    };

    const handleUpdateL2 = async (subId: number, updates: Partial<SubTodoItem>) => {
        if (!selectedL1Id) return;
        // 乐观更新
        setItems(prev => prev.map(parent => {
            if (parent.id === selectedL1Id && parent.subItems) {
                return {
                    ...parent,
                    subItems: parent.subItems.map(sub =>
                        sub.id === subId ? { ...sub, ...updates } : sub
                    )
                };
            }
            return parent;
        }));
        try {
            await todoApi.updateSubTodo(subId, updates);
        } catch (error) {
            console.error('Failed to update sub todo:', error);
            loadTodos(); // 回滚
        }
    };

    const handleDeleteL2 = async (subId: number) => {
        if (!selectedL1Id) return;
        // 乐观更新
        setItems(prev => prev.map(parent => {
            if (parent.id === selectedL1Id && parent.subItems) {
                return {
                    ...parent,
                    subItems: parent.subItems.filter(sub => sub.id !== subId)
                };
            }
            return parent;
        }));
        try {
            await todoApi.deleteSubTodo(subId);
        } catch (error) {
            console.error('Failed to delete sub todo:', error);
            loadTodos(); // 回滚
        }
    };

    const handleCreateL1 = async (content: string) => {
        if (!content.trim()) return;
        // 随机选择颜色（排除白色 #FFFFFF，选择更有辨识度的颜色）
        const colorOptions = TODO_COLORS.slice(1); // 去掉第一个白色
        const randomColor = colorOptions[Math.floor(Math.random() * colorOptions.length)];
        try {
            const newItem = await todoApi.createTodo({
                content,
                date: selectedDate,
                linkToGoalId: selectedGoalId,
                color: randomColor
            });
            setItems(prev => [...prev, newItem]);
        } catch (error) {
            console.error('Failed to create todo:', error);
        }
    };

    const handleCreateL2 = async (content: string) => {
        if (!selectedL1Id || !content.trim()) return;
        try {
            const newSub = await todoApi.createSubTodo(selectedL1Id, content);
            setItems(prev => prev.map(parent => {
                if (parent.id === selectedL1Id) {
                    return {
                        ...parent,
                        subItems: [...(parent.subItems || []), newSub]
                    };
                }
                return parent;
            }));
        } catch (error) {
            console.error('Failed to create sub todo:', error);
        }
    };

    // --- Drag & Drop ---

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 2 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    const handleDragEndL1 = async (event: DragEndEvent) => {
        const { active, over } = event;
        if (over && active.id !== over.id) {
            const activeId = Number(active.id);
            const overId = Number(over.id);
            const oldIndex = filteredL1Items.findIndex((item) => item.id === activeId);
            const newIndex = filteredL1Items.findIndex((item) => item.id === overId);
            const newOrder = arrayMove<TodoItem>(filteredL1Items, oldIndex, newIndex);

            // 乐观更新
            setItems(currentItems => {
                const otherItems = currentItems.filter(item =>
                    !filteredL1Items.some(f => f.id === item.id)
                );
                return [...otherItems, ...newOrder];
            });

            // 同步到服务器
            try {
                await todoApi.reorderTodos(newOrder.map(item => item.id));
            } catch (error) {
                console.error('Failed to reorder todos:', error);
                loadTodos(); // 回滚
            }
        }
    };

    const handleDragEndL2 = async (event: DragEndEvent) => {
        const { active, over } = event;
        if (over && active.id !== over.id && selectedL1Id && selectedL1Item?.subItems) {
            const activeId = Number(active.id);
            const overId = Number(over.id);
            const oldIndex = selectedL1Item.subItems.findIndex((item) => item.id === activeId);
            const newIndex = selectedL1Item.subItems.findIndex((item) => item.id === overId);
            const newOrder = arrayMove<SubTodoItem>(selectedL1Item.subItems, oldIndex, newIndex);

            // 乐观更新
            setItems(currentItems => currentItems.map(parent => {
                if (parent.id === selectedL1Id) {
                    return { ...parent, subItems: newOrder };
                }
                return parent;
            }));

            // 同步到服务器
            try {
                await todoApi.reorderSubTodos(selectedL1Id, newOrder.map(item => item.id));
            } catch (error) {
                console.error('Failed to reorder sub todos:', error);
                loadTodos(); // 回滚
            }
        }
    };

    // Inputs state
    const [l1Input, setL1Input] = useState('');
    const [l2Input, setL2Input] = useState('');
    // 目标选择状态 - 用于给新任务绑定默认目标
    const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);

    // 日期范围选择弹窗状态
    const [showDateRangePicker, setShowDateRangePicker] = useState(false);

    return (
        <div className="flex-1 flex h-full overflow-hidden bg-[#F8FAFC]">

            {/* 1. LEFT PANE: DATE SELECTION */}
            <aside className="w-52 bg-white flex-col flex-shrink-0 px-3 py-4 border-r border-slate-100 z-10 flex">
                <WeekDayTreeSelector
                    selectedDate={selectedDate}
                    onDateChange={handleDateChange}
                />
            </aside>

            {/* 2. MIDDLE PANE: LEVEL 1 TODOS */}
            <div className="flex-1 min-w-[300px] max-w-md bg-[#F8FAFC] flex flex-col border-r border-slate-200/60 overflow-hidden">
                {/* 固定头部区域 */}
                <div className="flex-shrink-0 px-8 pt-8 pb-4">
                    <div className="flex items-center gap-3 mb-6">
                        <h3 className="text-lg font-black text-slate-800 tracking-tight">Today's Focus</h3>
                        <span className={`text-sm font-medium px-3 py-1 rounded-full ${dailyFocusContent
                            ? 'bg-blue-50 text-blue-600 border border-blue-100'
                            : 'bg-slate-50 text-slate-400 border border-slate-100'
                            }`}>
                            {dailyFocusContent || '未设置今日重点'}
                        </span>
                    </div>

                    {/* Create L1 Input with Goal Selector */}
                    <div className="flex flex-col bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden focus-within:ring-2 focus-within:ring-blue-100 focus-within:border-blue-300 transition-all">
                        {/* 目标选择器 - 上方 */}
                        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 bg-slate-50/30">
                            <Target size={14} className="text-blue-500 flex-shrink-0" />
                            <span className="text-sm font-semibold text-slate-500 flex-shrink-0">目标</span>
                            <select
                                value={selectedGoalId || ''}
                                onChange={(e) => setSelectedGoalId(e.target.value || null)}
                                className="flex-1 appearance-none bg-transparent text-sm font-semibold text-slate-700 outline-none cursor-pointer"
                            >
                                <option value="">无</option>
                                {activeGoals.map(g => (
                                    <option key={g.id} value={g.id}>{g.name}</option>
                                ))}
                            </select>
                            <ChevronDown size={14} className="text-slate-400 flex-shrink-0" />
                        </div>

                        {/* 输入框 - 下方 */}
                        <div className="relative group">
                            <input
                                type="text"
                                value={l1Input}
                                onChange={(e) => setL1Input(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                        handleCreateL1(l1Input);
                                        setL1Input('');
                                    }
                                }}
                                placeholder="Type to create a task..."
                                className="w-full bg-transparent px-4 py-4 pl-11 text-sm font-semibold outline-none"
                            />
                            <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 group-focus-within:text-blue-500 transition-colors">
                                <Plus size={18} />
                            </div>
                        </div>
                    </div>
                </div>

                {/* 可滚动的任务列表区域 - 隐藏滚动条 */}
                <div className="flex-1 overflow-y-auto px-8 pt-1 pb-8 scrollbar-hide" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                    <style>{`
                        .scrollbar-hide::-webkit-scrollbar {
                            display: none;
                        }
                    `}</style>
                    {/* Loading State */}
                    {loading ? (
                        <div className="flex items-center justify-center py-10">
                            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                        </div>
                    ) : (
                        /* L1 List */
                        <DndContext
                            id="dnd-l1"
                            sensors={sensors}
                            collisionDetection={pointerWithin}
                            onDragEnd={handleDragEndL1}
                        >
                            <SortableContext items={filteredL1Items.map(t => t.id)} strategy={verticalListSortingStrategy}>
                                <div className="space-y-2">
                                    {filteredL1Items.map(item => (
                                        <SortableTaskItem
                                            key={item.id}
                                            todo={item}
                                            isActive={item.id === selectedL1Id}
                                            onUpdate={handleUpdateL1}
                                            onDelete={handleDeleteL1}
                                            onSelect={setSelectedL1Id}
                                        />
                                    ))}
                                    {filteredL1Items.length === 0 && (
                                        <div className="text-center py-10 text-slate-300 text-xs font-bold italic">
                                            No tasks yet. Start by creating one!
                                        </div>
                                    )}
                                </div>
                            </SortableContext>
                        </DndContext>
                    )}
                </div>
            </div>

            {/* 3. RIGHT PANE: LEVEL 2 DETAILS */}
            <div className="flex-1 bg-white flex flex-col px-8 pt-4 pb-8 overflow-y-auto">
                {selectedL1Item ? (
                    <div className="w-full max-w-2xl animate-in fade-in slide-in-from-right-4 duration-300">
                        {/* Task Name (Header) */}
                        <div className="mb-6">
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 block">Task Name</label>
                            <input
                                type="text"
                                value={selectedL1Item.content}
                                onChange={(e) => handleUpdateL1(selectedL1Item.id, { content: e.target.value })}
                                className="w-full text-2xl font-bold text-slate-800 outline-none bg-transparent border-b border-transparent focus:border-slate-200 transition-all pb-1 placeholder-slate-300"
                            />
                        </div>

                        {/* 5-column Grid for Metadata */}
                        <div className="grid grid-cols-5 gap-2 mb-6">
                            {/* 1. Date Range - Single module with popup */}
                            <div
                                className="bg-slate-50/50 p-2.5 rounded-xl border border-slate-100 flex flex-col gap-1 hover:bg-white hover:shadow-sm transition-all group cursor-pointer relative"
                                onClick={() => setShowDateRangePicker(!showDateRangePicker)}
                            >
                                <div className="flex items-center gap-1.5 text-slate-400">
                                    <Calendar size={11} className="group-hover:text-blue-500 transition-colors" />
                                    <span className="text-[8px] font-bold uppercase tracking-wider">日期</span>
                                </div>
                                <div className="flex items-center gap-1 text-[10px] font-bold text-slate-700">
                                    <span className="truncate">{selectedL1Item.date?.slice(5) || '--'}</span>
                                    <span className="text-slate-400">→</span>
                                    <span className="truncate">{selectedL1Item.expectedFinishedAt?.slice(5) || '--'}</span>
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
                                                    value={selectedL1Item.date}
                                                    onChange={(e) => handleUpdateL1(selectedL1Item.id, { date: e.target.value })}
                                                    className="w-full px-3 py-2 text-sm font-semibold text-slate-700 bg-slate-50 border border-slate-200 rounded-lg outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                                                />
                                            </div>
                                            <div>
                                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">结束日期</label>
                                                <input
                                                    type="date"
                                                    value={selectedL1Item.expectedFinishedAt || ''}
                                                    onChange={(e) => handleUpdateL1(selectedL1Item.id, { expectedFinishedAt: e.target.value || null })}
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
                                onClick={() => handleUpdateL1(selectedL1Item.id, { crossDay: !selectedL1Item.crossDay })}
                                className={`p-2.5 rounded-xl border flex flex-col gap-1 cursor-pointer transition-all group ${selectedL1Item.crossDay
                                    ? 'bg-amber-50/50 border-amber-200 hover:bg-amber-100'
                                    : 'bg-slate-50/50 border-slate-100 hover:bg-white hover:shadow-sm'
                                    }`}
                                title="长期任务：每天都会出现直至完成"
                            >
                                <div className={`flex items-center gap-1.5 ${selectedL1Item.crossDay ? 'text-amber-600' : 'text-slate-400'}`}>
                                    <RefreshCw size={11} className="group-hover:text-amber-500 transition-colors" />
                                    <span className="text-[8px] font-bold uppercase tracking-wider">跨日</span>
                                </div>
                                <span className={`text-[10px] font-bold truncate ${selectedL1Item.crossDay ? 'text-amber-700' : 'text-slate-500'}`}>
                                    {selectedL1Item.crossDay ? '长期' : '单日'}
                                </span>
                            </div>

                            {/* 3. Goal Link */}
                            <div className="bg-slate-50/50 p-2.5 rounded-xl border border-slate-100 flex flex-col gap-1 hover:bg-white hover:shadow-sm transition-all group">
                                <div className="flex items-center gap-1.5 text-slate-400">
                                    <Target size={11} className="group-hover:text-orange-500 transition-colors" />
                                    <span className="text-[8px] font-bold uppercase tracking-wider">目标</span>
                                </div>
                                <select
                                    value={selectedL1Item.linkToGoalId || ''}
                                    onChange={(e) => handleUpdateL1(selectedL1Item.id, {
                                        linkToGoalId: e.target.value || null
                                    })}
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
                                    {TODO_COLORS.slice(0, 5).map(c => (
                                        <button
                                            key={c}
                                            onClick={() => handleUpdateL1(selectedL1Item.id, { color: c })}
                                            className={`w-3.5 h-3.5 rounded-full border border-slate-200 shadow-sm transition-transform hover:scale-110 ${selectedL1Item.color === c ? 'ring-2 ring-slate-400 scale-110' : ''}`}
                                            style={{ backgroundColor: c }}
                                        />
                                    ))}
                                </div>
                            </div>

                            {/* 5. Status Toggle */}
                            <div
                                onClick={() => handleUpdateL1(selectedL1Item.id, {
                                    state: selectedL1Item.state === 'completed' ? 'active' : 'completed'
                                } as any)}
                                className={`p-2.5 rounded-xl border flex flex-col gap-1 cursor-pointer transition-all ${selectedL1Item.state === 'completed'
                                    ? 'bg-green-50/50 border-green-200 hover:bg-green-100'
                                    : 'bg-slate-50/50 border-slate-100 hover:bg-white hover:shadow-sm hover:border-blue-200'
                                    }`}
                            >
                                <div className={`flex items-center gap-1.5 ${selectedL1Item.state === 'completed' ? 'text-green-600' : 'text-slate-400'}`}>
                                    {selectedL1Item.state === 'completed' ? <CheckCircle size={11} /> : <Activity size={11} />}
                                    <span className="text-[8px] font-bold uppercase tracking-wider">状态</span>
                                </div>
                                <span className={`text-[10px] font-bold truncate ${selectedL1Item.state === 'completed' ? 'text-green-700' : 'text-slate-700'}`}>
                                    {selectedL1Item.state === 'completed' ? '完成' : '进行中'}
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
                                value={l2Input}
                                onChange={(e) => setL2Input(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                        handleCreateL2(l2Input);
                                        setL2Input('');
                                    }
                                }}
                                placeholder="Create a sub-task..."
                                className="w-full bg-slate-50 border border-transparent rounded-xl px-4 py-3 text-sm font-medium outline-none focus:bg-white focus:border-blue-200 focus:ring-4 focus:ring-blue-50 transition-all placeholder-slate-400"
                            />
                        </div>

                        {/* Level 2 List */}
                        <DndContext
                            id="dnd-l2"
                            sensors={sensors}
                            collisionDetection={pointerWithin}
                            onDragEnd={handleDragEndL2}
                        >
                            <SortableContext items={(selectedL1Item.subItems || []).map(s => s.id)} strategy={verticalListSortingStrategy}>
                                <div className="space-y-2">
                                    {(selectedL1Item.subItems || []).map(sub => (
                                        <SortableTaskItem
                                            key={sub.id}
                                            todo={sub}
                                            isSubItem={true}
                                            onUpdate={handleUpdateL2}
                                            onDelete={handleDeleteL2}
                                        />
                                    ))}
                                    {(!selectedL1Item.subItems || selectedL1Item.subItems.length === 0) && (
                                        <div className="text-center py-10 text-slate-300 text-xs font-bold italic">
                                            No sub-tasks yet. Break it down!
                                        </div>
                                    )}
                                </div>
                            </SortableContext>
                        </DndContext>
                    </div>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-slate-300 pb-32">
                        <div className="w-24 h-24 bg-slate-50 rounded-[2rem] flex items-center justify-center mb-6">
                            <Target size={40} className="text-slate-200" />
                        </div>
                        <p className="text-sm font-bold uppercase tracking-widest">Select a task to view details</p>
                    </div>
                )}
            </div>

        </div>
    );
};

export default TodoTabView;
