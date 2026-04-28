/**
 * Home Page
 * 
 * 首页，使用 /api/v2/activity 接口
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ActivitySummaryHeader from './components/ActivitySummaryHeader';
import ActivityDetailsWidget from './components/ActivityDetailsWidget';
import TodoListWidget from './components/TodoListWidget';
import { TimeOverviewWidget, TimeOverviewData } from '../../../../core/components';
import { ActivityAPI } from './api';
import { Loader2, AlertCircle } from 'lucide-react';

interface HomeProps { }

// 获取今天日期 YYYY-MM-DD 格式
const getTodayDate = (): string => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

// 缓存键名
const CACHE_KEY = 'homepage_last_update_date_v1';

// 更新时间边界（使用本地系统时间）
const UPDATE_BOUNDARY_HOUR = 4;

// 获取当前时间是否 >= 4:00
const isAfter4AM = (): boolean => {
    const now = new Date();
    const hours = now.getHours();
    return hours >= UPDATE_BOUNDARY_HOUR;
};

// 获取"有效日期"（4点之前算前一天，使用本地系统时间）
const getEffectiveDate = (): string => {
    const now = new Date();
    if (now.getHours() < UPDATE_BOUNDARY_HOUR) {
        // 4点之前，算前一天
        now.setDate(now.getDate() - 1);
    }
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

// 判断是否需要自动更新
const shouldAutoUpdate = (): boolean => {
    // 条件1：当前时间 >= 4:00
    if (!isAfter4AM()) {
        console.log(`⏸️ [Home] 当前时间未到4点，跳过自动更新`);
        return false;
    }

    // 条件2：今天没有更新过
    try {
        const lastUpdate = localStorage.getItem(CACHE_KEY);
        const effectiveDate = getEffectiveDate();
        if (lastUpdate === effectiveDate) {
            console.log(`⏸️ [Home] 今日已更新过（${effectiveDate}），跳过自动更新`);
            return false;
        }
    } catch (error) {
        console.warn(`⚠️ [Home] localStorage 读取失败，允许更新:`, error);
        // Fail open: 缓存检查失败时允许更新
    }

    console.log(`✅ [Home] 满足自动更新条件（时间>=4点 且 今日未更新）`);
    return true;
};

// 记录更新日期
const recordUpdateDate = (): void => {
    try {
        const effectiveDate = getEffectiveDate();
        localStorage.setItem(CACHE_KEY, effectiveDate);
        console.log(`📝 [Home] 记录更新日期: ${effectiveDate}`);
    } catch (error) {
        console.warn(`⚠️ [Home] localStorage 写入失败:`, error);
        // 写入失败不影响功能，仅记录警告
    }
};

const Home: React.FC<HomeProps> = () => {
    const navigate = useNavigate();
    const [selectedDate, setSelectedDate] = useState(getTodayDate());
    const [refreshKey, setRefreshKey] = useState(0);

    // 统一的数据状态
    const [homepageData, setHomepageData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // 判断是否在 Electron 环境（生产环境）
    const isElectron = typeof window !== 'undefined' && window.electronAPI !== undefined;

    // 记录组件挂载时间
    const [mountTime] = useState(() => {
        const time = performance.now();
        console.log(`⏱️ [Home] 组件开始渲染: ${new Date().toLocaleTimeString()}`);
        console.log(`🔧 [Home] 运行环境: ${isElectron ? 'Electron (生产)' : '浏览器 (开发)'}`);
        return time;
    });

    // 统一获取首页所有数据
    useEffect(() => {
        // 开发环境（浏览器）下不自动加载，需要手动刷新
        if (!isElectron && refreshKey === 0) {
            console.log(`⏸️ [Home] 开发环境下跳过自动加载，请手动刷新`);
            setLoading(false);
            return;
        }

        // 生产环境：判断是否需要记录自动更新
        const shouldRecordUpdate = isElectron && refreshKey === 0 && shouldAutoUpdate();

        const fetchHomepageData = async () => {
            const fetchStart = performance.now();
            console.log(`📡 [Home] 开始请求数据...`);

            try {
                setLoading(true);
                setError(null);
                const response = await ActivityAPI.getHomepageData(selectedDate, 15, 14);

                // 诊断日志：检查 time_overview 数据
                console.log(`🔍 [Home] 完整响应数据:`, response);
                console.log(`🔍 [Home] time_overview 存在:`, !!response?.time_overview);
                console.log(`🔍 [Home] time_overview 内容:`, response?.time_overview);

                setHomepageData(response);

                const fetchEnd = performance.now();
                console.log(`✅ [Home] 数据加载完成: ${(fetchEnd - fetchStart).toFixed(0)}ms (API 请求)`);
                console.log(`✅ [Home] 总渲染时间: ${(fetchEnd - mountTime).toFixed(0)}ms (从组件挂载到数据就绪)`);

                // 只有在满足自动更新条件时才记录更新日期
                if (shouldRecordUpdate) {
                    recordUpdateDate();
                }
            } catch (err) {
                console.error('Failed to fetch homepage data:', err);
                setError('Failed to load homepage data');
            } finally {
                setLoading(false);
            }
        };

        fetchHomepageData();
    }, [selectedDate, refreshKey, mountTime, isElectron]);

    const handleRefresh = () => {
        setRefreshKey(prev => prev + 1);
    };

    // 加载状态
    if (loading) {
        return (
            <div className="max-w-7xl mx-auto">
                <header className="mb-6">
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome to LifePrism</h1>
                    <p className="text-slate-500 mt-1 font-medium">Refract Your Day, Reflect Your Life</p>
                </header>
                <div className="flex items-center justify-center h-96">
                    <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
                </div>
            </div>
        );
    }

    // 开发环境未加载数据状态
    if (!isElectron && !homepageData) {
        return (
            <div className="max-w-7xl mx-auto">
                <header className="mb-6">
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome to LifePrism</h1>
                    <p className="text-slate-500 mt-1 font-medium">Refract Your Day, Reflect Your Life</p>
                </header>
                <div className="flex flex-col items-center justify-center h-96 gap-4">
                    <div className="text-slate-400 text-center">
                        <p className="text-lg font-semibold mb-2">开发环境：数据未加载</p>
                        <p className="text-sm">点击下方按钮手动加载数据</p>
                    </div>
                    <button
                        onClick={handleRefresh}
                        className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors font-medium"
                    >
                        加载数据
                    </button>
                </div>
            </div>
        );
    }

    // 错误状态
    if (error) {
        return (
            <div className="max-w-7xl mx-auto">
                <header className="mb-6">
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome to LifePrism</h1>
                    <p className="text-slate-500 mt-1 font-medium">Refract Your Day, Reflect Your Life</p>
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
                <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Welcome to LifePrism</h1>
                <p className="text-slate-500 mt-1 font-medium">Refract Your Day, Reflect Your Life</p>
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
                        onNavigateToGoals={() => navigate('/goals')}
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
                <p className="text-slate-400 text-sm font-medium">© 2024 LifePrism. Crafted with Gemini.</p>
            </div>
        </div>
    );
};

export default Home;
