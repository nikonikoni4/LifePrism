/**
 * CalendarView 组件类型定义
 */

import type { TodoItem } from '../../shared/components/todoItem/types';

export interface DateCellData {
    date: string;        // YYYY-MM-DD
    tasks: TodoItem[];   // 该日期的任务（仅父任务）
}

export interface CalendarViewProps {
    // 暂无必须 props
}
