/**
 * 日期工具函数
 *
 * 核心原则：前端所有 Date → 日期字符串 的转换必须使用本地时区方法
 * （getFullYear / getMonth / getDate），禁止使用 toISOString()（UTC）。
 *
 * 原因：toISOString() 返回 UTC 时间，在 UTC+ 时区的午夜时刻会导致日期减一天。
 * 例如：本地 2026-03-03 00:00 (UTC+8) → toISOString() → "2026-03-02T16:00:00.000Z"
 */

/**
 * 将 Date 对象格式化为本地日期字符串 YYYY-MM-DD
 *
 * ⚠️ 请勿使用 date.toISOString().split('T')[0] 替代此函数，
 *    toISOString 返回的是 UTC 时间，会产生时区偏移 bug。
 */
export function toLocalDateString(date: Date): string {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}
