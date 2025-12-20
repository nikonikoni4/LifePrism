
import React, { useState } from 'react';
import {
   PieChart,
   Pie,
   Cell,
   ResponsiveContainer,
   BarChart,
   Bar,
   XAxis,
   YAxis,
   Tooltip,
   CartesianGrid,
   Legend
} from 'recharts';
import { CreditCard, Info, DollarSign, Database, TrendingUp } from 'lucide-react';
import { MOCK_USAGE_HISTORY } from '../../constants';

const UsagePage: React.FC = () => {
   const [inputRate, setInputRate] = useState<number>(0.0001); // Rate per 1k
   const [outputRate, setOutputRate] = useState<number>(0.0004); // Rate per 1k

   const todayUsage = MOCK_USAGE_HISTORY[MOCK_USAGE_HISTORY.length - 1];
   const totalTokensToday = todayUsage.inputTokens + todayUsage.outputTokens;

   const todayCost = (
      (todayUsage.inputTokens / 1000) * inputRate +
      (todayUsage.outputTokens / 1000) * outputRate
   ).toFixed(4);

   const pieData = [
      { name: 'Input Tokens', value: todayUsage.inputTokens, color: '#5B8FF9' },
      { name: 'Output Tokens', value: todayUsage.outputTokens, color: '#FA8C16' }
   ];

   const avgTokensPerRecord = Math.round(totalTokensToday / todayUsage.processedRecords);
   const avgCostPerRecord = (parseFloat(todayCost) / todayUsage.processedRecords).toFixed(5);

   const chartData = MOCK_USAGE_HISTORY.map(item => ({
      ...item,
      cost: ((item.inputTokens / 1000) * inputRate + (item.outputTokens / 1000) * outputRate).toFixed(3)
   }));

   const CustomTooltip = ({ active, payload, label }: any) => {
      if (active && payload && payload.length) {
         return (
            <div className="bg-white p-4 border border-gray-100 shadow-xl rounded-2xl text-sm">
               <p className="font-bold text-slate-800 mb-2">{label}</p>
               {payload.map((entry: any, index: number) => (
                  <div key={index} className="flex items-center justify-between gap-4 mb-1 last:mb-0">
                     <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }}></div>
                        <span className="text-slate-500 font-medium">{entry.name}</span>
                     </div>
                     <span className="font-mono font-bold text-slate-700">
                        {entry.name === 'Cost' ? `$${entry.value}` : entry.value}
                     </span>
                  </div>
               ))}
            </div>
         );
      }
      return null;
   };

   return (
      <div className="max-w-7xl mx-auto space-y-8 animate-fade-in">
         <header className="mb-8">
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">API Usage & Billing</h1>
            <p className="text-slate-500 mt-1 font-medium">Monitor your Gemini API consumption and project costs.</p>
         </header>

         <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

            {/* Today's Usage Overview */}
            <div className="col-span-1 lg:col-span-8 bg-white rounded-3xl shadow-sm border border-gray-100 p-8 flex flex-col md:flex-row gap-8">
               <div className="flex-1">
                  <div className="flex justify-between items-start mb-6">
                     <div>
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Today's Usage</span>
                        <h2 className="text-4xl font-mono font-bold text-slate-800 mt-1">
                           {(totalTokensToday / 1000).toFixed(1)}k
                        </h2>
                     </div>
                     <div className="p-3 bg-blue-50 text-morandi-blue rounded-2xl border border-blue-100">
                        <CreditCard size={24} />
                     </div>
                  </div>

                  <div className="space-y-4">
                     <div>
                        <label className="text-xs font-bold text-slate-500 mb-2 block">Input Token Rate (per 1k)</label>
                        <div className="relative">
                           <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"><DollarSign size={14} /></div>
                           <input
                              type="number"
                              step="0.00001"
                              value={inputRate}
                              onChange={(e) => setInputRate(parseFloat(e.target.value) || 0)}
                              className="w-full pl-8 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-mono focus:ring-2 focus:ring-blue-100 focus:outline-none"
                           />
                        </div>
                     </div>
                     <div>
                        <label className="text-xs font-bold text-slate-500 mb-2 block">Output Token Rate (per 1k)</label>
                        <div className="relative">
                           <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"><DollarSign size={14} /></div>
                           <input
                              type="number"
                              step="0.00001"
                              value={outputRate}
                              onChange={(e) => setOutputRate(parseFloat(e.target.value) || 0)}
                              className="w-full pl-8 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-mono focus:ring-2 focus:ring-blue-100 focus:outline-none"
                           />
                        </div>
                     </div>
                     <div className="pt-4 border-t border-dashed border-gray-100">
                        <div className="flex justify-between items-end">
                           <span className="text-sm font-bold text-slate-500">Estimated Today:</span>
                           <span className="text-3xl font-mono font-bold text-morandi-orange">${todayCost}</span>
                        </div>
                     </div>
                  </div>
               </div>

               {/* Donut Chart */}
               <div className="w-full md:w-64 h-64 relative flex flex-col items-center justify-center bg-gray-50/50 rounded-2xl border border-dashed border-gray-200 p-4">
                  <ResponsiveContainer width="100%" height="100%">
                     <PieChart>
                        <Pie
                           data={pieData}
                           innerRadius={55}
                           outerRadius={75}
                           paddingAngle={8}
                           dataKey="value"
                           stroke="none"
                           cornerRadius={10}
                        >
                           {pieData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                           ))}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                     </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                     <span className="text-xl font-bold text-slate-700">Tokens</span>
                     <span className="text-[10px] text-slate-400 font-bold uppercase">Split</span>
                  </div>
                  <div className="flex gap-4 mt-2">
                     {pieData.map(item => (
                        <div key={item.name} className="flex items-center gap-1.5">
                           <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }}></div>
                           <span className="text-[10px] font-bold text-slate-500 uppercase">{item.name.split(' ')[0]}</span>
                        </div>
                     ))}
                  </div>
               </div>
            </div>

            {/* Data Efficiency Stats */}
            <div className="col-span-1 lg:col-span-4 bg-white rounded-3xl shadow-sm border border-gray-100 p-8 flex flex-col">
               <div className="flex items-center gap-3 mb-6">
                  <div className="p-2 bg-purple-50 text-purple-600 rounded-xl">
                     <Database size={20} />
                  </div>
                  <h3 className="text-lg font-bold text-slate-800">Data Processing</h3>
               </div>

               <div className="flex-1 space-y-8">
                  <div>
                     <p className="text-sm font-medium text-slate-400 mb-1">Records Processed Today</p>
                     <p className="text-3xl font-mono font-bold text-slate-800">{todayUsage.processedRecords}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                     <div className="p-4 bg-gray-50 rounded-2xl border border-gray-100">
                        <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Avg Tokens</p>
                        <p className="text-lg font-mono font-bold text-slate-700">{avgTokensPerRecord}</p>
                        <p className="text-[10px] text-slate-400 font-medium">per record</p>
                     </div>
                     <div className="p-4 bg-gray-50 rounded-2xl border border-gray-100">
                        <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Avg Cost</p>
                        <p className="text-lg font-mono font-bold text-slate-700">${avgCostPerRecord}</p>
                        <p className="text-[10px] text-slate-400 font-medium">per record</p>
                     </div>
                  </div>

                  <div className="mt-auto pt-6 border-t border-gray-100">
                     <div className="flex items-start gap-3 text-amber-600 bg-amber-50 p-4 rounded-2xl border border-amber-100">
                        <Info size={16} className="mt-0.5 flex-shrink-0" />
                        <p className="text-xs font-medium leading-relaxed">
                           Lowering the average tokens per record will directly reduce your monthly billing. Consider optimizing prompts.
                        </p>
                     </div>
                  </div>
               </div>
            </div>

            {/* Usage Timeline Chart */}
            <div className="col-span-1 lg:col-span-12 bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
               <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                  <div>
                     <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                        <TrendingUp size={20} className="text-morandi-blue" />
                        Historical Token Consumption
                     </h3>
                     <p className="text-sm text-slate-500 font-medium mt-1">7-day rolling window of Gemini API activity.</p>
                  </div>
                  <div className="flex gap-2">
                     <div className="px-3 py-1.5 bg-gray-50 border border-gray-100 rounded-lg flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-morandi-blue"></div>
                        <span className="text-[10px] font-bold text-slate-600 uppercase">Input</span>
                     </div>
                     <div className="px-3 py-1.5 bg-gray-50 border border-gray-100 rounded-lg flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-morandi-orange"></div>
                        <span className="text-[10px] font-bold text-slate-600 uppercase">Output</span>
                     </div>
                  </div>
               </div>

               <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                     <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <CartesianGrid vertical={false} stroke="#E2E8F0" strokeDasharray="3 3" />
                        <XAxis
                           dataKey="date"
                           axisLine={false}
                           tickLine={false}
                           tick={{ fill: '#94A3B8', fontSize: 11, fontWeight: 600 }}
                           dy={10}
                        />
                        <YAxis
                           yAxisId="left"
                           axisLine={false}
                           tickLine={false}
                           tick={{ fill: '#94A3B8', fontSize: 11 }}
                        />
                        <YAxis
                           yAxisId="right"
                           orientation="right"
                           axisLine={false}
                           tickLine={false}
                           tick={{ fill: '#FA8C16', fontSize: 11 }}
                           unit="$"
                        />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#F1F5F9', radius: 8 }} />
                        <Bar
                           yAxisId="left"
                           dataKey="inputTokens"
                           name="Input Tokens"
                           stackId="a"
                           fill="#5B8FF9"
                           radius={[0, 0, 0, 0]}
                           barSize={40}
                        />
                        <Bar
                           yAxisId="left"
                           dataKey="outputTokens"
                           name="Output Tokens"
                           stackId="a"
                           fill="#FA8C16"
                           radius={[8, 8, 0, 0]}
                           barSize={40}
                        />
                        <Bar
                           yAxisId="right"
                           dataKey="cost"
                           name="Cost"
                           fill="transparent"
                           barSize={0} // Invisible bar just for tooltip/right axis scaling
                        />
                     </BarChart>
                  </ResponsiveContainer>
               </div>
            </div>

         </div>
      </div>
   );
};

export default UsagePage;
