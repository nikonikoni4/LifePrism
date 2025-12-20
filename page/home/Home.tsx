/**
 * Home Page
 * 
 * 首页，使用 /api/v2/activity 接口
 */

import React, { useState, useEffect } from 'react';
import ActivitySummaryHeader from './components/ActivitySummaryHeader';
import ActivityDetailsWidget from './components/ActivityDetailsWidget';
import TodoListWidget from './components/TodoListWidget';
import { TimeOverviewWidget, TimeOverviewData } from '../common';
import { ActivityAPI } from './api';
import { Loader2, AlertCircle } from 'lucide-react';

// 获取今天日期 YYYY-MM-DD 格式
const getTodayDate = (): string => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

const Home: React.FC = () => {
    const [selectedDate, setSelectedDate] = useState(getTodayDate());
    const [refreshKey, setRefreshKey] = useState(0);

    // TimeOverview 数据状态
    const [timeOverviewData, setTimeOverviewData] = useState<TimeOverviewData | null>(null);
    const [timeOverviewLoading, setTimeOverviewLoading] = useState(true);
    const [timeOverviewError, setTimeOverviewError] = useState<string | null>(null);

    // 获取 TimeOverview 数据
    useEffect(() => {
        const fetchTimeOverview = async () => {
            try {
                setTimeOverviewLoading(true);
                setTimeOverviewError(null);
                const response = await ActivityAPI.getStats({
                    date: selectedDate,
                    include: 'time_overview',
                });
                if (response.time_overview) {
                    setTimeOverviewData(response.time_overview as TimeOverviewData);
                }
            } catch (err) {
                console.error('Failed to fetch time overview:', err);
                setTimeOverviewError('Failed to load time overview data');
            } finally {
                setTimeOverviewLoading(false);
            }
        };

        fetchTimeOverview();
    }, [selectedDate, refreshKey]);

    const handleRefresh = () => {
        setRefreshKey(prev => prev + 1);
    };

    // TimeOverview 渲染函数
    const renderTimeOverview = () => {
        if (timeOverviewLoading) {
            return (
                <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 h-full flex items-center justify-center">
                    <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                </div>
            );
        }

        if (timeOverviewError) {
            return (
                <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 h-full flex flex-col items-center justify-center text-red-500 gap-2">
                    <AlertCircle className="w-8 h-8" />
                    <p>{timeOverviewError}</p>
                    <button
                        onClick={handleRefresh}
                        className="px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors text-sm font-medium"
                    >
                        Retry
                    </button>
                </div>
            );
        }

        if (!timeOverviewData) return null;

        return <TimeOverviewWidget data={timeOverviewData} />;
    };

    return (
        <div className="max-w-7xl mx-auto">
            {/* Page Header */}
            <header className="mb-6">
                <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome to LifeWatchAI</h1>
                <p className="text-slate-500 mt-1 font-medium">愿此行, 终抵群星</p>
            </header>

            {/* Activity Summary Header */}
            <ActivitySummaryHeader
                key={refreshKey}
                selectedDate={selectedDate}
                onDateChange={setSelectedDate}
                onRefresh={handleRefresh}
            />

            {/* Bento Grid Layout */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8">

                {/* Row 1: TodoList (5 columns) + Time Overview (7 columns) */}
                <div className="col-span-1 md:col-span-5 h-[700px]">
                    <TodoListWidget
                        key={`todolist-${refreshKey}`}
                        selectedDate={selectedDate}
                    />
                </div>

                <div className="col-span-1 md:col-span-7 h-[700px]">
                    {renderTimeOverview()}
                </div>

                {/* Row 2: Activity Details (Full Width) */}
                <div className="col-span-1 md:col-span-12 h-auto">
                    <ActivityDetailsWidget
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

export default Home;
