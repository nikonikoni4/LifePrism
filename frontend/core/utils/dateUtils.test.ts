import { describe, it, expect } from 'vitest';
import { toLocalDateString, toLocalDateTimeString } from './dateUtils';

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
