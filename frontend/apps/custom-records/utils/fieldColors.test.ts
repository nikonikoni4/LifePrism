/**
 * 字段配色工具测试
 *
 * Seam: fieldColors.ts — 纯函数 hashStr + getFieldColor
 * 验证同一 field_key 永远获得同一颜色，颜色循环稳定
 */
import { describe, it, expect } from 'vitest';
import { hashStr, getFieldColor, FIELD_COLORS } from './fieldColors';

describe('fieldColors', () => {
  // ==================== Cycle 1: hashStr ====================

  describe('hashStr', () => {
    it('should return a non-negative integer for any string', () => {
      const result = hashStr('book_title');
      expect(result).toBeGreaterThanOrEqual(0);
      expect(Number.isInteger(result)).toBe(true);
    });

    it('should be deterministic — same input always gives same output', () => {
      const a = hashStr('movie_title');
      const b = hashStr('movie_title');
      expect(a).toBe(b);
    });

    it('should produce different hashes for different inputs (typically)', () => {
      const a = hashStr('title');
      const b = hashStr('content');
      expect(a).not.toBe(b);
    });

    it('should handle empty string without error', () => {
      expect(() => hashStr('')).not.toThrow();
      expect(hashStr('')).toBeGreaterThanOrEqual(0);
    });
  });

  // ==================== Cycle 1: getFieldColor ====================

  describe('getFieldColor', () => {
    it('should return a color object with required properties', () => {
      const color = getFieldColor('book_title');
      expect(color).toHaveProperty('bg');
      expect(color).toHaveProperty('text');
      expect(color).toHaveProperty('border');
      expect(color).toHaveProperty('dot');
      expect(color).toHaveProperty('solid');
    });

    it('should be deterministic — same field_key always returns same color', () => {
      const a = getFieldColor('rating');
      const b = getFieldColor('rating');
      expect(a).toEqual(b);
    });

    it('should return colors from the FIELD_COLORS palette', () => {
      const color = getFieldColor('notes');
      expect(FIELD_COLORS).toContain(color);
    });

    it('should distribute different field_keys across the palette', () => {
      // 10 个不同 field_key 应该至少命中 3 个不同颜色
      const keys = ['title', 'name', 'content', 'rating', 'notes', 'tags', 'date', 'author', 'url', 'summary'];
      const colors = new Set(keys.map(k => getFieldColor(k).solid));
      expect(colors.size).toBeGreaterThanOrEqual(3);
    });
  });
});
