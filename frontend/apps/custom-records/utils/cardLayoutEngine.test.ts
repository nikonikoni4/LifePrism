/**
 * L1 启发式布局引擎测试
 *
 * Seam: cardLayoutEngine.ts — 纯函数 analyzeCardLayout
 * 输入: fields[] + data{} + overrides{}
 * 输出: { layout, title, main, chips, hidden }
 */
import { describe, it, expect } from 'vitest';
import { analyzeCardLayout } from './cardLayoutEngine';
import type { FieldDefinition } from '../types';

const mkFields = (...defs: [string, string][]): FieldDefinition[] =>
  defs.map(([field_key, field_name]) => ({ field_key, field_name, field_type: 'text' }));

const mkData = (obj: Record<string, string>): Record<string, string> => obj;

describe('analyzeCardLayout', () => {
  // ==================== Cycle 2: 字段角色识别 — 关键词匹配 ====================

  describe('keyword matching — title role', () => {
    it('should identify title field by English keyword "title"', () => {
      const fields = mkFields(['title', 'Title'], ['notes', 'Notes']);
      const data = mkData({ title: '百年孤独', notes: '魔幻现实主义' });
      const result = analyzeCardLayout(fields, data);
      expect(result.title).toBe('百年孤独');
    });

    it('should identify title field by English keyword "name"', () => {
      const fields = mkFields(['name', 'Name'], ['desc', 'Description']);
      const data = mkData({ name: ' Inbox Zero 方法', desc: '清空收件箱' });
      const result = analyzeCardLayout(fields, data);
      expect(result.title).toBe(' Inbox Zero 方法');
    });

    it('should identify title field by English keyword "book_name"', () => {
      const fields = mkFields(['book_name', '书名'], ['note', '笔记']);
      const data = mkData({ book_name: '三体', note: '震撼的宇宙史诗' });
      const result = analyzeCardLayout(fields, data);
      expect(result.title).toBe('三体');
    });

    it('should identify title field by Chinese keyword 书名', () => {
      const fields = mkFields(['book_title', '书名'], ['content', '内容']);
      const data = mkData({ book_title: '活着', content: '福贵的一生' });
      const result = analyzeCardLayout(fields, data);
      expect(result.title).toBe('活着');
    });
  });

  describe('keyword matching — main role', () => {
    it('should identify main field by English keyword "note"', () => {
      const fields = mkFields(['title', 'Title'], ['note', 'Note']);
      const data = mkData({ title: '测试', note: '这是一段笔记内容' });
      const result = analyzeCardLayout(fields, data);
      expect(result.main).toBe('这是一段笔记内容');
    });

    it('should identify main field by English keyword "content"', () => {
      const fields = mkFields(['content', 'Content']);
      const data = mkData({ content: '正文内容' });
      const result = analyzeCardLayout(fields, data);
      expect(result.main).toBe('正文内容');
    });

    it('should identify main field by English keyword "review"', () => {
      const fields = mkFields(['title', 'Title'], ['review', 'Review']);
      const data = mkData({ title: '电影', review: '非常精彩' });
      const result = analyzeCardLayout(fields, data);
      expect(result.main).toBe('非常精彩');
    });

    it('should identify main field by Chinese keyword 笔记', () => {
      const fields = mkFields(['book_title', '书名'], ['notes', '笔记']);
      const data = mkData({ book_title: '三体', notes: '宇宙社会学猜想' });
      const result = analyzeCardLayout(fields, data);
      expect(result.main).toBe('宇宙社会学猜想');
    });
  });

  describe('keyword matching — hidden role', () => {
    it('should hide system fields like id, created_at, updated_at', () => {
      const fields = mkFields(['title', 'Title'], ['id', 'ID']);
      const data = mkData({ title: '测试', id: '123' });
      const result = analyzeCardLayout(fields, data);
      expect(result.hidden).toContain('id');
      expect(result.title).toBe('测试');
    });
  });

  // ==================== Cycle 3: 布局模式决策 ====================

  describe('layout mode decision — note', () => {
    it('should use note layout when a main field exists', () => {
      const fields = mkFields(['title', 'Title'], ['content', 'Content']);
      const data = mkData({ title: '测试', content: '这是正文内容，超过短文本范围' });
      const result = analyzeCardLayout(fields, data);
      expect(result.layout).toBe('note');
      expect(result.main).not.toBeNull();
    });
  });

  describe('layout mode decision — tight', () => {
    it('should use tight layout when all chips are short (<12 chars) and no main', () => {
      const fields = mkFields(['rating', 'Rating'], ['status', 'Status']);
      const data = mkData({ rating: '9.3', status: '已完成' });
      const result = analyzeCardLayout(fields, data);
      expect(result.layout).toBe('tight');
      expect(result.main).toBeNull();
    });
  });

  describe('layout mode decision — compact', () => {
    it('should use compact layout when no main but has medium-length chips (>=12 chars)', () => {
      const fields = mkFields(['summary', 'Summary'], ['author', 'Author']);
      const data = mkData({ summary: '这是一段中等长度的摘要文字', author: '张三' });
      const result = analyzeCardLayout(fields, data);
      expect(result.layout).toBe('compact');
      expect(result.main).toBeNull();
    });
  });

  // ==================== Cycle 4: 用户覆盖 + 内容长度启发 ====================

  describe('user overrides — priority over keywords', () => {
    it('should respect explicit title override over keyword matching', () => {
      // 'content' normally matches MAIN_KEYWORDS, but override says 'title'
      const fields = mkFields(['content', 'Content'], ['rating', 'Rating']);
      const data = mkData({ content: '被覆盖为标题', rating: '8' });
      const result = analyzeCardLayout(fields, data, { content: 'title' });
      expect(result.title).toBe('被覆盖为标题');
      expect(result.main).toBeNull();
    });

    it('should respect explicit hidden override', () => {
      // 'title' normally matches TITLE_KEYWORDS, but override says 'hidden'
      const fields = mkFields(['title', 'Title'], ['rating', 'Rating']);
      const data = mkData({ title: '被隐藏', rating: '8' });
      const result = analyzeCardLayout(fields, data, { title: 'hidden' });
      expect(result.hidden).toContain('title');
      expect(result.title).toBeNull();
    });

    it('should respect explicit chip override for a long field', () => {
      // Long content would be 'main' by length heuristic, but override says 'chip'
      const fields = mkFields(['description', 'Description']);
      const data = mkData({ description: '这是一段超过25个字符的较长描述文字内容' });
      const result = analyzeCardLayout(fields, data, { description: 'chip' });
      expect(result.chips).toHaveLength(1);
      expect(result.chips[0].field_key).toBe('description');
      expect(result.main).toBeNull();
    });

    it('should treat "auto" override as no override (falls through to heuristic)', () => {
      const fields = mkFields(['title', 'Title'], ['content', 'Content']);
      const data = mkData({ title: '标题', content: '正文' });
      const result = analyzeCardLayout(fields, data, { title: 'auto', content: 'auto' });
      expect(result.title).toBe('标题');
      expect(result.main).toBe('正文');
    });
  });

  describe('content length heuristic — fallback when no keyword match', () => {
    it('should mark long content (>25 chars) as main', () => {
      const fields = mkFields(['custom_field', '自定义']);
      const longValue = '这是一段超过25个字符的自定义字段值内容文字';
      const data = mkData({ custom_field: longValue });
      const result = analyzeCardLayout(fields, data);
      expect(result.main).toBe(longValue);
      expect(result.layout).toBe('note');
    });

    it('should mark short content (<=20 chars) as chip', () => {
      const fields = mkFields(['custom_field', '自定义']);
      const data = mkData({ custom_field: '短文本' });
      const result = analyzeCardLayout(fields, data);
      expect(result.chips).toHaveLength(1);
      expect(result.main).toBeNull();
      expect(result.layout).toBe('tight');
    });

    it('should mark medium content (21-25 chars) as main', () => {
      const fields = mkFields(['custom_field', '自定义']);
      // Exactly 22 characters
      const mediumValue = '一二三四五六七八九十一二三四五六七八九十一二';
      expect(mediumValue.length).toBe(22);
      const data = mkData({ custom_field: mediumValue });
      const result = analyzeCardLayout(fields, data);
      expect(result.main).toBe(mediumValue);
    });
  });
});
