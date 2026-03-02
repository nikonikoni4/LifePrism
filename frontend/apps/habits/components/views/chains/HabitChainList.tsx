import React, { useState } from 'react';
import { ListTree, Plus, Link2 } from 'lucide-react';
import { useChainStore } from '../../../hooks/useChainStore';
import { ChainCard } from './ChainCard';
import { ChainEditDialog } from '../../dialogs/ChainEditDialog';

export const HabitChainList: React.FC = () => {
    const { chains } = useChainStore();
    const [isCreateOpen, setIsCreateOpen] = useState(false);

    return (
        <div className="col-span-12 lg:col-span-3 bg-[linear-gradient(180deg,#FFFFFF_0%,#F8FAFC_100%)] rounded-[24px] p-6 h-full flex flex-col overflow-hidden shadow-[0_10px_28px_rgba(15,23,42,0.08)] border border-slate-100/80">
            <div className="flex items-center justify-between mb-6 shrink-0">
                <h2 className="text-[14px] font-semibold text-slate-700 uppercase tracking-[0.02em] flex items-center gap-2">
                    <ListTree size={14} className="text-emerald-500" /> 习惯链条
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
                {chains.length === 0 ? (
                    <div className="flex flex-col items-center justify-center flex-1 text-center py-10">
                        <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center mb-3">
                            <Link2 size={18} className="text-slate-300" />
                        </div>
                        <p className="text-sm text-slate-600 font-semibold">暂无链条</p>
                        <p className="text-xs text-slate-500 mt-1">将多个习惯串联成链条</p>
                    </div>
                ) : (
                    chains.map((chain) => (
                        <ChainCard key={chain.id} chain={chain} />
                    ))
                )}
            </div>

            <ChainEditDialog
                isOpen={isCreateOpen}
                onClose={() => setIsCreateOpen(false)}
                chain={null}
            />
        </div>
    );
};
