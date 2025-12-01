import React from 'react';
import { TOP_APPS, TOP_WINDOWS } from '../../constants';
import { AppUsage } from '../../types';
import { Monitor, Smartphone } from 'lucide-react';

const ActivityBar: React.FC<{ item: AppUsage; colorClass: string; barColor: string }> = ({ item, colorClass, barColor }) => (
  <div className="mb-5 last:mb-0 group">
    <div className="flex justify-between items-center mb-2">
      <div className="flex items-center gap-3 overflow-hidden">
        {/* Icon */}
        <div className={`w-8 h-8 rounded-lg ${colorClass} bg-opacity-10 flex-shrink-0 flex items-center justify-center text-xs font-bold border border-opacity-20`}>
            {item.name.substring(0, 1)}
        </div>
        <div className="flex flex-col min-w-0">
             <span className="text-sm font-semibold text-slate-700 truncate group-hover:text-blue-600 transition-colors">{item.name}</span>
             <span className="text-xs text-slate-400 font-medium">{item.percentage}% Usage</span>
        </div>
      </div>
      <span className="text-xs font-mono font-bold text-slate-600 bg-gray-50 px-2 py-1 rounded-md border border-gray-100">{item.duration}</span>
    </div>
    <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
      <div 
        className={`h-full rounded-full ${barColor}`} 
        style={{ width: `${item.percentage}%` }}
      ></div>
    </div>
  </div>
);

const ActivityDetailsWidget: React.FC = () => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
      {/* Top Applications */}
      <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
        <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center gap-3">
            <div className="p-2 bg-blue-50 rounded-xl text-morandi-blue">
                <Smartphone size={20} />
            </div>
            Top Applications
        </h3>
        <div className="space-y-1">
          {TOP_APPS.map((app, idx) => (
            <ActivityBar key={idx} item={app} colorClass="bg-morandi-blue text-morandi-blue border-morandi-blue" barColor="bg-morandi-blue" />
          ))}
        </div>
      </div>

      {/* Top Window Titles */}
      <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
         <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center gap-3">
            <div className="p-2 bg-orange-50 rounded-xl text-morandi-orange">
                <Monitor size={20} />
            </div>
            Active Windows
        </h3>
        <div className="space-y-1">
          {TOP_WINDOWS.map((win, idx) => (
            <ActivityBar key={idx} item={win} colorClass="bg-morandi-orange text-morandi-orange border-morandi-orange" barColor="bg-morandi-orange" />
          ))}
        </div>
      </div>
    </div>
  );
};

export default ActivityDetailsWidget;