/**
 * useCustomBlockDrag Hook
 * 
 * 处理自定义时间块的拖拽交互逻辑，包括：
 * - 上边缘拖拽：调整开始时间
 * - 下边缘拖拽：调整结束时间
 * - 中间区域拖拽：整体移动
 * - 自动吸附到 5 分钟刻度
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { DragState, DragZone, UserCustomBlock } from './types';

// 常量
const EDGE_ZONE_SIZE = 8;       // 边缘检测区域大小（像素）
const SNAP_MINUTES = 5;         // 吸附到最近的分钟刻度
const MIN_DURATION_MINUTES = 5; // 最小持续时长（分钟）

interface UseCustomBlockDragOptions {
    hourHeight: number;                          // 每小时的像素高度
    onDragStart?: (blockId: number) => void;     // 拖拽开始回调
    onDragEnd?: (blockId: number, startTime: string, endTime: string) => void;  // 拖拽结束回调
    onDragCancel?: () => void;                   // 拖拽取消回调
}

interface UseCustomBlockDragReturn {
    dragState: DragState;
    getDragZone: (e: React.MouseEvent, block: UserCustomBlock) => DragZone;
    getCursorStyle: (zone: DragZone) => string;
    handleMouseDown: (e: React.MouseEvent, block: UserCustomBlock, zone: DragZone) => void;
    getPreviewTime: () => { start: string; end: string } | null;
}

/**
 * 将时间字符串（YYYY-MM-DDTHH:MM:SS）转换为小时浮点数
 */
function timeToHour(timeStr: string): number {
    const timePart = timeStr.includes('T') ? timeStr.split('T')[1] : timeStr.split(' ')[1] || timeStr;
    const [hours, minutes] = timePart.split(':').map(Number);
    return hours + minutes / 60;
}

/**
 * 将小时浮点数转换为 HH:MM 格式
 */
