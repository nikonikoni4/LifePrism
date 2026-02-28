import {
    HabitStatus,
    ChallengeStatus,
    FrequencyType,
    ChallengeObject,
    AnchorInfoObject,
    FrequencyObject,
    ChainListItem,
    ChainNodeObject
} from './backend';

// 前端 Store 模型及组件内部流转用实体类型

/**
 * 习惯前端实体（目前大部分保留与后端一致的数据结构）
 */
export interface Habit {
    id: string;
    name: string;
    description: string | null;
    frequency: FrequencyObject;
    currentLevel: number;
    status: HabitStatus;
    currentChallenge: ChallengeObject | null;
    valueId: string | null;
    commitmentId: string | null;
    createdAt: string;
    pausedAt: string | null;
    streak: number;
    anchorInfo: AnchorInfoObject | null;

    // 前端衍生状态
    isCheckingIn?: boolean; // 乐观更新状态位
    todayCompleted: boolean; // 今日是否已打卡
}

/**
 * 习惯链条前端实体 — 继承后端 ChainListItem，仅扩展前端衍生字段
 */
export interface HabitChain extends ChainListItem {
    nodes: HabitChainNode[];
}

/**
 * 链条节点前端实体 — 继承后端 ChainNodeObject
 */
export interface HabitChainNode extends ChainNodeObject {
}

/**
 * 检查记录实体
 */
export interface CheckInRecord {
    id: string;
    habitId: string;
    challengeId: string;
    date: string;
    completed: boolean;
    completedAt: string;
}
