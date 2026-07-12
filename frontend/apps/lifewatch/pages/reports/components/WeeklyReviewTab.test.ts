import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { getWeekRange } from './WeeklyReviewTab';

describe('getWeekRange', () => {
    it('returns Monday as start and Sunday as end for a mid-week date', () => {
        // 2026-07-15 is a Wednesday
        const wednesday = new Date(2026, 6, 15);
        const range = getWeekRange(wednesday);
        expect(range.start).toBe('2026-07-13'); // Monday
        expect(range.end).toBe('2026-07-19');   // Sunday
    });

    it('returns Monday as start when input is Monday', () => {
        // 2026-07-13 is a Monday
        const monday = new Date(2026, 6, 13);
        const range = getWeekRange(monday);
        expect(range.start).toBe('2026-07-13');
        expect(range.end).toBe('2026-07-19');
    });

    it('returns previous Monday as start when input is Sunday', () => {
        // 2026-07-19 is a Sunday; should NOT roll forward to next week
        const sunday = new Date(2026, 6, 19);
        const range = getWeekRange(sunday);
        expect(range.start).toBe('2026-07-13');
        expect(range.end).toBe('2026-07-19');
    });

    it('handles month boundary (Monday in previous month)', () => {
        // 2026-08-02 is a Sunday; Monday is 2026-07-27 (previous month)
        const sunday = new Date(2026, 7, 2);
        const range = getWeekRange(sunday);
        expect(range.start).toBe('2026-07-27');
        expect(range.end).toBe('2026-08-02');
    });

    it('handles year boundary (week spanning Dec -> Jan)', () => {
        // 2026-01-01 is a Thursday; Monday is 2025-12-29, Sunday is 2026-01-04
        const thursday = new Date(2026, 0, 1);
        const range = getWeekRange(thursday);
        expect(range.start).toBe('2025-12-29');
        expect(range.end).toBe('2026-01-04');
    });

    it('returns YYYY-MM-DD format with zero-padded components', () => {
        // 2026-01-05 is a Monday
        const monday = new Date(2026, 0, 5);
        const range = getWeekRange(monday);
        expect(range.start).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(range.end).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(range.start).toBe('2026-01-05');
        expect(range.end).toBe('2026-01-11');
    });

    // UTC+8 午夜边界场景：验证周范围计算在 UTC+ 时区午夜前后不发生错位
    // 本地 2026-07-13 00:00 (UTC+8) = UTC 2026-07-12 16:00
    // 如果使用 toISOString().split('T')[0] 会得到 "2026-07-12" (UTC 日期)，
    // 导致 Monday 计算错误（变成上一周的某天）
    describe('UTC+8 midnight boundary', () => {
        const originalTZ = process.env.TZ;

        beforeEach(() => {
            process.env.TZ = 'Asia/Shanghai';
        });

        afterEach(() => {
            if (originalTZ === undefined) {
                delete process.env.TZ;
            } else {
                process.env.TZ = originalTZ;
            }
        });

        it('returns correct local Monday when Monday falls at UTC+8 midnight', () => {
            // Local 2026-07-13 00:00 (UTC+8) is Monday morning.
            // UTC time is 2026-07-12 16:00 (Sunday).
            // getWeekRange must return local date "2026-07-13", NOT "2026-07-12".
            const mondayMidnight = new Date(2026, 6, 13, 0, 0, 0);
            const range = getWeekRange(mondayMidnight);
            expect(range.start).toBe('2026-07-13');
            expect(range.end).toBe('2026-07-19');
        });

        it('returns correct local Sunday when Sunday falls at UTC+8 midnight', () => {
            // Local 2026-07-19 00:00 (UTC+8) is Sunday morning.
            // UTC time is 2026-07-18 16:00 (Saturday).
            // When input is this Sunday, range.start should be previous Monday 2026-07-13,
            // range.end should be 2026-07-19 (local Sunday, not UTC Saturday).
            const sundayMidnight = new Date(2026, 6, 19, 0, 0, 0);
            const range = getWeekRange(sundayMidnight);
            expect(range.start).toBe('2026-07-13');
            expect(range.end).toBe('2026-07-19');
        });

        it('returns correct local dates just before UTC+8 midnight (23:59)', () => {
            // Local 2026-07-15 23:59 (UTC+8) Wednesday = UTC 2026-07-15 15:59
            // Same UTC date, but verifying the function is consistent across the day.
            const wednesday = new Date(2026, 6, 15, 23, 59, 59);
            const range = getWeekRange(wednesday);
            expect(range.start).toBe('2026-07-13');
            expect(range.end).toBe('2026-07-19');
        });
    });
});
