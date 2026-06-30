/**
 * 日记组件调试配置
 * 设置 DEBUG = true 可以在控制台看到详细的调试日志
 */
export const DIARY_DEBUG = {
  // 主开关：设置为 true 启用所有调试日志
  enabled: false,

  // 细粒度控制（仅在 enabled = true 时生效）
  scroll: true,      // 滚动相关日志
  dataLoad: true,    // 数据加载相关日志
  userAction: true,  // 用户操作相关日志
};

/**
 * 调试日志函数
 */
export function debugLog(category: keyof typeof DIARY_DEBUG, ...args: any[]) {
  if (!DIARY_DEBUG.enabled) return;
  if (category === 'enabled') return;
  if (!DIARY_DEBUG[category]) return;

  console.log(...args);
}
