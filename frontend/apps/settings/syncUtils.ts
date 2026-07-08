/**
 * 数据同步相关工具函数
 */

/**
 * 将 ISO 8601 时间戳格式化为相对时间字符串
 *
 * 规则：
 * - 空/null/undefined → "从未同步"
 * - < 1 分钟 → "刚刚"
 * - < 1 小时 → "X 分钟前"
 * - < 1 天 → "X 小时前"
 * - >= 1 天 → "X 天前"
 *
 * @param timestamp ISO 8601 格式的时间字符串
 * @returns 相对时间描述
 */
export function formatRelativeTime(timestamp: string | null | undefined): string {
    if (!timestamp) {
        return '从未同步';
    }

    const now = Date.now();
    const then = new Date(timestamp).getTime();

    if (isNaN(then)) {
        return '从未同步';
    }

    const diffMs = now - then;

    // 如果时间在未来（时钟偏差），显示"刚刚"
    if (diffMs < 0) {
        return '刚刚';
    }

    const diffMinutes = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMinutes < 1) {
        return '刚刚';
    }
    if (diffHours < 1) {
        return `${diffMinutes} 分钟前`;
    }
    if (diffDays < 1) {
        return `${diffHours} 小时前`;
    }
    return `${diffDays} 天前`;
}
