/**
 * 跨区域拖拽组件库使用示例
 * 
 * 本文件展示如何将 dragDrop 组件库与 todoItem 组件库结合使用
 * 实现任务池 → 日历的跨区域拖拽功能
 */

import React, { useState, useCallback } from 'react';
import {
    CrossAreaDndProvider,
    DraggableItem,
    DroppableDateCell,
    DroppablePoolRoot,
    useCrossAreaDnd,
    type DragItemData,
    type DropAreaData,
} from '../index';
import { TodoItem as TodoItemType } from '../../todoItem/types';
import { TodoItem } from '../../todoItem/TodoItem';

// =============================================================================
// 示例 1: 使用 CrossAreaDndProvider 组件
// =============================================================================

interface TaskPoolCalendarExampleProps {
    tasks: TodoItemType[];
    onScheduleTask: (task: TodoItemType, date: string) => void;
    onUnscheduleTask: (task: TodoItemType) => void;
}

/**
 * 任务池 + 日历布局示例
 * 支持从任务池拖拽任务到日历日期
 */
export const TaskPoolCalendarExample: React.FC<TaskPoolCalendarExampleProps> = ({
    tasks,
    onScheduleTask,
    onUnscheduleTask,
}) => {
    // 分离任务池任务和已安排任务
    const poolTasks = tasks.filter(t => t.state === 'pool');
    const scheduledTasks = tasks.filter(t => t.state === 'scheduled');

    // 按日期分组已安排的任务
    const tasksByDate = scheduledTasks.reduce((acc, task) => {
        if (task.scheduledDate) {
            if (!acc[task.scheduledDate]) {
                acc[task.scheduledDate] = [];
            }
            acc[task.scheduledDate].push(task);
        }
        return acc;
    }, {} as Record<string, TodoItemType[]>);

    // 处理跨区域拖拽
    const handleCrossAreaDrop = useCallback((
        dragItem: DragItemData<TodoItemType>,
        dropArea: DropAreaData<{ date?: string }>
    ) => {
        const task = dragItem.payload;

        if (dropArea.type === 'date-cell' && dropArea.payload?.date) {
            // 从任务池拖到日历 → 安排任务
            onScheduleTask(task, dropArea.payload.date);
        } else if (dropArea.type === 'pool-root') {
            // 从日历拖回任务池 → 取消安排
            onUnscheduleTask(task);
        }
    }, [onScheduleTask, onUnscheduleTask]);

    // 生成本周日期
    const weekDates = getWeekDates();

    return (
        <CrossAreaDndProvider
            onCrossAreaDrop={handleCrossAreaDrop}
            renderDragOverlay={(dragItem) => (
                <div className="bg-white shadow-2xl rounded-xl border-2 border-indigo-400 p-3 opacity-90 rotate-2">
                    <span className="text-sm font-medium text-slate-700">
                        {(dragItem.payload as TodoItemType).content}
                    </span>
                </div>
            )}
        >
            <div className="flex gap-4 h-screen p-4 bg-slate-50">
                {/* 左侧：任务池 */}
                <div className="w-80 bg-white rounded-2xl shadow-sm border border-slate-200 p-4">
                    <h2 className="text-lg font-bold text-slate-800 mb-4">任务池</h2>

                    <DroppablePoolRoot className="space-y-2 min-h-[200px]">
                        {poolTasks.map(task => (
                            <DraggableItem
                                key={task.id}
                                id={task.id}
                                type="task"
                                source="task-pool"
                                data={task}
                                withChildren={task.children && task.children.length > 0}
                                draggingClassName="opacity-50 scale-105 shadow-xl"
                            >
                                <TodoItem
                                    todo={task}
                                    onUpdate={() => { }}
                                    onDelete={() => { }}
                                    showDate={false}
                                />
                            </DraggableItem>
                        ))}

                        {poolTasks.length === 0 && (
                            <div className="text-center text-slate-400 text-sm py-8">
                                任务池为空
                            </div>
                        )}
                    </DroppablePoolRoot>
                </div>

                {/* 右侧：日历 */}
                <div className="flex-1 bg-white rounded-2xl shadow-sm border border-slate-200 p-4">
                    <h2 className="text-lg font-bold text-slate-800 mb-4">本周日历</h2>

                    <div className="grid grid-cols-7 gap-2">
                        {weekDates.map(date => (
                            <DroppableDateCell
                                key={date}
                                date={date}
                                className="bg-slate-50 hover:bg-slate-100"
                            >
                                {/* 日期标题 */}
                                <div className="text-xs font-bold text-slate-500 p-2 border-b border-slate-200">
                                    {formatDate(date)}
                                </div>

                                {/* 已安排的任务 */}
                                <div className="p-2 space-y-1">
                                    {(tasksByDate[date] || []).map(task => (
                                        <DraggableItem
                                            key={task.id}
                                            id={task.id}
                                            type="task"
                                            source="calendar"
                                            data={task}
                                            draggingClassName="opacity-50"
                                        >
                                            <div className="text-xs bg-violet-100 text-violet-700 px-2 py-1 rounded truncate">
                                                {task.content}
                                            </div>
                                        </DraggableItem>
                                    ))}
                                </div>
                            </DroppableDateCell>
                        ))}
                    </div>
                </div>
            </div>
        </CrossAreaDndProvider>
    );
};

// =============================================================================
// 示例 2: 使用 useCrossAreaDnd Hook（更灵活的方式）
// =============================================================================

import {
    DndContext,
    DragOverlay,
    pointerWithin,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';

export const TaskPoolCalendarWithHook: React.FC<TaskPoolCalendarExampleProps> = ({
    tasks,
    onScheduleTask,
    onUnscheduleTask,
}) => {
    const {
        handleDragStart,
        handleDragEnd,
        handleDragOver,
        activeItem,
        isDragging,
    } = useCrossAreaDnd<TodoItemType, { date?: string }>({
        onCrossAreaDrop: (dragItem, dropArea) => {
            const task = dragItem.payload;

            if (dropArea.type === 'date-cell' && dropArea.payload?.date) {
                onScheduleTask(task, dropArea.payload.date);
            } else if (dropArea.type === 'pool-root') {
                onUnscheduleTask(task);
            }
        },
        onDragStart: (event) => {
            console.log('开始拖拽:', event.dragItem);
        },
        onDragEnd: (event) => {
            console.log('结束拖拽:', event.isCrossArea ? '跨区域' : '同区域');
        },
    });

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    return (
        <DndContext
            sensors={sensors}
            collisionDetection={pointerWithin}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDragEnd={handleDragEnd}
        >
            <div className="flex gap-4">
                {/* 你的布局内容 */}
            </div>

            {/* 自定义拖拽预览 */}
            <DragOverlay>
                {isDragging && activeItem && (
                    <div className="bg-white shadow-2xl rounded-xl p-3">
                        {activeItem.payload.content}
                    </div>
                )}
            </DragOverlay>
        </DndContext>
    );
};

// =============================================================================
// 工具函数
// =============================================================================

function getWeekDates(): string[] {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const startOfWeek = new Date(today);
    startOfWeek.setDate(today.getDate() - dayOfWeek);

    return Array.from({ length: 7 }, (_, i) => {
        const date = new Date(startOfWeek);
        date.setDate(startOfWeek.getDate() + i);
        return date.toISOString().split('T')[0];
    });
}

function formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    const weekDays = ['日', '一', '二', '三', '四', '五', '六'];
    return `${date.getMonth() + 1}/${date.getDate()} ${weekDays[date.getDay()]}`;
}

export default TaskPoolCalendarExample;
