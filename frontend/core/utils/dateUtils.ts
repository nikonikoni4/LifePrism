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

/**
 * 将 Date 对象格式化为本地日期时间字符串 YYYY-MM-DDTHH:MM:SS
 *
 * ⚠️ 请勿使用 date.toISOString() 替代此函数，
 *    toISOString 返回的是 UTC 时间，在 UTC+ 时区会导致日期偏移。
 *
 * 用于存储到数据库的日期时间字段（后端按本地时间字符串做日期范围查询）。
 */
export function toLocalDateTimeString(date: Date): string {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

/**
 * 解析后端返回的 ISO 8601 字符串为 Date 对象
 *
 * 后端迁移到 UTC 后，所有时间戳字段使用 ISO 8601 格式（带时区标识），
 * 例如 "2026-07-11T16:29:54.123456+00:00" 或 "2026-07-11T16:29:54.123Z"。
 * 浏览器的 new Date(isoString) 能正确解析带时区的 ISO 字符串，
 * 封装此函数作为单一入口，便于后续统一处理边界情况。
 *
 * @param isoString 后端返回的 ISO 8601 字符串
 * @returns 对应的 Date 对象
 */
export function parseISOString(isoString: string): Date {
    return new Date(isoString);
}

/**
 * 将 Date 对象转为 UTC ISO 8601 字符串，用于发送时间给后端
 *
 * 后端迁移到 UTC 后，前端发送的时间戳字段（如 created_at、updated_at）
 * 必须使用 UTC ISO 8601 格式。Date.prototype.toISOString() 原生生成
 * UTC 格式（带 Z 后缀），封装此函数作为单一入口，明确表达"发送给后端"
 * 的意图，与 toLocalDateString（本地日期）区分。
 *
 * 注意：此函数用于时间戳字段。YYYY-MM-DD 格式的业务日期字段
 * （如 date、start_date）仍应使用 toLocalDateString。
 *
 * @param date 要转换的 Date 对象
 * @returns UTC ISO 8601 字符串，如 "2026-07-11T16:29:54.123Z"
 */
export function toISOStringUTC(date: Date): string {
    return date.toISOString();
}

// ==================== 用户时区配置 ====================
// 用户时区缓存在 localStorage 中，由设置界面写入。
// 后端 AI 工具使用此时区进行交互，前端时间显示目前仍使用浏览器本地时区，
// 后续可引入 date-fns-tz 按配置时区显示。

const TIMEZONE_STORAGE_KEY = 'lifeprism_timezone';

/**
 * 获取用户配置的时区（IANA 标识符）
 *
 * 优先从 localStorage 读取（由设置界面写入），fallback 到上海时区。
 * 后端 AI 工具的本地时间显示使用此时区。
 *
 * @returns 时区标识符，如 "Asia/Shanghai"
 */
export function getUserTimezone(): string {
    try {
        const tz = localStorage.getItem(TIMEZONE_STORAGE_KEY);
        return tz || 'Asia/Shanghai';
    } catch {
        return 'Asia/Shanghai';
    }
}

/**
 * 设置用户时区到 localStorage
 *
 * 由设置界面在加载/保存配置时调用，供前端其他模块读取。
 *
 * @param timezone IANA 时区标识符，如 "Asia/Shanghai"
 */
export function setUserTimezone(timezone: string): void {
    try {
        localStorage.setItem(TIMEZONE_STORAGE_KEY, timezone);
    } catch {
        // localStorage 不可用时静默失败
    }
}
