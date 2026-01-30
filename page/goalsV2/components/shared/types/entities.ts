
export type ThemeKey = 'indigo' | 'rose' | 'amber' | 'emerald' | 'violet' | 'cyan';

export interface MilestoneItem {
    id: string;
    content: string;
    state: number; // 0: Pending, 1: Completed
    finishTime: string | null;
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
    theme: ThemeKey;
    timeInvested: string;
    unit: string;
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
    goalId: string;
    title: string;
    content: string;
    createdAt: string;
    updatedAt: string;
    status: 'active' | 'completed' | 'shelved';
}
