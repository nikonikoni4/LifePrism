
import React, { useState } from 'react';
import { 
  PieChart, 
  Pie, 
  Cell, 
  ResponsiveContainer, 
  BarChart, 
  Bar, 
  XAxis, 
  Tooltip,
  YAxis,
  CartesianGrid
} from 'recharts';
import { PIE_DATA, BAR_DATA, COLORS, DRILLDOWN_DATA } from '../../constants';
import { ChevronLeft } from 'lucide-react';

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

const TimeOverviewWidget: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // Determine which data to show
  const activeDrilldown = selectedCategory ? DRILLDOWN_DATA[selectedCategory] : null;

  const currentPieData = activeDrilldown ? activeDrilldown.pieData : PIE_DATA;
  const currentBarData = activeDrilldown ? activeDrilldown.barData : BAR_DATA;

  // Configuration for the Bar Chart bars
  const defaultBarKeys = [
    { key: 'work', color: COLORS.WORK, label: 'Work' },
    { key: 'entertainment', color: COLORS.ENTERTAINMENT, label: 'Ent' },
    { key: 'other', color: COLORS.OTHER, label: 'Other' }
  ];

  const currentBarKeys = activeDrilldown ? activeDrilldown.barKeys : defaultBarKeys;
  const title = activeDrilldown ? activeDrilldown.title : "Time Overview";
  const subTitle = activeDrilldown ? "Detailed breakdown & timeline" : "Activity breakdown & timeline";

  const totalMinutes = currentPieData.reduce((acc, curr) => acc + curr.value, 0);
  const hours = Math.floor(totalMinutes / 60);

  const handlePieClick = (data: any) => {
    if (!selectedCategory && data.key && DRILLDOWN_DATA[data.key]) {
      setSelectedCategory(data.key);
    }
  };

  const handleBack = () => {
    setSelectedCategory(null);
  };

  return (
    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 h-full flex flex-col transition-all duration-300">
      <div className="flex justify-between items-center mb-8">
        <div className="flex items-center gap-3">
            {selectedCategory && (
                <button 
                    onClick={handleBack}
                    className="p-2 -ml-2 rounded-xl hover:bg-gray-50 text-slate-400 hover:text-slate-700 transition-colors"
                >
                    <ChevronLeft size={24} />
                </button>
            )}
            <div>
                <h2 className="text-2xl font-bold text-slate-900 tracking-tight animate-fade-in">{title}</h2>
                <p className="text-slate-500 text-sm mt-1 font-medium">{subTitle}</p>
            </div>
        </div>
        
        {/* Dynamic Legend */}
        <div className="flex gap-2 bg-gray-50 p-1.5 rounded-xl border border-gray-100 overflow-x-auto no-scrollbar max-w-[50%]">
             {currentBarKeys.map((item) => {
                 return (
                    <div key={item.key} className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-white rounded-lg shadow-sm border border-gray-100">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }}></div> 
                        <span className="text-xs font-bold text-slate-600 uppercase tracking-wide whitespace-nowrap">{item.label}</span>
                    </div>
                 );
             })}
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-8 flex-1 min-h-0">
        
        {/* Donut Chart */}
        <div className="w-full lg:w-1/3 h-64 lg:h-auto relative flex flex-col items-center justify-center bg-gray-50/50 rounded-2xl border border-dashed border-gray-200 p-4">
            <div className="w-full h-48 relative isolate">
                {/* Center Text - Z-0 (Behind) */}
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-0">
                    <span className="text-5xl font-bold text-slate-800 font-mono tracking-tighter">{hours}h</span>
                    <span className="text-xs text-slate-400 font-bold uppercase tracking-widest mt-1">Tracked</span>
                </div>

                {/* Chart - Z-10 (On Top) */}
                <div className="absolute inset-0 z-10">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={currentPieData}
                                innerRadius={65}
                                outerRadius={85}
                                paddingAngle={4}
                                dataKey="value"
                                stroke="none"
                                cornerRadius={6}
                                onClick={handlePieClick}
                                className={!selectedCategory ? "cursor-pointer" : ""}
                            >
                                {currentPieData.map((entry, index) => (
                                    <Cell 
                                        key={`cell-${index}`} 
                                        fill={entry.color} 
                                        className={`transition-all duration-300 ${!selectedCategory ? 'hover:opacity-80' : ''}`}
                                    />
                                ))}
                            </Pie>
                            <Tooltip content={<CustomTooltip />} />
                        </PieChart>
                    </ResponsiveContainer>
                </div>
            </div>
            
            {/* Legend underneath */}
            <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 mt-4 pb-2 relative z-20">
                 {currentPieData.map((item, idx) => (
                     <div key={idx} className="text-center min-w-[60px]">
                         <p className="text-lg font-bold text-slate-700">{Math.round((item.value/totalMinutes)*100)}%</p>
                         <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider truncate max-w-[80px]">{item.name}</p>
                     </div>
                 ))}
            </div>
            {!selectedCategory && (
                <p className="absolute bottom-4 text-[10px] text-slate-300 font-medium italic">Click slice to drill down</p>
            )}
        </div>

        {/* Stacked Bar Chart */}
        <div className="w-full lg:w-2/3 h-64 lg:h-auto pt-2">
             <ResponsiveContainer width="100%" height="100%">
                <BarChart data={currentBarData} margin={{ top: 10, right: 0, left: -25, bottom: 0 }} barSize={36}>
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
                    {currentBarKeys.map((barItem, index) => (
                        <Bar 
                            key={barItem.key}
                            dataKey={barItem.key} 
                            stackId="a" 
                            fill={barItem.color} 
                            radius={index === currentBarKeys.length - 1 ? [8, 8, 0, 0] : [0, 0, 0, 0]}
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
