import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Trash2, AlertTriangle } from 'lucide-react';
import { TodoDeletePreview } from '../../../types/backend';

// 状态标签颜色
const STATE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
    pool: { bg: 'bg-indigo-100', text: 'text-indigo-700', label: '待处理' },
    scheduled: { bg: 'bg-violet-100', text: 'text-violet-700', label: '已安排' },
    completed: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: '已完成' },
    shelved: { bg: 'bg-gray-100', text: 'text-gray-600', label: '已搁置' },
};

interface SyncDeleteConfirmDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirmDelete: () => void;
    onKeepAll: () => void;
    toDelete: TodoDeletePreview[];
    syncStats: { created: number; updated: number };
    loading?: boolean;
}

export const SyncDeleteConfirmDialog: React.FC<SyncDeleteConfirmDialogProps> = ({
    isOpen,
    onClose,
    onConfirmDelete,
    onKeepAll,
    toDelete,
    syncStats,
    loading = false
}) => {
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (!isOpen) return;
            if (e.key === 'Escape') {
                onClose();
            }
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, onClose]);

    return createPortal(
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-[9999] flex items-center justify-center"
                >
                    {/* Backdrop */}
                    <div
                        className="absolute inset-0 bg-black/20 backdrop-blur-sm"
                        onClick={onClose}
                    />

                    {/* Dialog */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: -20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: -10 }}
                        transition={{ type: "spring", stiffness: 400, damping: 30 }}
                        className="relative w-[520px] max-h-[80vh] bg-white/95 backdrop-blur-xl rounded-2xl shadow-[0_20px_40px_-12px_rgba(0,0,0,0.15)] border border-white/40 overflow-hidden flex flex-col"
                    >
                        {/* Header */}
                        <div className="flex-shrink-0 flex items-center justify-between px-5 py-4 border-b border-slate-100">
                            <div className="flex items-center gap-2">
                                <AlertTriangle size={18} className="text-amber-500" />
                                <h3 className="text-base font-semibold text-slate-700">
                                    同步检测到任务变更
                                </h3>
                            </div>
                            <button
                                onClick={onClose}
                                disabled={loading}
                                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        {/* Sync Stats */}
                        <div className="flex-shrink-0 px-5 py-3 bg-slate-50/80 border-b border-slate-100">
                            <div className="flex items-center gap-4 text-sm">
                                {syncStats.created > 0 && (
                                    <span className="text-emerald-600">
                                        <span className="font-medium">+{syncStats.created}</span> 新增
                                    </span>
                                )}
                                {syncStats.updated > 0 && (
                                    <span className="text-blue-600">
                                        <span className="font-medium">{syncStats.updated}</span> 更新
                                    </span>
                                )}
                                <span className="text-red-600">
                                    <span className="font-medium">{toDelete.length}</span> 待删除
                                </span>
                            </div>
                        </div>

                        {/* Content - Task List */}
                        <div className="flex-1 overflow-y-auto px-5 py-4">
                            <p className="text-sm text-slate-600 mb-3">
                                以下任务已从计划书中删除，请选择处理方式：
                            </p>
                            <div className="space-y-2">
                                {toDelete.map((task) => {
                                    const stateStyle = STATE_COLORS[task.state] || STATE_COLORS.pool;
                                    return (
                                        <div
                                            key={task.id}
                                            className="flex items-center gap-3 p-3 bg-red-50/50 border border-red-100 rounded-xl"
                                        >
                                            <Trash2 size={14} className="flex-shrink-0 text-red-400" />
                                            <span className="flex-1 text-sm text-slate-700 truncate">
                                                {task.content}
                                            </span>
                                            <span className={`flex-shrink-0 px-2 py-0.5 text-xs font-medium rounded-full ${stateStyle.bg} ${stateStyle.text}`}>
                                                {stateStyle.label}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Footer */}
                        <div className="flex-shrink-0 flex items-center justify-between gap-2 px-5 py-4 bg-slate-50/50 border-t border-slate-100">
                            <button
                                onClick={onClose}
                                disabled={loading}
                                className="px-4 py-2 text-sm font-medium text-slate-500 hover:text-slate-700 transition-colors disabled:opacity-50"
                            >
                                取消
                            </button>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={onKeepAll}
                                    disabled={loading}
                                    className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors disabled:opacity-50"
                                >
                                    保留全部
                                </button>
                                <button
                                    onClick={onConfirmDelete}
                                    disabled={loading}
                                    className="px-4 py-2 text-sm font-medium text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                                >
                                    {loading ? (
                                        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    ) : (
                                        <Trash2 size={14} />
                                    )}
                                    确认删除
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>,
        document.body
    );
};
