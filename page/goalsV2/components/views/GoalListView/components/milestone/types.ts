export interface MilestoneItem {
    id: string;
    content: string;
    state: number;  // 0: Pending, 1: Completed
    finishTime: string | null;
    orderIndex: number;
}

export interface EditableMilestone {
    id: string;
    content: string;
    orderIndex: number;
}