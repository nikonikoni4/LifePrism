/**
 * ReportCacheService UTC 时区迁移测试
 *
 * Seam: preloadAdjacentDays 行为 — 预加载相邻日期报告时，
 *       传给 fetchFn 的日期字符串应基于本地日期（YYYY-MM-DD），
 *       而非 UTC 日期（toISOString().split('T')[0]）。
 *
 * 背景：Issue #15 — 前端 UI Kit 和 Core Services 迁移
 *       reportCacheService.ts:290 getAdjacentDates 使用了 toISOString().split('T')[0]
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock CacheManager — 所有缓存操作返回空/成功，确保 fetchFn 被调用
vi.mock('../utils/cacheManager', () => ({
    CacheManager: {
        get: vi.fn(() => null),
        set: vi.fn(() => true),
        remove: vi.fn(),
        keys: vi.fn(() => []),
        getStats: vi.fn(() => ({
            totalItems: 0,
            totalSize: 0,
            expiredItems: 0,
        })),
    },
    CacheOptions: {},
}));

import { ReportCacheService } from './reportCacheService';

// ============================================================================
// UTC-8 时区测试：该时区下 toISOString().split('T')[0] 会返回错误的 UTC 日期
// ============================================================================

describe('ReportCacheService - getAdjacentDates UTC 时区迁移', () => {
    const originalTZ = process.env.TZ;

    afterEach(() => {
        if (originalTZ === undefined) {
            delete process.env.TZ;
        } else {
            process.env.TZ = originalTZ;
        }
        vi.clearAllMocks();
    });

    it('UTC-8 时区下相邻日期应使用本地日期（非 UTC 日期）', async () => {
        // 在 UTC-8 (America/Los_Angeles) 中：
        // new Date('2026-03-03') → UTC 2026-03-03T00:00:00Z → 本地 2026-03-02 16:00
        // 本地日期是 3月2日，所以相邻日期应为 3月1日 和 3月3日
        //
        // 修复前（toISOString().split('T')[0]）：
        //   -1 → UTC 2026-03-02T00:00:00Z → '2026-03-02'（错误 — UTC 日期）
        //   +1 → UTC 2026-03-04T00:00:00Z → '2026-03-04'（错误 — UTC 日期）
        //
        // 修复后（toLocalDateString）：
        //   -1 → 本地 2026-03-01 → '2026-03-01'（正确 — 本地日期）
        //   +1 → 本地 2026-03-03 → '2026-03-03'（正确 — 本地日期）
        process.env.TZ = 'America/Los_Angeles';

        const fetchFn = vi.fn().mockResolvedValue({});
        await ReportCacheService.preloadAdjacentDays('2026-03-03', fetchFn);

        expect(fetchFn).toHaveBeenCalledTimes(2);
        const calledDates = fetchFn.mock.calls.map((call) => call[0]);
        expect(calledDates).toContain('2026-03-01');
        expect(calledDates).toContain('2026-03-03');
        // 确保不包含错误的 UTC 日期
        expect(calledDates).not.toContain('2026-03-02');
        expect(calledDates).not.toContain('2026-03-04');
    });

    it('UTC+8 时区下相邻日期正常计算', async () => {
        // 在 UTC+8 (Asia/Shanghai) 中：
        // new Date('2026-03-03') → UTC 2026-03-03T00:00:00Z → 本地 2026-03-03 08:00
        // 本地日期是 3月3日，相邻日期为 3月2日 和 3月4日
        // 此时 UTC 日期和本地日期相同（因为 08:00 远离午夜）
        process.env.TZ = 'Asia/Shanghai';

        const fetchFn = vi.fn().mockResolvedValue({});
        await ReportCacheService.preloadAdjacentDays('2026-03-03', fetchFn);

        expect(fetchFn).toHaveBeenCalledTimes(2);
        const calledDates = fetchFn.mock.calls.map((call) => call[0]);
        expect(calledDates).toContain('2026-03-02');
        expect(calledDates).toContain('2026-03-04');
    });
});
