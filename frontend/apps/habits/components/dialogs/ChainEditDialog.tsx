import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Type, AlignLeft } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { ChainListItem } from '../../types/backend';
import { useChainStore } from '../../hooks/useChainStore';

interface ChainEditDialogProps {
    isOpen: boolean;
    onClose: () => void;
    chain?: ChainListItem | null; // null for create mode
}

interface ChainFormData {
    name: string;
    description: string;
}

export const ChainEditDialog: React.FC<ChainEditDialogProps> = ({
    isOpen,
    onClose,
    chain
}) => {
    const { createChain, updateChain } = useChainStore();
    const isEditMode = !!chain;

    const {
        register,
        handleSubmit,
        reset,
        formState: { errors }
    } = useForm<ChainFormData>({
        defaultValues: {
            name: '',
            description: ''
        }
    });

    useEffect(() => {
        if (isOpen) {
            if (chain) {
                reset({
                    name: chain.name,
                    description: chain.description || ''
                });
            } else {
                reset({
                    name: '',
                    description: ''
                });
            }
        }
    }, [isOpen, chain, reset]);

    const onSubmit = async (data: ChainFormData) => {
        try {
            if (isEditMode) {
                await updateChain(chain.id, {
                    name: data.name,
                    description: data.description || null
                });
            } else {
                await createChain({
                    name: data.name,
                    description: data.description || null
                });
            }
            onClose();
        } catch (error) {
            console.error("Failed to save chain", error);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Escape') {
            onClose();
        }
    };

    return createPortal(
        <AnimatePresence>
            {isOpen && (
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
                        className="relative z-10 w-full max-w-[400px] bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
                            <h2 className="text-lg font-bold text-slate-800">
                                {isEditMode ? '编辑链条' : '新建链条'}
                            </h2>
                            <button
                                onClick={onClose}
                                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Form Body */}
                        <form id="chain-form" onSubmit={handleSubmit(onSubmit)} className="px-6 py-5 space-y-5">
                            {/* Name */}
                            <div className="space-y-1.5">
                                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                                    <Type size={16} className="text-indigo-500" />
                                    链条名称
                                </label>
                                <input
                                    {...register('name', { required: '请输入链条名称' })}
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 text-slate-700"
                                    placeholder="例如：晨间唤醒、晚间睡前..."
                                />
                                {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name.message}</p>}
                            </div>

                            {/* Description */}
                            <div className="space-y-1.5">
                                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                                    <AlignLeft size={16} className="text-slate-400" />
                                    描述 (可选)
                                </label>
                                <textarea
                                    {...register('description')}
                                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 text-slate-700 min-h-[80px] resize-none text-sm"
                                    placeholder="链条的简单说明..."
                                />
                            </div>
                        </form>

                        {/* Footer */}
                        <div className="px-6 py-4 bg-slate-50/80 border-t border-slate-100 shrink-0 flex justify-end gap-3">
                            <button
                                type="button"
                                onClick={onClose}
                                className="px-5 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-200 bg-slate-100 rounded-xl transition-colors"
                            >
                                取消
                            </button>
                            <button
                                type="submit"
                                form="chain-form"
                                className="px-6 py-2.5 text-sm font-semibold text-white bg-indigo-500 hover:bg-indigo-600 rounded-xl transition-all shadow-md shadow-indigo-500/20"
                            >
                                {isEditMode ? '保存修改' : '创建链条'}
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>,
        document.body
    );
};
