import { describe, it, expect } from 'vitest';
import { formatLocalDateTime, getTodayStr, formatElapsed, formatMinutes } from './formatTime';
import { toLocalDateTimeString, toLocalDateString } from '../../../core/utils/dateUtils';

describe('formatLocalDateTime (re-export)', () => {
    it('produces same result as toLocalDateTimeString', () => {
        const d = new Date(2026, 5, 13, 14, 30, 5);
        expect(formatLocalDateTime(d)).toBe(toLocalDateTimeString(d));
    });

    it('formats correctly', () => {
        const d = new Date(2026, 5, 13, 14, 30, 5);
        expect(formatLocalDateTime(d)).toBe('2026-06-13T14:30:05');
    });
});

describe('getTodayStr (re-export)', () => {
    it('produces same result as toLocalDateString(new Date())', () => {
        const result = getTodayStr();
        expect(result).toBe(toLocalDateString(new Date()));
    });

    it('returns YYYY-MM-DD format', () => {
        const result = getTodayStr();
        expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });
});

describe('formatElapsed', () => {
    it('formats zero seconds', () => {
        expect(formatElapsed(0)).toBe('00:00');
    });

    it('formats under one minute', () => {
        expect(formatElapsed(45)).toBe('00:45');
    });

    it('formats exactly one minute', () => {
        expect(formatElapsed(60)).toBe('01:00');
    });

    it('formats mixed minutes and seconds', () => {
        expect(formatElapsed(125)).toBe('02:05');
    });

    it('formats large values without hour truncation', () => {
        expect(formatElapsed(3661)).toBe('61:01');
    });
});

describe('formatMinutes', () => {
    it('formats zero minutes', () => {
        expect(formatMinutes(0)).toBe('0min');
    });

    it('formats under 60 minutes', () => {
        expect(formatMinutes(30)).toBe('30min');
    });

    it('formats exactly 60 minutes', () => {
        expect(formatMinutes(60)).toBe('1h');
    });

    it('formats over 60 with remainder', () => {
        expect(formatMinutes(90)).toBe('1h30min');
    });

    it('formats exactly 120 minutes', () => {
        expect(formatMinutes(120)).toBe('2h');
    });
});
