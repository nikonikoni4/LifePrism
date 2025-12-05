
import React, { useEffect, useState } from 'react';
import GoalsWidget from './widgets/GoalsWidget';
import TimeOverviewWidget from './widgets/TimeOverviewWidget';
import ActivityDetailsWidget from './widgets/ActivityDetailsWidget';
import ActivitySummaryHeader from './ActivitySummaryHeader';
import { DashboardAPI } from '../services/dashboardService';
import { HomepageResponse } from '../types';

const Dashboard: React.FC = () => {
  const [selectedDate, setSelectedDate] = React.useState(() => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  });

  const [homepageData, setHomepageData] = useState<HomepageResponse | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasLoaded = React.useRef(false);

  // Fetch all homepage data in one API call
  const fetchHomepageData = React.useCallback(async () => {
    // Only show full loading state on initial mount
    if (!hasLoaded.current) {
      setIsInitialLoading(true);
    } else {
      // For subsequent updates, just set updating flag
      setIsUpdating(true);
    }
    setError(null);

    try {
      const data = await DashboardAPI.getHomepageData(selectedDate, 15, 14);
      setHomepageData(data);
      hasLoaded.current = true;
    } catch (err) {
      console.error('Failed to fetch homepage data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load homepage data');
    } finally {
      setIsInitialLoading(false);
      setIsUpdating(false);
    }
  }, [selectedDate]);

  useEffect(() => {
    fetchHomepageData();
  }, [fetchHomepageData]);

  // Only show full loading screen on initial load
  if (isInitialLoading && homepageData === null) {
    return (
      <div className="max-w-7xl mx-auto flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-morandi-blue mx-auto"></div>
          <p className="mt-4 text-gray-500">加载首页数据...</p>
        </div>
      </div>
    );
  }

  if (error && !homepageData) {
    return (
      <div className="max-w-7xl mx-auto flex items-center justify-center h-screen">
        <div className="text-center text-red-500">
          <p className="text-xl font-bold">加载失败</p>
          <p className="mt-2">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-6 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  // This should never happen, but just in case
  if (!homepageData) {
    return null;
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Subtle loading indicator when updating data */}
      {isUpdating && (
        <div className="fixed top-0 left-0 right-0 z-50">
          <div className="h-1 bg-morandi-blue animate-pulse"></div>
        </div>
      )}

      <header className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome back, Alex</h1>
        <p className="text-slate-500 mt-1 font-medium">Here's what's happening today.</p>
      </header>

      {/* New Activity Summary Header - pass data as props */}
      <ActivitySummaryHeader
        selectedDate={selectedDate}
        onDateChange={setSelectedDate}
        activitySummaryData={homepageData.activity_summary}
        onRefresh={fetchHomepageData}
      />

      {/* Bento Grid Layout */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-8">

        {/* Row 1: Goals & Identity (33%) + Time Overview Charts (66%) */}
        <div className="col-span-1 md:col-span-4 h-[500px]">
          <GoalsWidget selectedDate={selectedDate} />
        </div>

        <div className="col-span-1 md:col-span-12 h-[600px]">
          {/* Pass initial time overview data as props */}
          <TimeOverviewWidget
            selectedDate={selectedDate}
            initialData={homepageData.time_overview}
          />
        </div>

        {/* Row 2: Activity Details (Full Width) */}
        <div className="col-span-1 md:col-span-12 h-auto">
          {/* Pass dashboard data as props */}
          <ActivityDetailsWidget
            selectedDate={selectedDate}
            dashboardData={homepageData.dashboard}
          />
        </div>

      </div>

      <div className="mt-16 text-center border-t border-gray-200 pt-8 pb-4">
        <p className="text-slate-400 text-sm font-medium">© 2024 LifeWatchAI. Crafted with Gemini.</p>
      </div>
    </div>
  );
};

export default Dashboard;
