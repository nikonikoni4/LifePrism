import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Download, RefreshCw, CheckCircle, XCircle, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

type UpdateStatus = 'idle' | 'checking' | 'available' | 'downloading' | 'downloaded' | 'error';

interface UpdateState {
    status: UpdateStatus;
    version?: string;
    releaseNotes?: string | null;
    errorMessage?: string;
    progress: { percent: number; bytesPerSecond: number; transferred: number; total: number };
}

function formatBytes(bytes: number): string {
    if (bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function formatSpeed(bytesPerSecond: number): string {
    return `${formatBytes(bytesPerSecond)}/s`;
}

const UpdateNotification: React.FC = () => {
    const [state, setState] = useState<UpdateState>({
        status: 'idle',
        progress: { percent: 0, bytesPerSecond: 0, transferred: 0, total: 0 },
    });
    const [dismissed, setDismissed] = useState(false);
    const statusHandlerRef = useRef<((_event: unknown, data: unknown) => void) | null>(null);
    const progressHandlerRef = useRef<((_event: unknown, data: unknown) => void) | null>(null);

    useEffect(() => {
        const api = window.electronAPI;
        if (!api) return;

        // Register status listener
        statusHandlerRef.current = api.onUpdaterStatus((data) => {
            const { status, version, message, releaseNotes } = data;
            if (status === 'checking') {
                setState(prev => ({ ...prev, status: 'checking' }));
            } else if (status === 'available') {
                setState(prev => ({ ...prev, status: 'available', version, releaseNotes }));
            } else if (status === 'not-available' || status === 'dev-mode') {
                setState(prev => ({ ...prev, status: 'idle' }));
            } else if (status === 'downloaded') {
                setDismissed(false);
                setState(prev => ({ ...prev, status: 'downloaded', version }));
            } else if (status === 'error') {
                setState(prev => ({ ...prev, status: 'error', errorMessage: message || '更新检查失败' }));
            }
        });

        // Register progress listener
        progressHandlerRef.current = api.onUpdaterProgress((data) => {
            setState(prev => ({ ...prev, status: 'downloading', progress: data }));
        });

        // Initial check
        api.checkForUpdates().catch(() => {});

        return () => {
            if (statusHandlerRef.current) {
                api.removeUpdaterListener('updater:status', statusHandlerRef.current);
            }
            if (progressHandlerRef.current) {
                api.removeUpdaterListener('updater:progress', progressHandlerRef.current);
            }
        };
    }, []);

    const handleDownload = useCallback(async () => {
        setState(prev => ({ ...prev, status: 'downloading' }));
        try {
            const result = await window.electronAPI?.downloadUpdate();
            if (result?.status === 'error') {
                setState(prev => ({ ...prev, status: 'error', errorMessage: result.message || '下载失败' }));
            }
        } catch {
            setState(prev => ({ ...prev, status: 'error', errorMessage: '下载失败' }));
        }
    }, []);

    const handleInstall = useCallback(() => {
        window.electronAPI?.quitAndInstall();
    }, []);

    const handleRetry = useCallback(async () => {
        setState(prev => ({ ...prev, status: 'checking', errorMessage: undefined }));
        try {
            const result = await window.electronAPI?.checkForUpdates();
            if (result?.status === 'error') {
                setState(prev => ({ ...prev, status: 'error', errorMessage: result.message || '检查更新失败' }));
            }
        } catch {
            setState(prev => ({ ...prev, status: 'error', errorMessage: '检查更新失败' }));
        }
    }, []);

    const handleDismiss = useCallback(() => {
        setDismissed(true);
    }, []);

    // Don't render in non-Electron or hidden states
    const visible = !dismissed && (state.status === 'available' || state.status === 'downloading' || state.status === 'downloaded' || state.status === 'error');

    return (
        <AnimatePresence>
            {visible && (
                <motion.div
                    initial={{ opacity: 0, y: 20, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 20, scale: 0.95 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                    className="fixed bottom-6 right-6 z-[9990] w-[340px] bg-white/95 backdrop-blur-xl rounded-2xl shadow-[0_20px_40px_-12px_rgba(0,0,0,0.15)] border border-white/40 overflow-hidden"
                >
                    {state.status === 'available' && <AvailableCard version={state.version} onDownload={handleDownload} onDismiss={handleDismiss} />}
                    {state.status === 'downloading' && <DownloadingCard progress={state.progress} onDismiss={handleDismiss} />}
                    {state.status === 'downloaded' && <DownloadedCard onInstall={handleInstall} onDismiss={handleDismiss} />}
                    {state.status === 'error' && <ErrorCard message={state.errorMessage} onRetry={handleRetry} onDismiss={handleDismiss} />}
                </motion.div>
            )}
        </AnimatePresence>
    );
};

// --- Sub-cards ---

function AvailableCard({ version, onDownload, onDismiss }: { version?: string; onDownload: () => void; onDismiss: () => void }) {
    return (
        <>
            <div className="flex items-start gap-3 px-4 py-4">
                <Download size={20} className="text-blue-500 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-700">发现新版本{version ? ` v${version}` : ''}</p>
                    <p className="text-xs text-slate-500 mt-1">新版本已可用，是否立即更新？</p>
                </div>
                <button onClick={onDismiss} className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors">
                    <X size={16} />
                </button>
            </div>
            <div className="flex items-center justify-end gap-2 px-4 py-3 bg-slate-50/50 border-t border-slate-100">
                <button onClick={onDismiss} className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors">
                    稍后
                </button>
                <button onClick={onDownload} className="px-3 py-1.5 text-xs font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors flex items-center gap-1.5">
                    <Download size={12} />
                    立即更新
                </button>
            </div>
        </>
    );
}

function DownloadingCard({ progress, onDismiss }: { progress: UpdateState['progress']; onDismiss: () => void }) {
    const percent = Math.round(progress.percent);
    return (
        <div className="px-4 py-4 space-y-3">
            <div className="flex items-center gap-3">
                <RefreshCw size={18} className="text-blue-500 animate-spin shrink-0" />
                <p className="text-sm font-semibold text-slate-700 flex-1">正在下载更新...</p>
                <button onClick={onDismiss} className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors">
                    <X size={16} />
                </button>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                <motion.div
                    className="bg-blue-500 h-full rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${percent}%` }}
                    transition={{ duration: 0.3 }}
                />
            </div>
            <div className="flex items-center justify-between text-xs text-slate-500">
                <span>{percent}%</span>
                <span>{formatBytes(progress.transferred)} / {formatBytes(progress.total)}</span>
                <span>{formatSpeed(progress.bytesPerSecond)}</span>
            </div>
        </div>
    );
}

function DownloadedCard({ onInstall, onDismiss }: { onInstall: () => void; onDismiss: () => void }) {
    return (
        <>
            <div className="flex items-start gap-3 px-4 py-4">
                <CheckCircle size={20} className="text-green-500 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-700">更新已就绪</p>
                    <p className="text-xs text-slate-500 mt-1">重启应用即可完成安装</p>
                </div>
            </div>
            <div className="flex items-center justify-end gap-2 px-4 py-3 bg-slate-50/50 border-t border-slate-100">
                <button onClick={onDismiss} className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors">
                    退出时更新
                </button>
                <button onClick={onInstall} className="px-3 py-1.5 text-xs font-medium text-white bg-green-500 hover:bg-green-600 rounded-lg transition-colors flex items-center gap-1.5">
                    <CheckCircle size={12} />
                    立即重启
                </button>
            </div>
        </>
    );
}

function ErrorCard({ message, onRetry, onDismiss }: { message?: string; onRetry: () => void; onDismiss: () => void }) {
    return (
        <>
            <div className="flex items-start gap-3 px-4 py-4">
                <XCircle size={20} className="text-red-500 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-700">更新失败</p>
                    <p className="text-xs text-slate-500 mt-1">{message || '未知错误'}</p>
                </div>
                <button onClick={onDismiss} className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors">
                    <X size={16} />
                </button>
            </div>
            <div className="flex items-center justify-end gap-2 px-4 py-3 bg-slate-50/50 border-t border-slate-100">
                <button onClick={onDismiss} className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors">
                    关闭
                </button>
                <button onClick={onRetry} className="px-3 py-1.5 text-xs font-medium text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors flex items-center gap-1.5">
                    <RefreshCw size={12} />
                    重试
                </button>
            </div>
        </>
    );
}

export default UpdateNotification;
