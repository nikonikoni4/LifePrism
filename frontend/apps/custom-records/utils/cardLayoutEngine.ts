/**
 * L1 启发式布局引擎
 *
 * 输入: fields[] (字段定义) + data{} (单条记录数据) + overrides{} (用户覆盖)
 * 输出: { layout, title, main, chips, hidden }
 *
 * 字段角色识别优先级:
 *   1. 用户覆盖 (overrides[field_key] = 'title'/'main'/'chip'/'hidden')
 *   2. 关键词匹配 (TITLE/MAIN/HIDDEN 关键词列表)
 *   3. 内容长度启发
 *
 * 布局模式决策:
 *   - note: 有 main 字段 → 标题 + 大段正文 + chips
 *   - tight: 无 main，chips 全短(<12字) → 纯标签云
 *   - compact: 无 main 但有中长字段 → 键值对列表
 */

import type { FieldDefinition } from '../types';

// ==================== 关键词常量 ====================

const TITLE_KEYWORDS = [
  'title', 'name', 'book_name', 'movie_name', 'game', 'place', 'destination', 'dream_theme',
  '书名', '标题', '名称', '片名', '游戏', '地点', '目的地',
];

const MAIN_KEYWORDS = [
  'note', 'review', 'content', 'desc', 'description', 'text', 'detail', 'body', 'diary', 'log', 'dream', 'thought', 'feeling',
  '笔记', '评论', '内容', '描述', '正文', '日记', '日志', '感想', '感受', '详情',
];

const HIDDEN_KEYWORDS = [
  'id', 'created_at', 'updated_at', 'slug', 'type_id',
];

// ==================== 类型定义 ====================

export type LayoutMode = 'note' | 'compact' | 'tight';
export type FieldRole = 'title' | 'main' | 'chip' | 'hidden' | 'auto';

export interface CardLayoutResult {
  layout: LayoutMode;
  title: string | null;
  main: string | null;
  chips: { field_key: string; field_name: string; value: string }[];
  hidden: string[];
}

export type Overrides = Partial<Record<string, FieldRole>>;

// ==================== 辅助函数 ====================

const matchKeywords = (key: string, name: string, keywords: string[]): boolean => {
  const lowerKey = key.toLowerCase();
  const lowerName = name.toLowerCase();
  return keywords.some(kw =>
    lowerKey === kw ||
    lowerKey.includes(kw) ||
    lowerName === kw ||
    lowerName.includes(kw),
  );
};

const resolveRole = (
  field: FieldDefinition,
  overrides: Overrides,
  value: string,
): FieldRole => {
  // 1. 用户覆盖优先
  const override = overrides[field.field_key];
  if (override && override !== 'auto') return override;

  // 2. 关键词匹配
  if (matchKeywords(field.field_key, field.field_name, HIDDEN_KEYWORDS)) return 'hidden';
  if (matchKeywords(field.field_key, field.field_name, TITLE_KEYWORDS)) return 'title';
  if (matchKeywords(field.field_key, field.field_name, MAIN_KEYWORDS)) return 'main';

  // 3. 内容长度启发
  if (value.length > 25) return 'main';
  if (value.length <= 20) return 'chip';
  // 20-25 且无主体 → main
  return 'main';
};

// ==================== 主函数 ====================

export function analyzeCardLayout(
  fields: FieldDefinition[],
  data: Record<string, string>,
  overrides: Overrides = {},
): CardLayoutResult {
  let title: string | null = null;
  let main: string | null = null;
  const chips: { field_key: string; field_name: string; value: string }[] = [];
  const hidden: string[] = [];

  for (const field of fields) {
    const value = data[field.field_key] ?? '';

    const role = resolveRole(field, overrides, value);

    switch (role) {
      case 'title':
        if (title === null) title = value;
        else chips.push({ field_key: field.field_key, field_name: field.field_name, value });
        break;
      case 'main':
        if (main === null) main = value;
        else chips.push({ field_key: field.field_key, field_name: field.field_name, value });
        break;
      case 'hidden':
        hidden.push(field.field_key);
        break;
      case 'chip':
      default:
        chips.push({ field_key: field.field_key, field_name: field.field_name, value });
        break;
    }
  }

  // 布局模式决策
  let layout: LayoutMode;
  if (main !== null) {
    layout = 'note';
  } else if (chips.length > 0 && chips.every(c => c.value.length < 12)) {
    layout = 'tight';
  } else {
    layout = 'compact';
  }

  return { layout, title, main, chips, hidden };
}
