/**
 * IPC PlanDoc Bridge
 *
 * 在主窗口中初始化，监听来自浮窗/对话框的 PlanDoc 同步请求。
 * 浮窗是独立 BrowserWindow，无法使用主窗口的 useTaskPoolStore Context，
 * 因此通过 IPC 消息桥接 PlanDoc 保存/刷新操作。
 */

import { triggerAllPlanDocSaves, triggerAllPlanDocRefreshes } from '../../apps/goals/hooks/usePlanDocSaveHook';

let initialized = false;

export function initPlanDocBridge() {
    if (initialized) return;
    if (!window.electronAPI?.onMessage) return;

    window.electronAPI.onMessage('plandoc-save-request', async () => {
        await triggerAllPlanDocSaves();
        // 回复浮窗：保存完成
        window.electronAPI?.sendToFloating?.('what-am-i-doing', 'plandoc-save-done', {});
    });

    window.electronAPI.onMessage('plandoc-refresh-request', async () => {
        await triggerAllPlanDocRefreshes();
    });

    initialized = true;
    console.log('[IpcPlanDocBridge] initialized');
}
