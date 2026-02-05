/**
 * PlanDoc Save Hook - 计划书保存钩子
 *
 * 解决冲突场景：
 * - 用户在 PlanDoc 编辑器修改文本（未保存）
 * - 同时在任务池等其他地方勾选 todo
 * - 后端更新 DB 和 MD 文件，导致 PlanDoc 编辑器内容与 MD 文件不同步
 *
 * 解决方案：
 * - PlanDocListView 注册保存回调
 * - 任何 todo 更新操作前，先触发保存回调
 * - 确保 MD 文件与编辑器内容同步后再更新 todo
 */

type SaveCallback = () => Promise<void>;

// 全局保存回调注册表
// key: planDocId, value: 保存回调函数
const saveCallbacks = new Map<string, SaveCallback>();

/**
 * 注册 PlanDoc 保存回调
 * @param planDocId 计划书 ID
 * @param callback 保存回调函数
 */
export function registerPlanDocSaveCallback(planDocId: string, callback: SaveCallback): void {
    saveCallbacks.set(planDocId, callback);
}

/**
 * 注销 PlanDoc 保存回调
 * @param planDocId 计划书 ID
 */
export function unregisterPlanDocSaveCallback(planDocId: string): void {
    saveCallbacks.delete(planDocId);
}

/**
 * 触发指定 PlanDoc 的保存
 * @param planDocId 计划书 ID
 */
export async function triggerPlanDocSave(planDocId: string): Promise<void> {
    const callback = saveCallbacks.get(planDocId);
    if (callback) {
        await callback();
    }
}

/**
 * 触发所有已注册的 PlanDoc 保存
 * 用于 todo 更新前确保所有编辑中的文档都已保存
 */
export async function triggerAllPlanDocSaves(): Promise<void> {
    const promises = Array.from(saveCallbacks.values()).map(cb => cb());
    await Promise.all(promises);
}

// ============================================================================
// Refresh Callbacks - 刷新回调注册机制
// ============================================================================

type RefreshCallback = () => Promise<void>;

// 全局刷新回调注册表
// key: planDocId, value: 刷新回调函数
const refreshCallbacks = new Map<string, RefreshCallback>();

/**
 * 注册 PlanDoc 刷新回调
 * @param planDocId 计划书 ID
 * @param callback 刷新回调函数
 */
export function registerPlanDocRefreshCallback(planDocId: string, callback: RefreshCallback): void {
    refreshCallbacks.set(planDocId, callback);
}

/**
 * 注销 PlanDoc 刷新回调
 * @param planDocId 计划书 ID
 */
export function unregisterPlanDocRefreshCallback(planDocId: string): void {
    refreshCallbacks.delete(planDocId);
}

/**
 * 触发所有已注册的 PlanDoc 刷新
 * 用于 todo 更新后刷新编辑器内容
 */
export async function triggerAllPlanDocRefreshes(): Promise<void> {
    const promises = Array.from(refreshCallbacks.values()).map(cb => cb());
    await Promise.all(promises);
}
