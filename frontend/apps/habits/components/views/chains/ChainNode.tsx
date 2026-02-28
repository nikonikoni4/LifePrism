import React, { useState, useRef, useEffect } from 'react';
import { Check, GripVertical, MoreHorizontal } from 'lucide-react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { HabitChainNode } from '../../../types/entities';
import { NodeEditDialog } from '../../dialogs/NodeEditDialog';
import { useChainStore } from '../../../hooks/useChainStore';

interface ChainNodeProps {
    node: HabitChainNode;
    chainId: number;
}

export const ChainNode: React.FC<ChainNodeProps> = ({ node, chainId }) => {
    const isHabit = !!node.habitId;
    const { deleteNode } = useChainStore();
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [isEditOpen, setIsEditOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging
    } = useSortable({ id: node.id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 50 : 10,
        opacity: isDragging ? 0.8 : 1,
    };

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false);
            }
        };
        if (isMenuOpen) document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isMenuOpen]);

    const handleDelete = async () => {
        if (window.confirm('确认删除该节点吗？')) {
            await deleteNode(chainId, node.id);
        }
    };

    return (
        <>
            <div
                ref={setNodeRef}
                style={style}
                className={`relative px-3 py-2 rounded-[12px] border flex items-center justify-between w-full transition-shadow group/node ${isHabit
                        ? 'bg-emerald-500 text-white border-emerald-600 shadow-sm shadow-emerald-500/20'
                        : 'bg-white border-neutral-200 text-neutral-600 shadow-sm'
                    } ${isDragging ? 'shadow-lg ring-2 ring-indigo-500/50' : ''}`}
            >
                {/* Left: Drag Handle */}
                <div
                    {...attributes}
                    {...listeners}
                    className="flex items-center justify-start w-5 h-5 shrink-0 cursor-grab active:cursor-grabbing text-current opacity-60 hover:opacity-100"
                >
                    <GripVertical size={14} />
                </div>

                {/* Left: Node dot / icon indicator */}
                <div className="flex items-center justify-center w-5 h-5 shrink-0 mr-1 ml-1">
                    {isHabit ? (
                        <Check size={12} strokeWidth={4} className="text-white" />
                    ) : (
                        <div className="w-1.5 h-1.5 rounded-full bg-neutral-300"></div>
                    )}
                </div>

                {/* Center: Text */}
                <span className="text-[11px] font-bold tracking-tight truncate flex-1 text-center">{node.name}</span>

                {/* Right: Actions Menu */}
                <div className="w-10 h-5 shrink-0 flex items-center justify-end relative" ref={menuRef}>
                    <button
                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                        className={`p-1 rounded-md transition-colors ${isMenuOpen
                                ? (isHabit ? 'bg-emerald-600' : 'bg-slate-200')
                                : `opacity-0 group-hover/node:opacity-100 ${isHabit ? 'hover:bg-emerald-600' : 'hover:bg-slate-100'}`
                            }`}
                    >
                        <MoreHorizontal size={14} className={isHabit ? "text-emerald-100" : "text-slate-400"} />
                    </button>
                    {isMenuOpen && (
                        <div className="absolute right-0 top-full mt-1 w-24 bg-white rounded-lg shadow-lg border border-slate-100 py-1 overflow-hidden z-20">
                            <button
                                onClick={() => { setIsEditOpen(true); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 font-medium"
                            >
                                编辑
                            </button>
                            <button
                                onClick={() => { handleDelete(); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-red-600 hover:bg-red-50 font-medium"
                            >
                                删除
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Edit Dialog */}
            <NodeEditDialog
                isOpen={isEditOpen}
                onClose={() => setIsEditOpen(false)}
                chainId={chainId}
                node={node}
            />
        </>
    );
};
