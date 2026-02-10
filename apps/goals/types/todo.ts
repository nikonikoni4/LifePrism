export interface TodoItem {
    id: number;
    content: string;
    parentId: string | null;
    goalId: string | null;
    planDocId: string | null;
    sourceAnchorId: string | null;
    state: 'pool' | 'scheduled' | 'completed' | 'shelved';
    scheduledDate: string | null;
    expectedFinishAt: string | null;
    actualFinishAt: string | null;
    delayDays: number | null;
    delayReason: string | null;
    color: string;
    orderIndex: number;
    poolOrderIndex: number | null;
    waidOrder: number | null;
    children?: TodoItem[];
}
