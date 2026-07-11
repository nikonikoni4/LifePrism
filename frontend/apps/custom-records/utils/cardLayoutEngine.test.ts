/**
 * L1 启发式布局引擎测试
 *
 * Seam: cardLayoutEngine.ts — 纯函数 analyzeCardLayout
 * 输入: fields[] + data{} + overrides{}
 * 输出: { layout, title, mains, chips, hidden }
 */
import { describe, it, expect } from 'vitest';
import { analyzeCardLayout } from './cardLayoutEngine';
import type { Overrides } from './cardLayoutEngine';
import type { FieldDefinition } from '../types';

const mkField = (field_key: string, field_name: string, display_role?: string): FieldDefinition => ({
  field_key,
  field_name,
  field_type: 'text',
  id: '',
  display_role: (display_role || 'auto') as FieldDefinition['display_role'],
});

const mkFields = (...defs: [string, string, string?][]): FieldDefinition[] =>
  defs.map(([field_key, field_name, role]) => mkField(field_key, field_name, role));

/**
 * 从字段定义中提取 overrides（与 EntryCard 组件逻辑一致）
 */
const extractOverrides = (fields: FieldDefinition[]): Overrides => {
  const overrides: Overrides = {};
  for (const f of fields) {
    if (f.display_role && f.display_role !== 'auto') {
      overrides[f.field_key] = f.display_role as Overrides[string];
    }
  }
  return overrides;
};

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
      expect(result.mains).toHaveLength(1);
      expect(result.mains[0].value).toBe('这是一段笔记内容');
    });

    it('should identify main field by English keyword "content"', () => {
      const fields = mkFields(['content', 'Content']);
      const data = mkData({ content: '正文内容' });
      const result = analyzeCardLayout(fields, data);
      expect(result.mains).toHaveLength(1);
      expect(result.mains[0].value).toBe('正文内容');
    });

    it('should identify main field by English keyword "review"', () => {
      const fields = mkFields(['title', 'Title'], ['review', 'Review']);
      const data = mkData({ title: '电影', review: '非常精彩' });
      const result = analyzeCardLayout(fields, data);
      expect(result.mains).toHaveLength(1);
      expect(result.mains[0].value).toBe('非常精彩');
    });

    it('should identify main field by Chinese keyword 笔记', () => {
      const fields = mkFields(['book_title', '书名'], ['notes', '笔记']);
      const data = mkData({ book_title: '三体', notes: '宇宙社会学猜想' });
      const result = analyzeCardLayout(fields, data);
      expect(result.mains).toHaveLength(1);
      expect(result.mains[0].value).toBe('宇宙社会学猜想');
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
      expect(result.mains.length).toBeGreaterThan(0);
    });
  });

  describe('layout mode decision — tight', () => {
    it('should use tight layout when all chips are short (<12 chars) and no main', () => {
      const fields = mkFields(['rating', 'Rating'], ['status', 'Status']);
      const data = mkData({ rating: '9.3', status: '已完成' });
      const result = analyzeCardLayout(fields, data);
      expect(result.layout).toBe('tight');
      expect(result.mains).toHaveLength(0);
    });
  });

  describe('layout mode decision — compact', () => {
    it('should use compact layout when no main but has medium-length chips (>=12 chars)', () => {
      const fields = mkFields(['summary', 'Summary'], ['author', 'Author']);
      const data = mkData({ summary: '这是一段中等长度的摘要文字', author: '张三' });
      const result = analyzeCardLayout(fields, data);
      expect(result.layout).toBe('compact');
      expect(result.mains).toHaveLength(0);
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
      expect(result.mains).toHaveLength(0);
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
      expect(result.mains).toHaveLength(0);
    });

    it('should treat "auto" override as no override (falls through to heuristic)', () => {
      const fields = mkFields(['title', 'Title'], ['content', 'Content']);
      const data = mkData({ title: '标题', content: '正文' });
      const result = analyzeCardLayout(fields, data, { title: 'auto', content: 'auto' });
      expect(result.title).toBe('标题');
      expect(result.mains).toHaveLength(1);
      expect(result.mains[0].value).toBe('正文');
    });
  });

  describe('content length heuristic — fallback when no keyword match', () => {
    it('should mark long content (>25 chars) as main', () => {
      const fields = mkFields(['custom_field', '自定义']);
      const longValue = '这是一段超过25个字符的自定义字段值内容文字';
      const data = mkData({ custom_field: longValue });
      const result = analyzeCardLayout(fields, data);
      expect(result.mains).toHaveLength(1);
      expect(result.mains[0].value).toBe(longValue);
      expect(result.layout).toBe('note');
    });

    it('should mark short content (<=20 chars) as chip', () => {
      const fields = mkFields(['custom_field', '自定义']);
      const data = mkData({ custom_field: '短文本' });
      const result = analyzeCardLayout(fields, data);
      expect(result.chips).toHaveLength(1);
      expect(result.mains).toHaveLength(0);
      expect(result.layout).toBe('tight');
    });

    it('should mark medium content (21-25 chars) as main', () => {
      const fields = mkFields(['custom_field', '自定义']);
      // Exactly 22 characters
      const mediumValue = '一二三四五六七八九十一二三四五六七八九十一二';
      expect(mediumValue.length).toBe(22);
      const data = mkData({ custom_field: mediumValue });
      const result = analyzeCardLayout(fields, data);
      expect(result.mains).toHaveLength(1);
      expect(result.mains[0].value).toBe(mediumValue);
    });
  });

  // ==================== 新增：多个正文叠加 ====================

  describe('multiple main fields — stacking support', () => {
    it('should support multiple main fields stacked together', () => {
      const fields = mkFields(
        ['title', '标题'],
        ['thoughts', '感想'],
        ['feelings', '感受'],
        ['mood', '心情'],
      );
      const data = mkData({
        title: '今天的反思',
        thoughts: '今天学习了很多新东西，感觉收获满满。',
        feelings: '心情很平静，对未来充满期待。',
        mood: '愉悦',
      });
      const result = analyzeCardLayout(fields, data);
      expect(result.layout).toBe('note');
      expect(result.title).toBe('今天的反思');
      // thoughts 和 feelings 都是 main 关键词
      expect(result.mains.length).toBeGreaterThanOrEqual(2);
      expect(result.mains[0].field_key).toBe('thoughts');
      expect(result.mains[1].field_key).toBe('feelings');
      // mood 是短文本，应为 chip
      expect(result.chips.some(c => c.field_key === 'mood')).toBe(true);
    });

    it('should render multiple explicit main overrides in order', () => {
      const fields = mkFields(
        ['title', '标题'],
        ['part1', '第一部分', 'main'],
        ['part2', '第二部分', 'main'],
        ['part3', '第三部分', 'main'],
      );
      const data = mkData({
        title: '分段笔记',
        part1: '第一部分的内容，关于引言。',
        part2: '第二部分的内容，关于主体。',
        part3: '第三部分的内容，关于结论。',
      });
      const overrides = extractOverrides(fields);
      const result = analyzeCardLayout(fields, data, overrides);
      expect(result.mains).toHaveLength(3);
      expect(result.mains[0].field_key).toBe('part1');
      expect(result.mains[1].field_key).toBe('part2');
      expect(result.mains[2].field_key).toBe('part3');
      expect(result.layout).toBe('note');
    });
  });

  // ==================== 新增：空字段不渲染 ====================

  describe('empty fields — should not render', () => {
    it('should skip fields with empty string values', () => {
      const fields = mkFields(['title', '标题'], ['note', '笔记'], ['tag', '标签']);
      const data = mkData({ title: '有标题', note: '', tag: '标签值' });
      const result = analyzeCardLayout(fields, data);
      expect(result.title).toBe('有标题');
      // note 为空，不应出现在 mains 中
      expect(result.mains).toHaveLength(0);
      // tag 非空，应在 chips 中
      expect(result.chips).toHaveLength(1);
      expect(result.chips[0].field_key).toBe('tag');
    });

    it('should skip fields with whitespace-only values', () => {
      const fields = mkFields(['title', '标题'], ['note', '笔记'], ['tag', '标签']);
      const data = mkData({ title: '   ', note: '  ', tag: '有内容' });
      const result = analyzeCardLayout(fields, data);
      // title 只有空白，不应成为标题
      expect(result.title).toBeNull();
      // note 只有空白，不应在 mains
      expect(result.mains).toHaveLength(0);
      expect(result.chips).toHaveLength(1);
    });

    it('should skip fields with missing values (undefined)', () => {
      const fields = mkFields(['title', '标题'], ['note', '笔记'], ['tag', '标签']);
      const data = mkData({ title: '标题存在' });
      // note 和 tag 都不存在
      const result = analyzeCardLayout(fields, data);
      expect(result.title).toBe('标题存在');
      expect(result.mains).toHaveLength(0);
      expect(result.chips).toHaveLength(0);
    });

    it('should not show empty chips — all empty fields should be filtered out', () => {
      const fields = mkFields(
        ['a', '字段A'],
        ['b', '字段B'],
        ['c', '字段C'],
      );
      const data = mkData({ a: '有值', b: '', c: '   ' });
      const result = analyzeCardLayout(fields, data);
      expect(result.chips).toHaveLength(1);
      expect(result.chips[0].field_key).toBe('a');
    });

    it('should handle configured title being empty — fall back to next non-empty title candidate', () => {
      const fields = mkFields(
        ['title', '标题', 'title'],
        ['name', '名称', 'auto'],
        ['content', '内容'],
      );
      const data = mkData({ title: '', name: '备用标题', content: '正文内容' });
      const overrides = extractOverrides(fields);
      const result = analyzeCardLayout(fields, data, overrides);
      // title 配置为 title 但为空，name 通过关键词匹配为 title 候选
      expect(result.title).toBe('备用标题');
      expect(result.mains).toHaveLength(1);
    });

    it('should not render empty chips when configured as chip', () => {
      const fields = mkFields(
        ['tag1', '标签1', 'chip'],
        ['tag2', '标签2', 'chip'],
        ['tag3', '标签3', 'chip'],
      );
      const data = mkData({ tag1: '标签A', tag2: '', tag3: '标签C' });
      const overrides = extractOverrides(fields);
      const result = analyzeCardLayout(fields, data, overrides);
      expect(result.chips).toHaveLength(2);
      expect(result.chips.map(c => c.field_key)).toEqual(['tag1', 'tag3']);
    });
  });

  // ==================== 标题降级逻辑 ====================

  describe('title overflow — extra title candidates become chips', () => {
    it('should demote second title candidate to chip', () => {
      const fields = mkFields(['title', '标题'], ['name', '名称']);
      const data = mkData({ title: '主标题', name: '副标题/别名' });
      const result = analyzeCardLayout(fields, data);
      expect(result.title).toBe('主标题');
      // name 也匹配 title 关键词，但只能有一个标题，其余降级为 chip
      expect(result.chips.some(c => c.field_key === 'name')).toBe(true);
    });
  });
});
