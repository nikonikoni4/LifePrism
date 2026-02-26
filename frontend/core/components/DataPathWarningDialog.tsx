import React, { useState } from 'react';
import { AlertTriangle, FolderOpen, X, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { SettingsAPI } from '../../apps/settings/api';
import { toast } from './Toast';

interface DataPathWarningDialogProps {
    warnings: string[];
    onClose: () => void;
}

type Step = 'warning' | 'confirm';

const DataPathWarningDialog: React.FC<DataPathWarningDialogProps> = ({ warnings, onClose }) => {
    const [step, setStep] = useState<Step>('warning');
    const [pendingPath, setPendingPath] = useState('');
    const [isMigrating, setIsMigrating] = useState(false);
    const isElectron = !!window.electronAPI;

    const handleSelectDirectory = async () => {
        const dir = await window.electronAPI?.selectDirectory();
        if (!dir) return;
        const installPath = await window.electronAPI?.getInstallPath();
        if (installPath && dir.startsWith(installPath)) {
            toast.error('数据路径不能位于安装目录内');
            return;
        }
        setPendingPath(dir);
        setStep('confirm');
    };

    const handleMigrate = async (migrateData: boolean) => {
        setIsMigrating(true);
        try {
            const result = await SettingsAPI.migrateDataPath({
                target_base_path: pendingPath,
                migrate_data: migrateData,
            });
            if (result.success) {
                const msg = migrateData
                    ? `数据已迁移到 ${result.new_path}，即将退出程序...`
                    : `路径已切换到 ${result.new_path}，即将退出程序...`;
                toast.success(msg);
                setTimeout(() => window.electronAPI?.quitApp(), 1500);
            }
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '操作失败');
            setIsMigrating(false);
        }
    };
    if (isMigrating) {
        return (
            <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/30 backdrop-blur-sm">
                <div className="bg-white rounded-2xl p-8 shadow-xl flex flex-col items-center gap-4">
                    <Loader2 className="animate-spin text-orange-500" size={32} />
                    <p className="text-sm font-medium text-slate-700">正在处理，请勿关闭程序...</p>
                </div>
            </div>
        );
    }

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-[9999] flex items-center justify-center"
            >
                <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
                <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: -20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: -10 }}
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                    className="relative w-[500px] bg-white/95 backdrop-blur-xl rounded-2xl shadow-[0_20px_40px_-12px_rgba(0,0,0,0.15)] border border-white/40 overflow-hidden"
                >
                    {/* Header */}
                    <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
                        <div className="flex items-center gap-2">
                            <AlertTriangle size={18} className="text-amber-500" />
                            <h3 className="text-base font-semibold text-slate-700">
                                {step === 'warning' ? '数据路径警告' : '更改数据路径'}
                            </h3>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                        >
                            <X size={18} />
                        </button>
                    </div>

                    {step === 'warning' ? (
                        <>
                            <div className="px-5 py-4 space-y-3">
                                {warnings.map((msg, i) => (
                                    <div key={i} className="flex gap-3 items-start bg-amber-50 border border-amber-200 rounded-xl p-3">
                                        <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
                                        <p className="text-sm text-slate-700">{msg}</p>
                                    </div>
                                ))}
                            </div>
                            <div className="flex items-center justify-end gap-2 px-5 py-4 bg-slate-50/50 border-t border-slate-100">
                                <button
                                    onClick={onClose}
                                    className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                                >
                                    稍后处理
                                </button>
                                {isElectron && (
                                    <button
                                        onClick={handleSelectDirectory}
                                        className="px-4 py-2 text-sm font-medium text-white bg-orange-500 hover:bg-orange-600 rounded-lg transition-colors flex items-center gap-2"
                                    >
                                        <FolderOpen size={14} />
                                        选择新路径
                                    </button>
                                )}
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="px-5 py-4 space-y-2">
                                <p className="text-sm text-slate-600">目标路径：</p>
                                <p className="text-sm font-mono bg-slate-50 px-3 py-2 rounded-lg text-slate-700 break-all">
                                    {pendingPath}\lifeprismData
                                </p>
                                <p className="text-xs text-amber-600 mt-2">
                                    操作完成后程序将自动退出，请手动重新启动。
                                </p>
                            </div>
                            <div className="flex items-center justify-end gap-2 px-5 py-4 bg-slate-50/50 border-t border-slate-100">
                                <button
                                    onClick={() => setStep('warning')}
                                    className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                                >
                                    返回
                                </button>
                                <button
                                    onClick={() => handleMigrate(false)}
                                    className="px-4 py-2 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
                                >
                                    仅切换路径
                                </button>
                                <button
                                    onClick={() => handleMigrate(true)}
                                    className="px-4 py-2 text-sm font-medium text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors"
                                >
                                    迁移数据并退出
                                </button>
                            </div>
                        </>
                    )}
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
};

export default DataPathWarningDialog;
