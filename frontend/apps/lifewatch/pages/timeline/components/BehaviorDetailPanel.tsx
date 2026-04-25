/**
 * BehaviorDetailPanel 组件
 *
 * 行为分析详情面板
 *
 * 设计规范：
 * - 嵌入式面板，显示在右侧详情区域
 * - 显示 behavior_summary 和 behavior
 * - 风格与 Timeline 右侧面板保持一致
 */

import React from 'react';
import { Clock } from 'lucide-react';
import { BehaviorAnalysisItem } from '../types';

interface BehaviorDetailPanelProps {
    behavior: BehaviorAnalysisItem | null;
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
    onClose,
}) => {
    if (!behavior) {
        return null;
    }

    const date = formatDate(behavior.start_time);
    const startTime = formatTime(behavior.start_time);
    const endTime = formatTime(behavior.end_time);
    const duration = formatDuration(behavior.start_time, behavior.end_time);

    return (
        <div className="p-8 h-full flex flex-col animate-fade-in">
            {/* Header */}
            <div className="flex items-center gap-2 mb-6 text-xs font-bold text-gray-400 uppercase tracking-widest">
                <Clock size={14} />
                Behavior Analysis
            </div>

            {/* 基本信息 */}
            <div className="mb-8">
                <h2 className="text-2xl font-bold text-slate-900 mb-4">{behavior.title}</h2>
                <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2 text-slate-500 font-mono">
                        <span>📅</span>
                        <span>{date}</span>
                    </div>
                    <div className="flex items-center gap-2 text-slate-500 font-mono">
                        <span>⏰</span>
                        <span>{startTime} → {endTime}</span>
                        <span className="text-slate-300">|</span>
                        <span>{duration}</span>
                    </div>
                    <div className="flex items-center gap-2 text-slate-500 font-mono">
                        <span>📸</span>
                        <span>{behavior.screen_count} 张截图</span>
                    </div>
                </div>
            </div>

            {/* 内容区域 */}
            <div className="flex-1 overflow-y-auto space-y-6">
                {/* 总结 */}
                <div>
                    <label className="block text-xs font-bold text-slate-700 mb-2">总结</label>
                    <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                            {behavior.behavior_summary}
                        </p>
                    </div>
                </div>

                {/* 详细行为 */}
                <div>
                    <label className="block text-xs font-bold text-slate-700 mb-2">详细行为</label>
                    <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                            {behavior.behavior}
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default BehaviorDetailPanel;
