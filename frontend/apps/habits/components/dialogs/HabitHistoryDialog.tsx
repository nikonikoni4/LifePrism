import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CalendarDays, TrendingUp, TrendingDown, Target } from 'lucide-react';
import { HabitListItem, ChallengeObject } from '../../types/backend';
import { habitApi } from '../../apis/habit';

interface HabitHistoryDialogProps {
    isOpen: boolean;
    onClose: () => void;
    habit: HabitListItem | null;
}

export const HabitHistoryDialog: React.FC<HabitHistoryDialogProps> = ({
    isOpen,
    onClose,
    habit
}) => {
    const [history, setHistory] = useState<ChallengeObject[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen && habit) {
            const fetchHistory = async () => {
                setIsLoading(true);
                setError(null);
                try {
                    const data = await habitApi.getHabitHistory(habit.id);
                    setHistory(data.challenges || []);
                } catch (err: any) {
                    setError('无法加载历史记录');
                } finally {
                    setIsLoading(false);
                }
            };
            fetchHistory();
        } else {
            setHistory([]);
            setError(null);
        }
    }, [isOpen, habit]);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Escape') {
            onClose();
        }
    };

    const formatDate = (dateStr: string) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    };

    return createPortal(
        <AnimatePresence>
            {isOpen && habit && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-[9999] isolate flex items-center justify-center p-4 sm:p-0"
                    onKeyDown={handleKeyDown}
                    tabIndex={-1}
                >
                    <div
                        className="absolute inset-0 z-0 bg-slate-900/40 backdrop-blur-sm"
                        onClick={onClose}
                    />

                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        transition={{ type: "spring", stiffness: 400, damping: 30 }}
                        className="relative z-10 w-full max-w-[550px] bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[85vh] sm:max-h-[80vh]"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
                            <div>
                                <h2 className="text-lg font-bold text-slate-800">挑战历史</h2>
                                <p className="text-xs text-slate-500 mt-0.5 max-w-[300px] truncate">
                                    {habit.name}
                                </p>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Body */}
                        <div className="overflow-y-auto px-6 py-4 flex-1 bg-slate-50/50">
                            {isLoading ? (
                                <div className="flex flex-col items-center justify-center py-10 space-y-3">
                                    <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                                    <span className="text-sm text-slate-500">正在加载记录...</span>
                                </div>
                            ) : error ? (
                                <div className="text-center py-10 text-red-500 text-sm">
                                    {error}
                                </div>
                            ) : history.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                                    <CalendarDays size={48} className="mb-4 opacity-20" />
                                    <p className="text-sm font-medium">还没有挑战记录</p>
                                    <p className="text-xs mt-1">开始你的第一个挑战吧！</p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {history.map((challenge) => {
                                        const isSuccess = challenge.status === 'succeeded';
                                        return (
                                            <div
                                                key={challenge.id}
                                                className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm"
                                            >
                                                <div className="flex justify-between items-start mb-3">
                                                    <div className="flex items-center gap-2">
                                                        {isSuccess ? (
                                                            <div className="bg-emerald-100 text-emerald-700 p-1.5 rounded-lg flex items-center justify-center">
                                                                <TrendingUp size={16} />
                                                            </div>
                                                        ) : (
                                                            <div className="bg-amber-100 text-amber-700 p-1.5 rounded-lg flex items-center justify-center">
                                                                <TrendingDown size={16} />
                                                            </div>
                                                        )}
                                                        <div>
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-sm font-bold text-slate-700">
                                                                    Lv.{challenge.fromLevel} → Lv.{challenge.toLevel}
                                                                </span>
                                                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${isSuccess
                                                                    ? 'bg-emerald-50 text-emerald-600 border border-emerald-200'
                                                                    : 'bg-amber-50 text-amber-600 border border-amber-200'
                                                                    }`}>
                                                                    {isSuccess ? '成功' : '失败'}
                                                                </span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>

                                                <div className="grid grid-cols-2 gap-y-3 mt-4 text-sm">
                                                    <div className="flex items-center gap-2 text-slate-600">
                                                        <Target size={14} className="text-slate-400" />
                                                        <span>完成 {challenge.completedCount}/{challenge.requiredCompletions} 天</span>
                                                        <span className="text-xs text-slate-400 ml-1">
                                                            ({Math.round((challenge.completedCount / challenge.requiredCompletions) * 100)}%)
                                                        </span>
                                                    </div>
                                                    <div className="flex items-center gap-2 text-slate-600 justify-end text-right">
                                                        <CalendarDays size={14} className="text-slate-400" />
                                                        <span className="text-xs">{formatDate(challenge.startDate)} ~ {formatDate(challenge.endDate)}</span>
                                                    </div>
                                                </div>

                                                {challenge.finishedAt && (
                                                    <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-400 flex justify-end">
                                                        结束于: {formatDate(challenge.finishedAt)}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>,
        document.body
    );
};
