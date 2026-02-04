import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, AlertTriangle, FileText, Edit3, XCircle } from 'lucide-react';

interface RefreshConflictDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onKeepLocal: () => void;
    onUseFile: () => void;
    docName: string;
}

export const RefreshConflictDialog: React.FC<RefreshConflictDialogProps> = ({
    isOpen,
    onClose,
    onKeepLocal,
    onUseFile,
    docName
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
                        className="relative w-[480px] bg-white/95 backdrop-blur-xl rounded-2xl shadow-[0_20px_40px_-12px_rgba(0,0,0,0.15)] border border-white/40 overflow-hidden"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
                            <div className="flex items-center gap-2">
                                <AlertTriangle size={18} className="text-amber-500" />
                                <h3 className="text-base font-semibold text-slate-700">检测到未保存的修改</h3>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        {/* Content */}
                        <div className="px-5 py-4">
                            <p className="text-sm text-slate-600 mb-4">
                                文档 <span className="font-medium text-slate-800">"{docName}"</span> 有未保存的本地修改。
                                刷新将从文件系统重新加载内容，请选择如何处理：
                            </p>

                            <div className="space-y-2">
                                {/* Option 1: Keep local */}
                                <button
                                    onClick={onKeepLocal}
                                    className="w-full flex items-start gap-3 p-3 rounded-xl border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/50 transition-all text-left group"
                                >
                                    <div className="p-2 rounded-lg bg-indigo-100 text-indigo-600 group-hover:bg-indigo-200 transition-colors">
                                        <Edit3 size={16} />
                                    </div>
                                    <div>
                                        <div className="font-medium text-slate-700 text-sm">保留本地修改</div>
                                        <div className="text-xs text-slate-500 mt-0.5">取消刷新，继续编辑当前内容</div>
                                    </div>
                                </button>

                                {/* Option 2: Use file */}
                                <button
                                    onClick={onUseFile}
                                    className="w-full flex items-start gap-3 p-3 rounded-xl border border-slate-200 hover:border-amber-300 hover:bg-amber-50/50 transition-all text-left group"
                                >
                                    <div className="p-2 rounded-lg bg-amber-100 text-amber-600 group-hover:bg-amber-200 transition-colors">
                                        <FileText size={16} />
                                    </div>
                                    <div>
                                        <div className="font-medium text-slate-700 text-sm">使用文件内容</div>
                                        <div className="text-xs text-slate-500 mt-0.5">丢弃本地修改，加载文件系统中的最新内容</div>
                                    </div>
                                </button>

                                {/* Option 3: Cancel */}
                                <button
                                    onClick={onClose}
                                    className="w-full flex items-start gap-3 p-3 rounded-xl border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-all text-left group"
                                >
                                    <div className="p-2 rounded-lg bg-slate-100 text-slate-500 group-hover:bg-slate-200 transition-colors">
                                        <XCircle size={16} />
                                    </div>
                                    <div>
                                        <div className="font-medium text-slate-700 text-sm">取消</div>
                                        <div className="text-xs text-slate-500 mt-0.5">不做任何操作</div>
                                    </div>
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
