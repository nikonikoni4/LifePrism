import React, { useState, useEffect } from 'react';

interface DialogParams {
    taskName: string;
    startTime: string;
    endTime: string;
    duration: number;
    todoId: string;
}

export const RecordActivityDialog: React.FC = () => {
    const [params, setParams] = useState<DialogParams | null>(null);
    const [content, setContent] = useState('');
    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        // 从 URL hash 中解析 query params
        // 格式: #/dialog/record-activity?taskName=xxx&startTime=xxx...
        const hash = window.location.hash;
        const queryStart = hash.indexOf('?');

        if (queryStart === -1) {
            console.error('[RecordActivity] No query params in hash:', hash);
            return;
        }

        const queryString = hash.substring(queryStart + 1);
        const urlParams = new URLSearchParams(queryString);

        const taskName = urlParams.get('taskName') || '';
        const startTime = urlParams.get('startTime') || '';
        const endTime = urlParams.get('endTime') || '';
        const duration = parseInt(urlParams.get('duration') || '0', 10);
        const todoId = urlParams.get('todoId') || '';

        console.log('[RecordActivity] Parsed params:', { taskName, startTime, endTime, duration, todoId });

        setParams({ taskName, startTime, endTime, duration, todoId });
        setContent(taskName); // 默认内容为任务名称
    }, []);

    const formatTime = (isoString: string): string => {
        if (!isoString) return '';
        try {
            const date = new Date(isoString);
            return date.toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            });
        } catch {
            return '';
        }
    };

    const formatDuration = (minutes: number): string => {
        if (minutes < 60) {
            return `${minutes} 分钟`;
        }
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return mins > 0 ? `${hours} 小时 ${mins} 分钟` : `${hours} 小时`;
    };

    const handleConfirm = async () => {
        if (!params || !content.trim()) return;

        setSubmitting(true);
        try {
            // 发送消息到浮窗，携带用户输入的内容
            await window.electronAPI?.sendToFloating?.(
                'what-am-i-doing',
                'activity-recorded',
                {
                    content: content.trim(),
                    startTime: params.startTime,
                    endTime: params.endTime,
                    duration: params.duration,
                    todoId: params.todoId,
                }
            );

            // 关闭对话框
            await window.electronAPI?.closeDialogWindow?.('record-activity');
        } catch (e) {
            console.error('[RecordActivity] Confirm failed:', e);
            setSubmitting(false);
        }
    };

    if (!params) {
        return (
            <div className="h-screen flex items-center justify-center bg-[#1e1e1e] text-white">
                <p className="text-sm text-white/50">Loading...</p>
            </div>
        );
    }

    return (
        <div className="h-screen flex flex-col bg-[#1e1e1e] text-white select-none overflow-hidden">
            {/* 标题栏 */}
            <div
                className="h-10 flex items-center justify-between px-4 bg-gradient-to-r from-emerald-600 to-teal-600 shrink-0"
                style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
            >
                <span className="text-sm font-medium text-white/90">记录活动内容</span>
            </div>

            {/* 内容区域 */}
            <div className="flex-1 flex flex-col px-4 py-4 gap-3 overflow-y-auto">
                {/* 任务信息提示 */}
                <div className="px-3 py-2 rounded bg-emerald-600/10 border border-emerald-600/20">
                    <div className="text-xs text-emerald-400/70 mb-1">任务：{params.taskName}</div>
                    <div className="text-xs text-white/50">
                        {formatTime(params.startTime)} - {formatTime(params.endTime)} ({formatDuration(params.duration)})
                    </div>
                </div>

                {/* 活动内容输入框 */}
                <div className="flex-1 flex flex-col">
                    <label className="block text-xs text-white/50 mb-1.5">
                        活动内容 <span className="text-emerald-400">*</span>
                    </label>
                    <textarea
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        placeholder="请输入实际的活动内容..."
                        className="flex-1 px-3 py-2 rounded bg-white/10 border border-white/10 focus:border-emerald-500/50 focus:outline-none text-sm text-white placeholder-white/30 resize-none"
                        autoFocus
                    />
                </div>
            </div>

            {/* 底部按钮 */}
            <div className="shrink-0 px-4 py-3 border-t border-white/5">
                <button
                    onClick={handleConfirm}
                    disabled={!content.trim() || submitting}
                    className={`w-full py-2.5 rounded text-sm font-medium transition-colors ${
                        content.trim() && !submitting
                            ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                            : 'bg-white/5 text-white/30 cursor-not-allowed'
                    }`}
                >
                    {submitting ? '保存中...' : '确定'}
                </button>
            </div>
        </div>
    );
};
