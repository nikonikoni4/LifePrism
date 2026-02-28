import React, { useState } from 'react';
import { ListTree, Plus } from 'lucide-react';
import { useChainStore } from '../../../hooks/useChainStore';
import { ChainCard } from './ChainCard';
import { ChainEditDialog } from '../../dialogs/ChainEditDialog';

export const HabitChainList: React.FC = () => {
    const { chains } = useChainStore();
    const [isCreateOpen, setIsCreateOpen] = useState(false);

    return (
        <div className="col-span-12 lg:col-span-3 bg-white rounded-[24px] p-6 h-full flex flex-col overflow-hidden shadow-sm border border-neutral-100">
            <div className="flex items-center justify-between mb-6 shrink-0">
                <h2 className="text-[12px] font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2">
                    <ListTree size={14} className="text-emerald-500" /> Activity Chains
                </h2>
                <div className="flex items-center gap-2">
                    <button className="text-[10px] font-bold text-neutral-400 hover:text-neutral-900 transition-colors uppercase tracking-wider">
                        All
                    </button>
                    <button
                        onClick={() => setIsCreateOpen(true)}
                        className="p-1 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-full transition-colors"
                        title="新建链条"
                    >
                        <Plus size={16} />
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col gap-4 pr-2">
                {chains.map((chain) => (
                    <ChainCard key={chain.id} chain={chain} />
                ))}
            </div>

            <ChainEditDialog
                isOpen={isCreateOpen}
                onClose={() => setIsCreateOpen(false)}
                chain={null}
            />
        </div>
    );
};
