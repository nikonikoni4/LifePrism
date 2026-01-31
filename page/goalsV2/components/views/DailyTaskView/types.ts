/**
 * DailyTaskView 组件类型定义
 */

export interface DailyTaskStats {
    total: number;
    completed: number;
    overdue: number;
}

export interface SelectOption {
    id: string;
    label: string;
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
