/**
 * 图表数据聚合函数测试
 *
 * Seam: chartAggregator.ts — 纯函数 aggregateChartData
 * 验证两种聚合模式：按数据点 / 按天聚合
 */
import { describe, it, expect } from 'vitest';
import { aggregateChartData } from './chartAggregator';
import type { FieldDefinition, CustomRecordEntryItem } from '../types';

// ==================== 测试数据 ====================

const numericFields: FieldDefinition[] = [
  { field_key: 'steps', field_name: '步数', field_type: 'integer' },
  { field_key: 'weight', field_name: '体重(kg)', field_type: 'float' },
];

const textField: FieldDefinition = { field_key: 'note', field_name: '备注', field_type: 'text' };

const makeEntry = (
  id: string,
  eventTime: string,
  data: Record<string, string | number>,
): CustomRecordEntryItem => ({
  id,
  event_time: eventTime,
  created_at: eventTime,
  updated_at: eventTime,
  ...data,
});

// ==================== 测试 ====================

describe('chartAggregator', () => {
  describe('按数据点模式（mode=point）', () => {
    it('每条记录一个数据点，X 轴为 MM-DD HH:MM', () => {
      const entries = [
        makeEntry('e1', '2026-07-13T06:30:00Z', { steps: 100, weight: 65.5 }),
        makeEntry('e2', '2026-07-13T18:00:00Z', { steps: 200, weight: 66.0 }),
      ];

      const result = aggregateChartData(entries, numericFields, 'point');

      expect(result.dataPoints).toHaveLength(2);
      // X 轴标签格式 MM-DD HH:MM（具体值依赖时区，只验证格式）
      expect(result.dataPoints[0].label).toMatch(/^\d{2}-\d{2} \d{2}:\d{2}$/);
      expect(result.dataPoints[0].steps).toBe(100);
      expect(result.dataPoints[0].weight).toBe(65.5);
    });

    it('同一天多条记录显示多个独立点（不合并）', () => {
      const entries = [
        makeEntry('e1', '2026-07-13T06:30:00Z', { steps: 100 }),
        makeEntry('e2', '2026-07-13T12:00:00Z', { steps: 200 }),
        makeEntry('e3', '2026-07-13T18:00:00Z', { steps: 300 }),
      ];

      const result = aggregateChartData(entries, numericFields, 'point');

      expect(result.dataPoints).toHaveLength(3);
    });

    it('X 轴按时间升序排列（与卡片/表格 DESC 相反）', () => {
      const entries = [
        makeEntry('e3', '2026-07-15T10:00:00Z', { steps: 300 }),
        makeEntry('e1', '2026-07-13T10:00:00Z', { steps: 100 }),
        makeEntry('e2', '2026-07-14T10:00:00Z', { steps: 200 }),
      ];

      const result = aggregateChartData(entries, numericFields, 'point');

      // 升序：e1 → e2 → e3
      expect(result.dataPoints[0].steps).toBe(100);
      expect(result.dataPoints[1].steps).toBe(200);
      expect(result.dataPoints[2].steps).toBe(300);
    });

    it('缺失数值字段的记录，对应字段为 undefined', () => {
      const entries = [
        makeEntry('e1', '2026-07-13T10:00:00Z', { steps: 100 }), // 没有 weight
      ];

      const result = aggregateChartData(entries, numericFields, 'point');

      expect(result.dataPoints[0].steps).toBe(100);
      expect(result.dataPoints[0].weight).toBeUndefined();
    });
  });

  describe('按天聚合模式（mode=daily）', () => {
    it('同一天多条记录对每个数值字段求和', () => {
      // 两个时间在本地时区同一天（UTC 02:00 和 10:00 → 东八区 10:00 和 18:00，同日）
      const entries = [
        makeEntry('e1', '2026-07-13T02:30:00Z', { steps: 100, weight: 65.5 }),
        makeEntry('e2', '2026-07-13T10:00:00Z', { steps: 200, weight: 66.0 }),
      ];

      const result = aggregateChartData(entries, numericFields, 'daily');

      // 同一天合并为 1 个点
      expect(result.dataPoints).toHaveLength(1);
      // steps 求和：100 + 200 = 300
      expect(result.dataPoints[0].steps).toBe(300);
      // weight 求和：65.5 + 66.0 = 131.5
      expect(result.dataPoints[0].weight).toBeCloseTo(131.5, 1);
    });

    it('X 轴为 MM-DD 格式', () => {
      const entries = [
        makeEntry('e1', '2026-07-13T10:00:00Z', { steps: 100 }),
      ];

      const result = aggregateChartData(entries, numericFields, 'daily');

      expect(result.dataPoints[0].label).toMatch(/^\d{2}-\d{2}$/);
    });

    it('多天数据按日期升序排列', () => {
      const entries = [
        makeEntry('e3', '2026-07-15T10:00:00Z', { steps: 300 }),
        makeEntry('e1', '2026-07-13T10:00:00Z', { steps: 100 }),
        makeEntry('e2', '2026-07-14T10:00:00Z', { steps: 200 }),
      ];

      const result = aggregateChartData(entries, numericFields, 'daily');

      expect(result.dataPoints).toHaveLength(3);
      expect(result.dataPoints[0].steps).toBe(100);
      expect(result.dataPoints[1].steps).toBe(200);
      expect(result.dataPoints[2].steps).toBe(300);
    });

    it('某天某字段全部缺失时，该字段值为 undefined', () => {
      const entries = [
        makeEntry('e1', '2026-07-13T10:00:00Z', { steps: 100 }), // 无 weight
        makeEntry('e2', '2026-07-14T10:00:00Z', { weight: 65.0 }), // 无 steps
      ];

      const result = aggregateChartData(entries, numericFields, 'daily');

      expect(result.dataPoints).toHaveLength(2);
      // 7-13：steps=100, weight=undefined
      expect(result.dataPoints[0].steps).toBe(100);
      expect(result.dataPoints[0].weight).toBeUndefined();
      // 7-14：steps=undefined, weight=65
      expect(result.dataPoints[1].steps).toBeUndefined();
      expect(result.dataPoints[1].weight).toBeCloseTo(65.0, 1);
    });
  });

  describe('通用行为', () => {
    it('空 entries 返回空数据点', () => {
      const result = aggregateChartData([], numericFields, 'point');
      expect(result.dataPoints).toEqual([]);
    });

    it('只含 text 字段时不应纳入聚合（numericFields 为空）', () => {
      const entries = [
        makeEntry('e1', '2026-07-13T10:00:00Z', { note: '跑步' }),
      ];
      // numericFields 为空（类型上不会发生，但应安全处理）
      const result = aggregateChartData(entries, [], 'point');
      expect(result.dataPoints).toEqual([]);
    });

    it('text 字段值不参与聚合（仅数值字段纳入）', () => {
      const allFields: FieldDefinition[] = [...numericFields, textField];
      const entries = [
        makeEntry('e1', '2026-07-13T10:00:00Z', { steps: 100, note: '跑步' }),
      ];

      const result = aggregateChartData(entries, allFields, 'point');

      expect(result.dataPoints[0].steps).toBe(100);
      expect(result.dataPoints[0].note).toBeUndefined(); // text 字段不入图
    });

    it('聚合后返回参与图表的数值字段列表（seriesFields）', () => {
      const entries = [
        makeEntry('e1', '2026-07-13T10:00:00Z', { steps: 100, weight: 65.5, note: 'x' }),
      ];
      const allFields: FieldDefinition[] = [...numericFields, textField];

      const result = aggregateChartData(entries, allFields, 'point');

      expect(result.seriesFields).toHaveLength(2);
      expect(result.seriesFields.map(f => f.field_key)).toEqual(['steps', 'weight']);
    });
  });
});
