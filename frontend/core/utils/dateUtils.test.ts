import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { toLocalDateString, toLocalDateTimeString, parseISOString, toISOStringUTC } from './dateUtils';

describe('toLocalDateString', () => {
    it('formats a known date correctly', () => {
        const d = new Date(2026, 2, 3); // 2026-03-03 (month is 0-indexed)
        expect(toLocalDateString(d)).toBe('2026-03-03');
    });

    it('pads single-digit month and day', () => {
        const d = new Date(2026, 0, 5); // 2026-01-05
        expect(toLocalDateString(d)).toBe('2026-01-05');
    });

    it('handles December 31', () => {
        const d = new Date(2026, 11, 31);
        expect(toLocalDateString(d)).toBe('2026-12-31');
    });
});

describe('toLocalDateTimeString', () => {
    it('formats date and time with zero-padded components', () => {
        const d = new Date(2026, 5, 13, 14, 30, 5); // 2026-06-13 14:30:05
        expect(toLocalDateTimeString(d)).toBe('2026-06-13T14:30:05');
    });

    it('formats midnight correctly (not previous day)', () => {
        const d = new Date(2026, 5, 13, 0, 0, 0);
        expect(toLocalDateTimeString(d)).toBe('2026-06-13T00:00:00');
    });

    it('formats end of day correctly', () => {
        const d = new Date(2026, 5, 13, 23, 59, 59);
        expect(toLocalDateTimeString(d)).toBe('2026-06-13T23:59:59');
    });

    it('does not contain Z or timezone suffix', () => {
        const d = new Date(2026, 5, 13, 14, 30, 0);
        const result = toLocalDateTimeString(d);
        expect(result).not.toContain('Z');
        expect(result).not.toContain('+');
        expect(result).not.toContain('.000');
    });

    it('date portion matches toLocalDateString', () => {
        const d = new Date(2026, 5, 13, 14, 30, 0);
        const dateTime = toLocalDateTimeString(d);
        const dateOnly = toLocalDateString(d);
        expect(dateTime.startsWith(dateOnly)).toBe(true);
    });

    it('pads single-digit hours, minutes, seconds', () => {
        const d = new Date(2026, 0, 1, 3, 5, 7);
        expect(toLocalDateTimeString(d)).toBe('2026-01-01T03:05:07');
    });
});

describe('parseISOString', () => {
    it('parses ISO 8601 string with Z suffix to correct Date instant', () => {
        const iso = '2026-07-11T16:29:54.123Z';
        const result = parseISOString(iso);
        expect(result).toBeInstanceOf(Date);
        expect(result.getTime()).toBe(new Date('2026-07-11T16:29:54.123Z').getTime());
    });

    it('parses ISO 8601 string with +00:00 offset (backend isoformat)', () => {
        // Python datetime.now(timezone.utc).isoformat() produces "+00:00" suffix
        const iso = '2026-07-11T16:29:54.123+00:00';
        const result = parseISOString(iso);
        // Same instant as the Z suffix version
        expect(result.getTime()).toBe(new Date('2026-07-11T16:29:54.123Z').getTime());
    });

    it('round-trips with toISOStringUTC losslessly', () => {
        const original = new Date('2026-07-11T16:29:54.123Z');
        const isoString = toISOStringUTC(original);
        const parsed = parseISOString(isoString);
        expect(parsed.getTime()).toBe(original.getTime());
    });
});

describe('toISOStringUTC', () => {
    it('converts Date to UTC ISO 8601 string with Z suffix', () => {
        const d = new Date('2026-07-11T16:29:54.123Z');
        expect(toISOStringUTC(d)).toBe('2026-07-11T16:29:54.123Z');
    });
});

// UTC+8 午夜边界场景：验证在 UTC+ 时区午夜前后日期不发生错位
// 本地 2026-03-03 00:00 (UTC+8) = UTC 2026-03-02 16:00
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

    it('toISOStringUTC returns UTC instant (previous day 16:00) at UTC+8 local midnight', () => {
        // Local midnight 2026-03-03 00:00 in UTC+8 = 2026-03-02T16:00:00Z
        const d = new Date(2026, 2, 3, 0, 0, 0);
        expect(toISOStringUTC(d)).toBe('2026-03-02T16:00:00.000Z');
    });

    it('toLocalDateString returns local date (not UTC date) at UTC+8 midnight', () => {
        // Local midnight 2026-03-03 00:00 in UTC+8 = UTC 2026-03-02 16:00
        // toLocalDateString must return "2026-03-03" (local date),
        // NOT "2026-03-02" (UTC date, which is the bug toISOString().split('T')[0] causes)
        const d = new Date(2026, 2, 3, 0, 0, 0);
        expect(toLocalDateString(d)).toBe('2026-03-03');
        // Verify the contrast: toISOString().split('T')[0] would give the wrong date
        expect(d.toISOString().split('T')[0]).toBe('2026-03-02');
    });

    it('toLocalDateString returns correct local date just before UTC+8 midnight', () => {
        // 23:59 local on 2026-03-03 in UTC+8 = 15:59 UTC on 2026-03-03
        const d = new Date(2026, 2, 3, 23, 59, 59);
        expect(toLocalDateString(d)).toBe('2026-03-03');
    });

    it('toLocalDateTimeString returns local datetime (not UTC) at UTC+8 midnight', () => {
        // Local midnight 2026-03-03 00:00 in UTC+8 = UTC 2026-03-02 16:00
        // toLocalDateTimeString must return local "2026-03-03T00:00:00",
        // NOT UTC "2026-03-02T16:00:00" (which toISOString would produce)
        const d = new Date(2026, 2, 3, 0, 0, 0);
        expect(toLocalDateTimeString(d)).toBe('2026-03-03T00:00:00');
        // Verify the contrast: toISOString would give the wrong datetime
        expect(d.toISOString()).toBe('2026-03-02T16:00:00.000Z');
    });

    it('toLocalDateTimeString returns correct local datetime at UTC+8 end of day', () => {
        // 23:59:59 local on 2026-03-03 in UTC+8 = 15:59:59 UTC on 2026-03-03
        const d = new Date(2026, 2, 3, 23, 59, 59);
        expect(toLocalDateTimeString(d)).toBe('2026-03-03T23:59:59');
    });
});
