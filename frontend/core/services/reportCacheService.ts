/**
 * Report Cache Service
 * 
 * 专门用于报告数据的缓存服务
 * 提供智能缓存策略和数据预加载功能
 */

import { CacheManager, CacheOptions } from '../utils/cacheManager';
import { toLocalDateString } from '../utils/dateUtils';
import { DailyReportData, WeeklyReportData, MonthlyReportData } from '../../apps/lifewatch/pages/reports/types';

export class ReportCacheService {
    // 缓存键前缀
    private static readonly DAILY_PREFIX = 'report_daily_';
    private static readonly WEEKLY_PREFIX = 'report_weekly_';
    private static readonly MONTHLY_PREFIX = 'report_monthly_';
    private static readonly SETTINGS_PREFIX = 'settings_';

    // 缓存过期时间配置
    private static readonly CACHE_TTL = {
        // 日报告：当天的缓存 30 分钟，历史数据缓存 24 小时
        dailyCurrent: 30 * 60 * 1000,        // 30 分钟
        dailyHistory: 24 * 60 * 60 * 1000,   // 24 小时

        // 周报告：当周缓存 1 小时，历史数据缓存 7 天
        weeklyCurrent: 60 * 60 * 1000,       // 1 小时
        weeklyHistory: 7 * 24 * 60 * 60 * 1000, // 7 天

        // 月报告：当月缓存 2 小时，历史数据缓存 30 天
        monthlyCurrent: 2 * 60 * 60 * 1000,  // 2 小时
        monthlyHistory: 30 * 24 * 60 * 60 * 1000, // 30 天

        // 用户设置：永久缓存（直到手动清除）
        settings: 365 * 24 * 60 * 60 * 1000, // 1 年
    };

    /**
     * ==================== 日报告缓存 ====================
     */

    /**
     * 缓存日报告
     */
    static cacheDailyReport(date: string, data: DailyReportData): boolean {
        const key = this.DAILY_PREFIX + date;
        const isToday = this.isToday(date);
        const ttl = isToday ? this.CACHE_TTL.dailyCurrent : this.CACHE_TTL.dailyHistory;

        return CacheManager.set(key, data, { ttl });
    }

    /**
     * 获取日报告缓存
     */
    static getDailyReport(date: string): DailyReportData | null {
        const key = this.DAILY_PREFIX + date;
        return CacheManager.get<DailyReportData>(key);
    }

    /**
     * 删除日报告缓存
     */
    static removeDailyReport(date: string): void {
        const key = this.DAILY_PREFIX + date;
        CacheManager.remove(key);
    }

    /**
     * 预加载相邻日期的报告（提升用户体验）
     */
    static async preloadAdjacentDays(
        currentDate: string,
        fetchFn: (date: string) => Promise<DailyReportData>
    ): Promise<void> {
        const dates = this.getAdjacentDates(currentDate, 1); // 前后各 1 天

        for (const date of dates) {
            // 如果缓存中没有，则预加载
            if (!this.getDailyReport(date)) {
                try {
                    const data = await fetchFn(date);
                    this.cacheDailyReport(date, data);
                    console.log(`[ReportCache] 预加载日报告成功: ${date}`);
                } catch (error) {
                    console.warn(`[ReportCache] 预加载日报告失败: ${date}`, error);
                }
            }
        }
    }

    /**
     * ==================== 周报告缓存 ====================
     */

    /**
     * 缓存周报告
     */
    static cacheWeeklyReport(weekStartDate: string, data: WeeklyReportData): boolean {
        const key = this.WEEKLY_PREFIX + weekStartDate;
        const isCurrentWeek = this.isCurrentWeek(weekStartDate);
        const ttl = isCurrentWeek ? this.CACHE_TTL.weeklyCurrent : this.CACHE_TTL.weeklyHistory;

        return CacheManager.set(key, data, { ttl });
    }

    /**
     * 获取周报告缓存
     */
    static getWeeklyReport(weekStartDate: string): WeeklyReportData | null {
        const key = this.WEEKLY_PREFIX + weekStartDate;
        return CacheManager.get<WeeklyReportData>(key);
    }

    /**
     * 删除周报告缓存
     */
    static removeWeeklyReport(weekStartDate: string): void {
        const key = this.WEEKLY_PREFIX + weekStartDate;
        CacheManager.remove(key);
    }

    /**
     * ==================== 月报告缓存 ====================
     */

    /**
     * 缓存月报告
     */
    static cacheMonthlyReport(month: string, data: MonthlyReportData): boolean {
        const key = this.MONTHLY_PREFIX + month;
        const isCurrentMonth = this.isCurrentMonth(month);
        const ttl = isCurrentMonth ? this.CACHE_TTL.monthlyCurrent : this.CACHE_TTL.monthlyHistory;

        return CacheManager.set(key, data, { ttl });
    }

    /**
     * 获取月报告缓存
     */
    static getMonthlyReport(month: string): MonthlyReportData | null {
        const key = this.MONTHLY_PREFIX + month;
        return CacheManager.get<MonthlyReportData>(key);
    }

    /**
     * 删除月报告缓存
     */
    static removeMonthlyReport(month: string): void {
        const key = this.MONTHLY_PREFIX + month;
        CacheManager.remove(key);
    }

    /**
     * ==================== 用户设置缓存 ====================
     */

    /**
     * 缓存用户设置
     */
    static cacheSettings<T>(key: string, value: T): boolean {
        const cacheKey = this.SETTINGS_PREFIX + key;
        return CacheManager.set(cacheKey, value, { ttl: this.CACHE_TTL.settings });
    }

    /**
     * 获取用户设置
     */
    static getSettings<T>(key: string): T | null {
        const cacheKey = this.SETTINGS_PREFIX + key;
        return CacheManager.get<T>(cacheKey);
    }

