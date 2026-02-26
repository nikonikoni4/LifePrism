/**
 * 核心业务实体类型定义
 */

export type ThemeKey = 'indigo' | 'rose' | 'amber' | 'emerald' | 'violet' | 'cyan';

export interface MilestoneItem {
    id: string;
    content: string;
    state: number; // 0: Pending, 1: Completed
    finishTime: string | null;
    orderIndex: number;
}

export interface EditableMilestone {
    id: string;
    content: string;
    orderIndex: number;
}

export interface JournalEntry {
    id: string;
    date: string;
    time: string;
    content: string;
    mood: 'joy' | 'calm' | 'frustrated' | 'neutral';
    duration: number;
    tags: string[];
}

export interface Goal {
    id: string;
    title: string;
    category: string;
    subCategory: string;
    theme: ThemeKey;
    timeInvested: string;  // 格式化字符串，如 "2h 30m"
    trackTimeAutomatically: boolean;
    startDate: string;
    endDate: string;
    value: string;
    commitment: string;
    details: string;
    status: 'active' | 'completed' | 'shelved';
    milestones: MilestoneItem[];
    journal: JournalEntry[];
    daysStarted?: number;
}

export interface PlanDoc {
    id: string;
    goalId: string | null;
    content: string;
    createdAt: string;
    updatedAt: string;
    status: 'active' | 'completed' | 'shelved';
}
