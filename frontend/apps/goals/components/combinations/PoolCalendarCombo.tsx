
import React from 'react';
import { DualPaneLayout } from '../layout/DualPaneLayout';
import { TaskPoolView } from '../views/TaskPoolView/TaskPoolView';
import { CalendarView } from '../views/CalendarView/CalendarView';
import { CrossAreaDndProvider, DragItemData, DropAreaData } from '@my-ui-kit/core';
import { useTaskPoolStore } from '../../hooks/useTaskPoolStore';
import { TodoItem } from '../../types/todo';

export const PoolCalendarCombo: React.FC = () => {
  const { tasks, scheduleTask, moveTaskToPool } = useTaskPoolStore();

  /**
   * 获取任务的所有子任务ID（递归）
   */
  const getChildTaskIds = (taskId: string): string[] => {
    const childIds: string[] = [];
    const children = tasks.filter(t => t.parentId === taskId);

    children.forEach(child => {
      childIds.push(child.id);
      childIds.push(...getChildTaskIds(child.id));
    });

    return childIds;
  };

  const handleCrossAreaDrop = (
    dragItem: DragItemData<TodoItem>,
    dropArea: DropAreaData<{ date?: string }>
  ) => {
    const task = dragItem.payload;
    const affectedTaskIds = [task.id, ...getChildTaskIds(task.id)];

    if (dropArea.type === 'date-cell' && dropArea.payload?.date) {
      // Drop on a specific date (From Pool or another Date in Calendar)
      // 父任务和所有子任务都安排到该日期
      affectedTaskIds.forEach(id => {
        scheduleTask(id, dropArea.payload.date!);
      });
    } else if (dropArea.type === 'pool-root') {
      // Drop back to pool (From Calendar)
      // 父任务和所有子任务都移回任务池
      affectedTaskIds.forEach(id => {
        moveTaskToPool(id);
      });
    }
  };

  const renderDragOverlay = (dragItem: DragItemData<TodoItem>) => {
    // 防御性检查：确保 payload 存在
    if (!dragItem.payload) {
      return (
        <div className="bg-white/90 backdrop-blur rounded-xl shadow-lg border border-slate-200 p-3 w-64">
          <span className="text-sm text-slate-400">加载中...</span>
        </div>
      );
    }

    // 根据来源显示不同样式
    const isFromCalendar = dragItem.source === 'calendar';

    return (
      <div className={`
        bg-white/90 backdrop-blur rounded-xl shadow-[0_10px_40px_-10px_rgba(0,0,0,0.2)]
        border p-3 w-64 rotate-2 ring-2
        ${isFromCalendar
          ? 'border-violet-100 ring-violet-500/20'
          : 'border-indigo-100 ring-indigo-500/20'
        }
      `}>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full animate-pulse ${isFromCalendar ? 'bg-violet-500' : 'bg-indigo-500'}`} />
          <span className="text-sm font-bold text-slate-700 truncate">{dragItem.payload.content}</span>
        </div>
        {isFromCalendar && dragItem.payload.scheduledDate && (
          <div className="mt-1 text-[10px] text-violet-500 font-medium">
            从 {dragItem.payload.scheduledDate} 移动
          </div>
        )}
      </div>
    );
  };

  return (
    <CrossAreaDndProvider
      onCrossAreaDrop={handleCrossAreaDrop}
      renderDragOverlay={renderDragOverlay}
      activationDistance={5}
    >
      <DualPaneLayout
        left={<TaskPoolView disableInternalDnd={true} />}
        right={<CalendarView />}
      />
    </CrossAreaDndProvider>
  );
};
