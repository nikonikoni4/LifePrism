import React from 'react';
import { Plus, GripVertical, Flag, Trash2 } from 'lucide-react';
import {
    DndContext,
    closestCenter,
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
    useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { EditableMilestone } from './types';

interface SortableMilestoneEditItemProps {
    milestone: EditableMilestone;
    onUpdate: (id: string, content: string) => void;
    onDelete: (id: string) => void;
}

const SortableMilestoneEditItem: React.FC<SortableMilestoneEditItemProps> = ({
    milestone,
    onUpdate,
    onDelete
}) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: milestone.id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    return (
        <div
            ref={setNodeRef}
            style={style}
            className="flex items-center gap-2 bg-slate-50 rounded-xl p-3 border border-slate-200 group"
        >
            <div
                {...attributes}
                {...listeners}
                className="cursor-grab text-slate-300 hover:text-slate-500 p-1"
            >
                <GripVertical size={16} />
            </div>
            <Flag size={14} className="text-orange-400 flex-shrink-0" />
            <input
                type="text"
                value={milestone.content}
                onChange={(e) => onUpdate(milestone.id, e.target.value)}
                placeholder="Milestone description..."
                className="flex-1 bg-transparent border-none outline-none text-sm text-slate-700 font-medium"
            />
            <button
                onClick={() => onDelete(milestone.id)}
                className="p-1 text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
            >
                <Trash2 size={14} />
            </button>
        </div>
    );
};

export interface MilestoneEditorProps {
    milestones: EditableMilestone[];
    onChange: (milestones: EditableMilestone[]) => void;
    label?: string;
    addButtonText?: string;
    maxHeight?: string;
}

const MilestoneEditor: React.FC<MilestoneEditorProps> = ({
    milestones,
    onChange,
    label = 'Milestones',
    addButtonText = 'Add Milestone',
    maxHeight = '12rem'
}) => {
    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    const handleAdd = () => {
        const newId = `m-${Date.now()}`;
        const maxOrder = milestones.length > 0 ? Math.max(...milestones.map(m => m.orderIndex)) : -1;
        onChange([...milestones, { id: newId, content: '', orderIndex: maxOrder + 1 }]);
    };

    const handleUpdate = (id: string, content: string) => {
        onChange(milestones.map(m => m.id === id ? { ...m, content } : m));
    };

    const handleDelete = (id: string) => {
        onChange(milestones.filter(m => m.id !== id));
    };

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event;
        if (over && active.id !== over.id) {
            const oldIndex = milestones.findIndex(m => m.id === active.id);
            const newIndex = milestones.findIndex(m => m.id === over.id);
            const newMilestones = arrayMove(milestones, oldIndex, newIndex);
            onChange(newMilestones.map((m, i) => ({ ...m, orderIndex: i })));
        }
    };

    return (
        <div className="space-y-3">
            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                <Flag size={12} />
                {label}
            </label>

            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                <SortableContext items={milestones.map(m => m.id)} strategy={verticalListSortingStrategy}>
                    <div className="space-y-2 overflow-y-auto pr-1" style={{ maxHeight }}>
                        {milestones.map(milestone => (
                            <SortableMilestoneEditItem
                                key={milestone.id}
                                milestone={milestone}
                                onUpdate={handleUpdate}
                                onDelete={handleDelete}
                            />
                        ))}
                    </div>
                </SortableContext>
            </DndContext>

            <button
                type="button"
                onClick={handleAdd}
                className="flex items-center gap-2 px-4 py-2 text-sm text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
            >
                <Plus size={14} />
                {addButtonText}
            </button>
        </div>
    );
};

export default MilestoneEditor;