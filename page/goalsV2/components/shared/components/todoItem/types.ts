/**
 * TodoItem 组件相关类型定义
 * 根据需求文档重构: 统一任务模型
 */

export interface TodoItem {
    // === 基础属性 === 
    id: number;
    content: string;
    parentId: string | null;         // 父任务ID（支持无限层级嵌套）
    goalId: string | null;           // 关联的Goal ID
    planDocId: string | null;        // 来源计划书ID

    // === 来源追踪（用于MD同步） ===
    sourceType: 'manual' | 'plan_doc';
    sourceAnchorId: string | null;   // MD中的锚点ID（格式: lp:xxxxxx）

    // === 状态管理 ===
    state: 'pool' | 'scheduled' | 'completed' | 'shelved';
    scheduledDate: string | null;    // 安排到某天的日期 (YYYY-MM-DD)

    // === 时间相关 ===
    expectedFinishAt: string | null; // 预计完成日期
    actualFinishAt: string | null;   // 实际完成日期
    delayDays: number | null;        // 拖延天数 (actual - expected)
    delayReason: string | null;      // 拖延/未完成原因

    // === 显示属性 ===
    color: string;                   // 默认 "#FFFFFF"
    orderIndex: number;              // 每日列表排序
    poolOrderIndex: number | null;   // 任务池排序

    // === 嵌套展示（非持久化） ===
    children?: TodoItem[];           // 子任务列表
}