function hourToTimeString(hour: number): string {
    const clampedHour = Math.max(0, Math.min(24, hour));
    const h = Math.floor(clampedHour);
    const m = Math.round((clampedHour - h) * 60);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/**
 * 将小时数吸附到最近的 N 分钟刻度
 */
function snapToMinutes(hour: number, snapMinutes: number): number {
    const totalMinutes = hour * 60;
    const snapped = Math.round(totalMinutes / snapMinutes) * snapMinutes;
    return snapped / 60;
}

/**
 * 基于原始时间字符串和新的 HH:MM 时间，生成完整的时间字符串
 */
function buildTimeString(originalTime: string, newTime: string): string {
    const datePart = originalTime.split('T')[0] || originalTime.split(' ')[0];
    return `${datePart}T${newTime}:00`;
}

export function useCustomBlockDrag(options: UseCustomBlockDragOptions): UseCustomBlockDragReturn {
    const { hourHeight, onDragStart, onDragEnd, onDragCancel } = options;

    const [dragState, setDragState] = useState<DragState>({
        isDragging: false,
        dragZone: null,
        blockId: null,
        initialY: 0,
        initialStartTime: '',
        initialEndTime: '',
        currentStartTime: '',
        currentEndTime: '',
    });

    const dragRef = useRef(dragState);
    dragRef.current = dragState;

    /**
     * 根据鼠标位置判断在时间块的哪个区域
     */
    const getDragZone = useCallback((e: React.MouseEvent, block: UserCustomBlock): DragZone => {
        const rect = e.currentTarget.getBoundingClientRect();
        const relativeY = e.clientY - rect.top;
        const height = rect.height;

        if (relativeY <= EDGE_ZONE_SIZE) {
            return 'top';
        } else if (relativeY >= height - EDGE_ZONE_SIZE) {
            return 'bottom';
        } else {
            return 'middle';
        }
    }, []);

    /**
     * 根据拖拽区域返回对应的光标样式
     */
    const getCursorStyle = useCallback((zone: DragZone): string => {
        switch (zone) {
            case 'top': return 'n-resize';
            case 'bottom': return 's-resize';
            case 'middle': return 'move';
            default: return 'default';
        }
    }, []);

    /**
     * 处理鼠标按下事件 - 开始拖拽
     */
    const handleMouseDown = useCallback((e: React.MouseEvent, block: UserCustomBlock, zone: DragZone) => {
        if (zone === null) return;

        e.preventDefault();
        e.stopPropagation();

        setDragState({
            isDragging: true,
            dragZone: zone,
            blockId: block.id,
            initialY: e.clientY,
            initialStartTime: block.start_time,
            initialEndTime: block.end_time,
            currentStartTime: block.start_time,
            currentEndTime: block.end_time,
        });

        onDragStart?.(block.id);
    }, [onDragStart]);

    /**
     * 处理鼠标移动事件 - 拖拽中
     */
    const handleMouseMove = useCallback((e: MouseEvent) => {
        const state = dragRef.current;
        if (!state.isDragging) return;

        const deltaY = e.clientY - state.initialY;
        const deltaHours = deltaY / hourHeight;

        const initialStartHour = timeToHour(state.initialStartTime);
        const initialEndHour = timeToHour(state.initialEndTime);
        const duration = initialEndHour - initialStartHour;

        let newStartHour: number;
        let newEndHour: number;

        switch (state.dragZone) {
            case 'top':
                // 调整开始时间，结束时间不变
                newStartHour = snapToMinutes(initialStartHour + deltaHours, SNAP_MINUTES);
                newEndHour = initialEndHour;
                // 确保最小持续时长
                if (newEndHour - newStartHour < MIN_DURATION_MINUTES / 60) {
                    newStartHour = newEndHour - MIN_DURATION_MINUTES / 60;
                }
                // 边界检查
                newStartHour = Math.max(0, newStartHour);
                break;

            case 'bottom':
                // 调整结束时间，开始时间不变
                newStartHour = initialStartHour;
                newEndHour = snapToMinutes(initialEndHour + deltaHours, SNAP_MINUTES);
                // 确保最小持续时长
                if (newEndHour - newStartHour < MIN_DURATION_MINUTES / 60) {
                    newEndHour = newStartHour + MIN_DURATION_MINUTES / 60;
                }
                // 边界检查
                newEndHour = Math.min(24, newEndHour);
                break;

            case 'middle':
            default:
                // 整体移动，保持 duration 不变
                newStartHour = snapToMinutes(initialStartHour + deltaHours, SNAP_MINUTES);
                newEndHour = newStartHour + duration;
                // 边界检查
                if (newStartHour < 0) {
                    newStartHour = 0;
                    newEndHour = duration;
                }
                if (newEndHour > 24) {
                    newEndHour = 24;
                    newStartHour = 24 - duration;
                }
                break;
        }

        const newStartTime = buildTimeString(state.initialStartTime, hourToTimeString(newStartHour));
        const newEndTime = buildTimeString(state.initialEndTime, hourToTimeString(newEndHour));

        setDragState(prev => ({
            ...prev,
            currentStartTime: newStartTime,
            currentEndTime: newEndTime,
        }));
    }, [hourHeight]);

    /**
     * 处理鼠标松开事件 - 结束拖拽
     */
    const handleMouseUp = useCallback(() => {
        const state = dragRef.current;
        if (!state.isDragging) return;

        // 检查时间是否有变化
        const hasChanged = state.currentStartTime !== state.initialStartTime ||
            state.currentEndTime !== state.initialEndTime;

        if (hasChanged && state.blockId !== null) {
            onDragEnd?.(state.blockId, state.currentStartTime, state.currentEndTime);
        } else {
            onDragCancel?.();
        }

        // 重置拖拽状态
        setDragState({
            isDragging: false,
            dragZone: null,
            blockId: null,
            initialY: 0,
            initialStartTime: '',
            initialEndTime: '',
            currentStartTime: '',
            currentEndTime: '',
        });
    }, [onDragEnd, onDragCancel]);

    /**
     * 处理按下 Escape 键 - 取消拖拽
     */
    const handleKeyDown = useCallback((e: KeyboardEvent) => {
        if (e.key === 'Escape' && dragRef.current.isDragging) {
            onDragCancel?.();
            setDragState({
                isDragging: false,
                dragZone: null,
                blockId: null,
                initialY: 0,
                initialStartTime: '',
                initialEndTime: '',
                currentStartTime: '',
                currentEndTime: '',
            });
        }
    }, [onDragCancel]);

    // 绑定全局事件监听器
    useEffect(() => {
        if (dragState.isDragging) {
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
            document.addEventListener('keydown', handleKeyDown);
            // 防止拖拽时选中文本
            document.body.style.userSelect = 'none';
        }

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
            document.removeEventListener('keydown', handleKeyDown);
            document.body.style.userSelect = '';
        };
    }, [dragState.isDragging, handleMouseMove, handleMouseUp, handleKeyDown]);

    /**
     * 获取拖拽预览时间
     */
    const getPreviewTime = useCallback(() => {
        if (!dragState.isDragging) return null;

        const startHour = timeToHour(dragState.currentStartTime);
        const endHour = timeToHour(dragState.currentEndTime);

        return {
            start: hourToTimeString(startHour),
            end: hourToTimeString(endHour),
        };
    }, [dragState.isDragging, dragState.currentStartTime, dragState.currentEndTime]);

    return {
        dragState,
        getDragZone,
        getCursorStyle,
        handleMouseDown,
        getPreviewTime,
    };
}
