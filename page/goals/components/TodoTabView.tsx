
import React, { useState, useMemo, useEffect } from 'react';
import {
    Check,
    Target,
    Plus,
    Link as LinkIcon,
    GripVertical,
    Calendar,
    MoreHorizontal,
    Clock,
    Trash2,
    Edit2,
    Palette,
    Activity,
    CheckCircle
} from 'lucide-react';
import {
    DndContext,
    closestCenter,
    pointerWithin,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragOverlay,
    defaultDropAnimationSideEffects,
    DragStartEvent,
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
import { GoalItem } from '../types';
import { MOCK_TODOS, MOCK_GOALS_LIST } from '../api';

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

// --- Sortable Task Item Component (Level 1 & Level 2 Generic) ---
interface SortableTaskItemProps {
    todo: GoalItem;
    isActive?: boolean;
    isSubItem?: boolean;
    onUpdate: (id: string, updates: Partial<GoalItem>) => void;
    onSelect?: (id: string) => void;
    onDelete: (id: string) => void;
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
        // Remove transition when dragging to eliminate "lag" feeling
        transition: isDragging ? undefined : transition,
        opacity: isDragging ? 0.6 : 1,
        zIndex: isDragging ? 50 : 'auto',
        position: 'relative',
        backgroundColor: todo.color || '#FFFFFF'
    };

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
                className="absolute left-3 top-1/2 -translate-y-1/2 p-1 text-slate-300 opacity-0 group-hover:opacity-100 cursor-grab active:cursor-grabbing hover:text-slate-500 transition-all z-20"
            >
                <GripVertical size={14} />
            </div>

            {/* Completion Checkbox */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onUpdate(todo.id, { completed: !todo.completed });
                }}
                className={`w-5 h-5 rounded-lg border-[1.5px] flex items-center justify-center transition-all flex-shrink-0 ${todo.completed
                        ? 'bg-slate-800 border-slate-800'
                        : 'border-slate-300 bg-white/50 hover:border-blue-400'
                    }`}
            >
                {todo.completed && <Check size={12} className="text-white" strokeWidth={3} />}
            </button>

            {/* Text Input - Direct Edit */}
            <div className="flex-1 min-w-0">
                <input
                    type="text"
                    value={todo.text}
                    onChange={(e) => onUpdate(todo.id, { text: e.target.value })}
                    className={`w-full bg-transparent border-none outline-none text-sm font-medium p-0 ${todo.completed ? 'text-slate-400 line-through decoration-slate-300' : 'text-slate-700'
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

const TodoTabView: React.FC = () => {
    const [selectedDate, setSelectedDate] = useState('2025-12-01');
    const dates = ['2025-12-01', '2025-12-02', '2025-12-03', '2025-12-04'];

    const [items, setItems] = useState<GoalItem[]>(MOCK_TODOS);
    const [selectedL1Id, setSelectedL1Id] = useState<string | null>(null);

    // Filter items based on Date (Level 1 items usually have dates)
    // For hierarchical structure, we filter top-level items by date
    const filteredL1Items = useMemo(() => {
        return items.filter(t => t.date === selectedDate);
    }, [items, selectedDate]);

    const selectedL1Item = useMemo(() => {
        return items.find(t => t.id === selectedL1Id) || null;
    }, [items, selectedL1Id]);

    // --- Handlers ---

    const handleUpdateL1 = (id: string, updates: Partial<GoalItem>) => {
        setItems(prev => prev.map(item => item.id === id ? { ...item, ...updates } : item));
    };

    const handleDeleteL1 = (id: string) => {
        if (selectedL1Id === id) setSelectedL1Id(null);
        setItems(prev => prev.filter(item => item.id !== id));
    };

    const handleUpdateL2 = (subId: string, updates: Partial<GoalItem>) => {
        if (!selectedL1Id) return;
        setItems(prev => prev.map(parent => {
            if (parent.id === selectedL1Id && parent.subItems) {
                return {
                    ...parent,
                    subItems: parent.subItems.map(sub => sub.id === subId ? { ...sub, ...updates } : sub)
                };
            }
            return parent;
        }));
    };

    const handleDeleteL2 = (subId: string) => {
        if (!selectedL1Id) return;
        setItems(prev => prev.map(parent => {
            if (parent.id === selectedL1Id && parent.subItems) {
                return {
                    ...parent,
                    subItems: parent.subItems.filter(sub => sub.id !== subId)
                };
            }
            return parent;
        }));
    };

    const handleCreateL1 = (text: string) => {
        if (!text.trim()) return;
        const newItem: GoalItem = {
            id: `l1-${Date.now()}`,
            text,
            completed: false,
            date: selectedDate,
            subItems: [],
            color: '#FFFFFF'
        };
        setItems([...items, newItem]);
    };

    const handleCreateL2 = (text: string) => {
        if (!selectedL1Id || !text.trim()) return;
        setItems(prev => prev.map(parent => {
            if (parent.id === selectedL1Id) {
                const newSub: GoalItem = {
                    id: `l2-${Date.now()}`,
                    text,
                    completed: false,
                    date: selectedDate
                };
                return {
                    ...parent,
                    subItems: [...(parent.subItems || []), newSub]
                };
            }
            return parent;
        }));
    };

    // --- Drag & Drop ---

    const sensors = useSensors(
        // Reduced activation distance to 2px for snappier drag start (less delay)
        useSensor(PointerSensor, { activationConstraint: { distance: 2 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    const handleDragEndL1 = (event: DragEndEvent) => {
        const { active, over } = event;
        if (over && active.id !== over.id) {
            setItems((currentItems) => {
                const oldIndex = currentItems.findIndex((item) => item.id === active.id);
                const newIndex = currentItems.findIndex((item) => item.id === over.id);
                return arrayMove(currentItems, oldIndex, newIndex);
            });
        }
    };

    const handleDragEndL2 = (event: DragEndEvent) => {
        const { active, over } = event;
        if (over && active.id !== over.id && selectedL1Id) {
            setItems((currentItems) => {
                return currentItems.map(parent => {
                    if (parent.id === selectedL1Id && parent.subItems) {
                        const oldIndex = parent.subItems.findIndex((item) => item.id === active.id);
                        const newIndex = parent.subItems.findIndex((item) => item.id === over.id);
                        return { ...parent, subItems: arrayMove(parent.subItems, oldIndex, newIndex) };
                    }
                    return parent;
                });
            });
        }
    };

    // Inputs state
    const [l1Input, setL1Input] = useState('');
    const [l2Input, setL2Input] = useState('');

    return (
        <div className="flex-1 flex h-full overflow-hidden bg-[#F8FAFC]">

            {/* 1. LEFT PANE: DATE SELECTION */}
            <aside className="w-48 bg-white flex-col flex-shrink-0 pt-10 px-4 border-r border-slate-100 z-10 flex">
                <h4 className="text-[10px] font-black text-slate-300 uppercase tracking-[0.25em] mb-6 pl-4">Calendar</h4>
                <div className="space-y-2 relative">
                    <div className="absolute left-[19px] top-2 bottom-2 w-[2px] bg-slate-50 rounded-full" />
                    {dates.map(date => {
                        const isSelected = selectedDate === date;
                        return (
                            <button
                                key={date}
                                onClick={() => { setSelectedDate(date); setSelectedL1Id(null); }}
                                className={`w-full text-left py-3 pl-8 transition-all flex items-center group relative rounded-xl ${isSelected
                                        ? 'bg-blue-50/50 text-blue-700'
                                        : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'
                                    }`}
                            >
                                <div className={`absolute left-[15px] top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border-2 transition-all z-10 ${isSelected
                                        ? 'bg-blue-600 border-blue-600 scale-110 shadow-lg shadow-blue-500/30'
                                        : 'bg-white border-slate-300 group-hover:border-slate-400'
                                    }`} />
                                <span className={`text-xs font-bold tracking-tight ${isSelected ? 'scale-105' : ''}`}>{date}</span>
                            </button>
                        );
                    })}
                </div>
            </aside>

            {/* 2. MIDDLE PANE: LEVEL 1 TODOS */}
            <div className="flex-1 min-w-[300px] max-w-md bg-[#F8FAFC] flex flex-col border-r border-slate-200/60">
                <div className="p-8">
                    <h3 className="text-lg font-black text-slate-800 tracking-tight mb-6">Today's Focus</h3>

                    {/* Create L1 Input */}
                    <div className="mb-6 relative group">
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
                            className="w-full bg-white border border-slate-200 rounded-2xl px-4 py-4 pl-11 shadow-sm text-sm font-semibold outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300 transition-all"
                        />
                        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300 group-focus-within:text-blue-500 transition-colors">
                            <Plus size={18} />
                        </div>
                    </div>

                    {/* L1 List */}
                    <DndContext
                        id="dnd-l1"
                        sensors={sensors}
                        // Using pointerWithin provides a more stable sort feel than closestCenter for lists
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
                            </div>
                        </SortableContext>
                    </DndContext>
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
                                value={selectedL1Item.text}
                                onChange={(e) => handleUpdateL1(selectedL1Item.id, { text: e.target.value })}
                                className="w-full text-2xl font-bold text-slate-800 outline-none bg-transparent border-b border-transparent focus:border-slate-200 transition-all pb-1 placeholder-slate-300"
                            />
                        </div>

                        {/* 2x2 Grid for Metadata */}
                        <div className="grid grid-cols-2 gap-4 mb-8">
                            {/* 1. Date Range */}
                            <div className="bg-slate-50/50 p-4 rounded-2xl border border-slate-100 flex flex-col justify-between gap-2 hover:bg-white hover:shadow-sm transition-all group">
                                <div className="flex items-center gap-2 text-slate-400">
                                    <Calendar size={14} className="group-hover:text-blue-500 transition-colors" />
                                    <span className="text-[10px] font-bold uppercase tracking-wider">Duration</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <input
                                        type="date"
                                        value={selectedL1Item.startDate || selectedDate}
                                        onChange={(e) => handleUpdateL1(selectedL1Item.id, { startDate: e.target.value })}
                                        className="bg-transparent text-xs font-bold text-slate-700 w-full outline-none p-0 cursor-pointer"
                                    />
                                </div>
                            </div>

                            {/* 2. Color Selection */}
                            <div className="bg-slate-50/50 p-4 rounded-2xl border border-slate-100 flex flex-col justify-between gap-2 hover:bg-white hover:shadow-sm transition-all group">
                                <div className="flex items-center gap-2 text-slate-400">
                                    <Palette size={14} className="group-hover:text-purple-500 transition-colors" />
                                    <span className="text-[10px] font-bold uppercase tracking-wider">Color</span>
                                </div>
                                <div className="flex gap-1.5 flex-wrap">
                                    {TODO_COLORS.slice(0, 5).map(c => (
                                        <button
                                            key={c}
                                            onClick={() => handleUpdateL1(selectedL1Item.id, { color: c })}
                                            className={`w-4 h-4 rounded-full border border-slate-200 shadow-sm transition-transform hover:scale-110 ${selectedL1Item.color === c ? 'ring-2 ring-slate-400 scale-110' : ''}`}
                                            style={{ backgroundColor: c }}
                                        />
                                    ))}
                                </div>
                            </div>

                            {/* 3. Link Goal */}
                            <div className="bg-slate-50/50 p-4 rounded-2xl border border-slate-100 flex flex-col justify-between gap-2 hover:bg-white hover:shadow-sm transition-all group">
                                <div className="flex items-center gap-2 text-slate-400">
                                    <Target size={14} className="group-hover:text-orange-500 transition-colors" />
                                    <span className="text-[10px] font-bold uppercase tracking-wider">Goal Link</span>
                                </div>
                                <select
                                    value={selectedL1Item.linkToGoalId || ''}
                                    onChange={(e) => handleUpdateL1(selectedL1Item.id, { linkToGoalId: e.target.value })}
                                    className="bg-transparent text-xs font-bold text-slate-700 w-full outline-none -ml-1 cursor-pointer"
                                >
                                    <option value="">No Goal</option>
                                    {MOCK_GOALS_LIST.map(g => (
                                        <option key={g.id} value={g.id}>{g.alias || g.name}</option>
                                    ))}
                                </select>
                            </div>

                            {/* 4. Status Toggle */}
                            <div
                                onClick={() => handleUpdateL1(selectedL1Item.id, { completed: !selectedL1Item.completed })}
                                className={`p-4 rounded-2xl border flex flex-col justify-between gap-2 cursor-pointer transition-all ${selectedL1Item.completed
                                        ? 'bg-green-50/50 border-green-200 hover:bg-green-100'
                                        : 'bg-slate-50/50 border-slate-100 hover:bg-white hover:shadow-sm hover:border-blue-200'
                                    }`}
                            >
                                <div className={`flex items-center gap-2 ${selectedL1Item.completed ? 'text-green-600' : 'text-slate-400'}`}>
                                    {selectedL1Item.completed ? <CheckCircle size={14} /> : <Activity size={14} />}
                                    <span className="text-[10px] font-bold uppercase tracking-wider">Status</span>
                                </div>
                                <div className={`text-xs font-bold ${selectedL1Item.completed ? 'text-green-700' : 'text-slate-700'}`}>
                                    {selectedL1Item.completed ? 'Completed' : 'In Progress'}
                                </div>
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
                            // Using pointerWithin provides a more stable sort feel than closestCenter for lists
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
