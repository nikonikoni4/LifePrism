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
        // 从 URL query params 解析参数
        const urlParams = new URLSearchParams(window.location.search);
        const taskName = urlParams.get('taskName') || '';
        const startTime = urlParams.get('startTime') || '';
        const endTime = urlParams.get('endTime') || '';
        const duration = parseInt(urlParams.get('duration') || '0', 10);
        const todoId = urlParams.get('todoId') || '';

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
                second: '2-digit',
                hour12: false
            });
        } catch {
            return '';
        }
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
            <div className="flex-1 flex flex-col px-4 py-4 gap-4 overflow-y-auto">
                {/* 任务名称（只读） */}
                <div>
                    <label className="block text-xs text-white/50 mb-1.5">任务名称</label>
                    <div className="px-3 py-2 rounded bg-white/5 border border-white/10 text-sm text-white/70">
                        {params.taskName}
                    </div>
                </div>

                {/* 时间信息 */}
                <div className="grid grid-cols-2 gap-3">
                    <div>
                        <label className="block text-xs text-white/50 mb-1.5">开始时间</label>
                        <div className="px-3 py-2 rounded bg-white/5 border border-white/10 text-sm text-white/70">
                            {formatTime(params.startTime)}
                        </div>
                    </div>
                    <div>
                        <label className="block text-xs text-white/50 mb-1.5">结束时间</label>
                        <div className="px-3 py-2 rounded bg-white/5 border border-white/10 text-sm text-white/70">
                            {formatTime(params.endTime)}
                        </div>
                    </div>
                </div>

                {/* 时长 */}
                <div>
                    <label className="block text-xs text-white/50 mb-1.5">时长</label>
                    <div className="px-3 py-2 rounded bg-white/5 border border-white/10 text-sm text-white/70">
                        {params.duration} 分钟
                    </div>
                </div>

                {/* 活动内容输入框 */}
                <div className="flex-1 flex flex-col">
                    <label className="block text-xs text-white/50 mb-1.5">活动内容</label>
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
