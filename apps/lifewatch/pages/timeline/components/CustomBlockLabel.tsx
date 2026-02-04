/**
 * CustomBlockLabel 组件
 * 
 * 显示在时间刻度和内容区域之间的自定义块标签
 * 
 * 样式规范：
 * - 显示前4字 + `...`（超出截断）
 * - Hover 时展开完整内容
 * - 颜色与对应 Custom Block 边框同色
 * - 多个 Custom Block 时间重叠时，标签垂直错开显示
 */

import React, { useState, useMemo } from 'react';
import { UserCustomBlock } from './types';

interface CustomBlockLabelProps {
    /** 自定义时间块数据 */
    block: UserCustomBlock;
    /** 垂直偏移量（用于重叠处理） */
    offsetIndex: number;
    /** 每小时的像素高度 */
    hourHeight: number;
    /** 点击标签回调（打开 Popover） */
    onClick: (block: UserCustomBlock) => void;
    /** 双击标签回调（内联重命名） */
    onDoubleClick?: (block: UserCustomBlock) => void;
    /** 是否处于编辑中 */
    isEditing?: boolean;
    /** 是否正在拖拽 */
    isDragging?: boolean;
}

// 常量
const LABEL_HEIGHT = 24;        // 标签高度（像素）
const LABEL_VERTICAL_GAP = 4;   // 标签垂直间距（像素）
const MAX_LABEL_CHARS = 4;      // 默认显示的最大字符数

/**
 * 将时间字符串转换为小时浮点数
 */
function timeToHour(timeStr: string): number {
    const timePart = timeStr.includes('T') ? timeStr.split('T')[1] : timeStr.split(' ')[1] || timeStr;
    const [hours, minutes] = timePart.split(':').map(Number);
    return hours + minutes / 60;
}

/**
 * 截断文本到指定字符数
 */
function truncateText(text: string, maxLength: number): string {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '...';
}

const CustomBlockLabel: React.FC<CustomBlockLabelProps> = ({
    block,
    offsetIndex,
    hourHeight,
    onClick,
    onDoubleClick,
    isEditing = false,
    isDragging = false,
}) => {
    const [isHovered, setIsHovered] = useState(false);

    // 计算标签位置
    const labelStyle = useMemo(() => {
        const startHour = timeToHour(block.start_time);
        const endHour = timeToHour(block.end_time);
        const blockHeight = (endHour - startHour) * hourHeight;

        // 标签垂直居中于色块，但需要考虑重叠偏移
        const baseTop = startHour * hourHeight + blockHeight / 2 - LABEL_HEIGHT / 2;
        const offsetTop = offsetIndex * (LABEL_HEIGHT + LABEL_VERTICAL_GAP);

        return {
            top: baseTop + offsetTop,
        };
    }, [block.start_time, block.end_time, hourHeight, offsetIndex]);

    // 显示文本
    const displayText = isHovered ? block.content : truncateText(block.content, MAX_LABEL_CHARS);

    // 从 Tailwind 100 色获取对应的深色（用于文字和边框）
    // 假设 block.color 是 Tailwind 100 系列颜色，我们需要使用更深的颜色显示文字
    const getAccentColor = (color: string): string => {
        // 简单处理：如果是浅色背景，返回一个更深的颜色
        // 这里我们使用子分类的颜色作为强调色
        return color;
    };

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        onClick(block);
    };

    const handleDoubleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        onDoubleClick?.(block);
    };

    return (
        <div
            className={`
                absolute right-0 
                flex items-center gap-1.5
                px-2 py-1
                text-xs font-medium
                rounded-r-md
                cursor-pointer
                transition-all duration-200 ease-out
                select-none
                z-10
                ${isDragging ? 'opacity-50' : ''}
                ${isEditing ? 'ring-2 ring-offset-1' : ''}
                ${isHovered ? 'shadow-md z-20' : 'hover:shadow-sm'}
            `}
            style={{
                top: `${labelStyle.top}px`,
                height: `${LABEL_HEIGHT}px`,
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                borderLeft: `3px solid ${block.color.replace('bg-', '#')}`,
                color: '#374151', // text-gray-700
                maxWidth: isHovered ? '200px' : '80px',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
            }}
            onClick={handleClick}
            onDoubleClick={handleDoubleClick}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            title={block.todo_content ? `${block.content}\n📝 ${block.todo_content}` : block.content}
        >
            {/* 颜色指示点 */}
            <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: block.color.startsWith('#') ? block.color : '#10b981' }}
            />
            {/* 标签文字 */}
            <span className="truncate">
                {displayText}
            </span>
        </div>
    );
};

export default CustomBlockLabel;

// ============================================================================
// 辅助函数：计算重叠偏移
// ============================================================================

/**
 * 计算每个 block 的标签偏移索引
 * 用于处理多个 Custom Block 时间重叠时的标签位置
 */
export function calculateLabelOffsets(blocks: UserCustomBlock[]): Map<number, number> {
    const offsets = new Map<number, number>();

    // 按开始时间排序
    const sortedBlocks = [...blocks].sort((a, b) => {
        return timeToHour(a.start_time) - timeToHour(b.start_time);
    });

    // 简单的贪心算法：检查与之前块的重叠情况
    sortedBlocks.forEach((block, index) => {
        const blockStart = timeToHour(block.start_time);
        const blockEnd = timeToHour(block.end_time);

        let maxOffset = -1;

        // 检查之前的块
        for (let i = 0; i < index; i++) {
            const prevBlock = sortedBlocks[i];
            const prevStart = timeToHour(prevBlock.start_time);
            const prevEnd = timeToHour(prevBlock.end_time);

            // 检查是否有时间重叠
            if (!(blockEnd <= prevStart || blockStart >= prevEnd)) {
                // 有重叠，取之前块的偏移量
                const prevOffset = offsets.get(prevBlock.id) || 0;
                maxOffset = Math.max(maxOffset, prevOffset);
            }
        }

        offsets.set(block.id, maxOffset + 1);
    });

    return offsets;
}
