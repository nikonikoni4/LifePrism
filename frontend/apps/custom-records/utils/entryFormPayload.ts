/**
 * EntryForm 表单数据构造工具
 *
 * 提供 create / edit 两种模式下的 payload 构造函数：
 * - buildCreatePayload: create 模式，留空字段不放入 data dict（后端默认 NULL）
 * - buildUpdatePayload: edit 模式，diff 后仅把变化字段放入 data dict
 *   （未变化=不修改，清空=null，改值=新值，遵循项目标准三态语义）
 *
 * 三态语义对齐 backend-api-rules.md：
 *   未传 → 不修改
 *   传 null → 清空（写入 NULL）
 *   传值 → 更新为新值
 */

import { parseISOString, toLocalDateTimeString, toISOStringUTC } from '../../../core/utils/dateUtils';
import type { FieldDefinition, CustomRecordEntryItem, UpdateCustomRecordEntryRequest } from '../types';

/**
 * 判断字段名是否暗示长文本（textarea）
 * 启发式规则：字段名含 note/content/review/desc/remark/memo 关键词
 */
const LONG_TEXT_KEYWORDS = ['note', 'content', 'review', 'desc', 'remark', 'memo'];

export function isLongTextField(fieldKey: string): boolean {
  const lower = fieldKey.toLowerCase();
  return LONG_TEXT_KEYWORDS.some((kw) => lower.includes(kw));
}

/**
 * 将表单字符串值按字段类型转换为后端期望的类型
 * - integer：尝试转 Number，非整数原样传（由后端拒绝并返回 422）
 * - float：尝试转 Number，非数值原样传（由后端拒绝）
 * - text：原样字符串
 */
function coerceValueByType(
  raw: string,
  fieldType: FieldDefinition['field_type'],
): string | number {
  if (fieldType === 'integer') {
    const num = Number(raw);
    return Number.isInteger(num) ? num : raw;
  }
  if (fieldType === 'float') {
    const num = Number(raw);
    return isNaN(num) ? raw : num;
  }
  return raw;
}

/**
 * buildCreatePayload: 构造 create 通道提交数据
 *
 * create 模式语义：留空字段不放入 data dict（后端默认 NULL）。
 * 原因：create 时不存在"清空"概念，留空即 NULL，前端不应传 null 表达"清空"。
 *
 * @param formData 表单值字典（field_key → 字符串值，空字符串表示留空）
 * @param fields 当前类型的字段定义列表
 * @returns 提交给后端 createEntry 的 data 字典
 */
export function buildCreatePayload(
  formData: Record<string, string>,
  fields: FieldDefinition[],
): Record<string, string | number> {
  const data: Record<string, string | number> = {};
  for (const f of fields) {
    const raw = formData[f.field_key];
    if (raw == null || raw === '') {
      continue; // 留空字段不放入（后端默认 NULL）
    }
    data[f.field_key] = coerceValueByType(raw, f.field_type);
  }
  return data;
}

/**
 * 将后端 ISO 8601 时间字符串转换为 datetime-local 控件值格式 yyyy-MM-ddTHH:mm（无秒）
 *
 * 用于 edit 模式预填事件时间控件，以及 diff 时与控件值比较。
 * 复用 dateUtils.toLocalDateTimeString（本地时区），截断秒部分匹配控件格式。
 */
export function isoToDatetimeLocal(iso: string): string {
  if (!iso) return '';
  // parseISOString → Date（本地时区）→ toLocalDateTimeString（yyyy-MM-ddTHH:MM:SS）→ slice(0,16)
  return toLocalDateTimeString(parseISOString(iso)).slice(0, 16);
}

/**
 * buildUpdatePayload: 构造 edit 通道提交数据（diff 模式，遵循项目标准三态语义）
 *
 * diff 规则（对齐 backend-api-rules.md 三态语义）：
 *   - 字段未变化 → 不放入 data dict（不修改）
 *   - 用户清空字段（新值空、原值非空） → data[key] = null（清空，写入 NULL）
 *   - 用户改值 → data[key] = 新值（更新）
 *   - 字段原值空且新值空 → 不放入（不修改）
 *
 * event_time diff：
 *   - 未变化 → 不放入 result.event_time（不修改）
 *   - 变化且新值非空 → result.event_time = UTC ISO 8601（更新）
 *   - 变化但新值为空 → 不放入（前端 UI 负责拦截清空，后端 event_time 不可清空）
 *
 * @param formData 表单值字典（field_key → 字符串值，空字符串表示清空/留空）
 * @param fields 当前类型的字段定义列表
 * @param originalEntry 编辑前的原始记录（用于 diff 比较）
 * @param eventTime 本地时间 yyyy-MM-ddTHH:mm（datetime-local 控件值）
 * @returns 提交给后端 updateEntry 的 payload
 */
export function buildUpdatePayload(
  formData: Record<string, string>,
  fields: FieldDefinition[],
  originalEntry: CustomRecordEntryItem,
  eventTime: string,
): UpdateCustomRecordEntryRequest {
  const data: Record<string, string | number | null> = {};

  // 字段值 diff
  for (const f of fields) {
    const newVal = formData[f.field_key] ?? '';
    const oldVal = originalEntry[f.field_key];
    const oldStr = oldVal != null ? String(oldVal) : '';

    // 都是空 → 不修改
    if (newVal === '' && oldStr === '') continue;
    // 没变化 → 不修改
    if (newVal === oldStr) continue;

    // 有变化
    if (newVal === '') {
      // 用户清空字段 → null（清空语义）
      data[f.field_key] = null;
    } else {
      data[f.field_key] = coerceValueByType(newVal, f.field_type);
    }
  }

  const result: UpdateCustomRecordEntryRequest = { data };

  // event_time diff：与原 event_time 转 datetime-local 格式后比较
  const oldEventTimeLocal = originalEntry.event_time
    ? isoToDatetimeLocal(originalEntry.event_time)
    : '';
  if (eventTime !== oldEventTimeLocal && eventTime !== '') {
    // 变化且非空 → 转 UTC ISO 8601 传给后端
    result.event_time = toISOStringUTC(new Date(eventTime));
  }
  // 若 eventTime === oldEventTimeLocal 或 eventTime === ''，不放入 result → 不修改 event_time

  return result;
}
