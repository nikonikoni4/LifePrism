/**
 * Home V2 Page
 * 
 * 新版首页，使用 /api/v2/activity 接口
 */

import React, { useState } from 'react';
import ActivitySummaryHeaderV2 from './components/ActivitySummaryHeaderV2';
import ActivityDetailsWidgetV2 from './components/ActivityDetailsWidgetV2';
import TodoListWidgetV2 from './components/TodoListWidgetV2';

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
        <div className="space-y-6 animate-fade-in">
            {/* Page Header */}
            <div className="mb-6">
                <h1 className="text-3xl font-bold text-slate-900">Home V2 (Testing)</h1>
                <p className="text-slate-500 mt-1">使用新版 /api/v2 接口的首页测试版本</p>
            </div>

            {/* Activity Summary Header - 使用 V2 API */}
            <ActivitySummaryHeaderV2
                key={refreshKey}
                selectedDate={selectedDate}
                onDateChange={setSelectedDate}
                onRefresh={handleRefresh}
            />

            {/* TodoList & Time Overview */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* TodoList Widget - 使用 V2 API */}
                <TodoListWidgetV2
                    key={`todolist-${refreshKey}`}
                    selectedDate={selectedDate}
                />

                {/* Time Overview Placeholder */}
                <div className="bg-white rounded-3xl p-6 shadow-sm border border-gray-100">
                    <h3 className="text-lg font-semibold text-slate-700 mb-4">Time Overview V2</h3>
                    <p className="text-slate-400 text-sm">组件开发中...</p>
                </div>
            </div>

            {/* Top Apps & Top Titles - 使用 V2 API */}
            <ActivityDetailsWidgetV2
                key={`details-${refreshKey}`}
                selectedDate={selectedDate}
            />
        </div>
    );
};

export default HomeV2;
