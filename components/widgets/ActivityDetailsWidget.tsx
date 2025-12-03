import React, { useEffect, useState } from 'react';
import { DashboardAPI } from '../../services/dashboardService';
import { TopItem } from '../../types';
import { Monitor, Smartphone } from 'lucide-react';

// Helper to format duration seconds to string
const formatDuration = (seconds: number): string => {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes === 0 ? `${hours}h` : `${hours}h ${remainingMinutes}m`;
};

const ActivityBar: React.FC<{ item: TopItem; colorClass: string; barColor: string }> = ({ item, colorClass, barColor }) => (
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
      <span className="text-xs font-mono font-bold text-slate-600 bg-gray-50 px-2 py-1 rounded-md border border-gray-100">
        {formatDuration(item.duration)}
      </span>
    </div>
    <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full ${barColor}`}
        style={{ width: `${item.percentage}%` }}
      ></div>
    </div>
  </div>
);

const ActivityDetailsWidget: React.FC<{ selectedDate: string }> = ({ selectedDate }) => {
  const [topApps, setTopApps] = useState<TopItem[]>([]);
  const [topWindows, setTopWindows] = useState<TopItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const data = await DashboardAPI.getDashboardData(selectedDate);
        setTopApps(data.summary.top_apps);
        setTopWindows(data.summary.top_titles);
      } catch (error) {
        console.error('Failed to load activity details:', error);
        // Fallback to empty or handle error UI
        setTopApps([]);
        setTopWindows([]);
      } finally {
        setLoading(false);
      }
    };

    if (selectedDate) {
      fetchData();
    }
  }, [selectedDate]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full animate-pulse">
        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 h-64"></div>
        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 h-64"></div>
      </div>
    );
  }

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
          {topApps.length > 0 ? (
            topApps.map((app, idx) => (
              <ActivityBar key={idx} item={app} colorClass="bg-morandi-blue text-morandi-blue border-morandi-blue" barColor="bg-morandi-blue" />
            ))
          ) : (
            <div className="text-center text-slate-400 py-8">No application data available</div>
          )}
        </div>
      </div>

      {/* Top Title */}
      <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
        <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center gap-3">
          <div className="p-2 bg-orange-50 rounded-xl text-morandi-orange">
            <Monitor size={20} />
          </div>
          Top Title
        </h3>
        <div className="space-y-1">
          {topWindows.length > 0 ? (
            topWindows.map((win, idx) => (
              <ActivityBar key={idx} item={win} colorClass="bg-morandi-orange text-morandi-orange border-morandi-orange" barColor="bg-morandi-orange" />
            ))
          ) : (
            <div className="text-center text-slate-400 py-8">No window title data available</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ActivityDetailsWidget;