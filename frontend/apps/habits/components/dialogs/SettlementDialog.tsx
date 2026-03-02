import React from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, TrendingUp, TrendingDown, Target, Shield } from 'lucide-react';
import { useSettlementStore } from '../../hooks/useSettlementStore';
import { useHabitStore } from '../../hooks/useHabitStore';
import { useStatsStore } from '../../hooks/useStatsStore';
import { SettlementItem } from '../../types/backend';
import { SettlementBackfillView } from './SettlementBackfillView';

export const SettlementDialog: React.FC = () => {
    const {
        settlements,
        isDialogOpen,
        backfillState,
        closeDialog,
        dismissSettlement,
        openBackfill,
    } = useSettlementStore();
    const { pauseHabit, resumeHabit, fetchHabits } = useHabitStore();
    const { fetchAllStats } = useStatsStore();
    const [processingAction, setProcessingAction] = React.useState<{ habitId: string; action: 'pause' | 'resume' } | null>(null);
    const [actionErrors, setActionErrors] = React.useState<Record<string, string>>({});

    const handleClose = () => {
        closeDialog();
        fetchHabits();
        fetchAllStats();
    };

    const handlePause = async (habitId: string) => {
        setProcessingAction({ habitId, action: 'pause' });
        setActionErrors(prev => {
            if (!prev[habitId]) return prev;
            const next = { ...prev };
            delete next[habitId];
            return next;
        });
        try {
            await pauseHabit(habitId);
            dismissSettlement(habitId);
            await fetchHabits();
            await fetchAllStats();
        } catch (err) {
            const msg = err instanceof Error ? err.message : '暂停失败，请稍后重试';
            setActionErrors(prev => ({ ...prev, [habitId]: msg }));
        } finally {
            setProcessingAction(prev => (prev?.habitId === habitId ? null : prev));
        }
    };

    const handleResume = async (habitId: string) => {
        setProcessingAction({ habitId, action: 'resume' });
        setActionErrors(prev => {
            if (!prev[habitId]) return prev;
            const next = { ...prev };
            delete next[habitId];
            return next;
        });
        try {
            await resumeHabit(habitId);
            dismissSettlement(habitId);
            await fetchHabits();
            await fetchAllStats();
        } catch (err) {
            const msg = err instanceof Error ? err.message : '重新开始失败，请稍后重试';
            setActionErrors(prev => ({ ...prev, [habitId]: msg }));
        } finally {
            setProcessingAction(prev => (prev?.habitId === habitId ? null : prev));
        }
    };

    const handleDismiss = (habitId: string) => {
        dismissSettlement(habitId);
    };

    const allProcessed = settlements.length === 0;

    const renderSettlementCard = (item: SettlementItem) => {
        const isSuccess = item.result === 'succeeded';
        const isProcessing = processingAction?.habitId === item.habitId;
        const rate = item.requiredCompletions > 0
            ? Math.round((item.completedCount / item.requiredCompletions) * 100)
            : 0;

        return (
            <div
                key={item.habitId}
                className={`rounded-xl border p-4 ${
                    isSuccess
                        ? 'bg-emerald-50/50 border-emerald-200'
                        : 'bg-amber-50/50 border-amber-200'
                }`}
            >
                {/* Card Header */}
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        {isSuccess ? (
                            <div className="bg-emerald-100 text-emerald-700 p-1.5 rounded-lg">
                                <TrendingUp size={16} />
                            </div>
                        ) : (
                            <div className="bg-amber-100 text-amber-700 p-1.5 rounded-lg">
                                <TrendingDown size={16} />
                            </div>
                        )}
                        <div>
                            <span className="text-sm font-bold text-slate-700">{item.habitName}</span>
                            <div className="flex items-center gap-2 mt-0.5">
                                <span className="text-xs text-slate-500">
                                    Lv.{item.fromLevel} → Lv.{item.toLevel}
                                </span>
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                                    isSuccess
                                        ? 'bg-emerald-50 text-emerald-600 border border-emerald-200'
                                        : 'bg-amber-50 text-amber-600 border border-amber-200'
                                }`}>
                                    {isSuccess ? '成功' : '失败'}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Progress */}
                <div className="flex items-center gap-2 text-sm text-slate-600 mb-3">
                    <Target size={14} className="text-slate-400" />
                    <span>完成 {item.completedCount}/{item.requiredCompletions} 天</span>
                    <span className="text-xs text-slate-400">({rate}%)</span>
                </div>

                {/* Actions */}
                {isSuccess ? (
                    <button
                        onClick={() => handleDismiss(item.habitId)}
                        className="w-full px-3 py-2 text-xs font-medium text-emerald-700 bg-emerald-100 hover:bg-emerald-200 rounded-lg transition-colors"
                    >
                        知道了
                    </button>
                ) : (
                    <div className="space-y-2">
                        {item.canSaveByBackfill && (
                            <button
                                onClick={() => openBackfill(item.habitId)}
                                disabled={isProcessing}
                                className="w-full px-3 py-2 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center justify-center gap-1"
                            >
                                <Shield size={12} />
                                补录近7天
                            </button>
                        )}
                        <button
                            onClick={() => handleResume(item.habitId)}
                            disabled={isProcessing}
                            className="w-full px-3 py-2 text-xs font-medium text-amber-700 bg-amber-100 hover:bg-amber-200 disabled:bg-slate-200 disabled:text-slate-500 disabled:cursor-not-allowed rounded-lg transition-colors"
                        >
                            {isProcessing && processingAction?.action === 'resume' ? '重新开始中...' : '重新开始当前挑战'}
                        </button>
                        <button
                            onClick={() => handlePause(item.habitId)}
                            disabled={isProcessing}
                            className="w-full px-3 py-2 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-500 disabled:cursor-not-allowed rounded-lg transition-colors"
                        >
                            {isProcessing && processingAction?.action === 'pause' ? '暂停中...' : `暂停${item.habitName}习惯`}
                        </button>
                        {actionErrors[item.habitId] && (
                            <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-2 py-1.5">
                                {actionErrors[item.habitId]}
                            </p>
                        )}
                    </div>
                )}
            </div>
        );
    };

    return createPortal(
        <AnimatePresence>
            {isDialogOpen && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-[9999] isolate flex items-center justify-center p-4 sm:p-0"
                >
                    <div className="absolute inset-0 z-0 bg-slate-900/40 backdrop-blur-sm" onClick={handleClose} />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                        className="relative z-10 w-full max-w-[500px] bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[85vh]"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {backfillState ? (
                            <SettlementBackfillView />
                        ) : (
                            <>
                                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
                                    <div>
                                        <h2 className="text-lg font-bold text-slate-800">挑战结算</h2>
                                        <p className="text-xs text-slate-500 mt-0.5">{settlements.length} 个挑战已结算</p>
                                    </div>
                                    <button onClick={handleClose} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors">
                                        <X size={20} />
                                    </button>
                                </div>
                                <div className="overflow-y-auto px-6 py-4 flex-1 space-y-3">
                                    {allProcessed ? (
                                        <div className="flex flex-col items-center justify-center py-10 text-slate-400">
                                            <TrendingUp size={40} className="mb-3 opacity-20" />
                                            <p className="text-sm font-medium">全部处理完毕</p>
                                        </div>
                                    ) : (
                                        settlements.map(renderSettlementCard)
                                    )}
                                </div>
                                <div className="px-6 py-3 border-t border-slate-100 shrink-0">
                                    <button onClick={handleClose} className="w-full px-4 py-2.5 text-sm font-medium text-white bg-slate-800 hover:bg-slate-900 rounded-xl transition-colors">
                                        {allProcessed ? '关闭' : '稍后处理'}
                                    </button>
                                </div>
                            </>
                        )}
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>,
        document.body
    );
};
