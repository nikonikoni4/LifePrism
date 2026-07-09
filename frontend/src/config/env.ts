/**
 * 环境变量配置
 *
 * 集中管理前端环境变量，提供类型安全的访问接口
 */

/**
 * 是否为 Demo 演示模式
 *
 * Demo 模式下：
 * - 首次访问显示引导弹窗
 * - 所有写操作会被后端拦截
 *
 * 设置方式：
 * 打包时通过 --mode demo 参数：npm run build -- --mode demo
 */
export const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true';

/**
 * 应用版本
 */
export const appVersion = import.meta.env.VITE_APP_VERSION || '0.1.3';
