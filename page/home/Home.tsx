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

interface HomeProps {
    onNavigate?: (page: string) => void;
}

// 获取今天日期 YYYY-MM-DD 格式
const getTodayDate = (): string => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

const Home: React.FC<HomeProps> = ({ onNavigate }) => {
    const [selectedDate, setSelectedDate] = useState(getTodayDate());
    const [refreshKey, setRefreshKey] = useState(0);

    // 统一的数据状态
    const [homepageData, setHomepageData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // 记录组件挂载时间
    const [mountTime] = useState(() => {
        const time = performance.now();
        console.log(`⏱️ [Home] 组件开始渲染: ${new Date().toLocaleTimeString()}`);
        return time;
    });

    // 统一获取首页所有数据
    useEffect(() => {
        const fetchHomepageData = async () => {
            const fetchStart = performance.now();
            console.log(`📡 [Home] 开始请求数据...`);

            try {
                setLoading(true);
                setError(null);
                const response = await ActivityAPI.getHomepageData(selectedDate, 15, 14);
                setHomepageData(response);

                const fetchEnd = performance.now();
                console.log(`✅ [Home] 数据加载完成: ${(fetchEnd - fetchStart).toFixed(0)}ms (API 请求)`);
                console.log(`✅ [Home] 总渲染时间: ${(fetchEnd - mountTime).toFixed(0)}ms (从组件挂载到数据就绪)`);
            } catch (err) {
                console.error('Failed to fetch homepage data:', err);
                setError('Failed to load homepage data');
            } finally {
                setLoading(false);
            }
        };

        fetchHomepageData();
    }, [selectedDate, refreshKey, mountTime]);

    const handleRefresh = () => {
        setRefreshKey(prev => prev + 1);
    };

    // 加载状态
    if (loading) {
        return (
            <div className="max-w-7xl mx-auto">
                <header className="mb-6">
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome to LifeWatchAI</h1>
                    <p className="text-slate-500 mt-1 font-medium">愿此行, 终抵群星</p>
                </header>
                <div className="flex items-center justify-center h-96">
                    <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
                </div>
            </div>
        );
    }

    // 错误状态
    if (error) {
        return (
            <div className="max-w-7xl mx-auto">
                <header className="mb-6">
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome to LifeWatchAI</h1>
                    <p className="text-slate-500 mt-1 font-medium">愿此行, 终抵群星</p>
                </header>
                <div className="flex flex-col items-center justify-center h-96 text-red-500 gap-4">
                    <AlertCircle className="w-12 h-12" />
                    <p className="text-lg font-semibold">{error}</p>
                    <button
                        onClick={handleRefresh}
                        className="px-6 py-3 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors font-medium"
                    >
                        Retry
                    </button>
                </div>
            </div>
        );
    }

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
                activitySummaryData={homepageData?.activity_summary}
            />

            {/* Bento Grid Layout */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8">

                {/* Row 1: TodoList (5 columns) + Time Overview (7 columns) */}
                <div className="col-span-1 md:col-span-5 h-[700px]">
                    <TodoListWidget
                        key={`todolist-${refreshKey}`}
                        selectedDate={selectedDate}
                        todolist={homepageData?.todolist}
                        onNavigateToGoals={() => onNavigate?.('goals')}
                    />
                </div>

                <div className="col-span-1 md:col-span-7 h-[700px]">
                    {homepageData?.time_overview ? (
                        <TimeOverviewWidget data={homepageData.time_overview as TimeOverviewData} />
                    ) : (
                        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 h-full flex items-center justify-center text-slate-400">
                            No time overview data available
                        </div>
                    )}
                </div>

                {/* Row 2: Activity Details (Full Width) */}
                <div className="col-span-1 md:col-span-12 h-auto">
                    <ActivityDetailsWidget
                        key={`details-${refreshKey}`}
                        selectedDate={selectedDate}
                        topApps={homepageData?.top_app}
                        topTitles={homepageData?.top_title}
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
