/**
 * BehaviorBlockLayer 组件
 *
 * 行为分析色块渲染层（只读）
 *
 * 设计规范：
 * - 作为半透明背景层显示在 Timeline 右侧
 * - 使用浅蓝色（区别于 CustomBlock 的绿色）
 * - 左侧 3px 蓝色边框
 * - 只读显示，点击打开详情面板
 */

import React from 'react';
import { BehaviorAnalysisItem } from '../types';

interface BehaviorBlockLayerProps {
    behaviors: BehaviorAnalysisItem[];
    hourHeight: number;
    onBehaviorClick: (item: BehaviorAnalysisItem) => void;
    isLoading?: boolean;
}

/**
 * 将时间字符串转换为小时浮点数
 */
function timeToHour(timeStr: string): number {
    const timePart = timeStr.includes('T')
        ? timeStr.split('T')[1]
        : timeStr.split(' ')[1] || timeStr;
    const [hours, minutes] = timePart.split(':').map(Number);
    return hours + minutes / 60;
}

/**
 * 格式化 HH:MM
 */
function formatHHMM(hour: number): string {
    const h = Math.floor(hour);
    const m = Math.round((hour - h) * 60);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

const BehaviorBlockLayer: React.FC<BehaviorBlockLayerProps> = ({
    behaviors,
    hourHeight,
    onBehaviorClick,
    isLoading = false,
}) => {
    // 渲染单个色块
    const renderBlock = (behavior: BehaviorAnalysisItem) => {
        const startHour = timeToHour(behavior.start_time);
        const endHour = timeToHour(behavior.end_time);
        const top = startHour * hourHeight;
        const height = (endHour - startHour) * hourHeight;

        return (
            <div
                key={`block-${behavior.start_time}-${behavior.end_time}`}
                className="absolute w-full rounded-sm cursor-pointer
                           hover:opacity-80 transition-opacity duration-150"
                style={{
                    left: 0,
                    right: 0,
                    top: `${top}px`,
                    height: `${height}px`,
                    backgroundColor: 'rgba(191, 219, 254, 0.5)',
                    borderLeft: '3px solid #3b82f6',
                }}
                onClick={() => onBehaviorClick(behavior)}
            />
        );
    };

    // 渲染标签
    const renderLabel = (behavior: BehaviorAnalysisItem) => {
        const startHour = timeToHour(behavior.start_time);
        const endHour = timeToHour(behavior.end_time);
        const top = startHour * hourHeight;
        const height = (endHour - startHour) * hourHeight;

        const startTime = formatHHMM(startHour);
        const endTime = formatHHMM(endHour);

        return (
            <div
                key={`label-${behavior.start_time}-${behavior.end_time}`}
                className="absolute left-0 right-0 flex items-center justify-center
                           px-1.5 cursor-pointer overflow-hidden
                           transition-opacity duration-150 hover:opacity-80"
                style={{
                    top: `${top}px`,
                    height: `${height}px`,
                }}
                onClick={() => onBehaviorClick(behavior)}
            >
                <span className="text-[10px] font-medium text-gray-700 text-center leading-tight">
                    {behavior.title}
                </span>
            </div>
        );
    };

    return (
        <>
            {/* 背景色块层 */}
            <div
                className="absolute right-0 w-[100px] top-0"
                style={{ height: `${24 * hourHeight}px`, zIndex: 0 }}
            >
                {behaviors.map(renderBlock)}
            </div>

            {/* 标签区域 */}
            <div className="absolute right-0 w-[100px] top-0 bottom-0 z-[3]">
                <div className="relative h-full">
                    {behaviors.map(renderLabel)}
                </div>
            </div>

            {/* 空状态提示 */}
            {behaviors.length === 0 && !isLoading && (
                <div className="absolute right-0 w-[100px] h-full
                                flex items-center justify-center
                                pointer-events-none z-[2]">
                    <div className="flex flex-col items-center gap-1 text-gray-300">
                        <span className="text-[10px] font-medium text-center leading-tight">
                            暂无行为分析
                        </span>
                    </div>
                </div>
            )}
        </>
    );
};

export default BehaviorBlockLayer;
