/**
 * Home V2 Page
 * 
 * 新版首页，使用 /api/v2/activity 接口
 */

import React, { useState } from 'react';
import ActivitySummaryHeaderV2 from './components/ActivitySummaryHeaderV2';
import ActivityDetailsWidgetV2 from './components/ActivityDetailsWidgetV2';
import TodoListWidgetV2 from './components/TodoListWidgetV2';
import TimeOverviewWidgetV2 from './components/TimeOverviewWidgetV2';

// 获取今天日期 YYYY-MM-DD 格式
const getTodayDate = (): string => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

const HomeV2: React.FC = () => {
    const [selectedDate, setSelectedDate] = useState(getTodayDate());
    const [refreshKey, setRefreshKey] = useState(0);

    const handleRefresh = () => {
        setRefreshKey(prev => prev + 1);
    };

    return (
        <div className="max-w-7xl mx-auto">
            {/* Page Header */}
            <header className="mb-6">
                <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Home V2 (Testing)</h1>
                <p className="text-slate-500 mt-1 font-medium">使用新版 /api/v2 接口的首页测试版本</p>
            </header>

            {/* Activity Summary Header - 使用 V2 API */}
            <ActivitySummaryHeaderV2
                key={refreshKey}
                selectedDate={selectedDate}
                onDateChange={setSelectedDate}
                onRefresh={handleRefresh}
            />

            {/* Bento Grid Layout */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8">

                {/* Row 1: TodoList (5 columns) + Time Overview (7 columns) */}
                <div className="col-span-1 md:col-span-5 h-[700px]">
                    <TodoListWidgetV2
                        key={`todolist-${refreshKey}`}
                        selectedDate={selectedDate}
                    />
                </div>

                <div className="col-span-1 md:col-span-7 h-[700px]">
                    <TimeOverviewWidgetV2
                        key={`timeoverview-${refreshKey}`}
                        selectedDate={selectedDate}
                    />
                </div>

                {/* Row 2: Activity Details (Full Width) */}
                <div className="col-span-1 md:col-span-12 h-auto">
                    <ActivityDetailsWidgetV2
                        key={`details-${refreshKey}`}
                        selectedDate={selectedDate}
                    />
                </div>

            </div>

            <div className="mt-16 text-center border-t border-gray-200 pt-8 pb-4">
                <p className="text-slate-400 text-sm font-medium">© 2024 LifeWatchAI. Crafted with Gemini.</p>
            </div>
        </div>
    );
};

export default HomeV2;

