import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Clock } from 'lucide-react';
import { useForm, useFieldArray } from 'react-hook-form';
import { HabitChain } from '../../types/entities';
import { useChainStore } from '../../hooks/useChainStore';
import { toast } from '../../../../core/components';

interface NodeTimeDialogProps {
    isOpen: boolean;
    onClose: () => void;
    chain: HabitChain;
}

interface NodeTimeForm {
    showInTimeline: boolean;
    nodes: Array<{
        nodeId: number;
        name: string;
        triggerTime: string; // HH:mm format
    }>;
}

export const NodeTimeDialog: React.FC<NodeTimeDialogProps> = ({
    isOpen,
    onClose,
    chain
}) => {
    const { updateChain } = useChainStore();

    const {
        register,
        handleSubmit,
        reset,
        control
    } = useForm<NodeTimeForm>({
        defaultValues: {
            showInTimeline: true,
            nodes: []
        }
    });

    const { fields } = useFieldArray({
        control,
        name: "nodes"
    });

    useEffect(() => {
        if (isOpen) {
            reset({
                showInTimeline: true, // we assume opening this dialog means they want to show it
                nodes: chain.nodes.map(node => {
                    // format triggerTime if exists, else default to empty string
                    let timeStr = "";
                    if (node.triggerTime) {
                        // Check if it's already HH:mm
                        if (/^\d{2}:\d{2}$/.test(node.triggerTime)) {
                            timeStr = node.triggerTime;
                        } else {
                            try {
                                const d = new Date(node.triggerTime);
                                if (!isNaN(d.getTime())) {
                                    timeStr = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
                                }
                            } catch (e) { }
                        }
                    }
                    return {
                        nodeId: node.id,
                        name: node.name,
                        triggerTime: timeStr
                    };
                })
            });
        }
    }, [isOpen, chain, reset]);

    const onSubmit = async (data: NodeTimeForm) => {
        try {
            // we need to construct proper ISO strings or the format the backend expects
            // assuming the backend expects an ISO string, we map HH:mm to today's date
            const triggerTimes = data.nodes
                .filter(n => n.triggerTime)
                .map(n => {
                    return {
                        nodeId: n.nodeId,
                        triggerTime: n.triggerTime // raw HH:mm string instead of ISO Date
                    };
                });

            await updateChain(chain.id, {
                showInTimeline: data.showInTimeline,
                triggerTimes: triggerTimes.length > 0 ? triggerTimes : undefined
            });
            onClose();
        } catch (error) {
            console.error("Failed to update chain nodes times", error);
            toast.error(error instanceof Error ? error.message : '保存时间线设置失败');
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
                >
                    <div
                        className="absolute inset-0 z-0 bg-slate-900/50"
                        onClick={onClose}
                    />

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 20 }}
                        transition={{ type: "spring", stiffness: 400, damping: 30 }}
                        className="relative z-10 w-full max-w-[480px] bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[90vh]"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
                            <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                                <Clock className="text-indigo-500" size={18} /> 时间线设置
                            </h2>
                            <button
                                onClick={onClose}
                                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Form Body */}
                        <form id="node-time-form" onSubmit={handleSubmit(onSubmit)} className="px-6 py-5 flex-1 overflow-y-auto space-y-5">
                            <div className="flex items-center gap-3 bg-slate-50 p-3 rounded-xl border border-slate-100">
                                <input
                                    type="checkbox"
                                    id="showTimeline"
                                    {...register('showInTimeline')}
                                    className="w-4 h-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500"
                                />
                                <label htmlFor="showTimeline" className="text-sm font-semibold text-slate-700 select-none cursor-pointer">
                                    在时间线中显示此链条
                                </label>
                            </div>

                            <div className="space-y-3">
                                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">为各个节点设置时间 (可选)</p>
                                {fields.map((field, index) => (
                                    <div key={field.id} className="flex items-center justify-between gap-4 p-3 rounded-xl border border-slate-100 bg-white shadow-sm">
                                        <div className="flex-1 truncate">
                                            <span className="text-sm font-semibold text-slate-800">{field.name}</span>
                                        </div>
                                        <div className="w-32 shrink-0 relative">
                                            <Clock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                            <input
                                                type="time"
                                                {...register(`nodes.${index}.triggerTime`)}
                                                className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 text-slate-700 text-sm"
                                            />
                                        </div>
                                    </div>
                                ))}
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
                                form="node-time-form"
                                className="px-6 py-2.5 text-sm font-semibold text-white bg-indigo-500 hover:bg-indigo-600 rounded-xl transition-all shadow-md shadow-indigo-500/20"
                            >
                                保存设置
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>,
        document.body
    );
};
