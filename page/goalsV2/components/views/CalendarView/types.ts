/**
 * CalendarView 组件类型定义
 */

import type { TodoItemType as TodoItem } from '@my-ui-kit/core';

export interface DateCellData {
    date: string;        // YYYY-MM-DD
    tasks: TodoItem[];   // 该日期的任务（仅父任务）
}

export interface CalendarViewProps {
    // 暂无必须 props
}
