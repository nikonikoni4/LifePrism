/**
 * TimeOverviewWidget - Pure Display Component
 * 
 * 时间概览组件（旭日图）
 * 纯展示组件，只接收数据 props，不负责数据获取
 */
import React, { useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { RotateCcw } from 'lucide-react';
import { TimeOverviewData, ChartSegment } from '../types';


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
    /** 可选的类名 */
    className?: string;
}

const TimeOverviewWidget: React.FC<TimeOverviewWidgetProps> = ({
    data,
    chartHeight = 'h-[400px]',
    className = ''
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

    const { title, subTitle } = selectedView;
    const hours = Math.floor(selectedView.totalTrackedMinutes / 60);
    const isRoot = selectedView === data;

    return (
        <div className={`bg-white rounded-3xl shadow-sm border border-gray-100 p-8 flex flex-col transition-all duration-300 ${className}`}>
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

            </div>

            <div className="flex-1 min-h-0">
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
            </div>
        </div>
    );
};

export default TimeOverviewWidget;
