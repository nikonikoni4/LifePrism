/**
 * 字段值格式化工具
 *
 * 数值字段显示规则：
 * - integer：显示原值，不格式化（如 5 显示为 "5"）
 * - float：固定 1 位小数（如 65.5 显示为 "65.5"，65 显示为 "65.0"）
 * - text：直接显示字符串
 */

import type { FieldType } from '../types';

/**
 * 格式化字段值为显示字符串
 *
 * @param value 字段值（后端返回的原始值，可能为 string/number/null/undefined）
 * @param fieldType 字段类型
 * @returns 格式化后的显示字符串；值为 null/undefined 返回空字符串
 */
export function formatFieldValue(
  value: string | number | null | undefined,
  fieldType: FieldType,
): string {
  if (value === null || value === undefined) return '';

  if (fieldType === 'integer') {
    // integer 字段：显示原值（后端已校验为 int）
    return String(value);
  }

  if (fieldType === 'float') {
    // float 字段：固定 1 位小数
    const num = typeof value === 'number' ? value : parseFloat(value);
    if (Number.isNaN(num)) return String(value);
    return num.toFixed(1);
  }

  // text 字段：直接转字符串
  return String(value);
}

/**
 * 判断字段是否为数值类型（integer 或 float）
 */
export function isNumericField(fieldType: FieldType): boolean {
  return fieldType === 'integer' || fieldType === 'float';
}
