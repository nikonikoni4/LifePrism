/**
 * 习惯系统后端 API 响应/请求 Schema 定义
 * 基于 docs/需求文档/功能需求/习惯系统/api接口.md 编写
 */

// ==========================================
// 枚举类型
// ==========================================

export type HabitStatus = 'active' | 'paused';
export type ChallengeStatus = 'in_progress' | 'succeeded' | 'failed' | 'cancelled';
export type FrequencyType = 'daily' | 'weekdays' | 'weekend' | 'custom';

// ==========================================
// 基础实体子模型
// ==========================================

export interface FrequencyObject {
    type: FrequencyType;
    specificDays?: number[]; // 取值 1-7（1=周一，7=周日），仅 type=custom 时有效
}

export interface ChallengeObject {
    id: string;
    habitId: string;
    fromLevel: number;
    toLevel: number;
    challengeWeeks: number;
    requiredCompletions: number;
    completedCount: number;
    startDate: string; // YYYY-MM-DD
    endDate: string; // YYYY-MM-DD
    streakBase: number;
    status: ChallengeStatus;
    finishedAt?: string | null; // ISO 8601
}

export interface AnchorInfoObject {
    chainName: string;
    nodeName: string;
    triggerTime: string | null; // HH:mm
}

export interface HabitListItem {
    id: string;
    name: string;
    description: string | null;
    frequency: FrequencyObject;
    currentLevel: number;
    status: HabitStatus;
    currentChallenge: ChallengeObject | null;
    valueId: string | null;
    commitmentId: string | null;
    createdAt: string; // ISO 8601
    pausedAt: string | null; // ISO 8601
    streak: number;
    todayCompleted: boolean;
    anchorInfo: AnchorInfoObject | null;
}

// 获取详情复用列表项结构
export type HabitDetailResponse = HabitListItem;

export interface CheckInObject {
    id: string;
    habitId: string;
    challengeId: string;
    date: string; // YYYY-MM-DD
    completed: boolean;
    completedAt: string; // ISO 8601
    createdAt: string; // ISO 8601
}

export interface SettlementItem {
    challengeId: string;
    habitId: string;
    habitName: string;
    result: 'succeeded' | 'failed';
    fromLevel: number;
    toLevel: number;
    completedCount: number;
    requiredCompletions: number;
    canSaveByBackfill: boolean;
}

export interface CheckSettlementsResponse {
    settlements: SettlementItem[];
}

export interface SettlementActionRequest {
    source: 'settlement';
    challengeId: string;
}

export interface ChainNodeObject {
    id: number;
    chainId: number;
    sortOrder: number;
    name: string;
    habitId: string | null;
    habitName: string | null;
    triggerTime: string | null; // HH:mm
    createdAt: string; // ISO 8601
    updatedAt: string; // ISO 8601
}

export interface ChainListItem {
    id: number;
    name: string;
    description: string | null;
    showInTimeline: boolean;
    createdAt: string; // ISO 8601
    nodes: ChainNodeObject[];
}

// ==========================================
// API 请求与响应包装模型
// ==========================================

// Habits
export interface HabitListResponse {
    habits: HabitListItem[];
}

export interface CreateHabitRequest {
    name: string;
    description?: string | null;
    frequency: FrequencyObject;
    initialLevel?: number; // default 0
    valueId?: string;
    commitmentId?: string;
}

export interface UpdateHabitRequest {
    name?: string;
    description?: string | null;
    frequency?: FrequencyObject;
    level?: number;
    valueId?: string | null;
    commitmentId?: string | null;
}

// Check-in
export interface CheckInResponse {
    checkin: CheckInObject;
    habit: HabitListItem;
    settlement: SettlementItem | null;
}

export interface CancelCheckInResponse {
    habit: HabitListItem;
    settlement: SettlementItem | null;
}

export interface BackfillCheckInRequest {
    challengeId: string;
    date: string; // YYYY-MM-DD
}

export interface BackfillAvailabilityRequest {
    habitId: string;
    challengeId: string;
}

export interface BackfillAvailabilityDay {
    date: string;
    selectable: boolean;
    reason: 'already_checked_in' | 'before_challenge_start' | 'after_challenge_end' | null;
}

export interface BackfillAvailabilityResponse {
    habitId: string;
    challengeId: string;
    days: BackfillAvailabilityDay[];
}

// Stats
export interface TodayOverviewResponse {
    scheduledCount: number;
    completedCount: number;
    completionRate: number | null; // 0-1
    isRestDay: boolean;
}

export interface WeeklyRateItem {
    weekStartDate: string; // YYYY-MM-DD
    weekEndDate: string; // YYYY-MM-DD
    rate: number; // 0-1
    habitCount: number;
}

export interface WeeklyStatsResponse {
    weeks: WeeklyRateItem[];
}

export interface HeatmapDayItem {
    date: string; // YYYY-MM-DD
    totalHabits: number;
    completedHabits: number;
    completionRate: number | null; // 0-1
    isRestDay: boolean;
}

export interface HeatmapResponse {
    days: HeatmapDayItem[];
}

// Chains
export interface ChainListResponse {
    chains: ChainListItem[];
}

export interface CreateChainRequest {
    name: string;
    description?: string | null;
    showInTimeline?: boolean;
}

export interface UpdateChainRequest {
    name?: string;
    description?: string | null;
    showInTimeline?: boolean;
    triggerTimes?: Array<{ nodeId: number; triggerTime: string }>;
}

export interface CreateChainNodeRequest {
    name: string;
    habitId?: string | null;
    triggerTime?: string | null;
    insertAfterNodeId?: number | null;
}

export interface UpdateChainNodeRequest {
    name?: string;
    habitId?: string | null;
    triggerTime?: string | null;
}

export interface ReorderNodeItem {
    nodeId: number;
    sortOrder: number;
}

export interface ReorderNodesRequest {
    nodes: ReorderNodeItem[];
}

// Timeline
export interface TimelineResponse {
    chains: ChainListItem[];
}
