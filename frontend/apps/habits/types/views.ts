import { HabitChainNode } from './entities';

// 视图专属衍生数据类型

/**
 * Timeline 时间轴上的事件结构
 */
export interface TimelineEvent {
    id: string;              // 唯一标识 (例如 chainId_nodeId)
    title: string;           // 显示名字
    startTime: string;       // 开始时间 HH:mm
    endTime: string;         // 预估结束时间 HH:mm
    theme?: string;          // 颜色主题
    associatedHabitId?: string | null; // 对应的习惯 ID
    height?: number;         // 绝对布局下的高度 (可选)
    top?: number;            // 绝对布局距离顶部的距离 (可选)
}

/**
 * 热力图中的数据格格式
 */
export interface HeatmapGridData {
    date: string;          // YYYY-MM-DD
    level: 0 | 1 | 2 | 3 | 4 | 5; // 用于给背景着色的等级 (0: 未打卡, 5: 高活跃/完成度高)
    details: {
        completed: number;
        total: number;
        isRestDay: boolean;
        rate: number;
    };
}
