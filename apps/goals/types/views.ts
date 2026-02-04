/**
 * 视图/组件相关类型定义
 */

import type { TodoItem } from './todo';

// ============ CalendarView ============

export interface DateCellData {
    date: string;        // YYYY-MM-DD
    tasks: TodoItem[];   // 该日期的任务（仅父任务）
}

export interface CalendarViewProps {
    // 暂无必须 props
}

// ============ TaskPoolView ============

export interface TaskPoolViewProps {
    /** 禁用内部拖拽排序，用于跨区域拖拽场景 */
    disableInternalDnd?: boolean;
}

// ============ DailyTaskView ============

export interface DailyTaskStats {
    total: number;
    completed: number;
    overdue: number;
}

export interface DailyTaskHeaderProps {
    selectedDate: Date;
    completedCount: number;
    totalCount: number;
    overdueCount: number;
}

export interface DailyTaskToolbarProps {
    isAllExpanded: boolean;
    onToggleExpandAll: () => void;
    onReset: () => void;
}

export interface TaskInputBoxProps {
    goals: SelectOption[];
    planDocs: SelectOption[];
    selectedGoalId: string | null;
    selectedPlanDocId: string | null;
    onGoalChange: (id: string | null) => void;
    onPlanDocChange: (id: string | null) => void;
    onAddTask: (content: string) => void;
}

// ============ PlanDocEditorView ============

export interface PlanDocEditorViewProps {
    content: string;
    onChange: (content: string) => void;
    placeholder?: string;
    className?: string;
}

// ============ Common View Types ============

export interface SelectOption {
    id: string;
    label: string;
}

export interface BaseViewProps {
    className?: string;
}
