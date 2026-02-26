import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, AlertTriangle, FileText, Monitor, ArrowRight, ArrowLeft, XCircle } from 'lucide-react';

interface RefreshConflictDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onUseEditedContent: () => void;
    onUseLocalMdContent: () => void;
    docName: string;
}

// 数据流向示意图组件
const DataFlowDiagram: React.FC<{
    direction: 'toFile' | 'fromFile';
    highlight: 'local' | 'file';
}> = ({ direction, highlight }) => {
    const isToFile = direction === 'toFile';
    const localHighlight = highlight === 'local';
    const fileHighlight = highlight === 'file';

    return (
        <div className="flex items-center justify-center gap-2 py-2">
            {/* 当前窗口 */}
            <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-colors ${localHighlight
                ? 'bg-indigo-100 border-indigo-300 text-indigo-700'
                : 'bg-slate-50 border-slate-200 text-slate-500'
                }`}>
                <Monitor size={14} />
                <span className="text-xs font-medium">当前窗口</span>
            </div>

            {/* 箭头 */}
            <div className={`flex items-center ${isToFile ? 'text-indigo-500' : 'text-amber-500'
                }`}>
                {isToFile ? (
                    <ArrowRight size={18} strokeWidth={2.5} />
                ) : (
                    <ArrowLeft size={18} strokeWidth={2.5} />
                )}
            </div>

            {/* MD 文件 */}
            <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-colors ${fileHighlight
                ? 'bg-amber-100 border-amber-300 text-amber-700'
                : 'bg-slate-50 border-slate-200 text-slate-500'
                }`}>
                <FileText size={14} />
                <span className="text-xs font-medium">MD 文件</span>
            </div>
        </div>
    );
};

export const RefreshConflictDialog: React.FC<RefreshConflictDialogProps> = ({
    isOpen,
    onClose,
    onUseEditedContent,
    onUseLocalMdContent,
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
                                <button
                                    onClick={onUseEditedContent}
                                    className="w-full flex flex-col p-3 rounded-xl border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/30 transition-all text-left group"
                                >
                                    <div className="flex items-center gap-2 mb-1">
                                        <div className="font-medium text-slate-700 text-sm">使用当前窗口所编辑的内容</div>
                                        <span className="text-xs text-slate-400">当你在本地窗口有</span>
                                    </div>
                                    <DataFlowDiagram direction="toFile" highlight="local" />
                                </button>

                                <button
                                    onClick={onUseLocalMdContent}
                                    className="w-full flex flex-col p-3 rounded-xl border border-slate-200 hover:border-amber-300 hover:bg-amber-50/30 transition-all text-left group"
                                >
                                    <div className="flex items-center gap-2 mb-1">
                                        <div className="font-medium text-slate-700 text-sm">使用本地MD文档的内容</div>
                                        <span className="text-xs text-slate-400">丢弃当前窗口内容</span>
                                    </div>
                                    <DataFlowDiagram direction="fromFile" highlight="file" />
                                </button>

                                {/* Option 3: Cancel */}
                                <button
                                    onClick={onClose}
                                    className="w-full flex items-center justify-center gap-2 p-2.5 rounded-xl border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-all text-slate-500 hover:text-slate-600"
                                >
                                    <XCircle size={14} />
                                    <span className="text-sm">取消</span>
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