    /**
     * 删除用户设置
     */
    static removeSettings(key: string): void {
        const cacheKey = this.SETTINGS_PREFIX + key;
        CacheManager.remove(cacheKey);
    }

    /**
     * ==================== 批量操作 ====================
     */

    /**
     * 清除所有报告缓存
     */
    static clearAllReports(): void {
        const keys = CacheManager.keys();
        keys.forEach(key => {
            if (
                key.startsWith(this.DAILY_PREFIX) ||
                key.startsWith(this.WEEKLY_PREFIX) ||
                key.startsWith(this.MONTHLY_PREFIX)
            ) {
                CacheManager.remove(key);
            }
        });
        console.log('[ReportCache] 已清除所有报告缓存');
    }

    /**
     * 清除指定日期范围的日报告缓存
     */
    static clearDailyReportsInRange(startDate: string, endDate: string): void {
        const keys = CacheManager.keys();
        keys.forEach(key => {
            if (key.startsWith(this.DAILY_PREFIX)) {
                const date = key.substring(this.DAILY_PREFIX.length);
                if (date >= startDate && date <= endDate) {
                    CacheManager.remove(key);
                }
            }
        });
        console.log(`[ReportCache] 已清除 ${startDate} 到 ${endDate} 的日报告缓存`);
    }

    /**
     * 获取缓存统计信息
     */
    static getCacheStats(): {
        dailyReports: number;
        weeklyReports: number;
        monthlyReports: number;
        settings: number;
        totalSize: string;
    } {
        const keys = CacheManager.keys();
        const stats = CacheManager.getStats();

        return {
            dailyReports: keys.filter(k => k.startsWith(this.DAILY_PREFIX)).length,
            weeklyReports: keys.filter(k => k.startsWith(this.WEEKLY_PREFIX)).length,
            monthlyReports: keys.filter(k => k.startsWith(this.MONTHLY_PREFIX)).length,
            settings: keys.filter(k => k.startsWith(this.SETTINGS_PREFIX)).length,
            totalSize: `${(stats.totalSize / 1024).toFixed(2)}KB`,
        };
    }

    /**
     * ==================== 工具方法 ====================
     */

    /**
     * 判断是否为今天
     */
    private static isToday(date: string): boolean {
        const today = new Date();
        const targetDate = new Date(date);
        return (
            today.getFullYear() === targetDate.getFullYear() &&
            today.getMonth() === targetDate.getMonth() &&
            today.getDate() === targetDate.getDate()
        );
    }

    /**
     * 判断是否为当前周
     */
    private static isCurrentWeek(weekStartDate: string): boolean {
        const today = new Date();
        const weekStart = new Date(weekStartDate);
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekEnd.getDate() + 6);

        return today >= weekStart && today <= weekEnd;
    }

    /**
     * 判断是否为当前月
     */
    private static isCurrentMonth(month: string): boolean {
        const today = new Date();
        const currentMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
        return month === currentMonth;
    }

    /**
     * 获取相邻日期
     */
    private static getAdjacentDates(date: string, range: number): string[] {
        const dates: string[] = [];
        const currentDate = new Date(date);

        for (let i = -range; i <= range; i++) {
            if (i === 0) continue; // 跳过当前日期

            const adjacentDate = new Date(currentDate);
            adjacentDate.setDate(adjacentDate.getDate() + i);

            const dateStr = toLocalDateString(adjacentDate);
            dates.push(dateStr);
        }

        return dates;
    }

    /**
     * 格式化日期为 YYYY-MM-DD
     */
    static formatDate(date: Date): string {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    /**
     * 获取本周的开始日期（周一）
     */
    static getWeekStartDate(date: Date = new Date()): string {
        const day = date.getDay();
        const diff = date.getDate() - day + (day === 0 ? -6 : 1); // 调整到周一
        const monday = new Date(date.setDate(diff));
        return this.formatDate(monday);
    }

    /**
     * 获取本月的开始日期
     */
    static getMonthStartDate(date: Date = new Date()): string {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        return `${year}-${month}`;
    }
}

/**
 * 导出便捷方法
 */
export const reportCache = {
    // 日报告
    daily: {
        get: (date: string) => ReportCacheService.getDailyReport(date),
        set: (date: string, data: DailyReportData) => ReportCacheService.cacheDailyReport(date, data),
        remove: (date: string) => ReportCacheService.removeDailyReport(date),
        preload: (date: string, fetchFn: (date: string) => Promise<DailyReportData>) =>
            ReportCacheService.preloadAdjacentDays(date, fetchFn),
    },

    // 周报告
    weekly: {
        get: (weekStartDate: string) => ReportCacheService.getWeeklyReport(weekStartDate),
        set: (weekStartDate: string, data: WeeklyReportData) =>
            ReportCacheService.cacheWeeklyReport(weekStartDate, data),
        remove: (weekStartDate: string) => ReportCacheService.removeWeeklyReport(weekStartDate),
    },

    // 月报告
    monthly: {
        get: (month: string) => ReportCacheService.getMonthlyReport(month),
        set: (month: string, data: MonthlyReportData) => ReportCacheService.cacheMonthlyReport(month, data),
        remove: (month: string) => ReportCacheService.removeMonthlyReport(month),
    },

    // 用户设置
    settings: {
        get: <T>(key: string) => ReportCacheService.getSettings<T>(key),
        set: <T>(key: string, value: T) => ReportCacheService.cacheSettings(key, value),
        remove: (key: string) => ReportCacheService.removeSettings(key),
    },

    // 工具方法
    clearAll: () => ReportCacheService.clearAllReports(),
    getStats: () => ReportCacheService.getCacheStats(),
};
