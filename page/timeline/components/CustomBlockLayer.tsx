/**
 * CustomBlockLayer 组件
 * 
 * 自定义时间块的透明色块渲染层
 * 
 * 设计规范：
 * - 作为半透明背景层显示在原有时间块之下
 * - 使用 Tailwind 100 系列颜色
 * - 左侧 3px 标识线
 * - 支持拖拽调整时间
 * - 支持点击编辑
 */

import React, { useState, useCallback, useMemo } from 'react';
import { Plus } from 'lucide-react';
import { UserCustomBlock, PopoverFormData, DragZone, TodoSelectItem } from './types';
import { CategoryTreeItem } from '../../common/types';
import { useCustomBlockDrag } from './useCustomBlockDrag';
import CustomBlockLabel, { calculateLabelOffsets } from './CustomBlockLabel';
import CustomBlockPopover from './CustomBlockPopover';
import { CustomBlockAPI } from './customBlockApi';

interface CustomBlockLayerProps {
    /** 当前日期 (YYYY-MM-DD) */
    currentDate: string;
    /** 自定义时间块列表 */
    blocks: UserCustomBlock[];
    /** 每小时的像素高度 */
    hourHeight: number;
    /** 分类列表 */
    categories: CategoryTreeItem[];
    /** 当天待办事项列表 */
    todos: TodoSelectItem[];
    /** 数据更新回调（刷新列表） */
    onUpdate: () => void;
    /** 是否正在加载 */
    isLoading?: boolean;
}

/**
 * 将时间字符串转换为小时浮点数
 */
