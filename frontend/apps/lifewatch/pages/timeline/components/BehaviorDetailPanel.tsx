/**
 * BehaviorDetailPanel 组件
 *
 * 行为分析详情面板
 *
 * 设计规范：
 * - 从右侧滑入的独立面板
 * - 宽度 400px
 * - 显示 behavior_summary 和 behaviors
 * - 点击遮罩层或关闭按钮关闭
 */

import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { BehaviorAnalysisItem } from '../types';

interface BehaviorDetailPanelProps {
    behavior: BehaviorAnalysisItem | null;
    isOpen: boolean;
    onClose: () => void;
}

/**
 * 格式化持续时长
 */
function formatDuration(startTime: string, endTime: string): string {
    const start = new Date(startTime.replace(' ', 'T'));
    const end = new Date(endTime.replace(' ', 'T'));
    const diffMs = end.getTime() - start.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);

    const hours = Math.floor(diffMinutes / 60);
    const minutes = diffMinutes % 60;

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
}

/**
 * 格式化时间为 HH:MM
 */
function formatTime(timeStr: string): string {
    const timePart = timeStr.includes('T')
        ? timeStr.split('T')[1]
        : timeStr.split(' ')[1] || timeStr;
    return timePart.substring(0, 5);
}

/**
 * 格式化日期为 YYYY-MM-DD
 */
function formatDate(timeStr: string): string {
    const datePart = timeStr.includes('T')
        ? timeStr.split('T')[0]
        : timeStr.split(' ')[0] || timeStr;
    return datePart;
}

const BehaviorDetailPanel: React.FC<BehaviorDetailPanelProps> = ({
    behavior,
    isOpen,
    onClose,
}) => {
    // ESC 键关闭面板
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isOpen) {
                onClose();
            }
        };
        window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [isOpen, onClose]);

    if (!isOpen || !behavior) {
        return null;
    }

    const date = formatDate(behavior.start_time);
    const startTime = formatTime(behavior.start_time);
    const endTime = formatTime(behavior.end_time);
    const duration = formatDuration(behavior.start_time, behavior.end_time);

    return (
        <>
            {/* 遮罩层 */}
            <div
                className="fixed inset-0 bg-black/30 z-40"
                onClick={onClose}
            />

            {/* 面板 */}
            <div
                className="fixed top-0 right-0 bottom-0 w-[400px] bg-white shadow-2xl z-50
                           flex flex-col animate-slide-in-right"
            >
                {/* 标题栏 */}
                <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b">
                    <h3 className="text-base font-semibold text-gray-800">行为分析详情</h3>
                    <button
                        onClick={onClose}
                        className="p-1 hover:bg-gray-200 rounded transition-colors"
                    >
                        <X size={20} className="text-gray-600" />
                    </button>
                </div>

                {/* 内容区域 */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                    {/* 基本信息 */}
                    <div className="space-y-2 text-sm">
                        <div className="flex items-center gap-2 text-gray-600">
                            <span>📅</span>
                            <span>{date}</span>
                        </div>
                        <div className="flex items-center gap-2 text-gray-600">
                            <span>⏰</span>
                            <span>{startTime} ~ {endTime} ({duration})</span>
                        </div>
                        <div className="flex items-center gap-2 text-gray-600">
                            <span>📸</span>
                            <span>{behavior.screen_count} 张截图</span>
                        </div>
                    </div>

                    {/* 分隔线 */}
                    <div className="border-t" />

                    {/* 总结 */}
                    <div>
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">总结：</h4>
                        <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                            {behavior.behavior_summary}
                        </p>
                    </div>

                    {/* 分隔线 */}
                    <div className="border-t" />

                    {/* 详细行为 */}
                    <div>
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">详细行为：</h4>
                        <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                            {behavior.behaviors}
                        </p>
                    </div>
                </div>
            </div>
        </>
    );
};

export default BehaviorDetailPanel;
