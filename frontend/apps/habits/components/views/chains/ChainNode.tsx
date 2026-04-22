import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { computePosition, autoUpdate, flip, shift, offset } from '@floating-ui/dom';
import { Check, Clock3, GripVertical, MoreHorizontal } from 'lucide-react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { HabitChainNode } from '../../../types/entities';
import { NodeEditDialog } from '../../dialogs/NodeEditDialog';
import { useChainStore } from '../../../hooks/useChainStore';

interface ChainNodeProps {
    node: HabitChainNode;
    chainId: number;
}

type NodeVisualType = 'habit' | 'anchor' | 'plain';

interface NodeColorTheme {
    container: string;
    indicator: string;
    dot: string;
    menuOpen: string;
    menuHover: string;
    menuIcon: string;
}

const NODE_COLOR_THEMES: NodeColorTheme[] = [
    {
        container: 'bg-emerald-50 border-emerald-200 text-emerald-900 shadow-sm shadow-emerald-100/60',
        indicator: 'text-emerald-600',
        dot: 'bg-emerald-400',
        menuOpen: 'bg-emerald-100',
        menuHover: 'hover:bg-emerald-100',
        menuIcon: 'text-emerald-600',
    },
    {
        container: 'bg-sky-50 border-sky-200 text-sky-900 shadow-sm shadow-sky-100/60',
        indicator: 'text-sky-600',
        dot: 'bg-sky-400',
        menuOpen: 'bg-sky-100',
        menuHover: 'hover:bg-sky-100',
        menuIcon: 'text-sky-600',
    },
    {
        container: 'bg-amber-50 border-amber-200 text-amber-900 shadow-sm shadow-amber-100/60',
        indicator: 'text-amber-600',
        dot: 'bg-amber-400',
        menuOpen: 'bg-amber-100',
        menuHover: 'hover:bg-amber-100',
        menuIcon: 'text-amber-600',
    },
    {
        container: 'bg-rose-50 border-rose-200 text-rose-900 shadow-sm shadow-rose-100/60',
        indicator: 'text-rose-600',
        dot: 'bg-rose-400',
        menuOpen: 'bg-rose-100',
        menuHover: 'hover:bg-rose-100',
        menuIcon: 'text-rose-600',
    },
    {
        container: 'bg-teal-50 border-teal-200 text-teal-900 shadow-sm shadow-teal-100/60',
        indicator: 'text-teal-600',
        dot: 'bg-teal-400',
        menuOpen: 'bg-teal-100',
        menuHover: 'hover:bg-teal-100',
        menuIcon: 'text-teal-600',
    },
];

const getNodeVisualType = (node: HabitChainNode): NodeVisualType => {
    if (node.habitId) return 'habit';
    if (node.triggerTime) return 'anchor';
    return 'plain';
};

export const ChainNode: React.FC<ChainNodeProps> = ({ node, chainId }) => {
    const nodeType = getNodeVisualType(node);
    const safeSortOrder = Number(node.sortOrder) || 1;
    const theme = NODE_COLOR_THEMES[Math.max(safeSortOrder - 1, 0) % NODE_COLOR_THEMES.length] || NODE_COLOR_THEMES[0];
    const { deleteNode } = useChainStore();
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [isEditOpen, setIsEditOpen] = useState(false);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const floatingRef = useRef<HTMLDivElement>(null);

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
        if (!isMenuOpen || !triggerRef.current || !floatingRef.current) return;
        
        const cleanup = autoUpdate(triggerRef.current, floatingRef.current, () => {
            if (!triggerRef.current || !floatingRef.current) return;
            computePosition(triggerRef.current, floatingRef.current, {
                placement: 'bottom-end',
                middleware: [offset(4), flip(), shift({ padding: 8 })]
            }).then(({ x, y }) => {
                if (floatingRef.current) {
                    floatingRef.current.style.left = `${x}px`;
                    floatingRef.current.style.top = `${y}px`;
                }
            });
        });
        
        return cleanup;
    }, [isMenuOpen]);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            const path = event.composedPath();
            const clickTrigger = triggerRef.current && path.includes(triggerRef.current);
            const clickFloating = floatingRef.current && path.includes(floatingRef.current);
            
            if (!clickTrigger && !clickFloating) {
                setIsMenuOpen(false);
            }
        };
        if (isMenuOpen) document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isMenuOpen]);

    const handleDelete = async () => {
        if (!(await window.electronAPI.showConfirm({ message: '确认删除该节点吗？' }))) {
            await deleteNode(chainId, node.id);
        }
    };

    return (
        <>
            <div
                ref={setNodeRef}
                style={style}
                className={`relative px-3 py-2 rounded-[12px] border flex items-center justify-between w-full transition-shadow group/node ${theme.container} ${isDragging ? 'shadow-lg ring-2 ring-indigo-500/50' : ''}`}
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
                    {nodeType === 'habit' && <Check size={12} strokeWidth={3.5} className={theme.indicator} />}
                    {nodeType === 'anchor' && <Clock3 size={12} strokeWidth={3} className={theme.indicator} />}
                    {nodeType === 'plain' && <div className={`w-1.5 h-1.5 rounded-full ${theme.dot}`}></div>}
                </div>

                {/* Center: Text */}
                <span className="text-[11px] font-bold tracking-tight truncate flex-1 text-center">{node.name}</span>

                {/* Right: Actions Menu */}
                <div className="w-10 h-5 shrink-0 flex items-center justify-end relative z-50">
                    <button
                        ref={triggerRef}
                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                        className={`p-1 rounded-md transition-colors ${isMenuOpen
                                ? theme.menuOpen
                                : `opacity-0 group-hover/node:opacity-100 ${theme.menuHover}`
                            }`}
                    >
                        <MoreHorizontal size={14} className={theme.menuIcon} />
                    </button>
                    {isMenuOpen && typeof document !== 'undefined' && createPortal(
                        <div 
                            ref={floatingRef}
                            className="absolute top-0 left-0 w-24 bg-white rounded-lg shadow-lg border border-slate-100 py-1 z-[9999]"
                        >
                            <button
                                onClick={(e) => { e.stopPropagation(); setIsEditOpen(true); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 font-medium"
                            >
                                编辑
                            </button>
                            <button
                                onClick={(e) => { e.stopPropagation(); handleDelete(); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-red-600 hover:bg-red-50 font-medium"
                            >
                                删除
                            </button>
                        </div>,
                        document.body
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
