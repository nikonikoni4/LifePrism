/**
 * TimeOverviewWidget - Pure Display Component
 * 
 * 时间概览组件（旭日图 + 柱状图）
 * 纯展示组件，只接收数据 props，不负责数据获取
 */
import React, { useState, useMemo } from 'react';
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
import { RotateCcw } from 'lucide-react';
import { TimeOverviewData, ChartSegment } from '../types/common-components';

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
const transformDataToSunburst = (data: TimeOverviewData): any[] => {
    if (!data || !data.pieData) return [];

    return data.pieData.map((segment: ChartSegment) => {
        const childData = data.details?.[segment.name];
        const children = childData ? transformDataToSunburst(childData) : undefined;

        return {
            name: segment.name,
            value: segment.value,
            itemStyle: { color: segment.color },
            dataRef: childData,
            appTitle: segment.title,
            children: children
        };
    });
};

export interface TimeOverviewWidgetProps {
    /** 完整的时间概览数据 */
    data: TimeOverviewData;
    /** 可选的高度类名，默认使用内置高度 */
    chartHeight?: string;
}

const TimeOverviewWidget: React.FC<TimeOverviewWidgetProps> = ({
    data,
    chartHeight = 'h-[400px]'
}) => {
    const [selectedView, setSelectedView] = useState<TimeOverviewData>(data);
    const [chartKey, setChartKey] = useState(0);

    // 当 data 变化时重置视图
    React.useEffect(() => {
        setSelectedView(data);
    }, [data]);

    const sunburstOption = useMemo(() => {
        if (!data) return {};

        const sunburstData = transformDataToSunburst(data);

        return {
            tooltip: {
                trigger: 'item',
                formatter: function (params: any) {
                    const name = params.name;
                    const value = params.value;
                    const hours = (value / 60).toFixed(2);
                    // 使用 totalRangeMinutes 作为分母（如果存在），否则使用 totalTrackedMinutes
                    const total = data?.totalRangeMinutes || data?.totalTrackedMinutes || 1;
                    const percent = ((value / total) * 100).toFixed(1);

                    const appTitle = params.data?.appTitle;
                    if (appTitle) {
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
                    data: sunburstData,
                    radius: ['15%', '90%'],
                    label: {
                        rotate: 'radial',
                        minAngle: 10,
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
    }, [data]);

    const onChartClick = (params: any) => {
        const { data: clickedData } = params;
        if (clickedData && clickedData.dataRef) {
            setSelectedView(clickedData.dataRef);
        }
    };

    const handleReset = () => {
        setSelectedView(data);
        setChartKey(prev => prev + 1);
    };

    if (!data) return null;

    const { title, subTitle, barKeys, barData } = selectedView;
    const hours = Math.floor(selectedView.totalTrackedMinutes / 60);
    const isRoot = selectedView === data;

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
                    {barKeys.map((item) => (
                        <div key={item.key} className="flex-shrink-0 flex items-center gap-1.5 px-2 py-1 bg-white rounded-lg shadow-sm border border-gray-100">
                            <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }}></div>
                            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide whitespace-nowrap">{item.label}</span>
                        </div>
                    ))}
                </div>
            </div>

            <div className="flex flex-col gap-8 flex-1 min-h-0">
                {/* Sunburst Chart */}
                <div className={`w-full ${chartHeight} relative flex flex-col items-center justify-center bg-gray-50/50 rounded-2xl border border-dashed border-gray-200 p-4`}>
                    <div className="w-full h-full relative isolate">
                        {/* Center Text */}
                        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-0">
                            <span className="text-2xl font-bold text-slate-800 font-mono tracking-tighter">{hours}h</span>
                        </div>

                        {/* Chart */}
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
                <div className="w-full h-[200px] pt-2">
                    <ResponsiveContainer width="100%" height="100%" minWidth={100} minHeight={100}>
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

                            {barKeys.map((barItem, index) => (
                                <Bar
                                    key={barItem.key}
                                    dataKey={barItem.key}
                                    name={barItem.label}
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

export default TimeOverviewWidget;
