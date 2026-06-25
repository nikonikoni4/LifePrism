/**
 * 时间格式化工具
 *
 * 日期→字符串的转换统一使用 @core/utils/dateUtils（SSOT）
 * 本文件仅保留纯展示格式化函数
 */

export { toLocalDateTimeString as formatLocalDateTime } from '../../../core/utils/dateUtils';

import { toLocalDateString } from '../../../core/utils/dateUtils';

/** 获取今天的日期字符串 YYYY-MM-DD */
export function getTodayStr(): string {
    return toLocalDateString(new Date());
}

/** 秒数格式化为 MM:SS */
export function formatElapsed(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/** 分钟数格式化为可读字符串 */
export function formatMinutes(minutes: number): string {
    if (minutes < 60) return `${minutes}min`;
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m > 0 ? `${h}h${m}min` : `${h}h`;
}
