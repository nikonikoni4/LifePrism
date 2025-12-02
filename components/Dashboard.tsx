
import React from 'react';
import GoalsWidget from './widgets/GoalsWidget';
import TimeOverviewWidget from './widgets/TimeOverviewWidget';
import ActivityDetailsWidget from './widgets/ActivityDetailsWidget';
import ActivitySummaryHeader from './ActivitySummaryHeader';

const Dashboard: React.FC = () => {
  const [selectedDate, setSelectedDate] = React.useState(new Date().toISOString().split('T')[0]);

  return (
    <div className="max-w-7xl mx-auto">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome back, Alex</h1>
        <p className="text-slate-500 mt-1 font-medium">Here's what's happening today.</p>
      </header>

      {/* New Activity Summary Header */}
      <ActivitySummaryHeader selectedDate={selectedDate} onDateChange={setSelectedDate} />

      {/* Bento Grid Layout */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-8">

        {/* Row 1: Goals & Identity (33%) + Time Overview Charts (66%) */}
        <div className="col-span-1 md:col-span-4 h-[500px]">
          <GoalsWidget selectedDate={selectedDate} />
        </div>

        <div className="col-span-1 md:col-span-8 h-[500px]">
          <TimeOverviewWidget selectedDate={selectedDate} />
        </div>

        {/* Row 2: Activity Details (Full Width) */}
        <div className="col-span-1 md:col-span-12 h-auto">
          <ActivityDetailsWidget selectedDate={selectedDate} />
        </div>

      </div>

      <div className="mt-16 text-center border-t border-gray-200 pt-8 pb-4">
        <p className="text-slate-400 text-sm font-medium">© 2024 LifeWatchAI. Crafted with Gemini.</p>
      </div>
    </div>
  );
};

export default Dashboard;
