import type { ValueItem, ValueItemFrontend } from './valueTypes';

/**
 * 后端 → 前端：解析 keywords 字符串为数组
 */
export function parseValueFromBackend(backend: ValueItem): ValueItemFrontend {
  const keywords = backend.keywords
    ? backend.keywords.split(';').map(k => k.trim()).filter(Boolean)
    : ['未命名'];

  return {
    ...backend,
    keywords,
  };
}

/**
 * 前端 → 后端：将 keywords 数组转为字符串
 */
export function formatValueForBackend(
  value: Partial<ValueItemFrontend>
): Partial<ValueItem> {
  const result: Partial<ValueItem> = {};

  if (value.keywords) {
    result.keywords = value.keywords.join(';');
  }
  if (value.content_positive !== undefined) {
    result.content_positive = value.content_positive;
  }
  if (value.content_negative !== undefined) {
    result.content_negative = value.content_negative;
  }
  if (value.sort_order !== undefined) {
    result.sort_order = value.sort_order;
  }

  return result;
}

/**
 * 验证后端数据格式
 */
export function validateBackendValue(data: any): boolean {
  if (!data.id || typeof data.id !== 'string') return false;
  if (typeof data.keywords !== 'string') return false;
  if (data.content_positive !== null && typeof data.content_positive !== 'string') return false;
  if (data.content_negative !== null && typeof data.content_negative !== 'string') return false;
  if (typeof data.sort_order !== 'number') return false;
  return true;
}
