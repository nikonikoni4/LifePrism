/**
 * Time Overview Widget V2
 * 
 * 时间概览组件（旭日图 + 柱状图），使用 V2 API
 */
import React, { useState, useEffect, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  Tooltip,
  YAxis,
  CartesianGrid
} from 'recharts';
import { Loader2, AlertCircle, RotateCcw } from 'lucide-react';
import { TimeOverviewDataV2, ChartSegmentV2 } from '../types';
import { ActivityAPIV2 } from '../api';

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-4 border border-gray-100 shadow-xl rounded-2xl text-sm z-50">
        <p className="font-bold text-slate-800 mb-2">{label ? `${label}:00` : payload[0].name}</p>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center justify-between gap-4 mb-1 last:mb-0">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }}></div>
              <span className="text-slate-500 capitalize font-medium">{entry.name}</span>
            </div>
            <span className="font-mono font-bold text-slate-700">{entry.value}m</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

// Helper to transform data for Sunburst recursively
const transformDataToSunburst = (data: TimeOverviewDataV2): any[] => {
  if (!data || !data.pieData) return [];

  return data.pieData.map((segment: ChartSegmentV2) => {
    const childData = data.details?.[segment.name];
    const children = childData ? transformDataToSunburst(childData) : undefined;

    return {
      name: segment.name,
      value: segment.value,
      itemStyle: { color: segment.color },
      // Custom payload to identify the node and its associated data
      // If childData exists, clicking this node should show the child's details (bar chart)
      dataRef: childData,
      // Keep the title for app layer tooltip
      appTitle: segment.title,
      children: children
    };
  });
};

interface TimeOverviewWidgetV2Props {
  selectedDate: string;
  initialData?: TimeOverviewDataV2;
}

