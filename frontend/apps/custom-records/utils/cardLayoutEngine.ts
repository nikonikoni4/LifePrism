/**
 * L1 启发式布局引擎
 *
 * 输入: fields[] (字段定义) + data{} (单条记录数据) + overrides{} (用户覆盖)
 * 输出: { layout, title, mains, chips, hidden }
 *
 * 字段角色识别优先级:
 *   1. 用户覆盖 (overrides[field_key] = 'title'/'main'/'chip'/'hidden')
 *   2. 关键词匹配 (TITLE/MAIN/HIDDEN 关键词列表)
 *   3. 内容长度启发
 *
 * 布局模式决策:
 *   - note: 有 main 字段 → 标题 + 大段正文（支持多个叠加） + chips
 *   - tight: 无 main，chips 全短(<12字) → 纯标签云
 *   - compact: 无 main 但有中长字段 → 键值对列表
 *
 * 空字段处理:
 *   - 无论字段配置为什么角色，若值为空（空字符串/null/undefined），则不渲染
 *   - 标题（title）只能有一个：若配置的 title 为空，第一个非空的 title 候选成为标题
 *   - 正文（main）支持多个叠加：所有配置为 main 且非空的字段按顺序渲染
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
  mains: { field_key: string; field_name: string; value: string }[];
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

  // 3. 内容长度启发（空值不参与启发，直接作为 chip 但会被过滤）
  if (value.length > 25) return 'main';
  if (value.length <= 20) return 'chip';
  // 20-25 且无主体 → main
  return 'main';
};

/**
 * 判断值是否为空（空字符串、null、undefined、仅空白字符）
 */
const isEmpty = (val: string | null | undefined): boolean => {
  if (val == null) return true;
  return val.trim().length === 0;
};

// ==================== 主函数 ====================

export function analyzeCardLayout(
  fields: FieldDefinition[],
  data: Record<string, string>,
  overrides: Overrides = {},
): CardLayoutResult {
  let title: string | null = null;
  const mains: { field_key: string; field_name: string; value: string }[] = [];
  const chips: { field_key: string; field_name: string; value: string }[] = [];
  const hidden: string[] = [];

  // 收集所有角色为 title 的非空候选（用于 fallback）
  const titleCandidates: { field_key: string; field_name: string; value: string }[] = [];

  for (const field of fields) {
    const rawValue = data[field.field_key];
    const value = rawValue ?? '';

    // 空值检查：无论什么角色，空值都不渲染（hidden 除外，它本来就不渲染）
    if (isEmpty(value)) {
      continue;
    }

    const role = resolveRole(field, overrides, value);

    switch (role) {
      case 'title':
        titleCandidates.push({ field_key: field.field_key, field_name: field.field_name, value });
        break;
      case 'main':
        mains.push({ field_key: field.field_key, field_name: field.field_name, value });
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

  // 标题选择：第一个非空 title 候选成为标题，其余降级为 chip
  if (titleCandidates.length > 0) {
    title = titleCandidates[0].value;
    // 其余 title 候选降级为 chip
    for (let i = 1; i < titleCandidates.length; i++) {
      chips.push(titleCandidates[i]);
    }
  }

  // 布局模式决策
  let layout: LayoutMode;
  if (mains.length > 0) {
    layout = 'note';
  } else if (chips.length > 0 && chips.every(c => c.value.length < 12)) {
    layout = 'tight';
  } else {
    layout = 'compact';
  }

  return { layout, title, mains, chips, hidden };
}
