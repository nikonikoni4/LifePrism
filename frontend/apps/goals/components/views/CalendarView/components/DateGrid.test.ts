import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock UI-kit and context dependencies so generateDateRange can be imported in isolation
vi.mock('@my-ui-kit/core', () => ({
    DroppableDateCell: ({ children }: { children: React.ReactNode }) => children,
    DraggableItem: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock('../../../../hooks/useTaskPoolStore', () => ({
    useTaskPoolStore: () => ({ tasks: [] }),
}));
vi.mock('../../../../context/GoalPageContext', () => ({
    useGoalPageContext: () => ({ selectedDate: new Date(), setSelectedDate: () => {} }),
}));

// Import after mocks are in place
import { generateDateRange } from './DateGrid';

// UTC+8 午夜边界场景：验证日历日期范围生成在本地午夜前后不发生错位
describe('generateDateRange - UTC+8 midnight boundary', () => {
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

    it('returns local dates (not UTC dates) when range starts at UTC+8 midnight', () => {
        // 本地 2026-03-03 00:00 (UTC+8) = UTC 2026-03-02 16:00
        // toISOString().split('T')[0] 会错误返回 "2026-03-02"
        // toLocalDateString 应正确返回 "2026-03-03"
        const start = new Date(2026, 2, 3, 0, 0, 0); // 本地 2026-03-03 00:00
        const end = new Date(2026, 2, 5, 0, 0, 0); // 本地 2026-03-05 00:00
        const dates = generateDateRange(start, end);
        expect(dates).toEqual(['2026-03-03', '2026-03-04', '2026-03-05']);
    });

    it('returns correct local date just before UTC+8 midnight', () => {
        // 本地 2026-03-03 23:59 (UTC+8) = UTC 2026-03-03 15:59
        const start = new Date(2026, 2, 3, 23, 59, 59);
        const end = new Date(2026, 2, 4, 23, 59, 59);
        const dates = generateDateRange(start, end);
        expect(dates).toEqual(['2026-03-03', '2026-03-04']);
    });

    it('handles single-day range at UTC+8 midnight correctly', () => {
        // 单天范围：本地 2026-03-03 00:00
        const start = new Date(2026, 2, 3, 0, 0, 0);
        const end = new Date(2026, 2, 3, 0, 0, 0);
        const dates = generateDateRange(start, end);
        expect(dates).toEqual(['2026-03-03']);
    });

    it('returns correct local dates across month boundary at UTC+8 midnight', () => {
        // 跨月边界：本地 2026-03-31 00:00 ~ 2026-04-02 00:00
        const start = new Date(2026, 2, 31, 0, 0, 0);
        const end = new Date(2026, 3, 2, 0, 0, 0);
        const dates = generateDateRange(start, end);
        expect(dates).toEqual(['2026-03-31', '2026-04-01', '2026-04-02']);
    });
});
