/**
 * CustomBlockLayer 组件
 * 
 * 自定义时间块的透明色块渲染层
 * 
 * 设计规范：
 * - 作为半透明背景层显示在原有时间块之下
 * - 使用 Tailwind 100 系列颜色
 * - 左侧 3px 标识线
 * - 支持点击编辑
 */

import React, { useState, useCallback, useMemo } from 'react';
import { Plus } from 'lucide-react';
import { UserCustomBlock, PopoverFormData, TodoSelectItem } from './types';
import { CategoryTreeItem } from '../../../../../core/types/common-components';
import CustomBlockLabel, { calculateLabelOffsets } from './CustomBlockLabel';
import CustomBlockPopover from './CustomBlockPopover';
import { CustomBlockAPI } from './customBlockApi';
import { toISOStringUTC, parseISOString } from '../../../../../core/utils/dateUtils';

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
 *
 * ⚠️ 规则：接收 UTC ISO 时间，转换为本地时间后计算小时数
 * 后端存储的是 UTC，前端显示必须转为本地时间
 */
function timeToHour(timeStr: string): number {
    // 解析 UTC ISO 字符串为 Date 对象（浏览器自动转为本地时间）
    const date = parseISOString(timeStr);
    const hours = date.getHours();
    const minutes = date.getMinutes();
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
        initialTime?: string; // 初始时间（用于通过 + 按钮创建时预填）
    }>({
        isOpen: false,
        block: null,
        position: undefined,
    });
    const [isSaving, setIsSaving] = useState(false);

    // 标签区域悬停状态（用于显示跟随鼠标的 + 按钮）
    const [labelAreaHover, setLabelAreaHover] = useState<{
        y: number;      // 吸附后的 Y 坐标
        hour: number;   // 对应的小时数
    } | null>(null);

    // 计算标签偏移
    const labelOffsets = useMemo(() => calculateLabelOffsets(blocks), [blocks]);

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
        setPopoverState({
            isOpen: true,
            block,
            position: undefined, // 居中显示
        });
    }, []);

    // 处理标签区域鼠标移动（显示跟随的 + 按钮）
    const handleLabelAreaMouseMove = useCallback((e: React.MouseEvent) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const relativeY = e.clientY - rect.top;
        const hour = relativeY / hourHeight;

        // 吸附到最近的 5 分钟
        const snappedHour = Math.round(hour * 12) / 12; // 12 = 60/5
        const snappedY = snappedHour * hourHeight;

        setLabelAreaHover({ y: snappedY, hour: snappedHour });
    }, [hourHeight]);

    // 处理标签区域鼠标离开
    const handleLabelAreaMouseLeave = useCallback(() => {
        setLabelAreaHover(null);
    }, []);

    // 处理点击 + 按钮创建新块
    const handleAddButtonClick = useCallback((e: React.MouseEvent) => {
        e.stopPropagation();
        if (!labelAreaHover) return;

        const startTime = formatHHMM(labelAreaHover.hour);
        const endTime = formatHHMM(labelAreaHover.hour + 1);

        setPopoverState({
            isOpen: true,
            block: null, // null 表示创建新块
            position: undefined, // 居中显示
            initialTime: startTime, // 预填开始时间
        });

        // 隐藏 + 按钮
        setLabelAreaHover(null);
    }, [labelAreaHover]);

    // 关闭 Popover
    const handleClosePopover = useCallback(() => {
        console.log('[CustomBlockLayer] handleClosePopover 被调用');
        console.log('[CustomBlockLayer] 关闭前 popoverState:', popoverState);
        setPopoverState({
            isOpen: false,
            block: null,
            position: undefined,
        });
        console.log('[CustomBlockLayer] setPopoverState 已调用，设置 isOpen=false');
    }, [popoverState]);

    // 保存 Popover 数据
    const handleSavePopover = useCallback(async (data: PopoverFormData, blockId?: number) => {
        setIsSaving(true);
        try {
            // ✅ 就近转换：构造本地 Date 对象，立即转为 UTC ISO 后提交
            const localStartDate = new Date(`${currentDate}T${data.startTime}:00`);
            const localEndDate = new Date(`${currentDate}T${data.endTime}:00`);

            const startTimeStr = toISOStringUTC(localStartDate);
            const endTimeStr = toISOStringUTC(localEndDate);

            const duration = calculateDuration(`${currentDate}T${data.startTime}:00`, `${currentDate}T${data.endTime}:00`);

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
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: '保存失败，请重试' });
            } else {
                alert('保存失败，请重试');
            }
        } finally {
            setIsSaving(false);
        }
    }, [currentDate, handleClosePopover, onUpdate]);

    // 删除块
    const handleDelete = useCallback(async (blockId: number) => {
        console.log('=== [CustomBlockLayer] handleDelete 开始 ===');
        console.log('[CustomBlockLayer] blockId:', blockId);
        console.log('[CustomBlockLayer] popoverState:', popoverState);

        try {
            await CustomBlockAPI.delete(blockId);
            console.log('[CustomBlockLayer] API删除成功');

            console.log('[CustomBlockLayer] 调用 handleClosePopover');
            handleClosePopover();

            console.log('[CustomBlockLayer] 调用 onUpdate');
            onUpdate();

            // 延迟检查最终状态
            setTimeout(() => {
                const overlays = document.querySelectorAll('.fixed.inset-0');
                console.log('[CustomBlockLayer] 删除完成500ms后，遮罩层数量:', overlays.length);
                overlays.forEach((overlay, idx) => {
                    console.log(`  遮罩层 ${idx}:`, {
                        className: overlay.className,
                        zIndex: window.getComputedStyle(overlay).zIndex,
                    });
                });
            }, 500);
        } catch (error) {
            console.error('Failed to delete custom block:', error);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: '删除失败，请重试' });
            } else {
                alert('删除失败，请重试');
            }
        }
        console.log('=== [CustomBlockLayer] handleDelete 结束 ===');
    }, [handleClosePopover, onUpdate, popoverState]);

    // 渲染单个色块（背景层）
    const renderBlock = (block: UserCustomBlock) => {
        const startHour = timeToHour(block.start_time);
        const endHour = timeToHour(block.end_time);
        const top = startHour * hourHeight;
        const height = (endHour - startHour) * hourHeight;

        // 解析颜色：后端返回的可能是 hex 或者 tailwind 类名
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
                className="absolute w-full rounded-sm pointer-events-auto cursor-pointer
                           hover:opacity-80 transition-opacity duration-150"
                style={{
                    left: 0,
                    right: 0,
                    top: `${top}px`,
                    height: `${height}px`,
                    backgroundColor: bgColor,
                    borderLeft: `3px solid ${borderColor}`,
                }}
                onClick={(e) => handleBlockClick(e, block)}
            />
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

        return (
            <div
                key={`label-${block.id}`}
                className={`
                    absolute left-0 right-0 
                    flex flex-col items-center justify-center gap-0.5
                    px-1.5 cursor-pointer overflow-hidden
                    transition-opacity duration-150
                    hover:opacity-80
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

            {/* 背景色块层 - 从时间刻度右边到 behavior analysis 左侧 */}
            <div
                className="absolute left-16 right-[100px] top-0"
                style={{ height: `${24 * hourHeight}px`, zIndex: 0 }}
            >
                {blocks.map(renderBlock)}
            </div>

            {/* 标签区域 - 显示在时间刻度右边的标签列 */}
            <div
                className="absolute left-16 top-0 bottom-0 w-20 z-[3]"
                onMouseMove={handleLabelAreaMouseMove}
                onMouseLeave={handleLabelAreaMouseLeave}
            >
                <div className="relative h-full">
                    {blocks.map(renderLabel)}

                    {/* 跟随鼠标的添加按钮 - 紧贴左侧时间轴 */}
                    {labelAreaHover && (
                        <div
                            className="absolute left-0 -translate-y-1/2
                                       pointer-events-auto cursor-pointer
                                       transition-all duration-100 ease-out
                                       group"
                            style={{ top: `${labelAreaHover.y}px` }}
                            onClick={handleAddButtonClick}
                        >
                            {/* 竖直布局：时间在上，+ 在下 */}
                            <div className="flex flex-col items-center
                                            bg-white/95 backdrop-blur-sm
                                            rounded-md px-1 py-0.5
                                            shadow-sm border border-gray-200
                                            hover:bg-indigo-50 hover:border-indigo-300
                                            hover:shadow-md
                                            transition-all duration-150">
                                {/* 时间数字 */}
                                <span className="text-[8px] font-mono font-medium text-gray-500 
                                                 group-hover:text-indigo-600 transition-colors leading-none">
                                    {formatHHMM(labelAreaHover.hour)}
                                </span>
                                {/* + 号 */}
                                <Plus size={10} className="text-gray-400 group-hover:text-indigo-600 transition-colors" />
                            </div>
                        </div>
                    )}
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
                initialTime={popoverState.initialTime}
            />

            {/* 空状态提示 */}
            {blocks.length === 0 && !isLoading && !labelAreaHover && (
                <div className="absolute left-16 top-0 w-20 h-full flex items-center justify-center pointer-events-none z-[2]">
                    <div className="flex flex-col items-center gap-1 text-gray-300">
                        <Plus size={18} />
                        <span className="text-[10px] font-medium text-center leading-tight">移动到此处<br />添加备注</span>
                    </div>
                </div>
            )}
        </>
    );
};

export default CustomBlockLayer;
