/**
 * EntryChart — 自定义记录折线图组件
 *
 * 样式参考 frontend/apps/lifewatch/pages/reports/components/TimeDistributionChart.tsx
 * 数据聚合通过 utils/chartAggregator 完成（纯函数已单测覆盖）。
 *
 * 仅数值字段（integer/float）参与折线图；text 字段不显示。
 * 支持两种聚合模式：按数据点 / 按天聚合。
 */
import React, { useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { TrendingUp, LineChart as LineChartIcon } from 'lucide-react';
import type { CustomRecordEntryItem, FieldDefinition } from '../types';
import { aggregateChartData, type AggregateMode } from '../utils/chartAggregator';
import { getFieldHexColor } from '../utils/fieldColors';
import { formatFieldValue } from '../utils/fieldFormatter';

interface EntryChartProps {
  entries: CustomRecordEntryItem[];
  fields: FieldDefinition[];
  /** subtitle 中展示的时间范围描述，如 "2026-07-07 ~ 2026-07-14" */
  timeRangeLabel?: string;
}

/** 自定义 Tooltip — 显示该数据点各字段值 */
const ChartTooltip: React.FC<any> = ({ active, payload, label, seriesFields }: any) => {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="bg-white p-4 border border-gray-100 shadow-xl rounded-2xl text-sm min-w-[160px]">
      <p className="font-bold text-slate-800 mb-2">{label}</p>
      {payload.map((entry: any) => {
        const field = seriesFields.find((f: FieldDefinition) => f.field_key === entry.dataKey);
        const fieldType = field?.field_type;
        const displayValue = entry.value == null
          ? '—'
          : formatFieldValue(entry.value, fieldType);
        return (
          <div key={entry.dataKey} className="flex items-center justify-between gap-4 mb-1 last:mb-0">
            <div className="flex items-center gap-2">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-slate-500 font-medium">{field?.field_name ?? entry.dataKey}</span>
            </div>
            <span className="font-mono font-bold text-slate-700">{displayValue}</span>
          </div>
        );
      })}
    </div>
  );
};

export const EntryChart: React.FC<EntryChartProps> = ({ entries, fields, timeRangeLabel }) => {
  const [mode, setMode] = useState<AggregateMode>('point');
  const [visibleFields, setVisibleFields] = useState<Set<string>>(
    () => new Set(fields.filter(f => f.field_type === 'integer' || f.field_type === 'float').map(f => f.field_key))
  );

  const { dataPoints, seriesFields } = useMemo(
    () => aggregateChartData(entries, fields, mode),
    [entries, fields, mode]
  );

  const toggleField = (key: string) => {
    setVisibleFields(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        // 至少保留一个字段可见
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // 无数值字段
  if (seriesFields.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-cyan-50 text-cyan-500 rounded-xl">
            <TrendingUp size={18} />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-800">趋势图</h3>
            <p className="text-xs text-slate-400 mt-0.5">仅数值字段（整数/浮点数）可绘制</p>
          </div>
        </div>
        <div className="py-16 flex flex-col items-center text-slate-400">
          <LineChartIcon size={36} strokeWidth={1} className="mb-3 opacity-40" />
          <p className="text-sm">当前类型没有数值字段</p>
        </div>
      </div>
    );
  }

  // 有数值字段但当前筛选下无记录
  if (dataPoints.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-cyan-50 text-cyan-500 rounded-xl">
            <TrendingUp size={18} />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-800">趋势图</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {timeRangeLabel ? `当前范围：${timeRangeLabel}` : '暂无数据'}
            </p>
          </div>
        </div>
        <div className="py-16 flex flex-col items-center text-slate-400">
          <LineChartIcon size={36} strokeWidth={1} className="mb-3 opacity-40" />
          <p className="text-sm">所选时间范围内暂无记录</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-50 text-cyan-500 rounded-xl">
            <TrendingUp size={18} />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-800">趋势图</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {timeRangeLabel ? `当前范围：${timeRangeLabel}` : `共 ${dataPoints.length} 个数据点`}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* 模式切换 */}
          <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-xl">
            <button
              onClick={() => setMode('point')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                mode === 'point' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              按数据点
            </button>
            <button
              onClick={() => setMode('daily')}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                mode === 'daily' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              按天聚合
            </button>
          </div>

          {/* 字段可见性 Toggle */}
          <div className="flex flex-wrap gap-2">
            {seriesFields.map(field => {
              const isActive = visibleFields.has(field.field_key);
              const color = getFieldHexColor(field.field_key);
              return (
                <button
                  key={field.field_key}
                  onClick={() => toggleField(field.field_key)}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all flex items-center gap-1.5 ${
                    isActive
                      ? 'bg-white border border-gray-200 shadow-sm'
                      : 'bg-gray-50 border border-transparent opacity-50'
                  }`}
                >
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  {field.field_name}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Chart */}
      <div style={{ height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={dataPoints}
            margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
          >
            <CartesianGrid vertical={false} stroke="#E2E8F0" strokeDasharray="3 3" />
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#94A3B8', fontSize: 11 }}
              height={40}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#94A3B8', fontSize: 11 }}
              tickCount={5}
            />
            <Tooltip
              content={<ChartTooltip seriesFields={seriesFields} />}
            />
            {seriesFields.map(field => (
              visibleFields.has(field.field_key) && (
                <Line
                  key={field.field_key}
                  type="monotone"
                  dataKey={field.field_key}
                  name={field.field_name}
                  stroke={getFieldHexColor(field.field_key)}
                  strokeWidth={2}
                  dot={{ fill: getFieldHexColor(field.field_key), strokeWidth: 0, r: 3 }}
                  activeDot={{ r: 5 }}
                  animationDuration={800}
                  connectNulls
                />
              )
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default EntryChart;
