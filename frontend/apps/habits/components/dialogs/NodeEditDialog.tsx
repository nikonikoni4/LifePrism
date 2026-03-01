import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Type, Link as LinkIcon, Clock } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { HabitChainNode } from '../../types/entities';
import { useChainStore } from '../../hooks/useChainStore';
import { useHabitStore } from '../../hooks/useHabitStore';
import { toast } from '../../../../core/components';

interface NodeEditDialogProps {
    isOpen: boolean;
    onClose: () => void;
    chainId: number;
    node?: HabitChainNode | null; // null for create mode
    insertAfterNodeId?: number | null; // useful for create mode to specify location
}

interface NodeFormData {
    name: string;
    habitId: string;
    triggerTime: string;
}

export const NodeEditDialog: React.FC<NodeEditDialogProps> = ({
    isOpen,
    onClose,
    chainId,
    node,
    insertAfterNodeId
}) => {
    const normalizeTimeValue = (value?: string | null): string => {
        if (!value) return '';
        if (/^\d{2}:\d{2}$/.test(value)) return value;
        const date = new Date(value);
        if (!Number.isNaN(date.getTime())) {
            return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
        }
        return '';
    };

    const { addNode, updateNode } = useChainStore();
    const { activeHabits } = useHabitStore();
    const isEditMode = !!node;

    const {
        register,
        handleSubmit,
        reset,
        watch,
        setValue,
        formState: { errors }
    } = useForm<NodeFormData>({
        defaultValues: {
            name: '',
            habitId: '',
            triggerTime: ''
        }
    });

    useEffect(() => {
        if (isOpen) {
            if (node) {
                reset({
                    name: node.name,
                    habitId: node.habitId || '',
                    triggerTime: normalizeTimeValue(node.triggerTime)
                });
            } else {
                reset({
                    name: '',
                    habitId: '',
                    triggerTime: ''
                });
            }
        }
    }, [isOpen, node, reset]);

    const onSubmit = async (data: NodeFormData) => {
        const payload = {
            name: data.name,
            habitId: data.habitId || null,
            triggerTime: data.triggerTime || null,
        };
        try {
            if (isEditMode) {
                await updateNode(chainId, node.id, payload);
            } else {
                await addNode(chainId, {
                    ...payload,
                    insertAfterNodeId
                });
            }
            onClose();
        } catch (error) {
            console.error("Failed to save chain node", error);
            toast.error(error instanceof Error ? error.message : (isEditMode ? '保存节点失败' : '添加节点失败'));
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
                                {isEditMode ? '编辑节点' : '添加节点'}
                            </h2>
                            <button
                                onClick={onClose}
                                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Form Body */}
                        <form id="node-form" onSubmit={handleSubmit(onSubmit)} className="px-6 py-5 space-y-5">
                            {/* Name */}
                            <div className="space-y-1.5">
                                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                                    <Type size={16} className="text-indigo-500" />
                                    节点名称
                                </label>
                                <input
                                    {...register('name', { required: '请输入节点名称' })}
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 text-slate-700"
                                    placeholder="例如：刷牙、冥想..."
                                />
                                {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name.message}</p>}
                            </div>

                            {/* Trigger Time */}
                            <div className="space-y-1.5">
                                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                                    <Clock size={16} className="text-amber-500" />
                                    Trigger Time (Optional)
                                </label>
                                <input
                                    type="time"
                                    {...register('triggerTime')}
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400 text-slate-700"
                                />
                                <p className="text-xs text-slate-500 mt-1">Used for timeline ordering validation; leave empty to skip.</p>
                            </div>

                            {/* Habit Binding */}
                            <div className="space-y-1.5">
                                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                                    <LinkIcon size={16} className="text-emerald-500" />
                                    绑定习惯 (可选)
                                </label>
                                <div className="relative">
                                    <select
                                        {...register('habitId')}
                                        className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-400 text-slate-700 appearance-none"
                                        onChange={(e) => {
                                            setValue('habitId', e.target.value);
                                            // auto fill name if empty
                                            if (e.target.value) {
                                                const selectedHabit = activeHabits.find(h => h.id === e.target.value);
                                                if (selectedHabit && !watch('name')) {
                                                    setValue('name', selectedHabit.name);
                                                }
                                            }
                                        }}
                                    >
                                        <option value="">-- 不绑定任何习惯 --</option>
                                        {activeHabits.map(h => (
                                            <option key={h.id} value={h.id}>{h.name}</option>
                                        ))}
                                    </select>
                                    <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none text-slate-400">
                                        <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                        </svg>
                                    </div>
                                </div>
                                <p className="text-xs text-slate-500 mt-1">绑定后，勾选此节点将自动触发对应习惯的打卡。</p>
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
                                form="node-form"
                                className="px-6 py-2.5 text-sm font-semibold text-white bg-indigo-500 hover:bg-indigo-600 rounded-xl transition-all shadow-md shadow-indigo-500/20"
                            >
                                {isEditMode ? '保存修改' : '添加节点'}
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>,
        document.body
    );
};
