import React, { useState, useRef, useEffect } from 'react';
import { Play, MoreHorizontal, ChevronDown, ChevronUp, Plus, Clock } from 'lucide-react';
import { HabitChain } from '../../../types/entities';
import { ChainNode } from './ChainNode';
import { useChainStore } from '../../../hooks/useChainStore';
import { ChainEditDialog } from '../../dialogs/ChainEditDialog';
import { NodeEditDialog } from '../../dialogs/NodeEditDialog';
import { NodeTimeDialog } from '../../dialogs/NodeTimeDialog';
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent
} from '@dnd-kit/core';
import {
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { restrictToVerticalAxis, restrictToParentElement } from '@dnd-kit/modifiers';

interface ChainCardProps {
    chain: HabitChain;
}

export const ChainCard: React.FC<ChainCardProps> = ({ chain }) => {
    const { deleteChain, reorderNodes } = useChainStore();
    const [isExpanded, setIsExpanded] = useState(false);
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [isEditOpen, setIsEditOpen] = useState(false);
    const [isAddNodeOpen, setIsAddNodeOpen] = useState(false);
    const [isTimeOpen, setIsTimeOpen] = useState(false);

    // Sort logic
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    const menuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false);
            }
        };
        if (isMenuOpen) document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isMenuOpen]);

    const displayNodes = isExpanded ? chain.nodes : chain.nodes.slice(0, 2);
    const hasMore = chain.nodes.length > 2;

    const handleDelete = async () => {
        if (!(await window.electronAPI.showConfirm({ message: '确认删除该链条及其所有节点吗？' }))) {
            await deleteChain(chain.id);
        }
    };

    const handleDragEnd = async (event: DragEndEvent) => {
        const { active, over } = event;
        if (over && active.id !== over.id) {
            const oldIndex = chain.nodes.findIndex((n) => n.id === active.id);
            const newIndex = chain.nodes.findIndex((n) => n.id === over.id);

            // Reorder array locally for the update payload
            const newNodes = Array.from(chain.nodes);
            const [moved] = newNodes.splice(oldIndex, 1);
            newNodes.splice(newIndex, 0, moved);

            // Create payload: { nodeId, sortOrder }
            const reorderData = newNodes.map((node, index) => ({
                nodeId: node.id,
                sortOrder: index + 1
            }));

            await reorderNodes(chain.id, reorderData);
        }
    };

    return (
        <>
            <div className="rounded-[20px] p-4 border border-neutral-100 bg-slate-50 flex flex-col gap-3 transition-colors hover:border-neutral-200 shrink-0 relative group">

                {/* Menu Action */}
                <div className="absolute top-2 right-2 z-20" ref={menuRef}>
                    <button
                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                        className={`p-1.5 rounded-lg transition-colors ${isMenuOpen ? 'bg-slate-200 text-slate-800' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-200 opacity-0 group-hover:opacity-100'}`}
                    >
                        <MoreHorizontal size={14} />
                    </button>
                    {isMenuOpen && (
                        <div className="absolute right-0 top-full mt-1 w-28 bg-white rounded-xl shadow-lg border border-slate-100 py-1 overflow-hidden">
                            <button
                                onClick={() => { setIsEditOpen(true); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 font-medium"
                            >
                                编辑链条
                            </button>
                            <button
                                onClick={() => { setIsAddNodeOpen(true); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-emerald-600 hover:bg-emerald-50 font-medium border-t border-slate-100"
                            >
                                添加节点<Plus size={12} className="inline mr-1" />
                            </button>
                            <div className="h-px bg-slate-100 my-1"></div>
                            <button
                                onClick={() => { handleDelete(); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-red-600 hover:bg-red-50 font-medium"
                            >
                                删除
                            </button>
                        </div>
                    )}
                </div>

                <div className="flex justify-between items-start mt-1 pr-6">
                    <div>
                        <h3 className="text-[14px] font-bold text-neutral-900 tracking-tight leading-tight truncate max-w-[140px]">{chain.name}</h3>
                        {chain.description && (
                            <p className="text-[10px] text-slate-400 mt-0.5 truncate max-w-[180px]">{chain.description}</p>
                        )}
                    </div>
                </div>

                <div className="flex flex-col gap-2 w-full mt-1.5 relative">
                    <DndContext
                        sensors={sensors}
                        collisionDetection={closestCenter}
                        onDragEnd={handleDragEnd}
                        modifiers={[restrictToVerticalAxis, restrictToParentElement]}
                    >
                        <SortableContext items={displayNodes.map(n => n.id)} strategy={verticalListSortingStrategy}>
                            {displayNodes.map((node) => (
                                <ChainNode key={node.id} node={node} chainId={chain.id} />
                            ))}
                        </SortableContext>
                    </DndContext>

                    {hasMore && !isExpanded && (
                        <div
                            onClick={() => setIsExpanded(true)}
                            className="relative z-10 px-3 py-2 rounded-[12px] border border-dashed border-neutral-300 bg-white/50 text-neutral-400 hover:bg-white flex items-center justify-between w-full cursor-pointer transition-colors group/expand"
                        >
                            <div className="flex items-center justify-start w-5 h-5 shrink-0">
                                <ChevronDown size={14} className="opacity-0 group-hover/expand:opacity-100 transition-opacity absolute" />
                                <div className="w-1 h-1 rounded-full bg-neutral-300 ml-1 group-hover/expand:opacity-0 transition-opacity"></div>
                            </div>
                            <span className="text-[10px] font-bold text-center flex-1">+{chain.nodes.length - 2} pending steps</span>
                            <div className="w-5 h-5 shrink-0"></div>
                        </div>
                    )}

                    {isExpanded && hasMore && (
                        <div
                            onClick={() => setIsExpanded(false)}
                            className="flex justify-center mt-1 cursor-pointer text-slate-400 hover:text-slate-600 transition-colors py-1"
                        >
                            <ChevronUp size={16} />
                        </div>
                    )}
                </div>

                <div className="flex items-center justify-between mt-2 pt-3 border-t border-slate-100/60">
                    <span className="text-[9px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wide bg-white border border-neutral-100 text-neutral-500 shadow-sm flex items-center gap-1">
                        <span className={`w-1.5 h-1.5 rounded-full ${chain.showInTimeline ? 'bg-emerald-500' : 'bg-slate-300'}`}></span>
                        {chain.nodes.length} steps
                    </span>
                    <button
                        onClick={() => setIsTimeOpen(true)}
                        className={`text-[10px] font-bold transition-colors flex items-center gap-1 bg-white border px-2 py-1 rounded-lg hover:shadow-sm ${chain.showInTimeline ? 'text-indigo-500 hover:text-indigo-600 border-indigo-100 bg-indigo-50/50' : 'text-neutral-500 hover:text-indigo-500 border-neutral-100'}`}
                    >
                        {chain.showInTimeline ? (
                            <><Clock size={10} className="stroke-[3px]" /> 设置时间线</>
                        ) : (
                            <><Plus size={10} className="stroke-[3px]" /> 加入时间线</>
                        )}
                    </button>
                </div>
            </div>

            <ChainEditDialog
                isOpen={isEditOpen}
                onClose={() => setIsEditOpen(false)}
                chain={chain}
            />

            <NodeEditDialog
                isOpen={isAddNodeOpen}
                onClose={() => setIsAddNodeOpen(false)}
                chainId={chain.id}
                node={null}
            />

            <NodeTimeDialog
                isOpen={isTimeOpen}
                onClose={() => setIsTimeOpen(false)}
                chain={chain}
            />
        </>
    );
};