const TimeOverviewWidgetV2: React.FC<TimeOverviewWidgetV2Props> = ({ selectedDate, initialData }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rootData, setRootData] = useState<TimeOverviewDataV2 | null>(null);
  const [selectedView, setSelectedView] = useState<TimeOverviewDataV2 | null>(null);
  const [chartKey, setChartKey] = useState(0); // Key to force re-render of chart

  useEffect(() => {
    if (initialData) {
      setRootData(initialData);
      setSelectedView(initialData);
      setLoading(false);
      return;
    }
    fetchData();
  }, [selectedDate, initialData]);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await ActivityAPIV2.getStats({
        date: selectedDate,
        include: 'time_overview',
      });
      if (response.time_overview) {
        setRootData(response.time_overview);
        setSelectedView(response.time_overview);
      }
    } catch (err) {
      console.error('Failed to fetch time overview:', err);
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const sunburstOption = useMemo(() => {
    if (!rootData) return {};

    const data = transformDataToSunburst(rootData);

    return {
      tooltip: {
        trigger: 'item',
        formatter: function (params: any) {
          const name = params.name;
          const value = params.value;
          const hours = (value / 60).toFixed(2);
          const total = rootData?.totalTrackedMinutes || 1;
          const percent = ((value / total) * 100).toFixed(1);

          // 检查是否是 app 层（有 appTitle）
          const appTitle = params.data?.appTitle;
          if (appTitle) {
            // 将 -split- 分隔的 titles 换行显示
            const titles = appTitle.split('-split-').map((t: string) =>
              `<div style="color: #666; font-size: 11px; padding: 2px 0; max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">• ${t}</div>`
            ).join('');
            return `<div style="max-width: 280px;">
              <strong>${name}</strong>: ${hours}h (${percent}%)<br/>
              <div style="color: #999; font-size: 10px; margin-top: 4px;">Top Titles:</div>
              ${titles}
            </div>`;
          }

          return `${name}: ${hours}h (${percent}%)`;
        }
      },
      series: [
        {
          type: 'sunburst',
          data: data,
          radius: ['15%', '90%'],
          label: {
            rotate: 'radial',
            minAngle: 10, // Hide labels for small slices
            fontSize: 10,
            formatter: function (param: any) {
              const name = param.name;
              if (!name) return '';
              return name.length > 5 ? name.slice(0, 5) + '...' : name;
            }
          },
          itemStyle: {
            borderRadius: 4,
            borderWidth: 2,
            borderColor: '#fff'
          },
          emphasis: {
            focus: 'ancestor'
          }
        }
      ]
    };
  }, [rootData]);

  const onChartClick = (params: any) => {
    const { data } = params;
    // data.dataRef contains the TimeOverviewDataV2 for this node (if it has children/details)
    if (data && data.dataRef) {
      setSelectedView(data.dataRef);
    }
    // If leaf node (no dataRef), do nothing as per requirements
  };

  const handleReset = () => {
    setSelectedView(rootData);
    setChartKey(prev => prev + 1); // Force chart re-render to reset visual state
  };

  if (loading && !rootData) {
    return (
      <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 h-full flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 h-full flex flex-col items-center justify-center text-red-500 gap-2">
        <AlertCircle className="w-8 h-8" />
        <p>{error}</p>
        <button
          onClick={fetchData}
          className="px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors text-sm font-medium"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!selectedView || !rootData) return null;

  const { title, subTitle, barKeys, barData } = selectedView;
  const hours = Math.floor(selectedView.totalTrackedMinutes / 60);
  const isRoot = selectedView === rootData;

  return (
    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 h-full flex flex-col transition-all duration-300">
      <div className="flex justify-between items-center mb-8">
        <div className="flex items-center gap-3">
          <button
            onClick={handleReset}
            disabled={isRoot}
            className={`p-2 -ml-2 rounded-xl transition-colors ${isRoot
              ? 'text-slate-200 cursor-not-allowed'
              : 'hover:bg-gray-50 text-slate-400 hover:text-slate-700'
              }`}
            title="Reset to Overview"
          >
            <RotateCcw size={20} />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight animate-fade-in">{title}</h2>
            <p className="text-slate-500 text-sm mt-1 font-medium">{subTitle}</p>
          </div>
        </div>

        {/* Dynamic Legend */}
        <div className="flex flex-wrap gap-2 bg-gray-50 p-1.5 rounded-xl border border-gray-100 max-w-[50%]">
          {barKeys.map((item) => {
            return (
              <div key={item.key} className="flex-shrink-0 flex items-center gap-1.5 px-2 py-1 bg-white rounded-lg shadow-sm border border-gray-100">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }}></div>
                <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide whitespace-nowrap">{item.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex flex-col gap-8 flex-1 min-h-0"> {/* Layout: Changed to vertical flex-col */}

        {/* Sunburst Chart */}
        {/* Adjust height here: h-[400px] */}
        <div className="w-full h-[400px] relative flex flex-col items-center justify-center bg-gray-50/50 rounded-2xl border border-dashed border-gray-200 p-4">
          <div className="w-full h-full relative isolate">
            {/* Center Text - Z-0 (Behind) */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-0">
              {/* Adjust font size here: text-3xl */}
              <span className="text-2xl font-bold text-slate-800 font-mono tracking-tighter">{hours}h</span>
              {/* <span className="text-xs text-slate-400 font-bold uppercase tracking-widest mt-1">Tracked</span> */}
            </div>

            {/* Chart - Z-10 (On Top) */}
            <div className="absolute inset-0 z-10">
              <ReactECharts
                key={chartKey}
                option={sunburstOption}
                style={{ height: '100%', width: '100%' }}
                onEvents={{
                  click: onChartClick
                }}
              />
            </div>
          </div>

          <p className="absolute bottom-4 text-[10px] text-slate-300 font-medium italic">Click slices to drill down</p>
        </div>

        {/* Stacked Bar Chart */}
        {/* Adjust height here: h-[200px] */}
        <div className="w-full h-[200px] pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 10, right: 0, left: -25, bottom: 0 }} barSize={36}>
              <CartesianGrid vertical={false} stroke="#E2E8F0" strokeDasharray="3 3" />
              <XAxis
                dataKey="timeRange"
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#94A3B8', fontSize: 11, fontWeight: 500 }}
                dy={10}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#94A3B8', fontSize: 11 }}
                tickCount={5}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: '#F1F5F9', radius: 8 }} />

              {/* Dynamically render bars based on current configuration */}
              {barKeys.map((barItem, index) => (
                <Bar
                  key={barItem.key}
                  dataKey={barItem.key}
                  stackId="a"
                  fill={barItem.color}
                  radius={index === barKeys.length - 1 ? [8, 8, 0, 0] : [0, 0, 0, 0]}
                  animationDuration={800}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default TimeOverviewWidgetV2;
