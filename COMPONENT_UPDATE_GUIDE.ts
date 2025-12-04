/**
 * 重要提醒：子组件更新说明
 * 
 * 由于前端已经改为通过 Dashboard 组件统一获取首页数据，
 * 以下三个子组件需要进行相应的更新：
 */

// ====================================================================
// 1. ActivitySummaryHeader.tsx
// ====================================================================
/**
 * 变更：添加新的可选 prop: activitySummaryData
 * 
 * 当 activitySummaryData prop 存在时，直接使用该数据，
 * 而不是内部调用 API。
 * 
 * 建议的接口定义：
 */
interface ActivitySummaryHeaderProps {
    selectedDate: string;
    onDateChange: (date: string) => void;
    activitySummaryData?: ActivitySummaryResponse; // 新增：可选的预加载数据
}

/**
 * 实现建议：
 * 1. 如果 activitySummaryData 存在，跳过 API 调用，直接使用该数据
 * 2. 如果 activitySummaryData 不存在，保持原有的 API 调用逻辑（向后兼容）
 */

// ====================================================================
// 2. ActivityDetailsWidget.tsx
// ====================================================================
/**
 * 变更：添加新的可选 prop: dashboardData
 * 
 * 当 dashboardData prop 存在时，直接使用该数据，
 * 而不是内部调用 API。
 */
interface ActivityDetailsWidgetProps {
    selectedDate: string;
    dashboardData?: DashboardResponse; // 新增：可选的预加载数据
}

/**
 * 实现建议：
 * 1. 如果 dashboardData 存在，跳过 API 调用，直接从中提取 top_apps 和 top_titles
 * 2. 如果 dashboardData 不存在，保持原有的 API 调用逻辑（向后兼容）
 */

// ====================================================================
// 3. TimeOverviewWidget.tsx
// ====================================================================
/**
 * 变更：添加新的可选 prop: initialData
 * 
 * 当 initialData prop 存在时，用作初始数据，
 * 但仍然保留下钻功能（点击饼图查看子分类）的独立 API 调用。
 */
interface TimeOverviewWidgetProps {
    selectedDate: string;
    initialData?: TimeOverviewResponse; // 新增：可选的初始数据
}

/**
 * 实现建议：
 * 1. 如果 initialData 存在且 selectedCategory 为 null（顶级视图），使用 initialData
 * 2. 如果用户点击了饼图进行下钻（selectedCategory 不为 null），才调用 API
 * 3. 点击返回按钮时，可以使用缓存的 initialData，无需重新调用 API
 * 4. 如果 initialData 不存在，保持原有的 API 调用逻辑（向后兼容）
 */

// ====================================================================
// 实施优先级
// ====================================================================
/**
 * 由于时间限制和现有后端已经正常运行，这些子组件的更新可以：
 * 
 * 方法1（推荐）：渐进式更新
 * - 先保持子组件不变，让它们继续使用独立的 API 调用
 * - Dashboard 组件的 getHomepageData() 目前不会被使用
 * - 后续逐个更新子组件，每次更新后测试一个组件
 * 
 * 方法2：一次性更新
 * - 立即更新所有三个子组件
 * - 添加对新 props 的支持
 * - 确保向后兼容（props 不存在时依然工作）
 * 
 * 当前建议：采用方法1，因为后端 API 已经可用，前端可以逐步迁移
 */

export { };
