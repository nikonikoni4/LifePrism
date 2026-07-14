/**
 * 图表数据聚合工具
 *
 * 将自定义记录条目聚合为折线图数据点。支持两种模式：
 * - point: 每条记录一个数据点（X 轴 MM-DD HH:MM）
 * - daily: 同一天多条记录对每个数值字段求和（X 轴 MM-DD）
 *
 * 仅纳入数值字段（integer/float），text 字段不参与聚合。
 * X 轴按时间升序排列（与卡片/表格的 DESC 相反，趋势图需要时间从左到右）。
 */

import { parseISOString, toLocalDateString, toLocalDateTimeString } from '../../../core/utils/dateUtils';
import type { FieldDefinition, CustomRecordEntryItem } from '../types';
import { isNumericField } from './fieldFormatter';

/** 聚合模式 */
export type AggregateMode = 'point' | 'daily';

/** 数据点（label 为 X 轴标签，其余键为各数值字段的值） */
export interface ChartDataPoint {
  label: string;
  [fieldKey: string]: string | number | undefined;
}

/** 聚合结果 */
export interface AggregatedChartData {
  /** 已聚合 + 升序排序的数据点 */
  dataPoints: ChartDataPoint[];
  /** 参与图表的数值字段列表（按 fields 中出现顺序） */
  seriesFields: FieldDefinition[];
}

/**
 * 聚合 entries 为折线图数据点
 *
 * @param entries 记录列表（已按 event_time DESC 排序，函数内会改为升序）
 * @param fields 类型字段定义列表（含 text 和数值字段，函数内过滤出数值字段）
 * @param mode 聚合模式：point 按数据点 / daily 按天聚合
 */
export function aggregateChartData(
  entries: CustomRecordEntryItem[],
  fields: FieldDefinition[],
  mode: AggregateMode,
): AggregatedChartData {
  const seriesFields = fields.filter(f => isNumericField(f.field_type));

  // 无数值字段或无记录，直接返回空
  if (seriesFields.length === 0 || entries.length === 0) {
    return { dataPoints: [], seriesFields };
  }

  if (mode === 'point') {
    return aggregateByPoint(entries, seriesFields);
  }
  return aggregateByDaily(entries, seriesFields);
}

/**
 * 按数据点模式聚合：每条记录一个数据点
 */
function aggregateByPoint(
  entries: CustomRecordEntryItem[],
  seriesFields: FieldDefinition[],
): AggregatedChartData {
  // 按 event_time 升序（与卡片/表格 DESC 相反）
  const sorted = [...entries].sort((a, b) => {
    const ta = a.event_time ? parseISOString(a.event_time).getTime() : 0;
    const tb = b.event_time ? parseISOString(b.event_time).getTime() : 0;
    return ta - tb;
  });

  const dataPoints: ChartDataPoint[] = sorted.map(entry => {
    const label = formatPointLabel(entry.event_time);
    const point: ChartDataPoint = { label };
    for (const f of seriesFields) {
      const val = entry[f.field_key];
      if (val != null && val !== '') {
        const num = typeof val === 'number' ? val : Number(val);
        point[f.field_key] = Number.isNaN(num) ? undefined : num;
      }
    }
    return point;
  });

  return { dataPoints, seriesFields };
}

/**
 * 按天聚合模式：同一天多条记录对每个数值字段求和
 */
function aggregateByDaily(
  entries: CustomRecordEntryItem[],
  seriesFields: FieldDefinition[],
): AggregatedChartData {
  // 按 local date 分组
  const groups = new Map<string, { sums: Record<string, number>; hasValue: Record<string, boolean> }>();

  for (const entry of entries) {
    if (!entry.event_time) continue;
    const dateKey = toLocalDateString(parseISOString(entry.event_time)); // YYYY-MM-DD

    if (!groups.has(dateKey)) {
      groups.set(dateKey, {
        sums: {},
        hasValue: {},
      });
    }
    const group = groups.get(dateKey)!;

    for (const f of seriesFields) {
      const val = entry[f.field_key];
      if (val != null && val !== '') {
        const num = typeof val === 'number' ? val : Number(val);
        if (!Number.isNaN(num)) {
          group.sums[f.field_key] = (group.sums[f.field_key] || 0) + num;
          group.hasValue[f.field_key] = true;
        }
      }
    }
  }

  // 按日期升序排序
  const sortedKeys = [...groups.keys()].sort();
  const dataPoints: ChartDataPoint[] = sortedKeys.map(dateKey => {
    const label = formatDailyLabel(dateKey);
    const group = groups.get(dateKey)!;
    const point: ChartDataPoint = { label };
    for (const f of seriesFields) {
      point[f.field_key] = group.hasValue[f.field_key] ? group.sums[f.field_key] : undefined;
    }
    return point;
  });

  return { dataPoints, seriesFields };
}

/**
 * 格式化数据点模式 X 轴标签：MM-DD HH:MM
 */
function formatPointLabel(eventTime: string): string {
  if (!eventTime) return '';
  const dt = toLocalDateTimeString(parseISOString(eventTime)); // YYYY-MM-DDTHH:MM:SS
  // 提取 MM-DD HH:MM
  const match = dt.match(/^\d{4}-(\d{2}-\d{2})T(\d{2}:\d{2})/);
  if (match) {
    return `${match[1]} ${match[2]}`;
  }
  return dt;
}

/**
 * 格式化按天模式 X 轴标签：MM-DD
 */
function formatDailyLabel(dateKey: string): string {
  // dateKey 格式 YYYY-MM-DD，提取 MM-DD
  const match = dateKey.match(/^\d{4}-(\d{2}-\d{2})$/);
  return match ? match[1] : dateKey;
}
