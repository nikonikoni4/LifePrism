import React, { useEffect, useState } from 'react';
import { HabitLayout } from './components/layout/HabitLayout';

// Store Providers
import { HabitProvider, useHabitStore } from './hooks/useHabitStore';
import { ChainProvider, useChainStore } from './hooks/useChainStore';
import { TimelineProvider } from './hooks/useTimelineStore';
import { SettlementProvider, useSettlementStore } from './hooks/useSettlementStore';
import { StatsProvider, useStatsStore } from './hooks/useStatsStore';
import { MindspaceProvider } from './hooks/useMindspaceStore';

// View Components
import { TodayDashboard } from './components/views/overview/TodayDashboard';
import { DailyTips } from './components/views/overview/DailyTips';
import { Heatmap } from './components/views/overview/Heatmap';
import { TrendsChart } from './components/views/overview/TrendsChart';
import { TimelineView } from './components/views/timeline/TimelineView';
import { HabitChainList } from './components/views/chains/HabitChainList';
import { HabitList } from './components/views/habits/HabitList';
import { SettlementDialog } from './components/dialogs/SettlementDialog';
import { ToastProvider } from './components/shared/Toast';
import { useUserInfo } from '../../core/context/UserInfoContext';

const HabitsAppContent: React.FC = () => {
    const { fetchHabits } = useHabitStore();
    const { fetchChains } = useChainStore();
    const { checkSettlements } = useSettlementStore();
    const { fetchAllStats } = useStatsStore();
    const { userName, refreshUserName } = useUserInfo();
    const [now, setNow] = useState(() => new Date());
    const weekDays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
    const currentDateText = `${now.getMonth() + 1}月${now.getDate()}日，${weekDays[now.getDay()]}`;

    useEffect(() => {
        void refreshUserName();
        fetchHabits();
        fetchChains();
        checkSettlements();
        fetchAllStats();
    }, [fetchHabits, fetchChains, checkSettlements, fetchAllStats, refreshUserName]);

    useEffect(() => {
        const timer = window.setInterval(() => setNow(new Date()), 60 * 1000);
        return () => window.clearInterval(timer);
    }, []);

    return (
        <HabitLayout>
            <SettlementDialog />

            {/* 1. GLOBAL HEADER */}
            <div className="w-full shrink-0 flex items-center px-2 mb-1 mt-1">
                <div>
                    <h1 className="text-[30px] sm:text-[34px] font-extrabold text-slate-900 tracking-[-0.02em] leading-[1.05] mb-1">Morning, {userName}</h1>
                    <p className="text-[14px] font-semibold text-slate-500 tracking-[0.01em]">{currentDateText}</p>
                </div>
            </div>

            {/* 2. TOP OVERVIEW (Bento Box Layout) */}
            <div className="w-full shrink-0 rounded-[28px] bg-emerald-50/55 border border-emerald-100/80 p-3 sm:p-4">
                <div className="w-full flex flex-col lg:flex-row gap-3 pb-0">
                    <DailyTips />

                    {/* Right Area - Stacked Panels */}
                    <div className="w-full lg:w-9/12 flex flex-col gap-3">
                        <TodayDashboard />

                        {/* Bottom Row: Charts (Split) */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 flex-1 min-h-[140px]">
                            <Heatmap />
                            <TrendsChart />
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="w-full rounded-[28px] bg-sky-50/45 border border-sky-100/80 p-3 sm:p-4">
                <div className="grid grid-cols-12 gap-3 flex-shrink-0 w-full h-[600px] xl:h-[600px]">
                    <TimelineView />
                    <HabitChainList />
                    <HabitList />
                </div>
            </div>
        </HabitLayout>
    );
};

/** 桥接组件：在 SettlementProvider 内部获取 pushSettlement，传给 HabitProvider */
const HabitWithSettlementBridge: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { pushSettlement } = useSettlementStore();
    const { fetchAllStats } = useStatsStore();
    return (
        <HabitProvider onSettlement={pushSettlement} onCheckInChange={fetchAllStats}>
            {children}
        </HabitProvider>
    );
};

export const HabitsApp: React.FC = () => {
    return (
        <ToastProvider>
            <ChainProvider>
                <SettlementProvider>
                    <StatsProvider>
                        <MindspaceProvider>
                            <HabitWithSettlementBridge>
                                <TimelineProvider>
                                    <HabitsAppContent />
                                </TimelineProvider>
                            </HabitWithSettlementBridge>
                        </MindspaceProvider>
                    </StatsProvider>
                </SettlementProvider>
            </ChainProvider>
        </ToastProvider>
    );
};

export default HabitsApp;