function timeToHour(timeStr: string): number {
    const timePart = timeStr.includes('T') ? timeStr.split('T')[1] : timeStr.split(' ')[1] || timeStr;
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

/**
 * 计算持续时长（分钟）
 */
function calculateDuration(startTime: string, endTime: string): number {
    const startHour = timeToHour(startTime);
    const endHour = timeToHour(endTime);
    return Math.round((endHour - startHour) * 60);
}

// 常量：标签区域宽度
const LABEL_AREA_WIDTH = 80;

const CustomBlockLayer: React.FC<CustomBlockLayerProps> = ({
    currentDate,
    blocks,
    hourHeight,
    categories,
    todos,
    onUpdate,
    isLoading = false,
}) => {
    // Popover 状态
    const [popoverState, setPopoverState] = useState<{
        isOpen: boolean;
        block: UserCustomBlock | null;
        position: { x: number; y: number } | undefined;
    }>({
        isOpen: false,
        block: null,
        position: undefined,
    });
    const [isSaving, setIsSaving] = useState(false);

    // 悬停状态（用于显示光标）
    const [hoveredBlock, setHoveredBlock] = useState<{
        id: number;
        zone: DragZone;
    } | null>(null);

    // 计算标签偏移
    const labelOffsets = useMemo(() => calculateLabelOffsets(blocks), [blocks]);

    // 拖拽 Hook
    const { dragState, getDragZone, getCursorStyle, handleMouseDown, getPreviewTime } = useCustomBlockDrag({
        hourHeight,
        onDragStart: (blockId) => {
            console.log('Drag started:', blockId);
        },
        onDragEnd: async (blockId, startTime, endTime) => {
            console.log('Drag ended:', blockId, startTime, endTime);
            try {
                await CustomBlockAPI.update(blockId, {
                    start_time: startTime,
                    end_time: endTime,
                    duration: calculateDuration(startTime, endTime),
                });
                onUpdate();
            } catch (error) {
                console.error('Failed to update block time:', error);
            }
        },
        onDragCancel: () => {
            console.log('Drag cancelled');
        },
    });

    // 处理标签点击 - 打开 Popover
    const handleLabelClick = useCallback((block: UserCustomBlock) => {
        setPopoverState({
            isOpen: true,
            block,
            position: undefined, // 居中显示
        });
    }, []);

    // 处理色块点击 - 打开 Popover（居中显示）
    const handleBlockClick = useCallback((e: React.MouseEvent, block: UserCustomBlock) => {
        // 如果正在拖拽，不处理点击
        if (dragState.isDragging) return;

        setPopoverState({
            isOpen: true,
            block,
            position: undefined, // 居中显示
        });
    }, [dragState.isDragging]);

    // 处理双击创建新块
    const handleDoubleClick = useCallback((e: React.MouseEvent) => {
        // 计算点击位置对应的时间
        const rect = e.currentTarget.getBoundingClientRect();
        const relativeY = e.clientY - rect.top;
        const hour = relativeY / hourHeight;

        // 吸附到最近的 5 分钟
        const snappedHour = Math.round(hour * 12) / 12; // 12 = 60/5
        const startTime = formatHHMM(snappedHour);
        const endTime = formatHHMM(snappedHour + 1);

        setPopoverState({
            isOpen: true,
            block: null, // null 表示创建新块
            position: undefined, // 居中显示
        });
    }, [hourHeight]);

    // 关闭 Popover
    const handleClosePopover = useCallback(() => {
        setPopoverState({
            isOpen: false,
            block: null,
            position: undefined,
        });
    }, []);

    // 保存 Popover 数据
    const handleSavePopover = useCallback(async (data: PopoverFormData, blockId?: number) => {
        setIsSaving(true);
        try {
            const startTimeStr = `${currentDate}T${data.startTime}:00`;
            const endTimeStr = `${currentDate}T${data.endTime}:00`;
            const duration = calculateDuration(startTimeStr, endTimeStr);

            if (blockId) {
                // 更新
                await CustomBlockAPI.update(blockId, {
                    content: data.content,
                    start_time: startTimeStr,
                    end_time: endTimeStr,
                    duration,
                    category_id: data.categoryId,
                    sub_category_id: data.subCategoryId,
                    todo_id: data.todoId,
                    color: data.color,
                });
            } else {
                // 创建
                await CustomBlockAPI.create({
                    content: data.content,
                    start_time: startTimeStr,
                    end_time: endTimeStr,
                    duration,
                    category_id: data.categoryId,
                    sub_category_id: data.subCategoryId,
                    todo_id: data.todoId,
                    color: data.color,
                });
            }

            handleClosePopover();
            onUpdate();
        } catch (error) {
            console.error('Failed to save custom block:', error);
            alert('保存失败，请重试');
        } finally {
            setIsSaving(false);
        }
    }, [currentDate, handleClosePopover, onUpdate]);

    // 删除块
    const handleDelete = useCallback(async (blockId: number) => {
        try {
            await CustomBlockAPI.delete(blockId);
            handleClosePopover();
            onUpdate();
        } catch (error) {
            console.error('Failed to delete custom block:', error);
            alert('删除失败，请重试');
        }
    }, [handleClosePopover, onUpdate]);

    // 处理鼠标移动（用于更新光标）
    const handleMouseMove = useCallback((e: React.MouseEvent, block: UserCustomBlock) => {
        if (dragState.isDragging) return;
        const zone = getDragZone(e, block);
        setHoveredBlock({ id: block.id, zone });
    }, [dragState.isDragging, getDragZone]);

    // 处理鼠标离开
    const handleMouseLeave = useCallback(() => {
        if (!dragState.isDragging) {
            setHoveredBlock(null);
        }
    }, [dragState.isDragging]);

    // 获取拖拽预览时间
    const previewTime = getPreviewTime();

    // 渲染单个色块（背景层）
    const renderBlock = (block: UserCustomBlock) => {
        const startHour = timeToHour(block.start_time);
        const endHour = timeToHour(block.end_time);
        const top = startHour * hourHeight;
        const height = (endHour - startHour) * hourHeight;

        // 如果正在拖拽这个块，使用拖拽状态的时间
        const isDragging = dragState.isDragging && dragState.blockId === block.id;
        let displayTop = top;
        let displayHeight = height;

        if (isDragging) {
            const dragStartHour = timeToHour(dragState.currentStartTime);
            const dragEndHour = timeToHour(dragState.currentEndTime);
            displayTop = dragStartHour * hourHeight;
            displayHeight = (dragEndHour - dragStartHour) * hourHeight;
        }

        // 获取当前光标样式
        const cursorStyle = hoveredBlock?.id === block.id
            ? getCursorStyle(hoveredBlock.zone)
            : 'pointer';

        // 解析颜色：后端返回的可能是 hex 或者 tailwind 类名
        // 使用极浅色并添加透明度，让下面的内容可见
        const baseColor = block.color.startsWith('#') ? block.color : '#dcfce7'; // green-100 fallback
        const borderColor = block.color.startsWith('#') ? block.color : '#22c55e'; // green-500 fallback

        // 将 hex 颜色转换为 rgba 格式，添加透明度
        const hexToRgba = (hex: string, alpha: number): string => {
            if (!hex.startsWith('#')) return hex;
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        };

        // 背景色使用 50% 透明度
        const bgColor = hexToRgba(baseColor, 0.5);

        return (
            <div
                key={block.id}
                className={`
                    absolute w-full
                    transition-all duration-75 ease-out
                    rounded-sm pointer-events-auto
                    ${isDragging ? 'opacity-90 shadow-lg' : ''}
                `}
                style={{
                    left: 0,
                    right: 0,
                    top: `${displayTop}px`,
                    height: `${displayHeight}px`,
                    backgroundColor: bgColor,
                    borderLeft: `3px solid ${borderColor}`,
                    cursor: cursorStyle,
                    zIndex: isDragging ? 10 : 0,
                }}
                onClick={(e) => handleBlockClick(e, block)}
                onMouseMove={(e) => handleMouseMove(e, block)}
                onMouseLeave={handleMouseLeave}
                onMouseDown={(e) => {
                    const zone = getDragZone(e, block);
                    handleMouseDown(e, block, zone);
                }}
            >
                {/* 拖拽时显示时间预览 */}
                {isDragging && previewTime && (
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="bg-black/70 text-white px-3 py-1.5 rounded-lg text-sm font-mono font-bold shadow-lg">
                            {previewTime.start} - {previewTime.end}
                        </div>
                    </div>
                )}
            </div>
        );
    };

    // 渲染标签
    const renderLabel = (block: UserCustomBlock) => {
        const startHour = timeToHour(block.start_time);
        const endHour = timeToHour(block.end_time);
        const blockHeight = (endHour - startHour) * hourHeight;
        const offsetIndex = labelOffsets.get(block.id) || 0;

        // 标签撑满整个色块高度
        const top = startHour * hourHeight;

        // 解析颜色
        const dotColor = block.color?.startsWith('#') ? block.color : '#22c55e';
        const isDragging = dragState.isDragging && dragState.blockId === block.id;

        return (
            <div
                key={`label-${block.id}`}
                className={`
                    absolute left-0 right-0 
                    flex flex-col items-center justify-center gap-0.5
                    px-1.5 cursor-pointer overflow-hidden
                    transition-opacity duration-150
                    ${isDragging ? 'opacity-50' : 'hover:opacity-80'}
                `}
                style={{
                    top: `${top}px`,
                    height: `${blockHeight}px`,
                    pointerEvents: 'auto',
                }}
                onClick={() => handleLabelClick(block)}
                title={block.todo_content ? `${block.content}\n📝 ${block.todo_content}` : block.content}
            >
                {/* 颜色指示点 */}
                <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: dotColor }}
                />
                {/* content 在上 */}
                <span className="text-[10px] font-medium text-gray-700 break-all text-center leading-[1.1] max-h-[50%] overflow-hidden">
                    {block.content}
                </span>
                {/* todo_content 在下（如果有） */}
                {block.todo_content && (
                    <span className="text-[9px] text-gray-500 break-all text-center leading-[1.1] max-h-[40%] overflow-hidden">
                        📝 {block.todo_content}
                    </span>
                )}
            </div>
        );
    };

    return (
        <>
            {/* 
                新布局结构说明（CustomBlockLayer 现在在 Timeline 的第一级）：
                - 背景色块：absolute left-16 right-0（从时间刻度右边到最右边）
                - 标签区域：absolute left-16 w-20（80px）
                - z-index: 0 确保在 ThumbnailBlock 之下
            */}

            {/* 背景色块层 - 从时间刻度右边横跨到最右边 */}
            <div
                className="absolute left-16 right-0 top-0"
                style={{ height: `${24 * hourHeight}px`, zIndex: 0 }}
                onDoubleClick={handleDoubleClick}
            >
                {blocks.map(renderBlock)}
            </div>

            {/* 标签区域 - 显示在时间刻度右边的标签列 */}
            <div
                className="absolute left-16 top-0 bottom-0 w-20 z-[3]"
            >
                <div className="relative h-full">
                    {blocks.map(renderLabel)}
                </div>
            </div>

            {/* 编辑弹出框 */}
            <CustomBlockPopover
                block={popoverState.block}
                isOpen={popoverState.isOpen}
                position={popoverState.position}
                categories={categories}
                todos={todos}
                onSave={handleSavePopover}
                onClose={handleClosePopover}
                onDelete={handleDelete}
                isSaving={isSaving}
                currentDate={currentDate}
            />

            {/* 添加按钮提示 */}
            {blocks.length === 0 && !isLoading && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-5">
                    <div className="flex flex-col items-center gap-2 text-gray-400">
                        <Plus size={24} />
                        <span className="text-xs font-medium">双击添加自定义时间块</span>
                    </div>
                </div>
            )}
        </>
    );
};

export default CustomBlockLayer;
