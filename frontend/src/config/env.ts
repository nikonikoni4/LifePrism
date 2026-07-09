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
 * 1. 开发环境：在 .env 文件中设置 VITE_DEMO_MODE=true
 * 2. 打包环境：构建时通过 --mode demo 参数
 */
export const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true';

/**
 * API 基础路径
 */
export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8088';

/**
 * 应用版本
 */
export const appVersion = import.meta.env.VITE_APP_VERSION || '0.1.3';
