import React, { useEffect } from 'react';
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

const HabitsAppContent: React.FC = () => {
    const { fetchHabits } = useHabitStore();
    const { fetchChains } = useChainStore();
    const { checkSettlements } = useSettlementStore();
    const { fetchAllStats } = useStatsStore();

    useEffect(() => {
        fetchHabits();
        fetchChains();
        checkSettlements();
        fetchAllStats();
    }, [fetchHabits, fetchChains, checkSettlements, fetchAllStats]);

    return (
        <HabitLayout>
            <SettlementDialog />

            {/* 1. GLOBAL HEADER */}
            <div className="w-full shrink-0 flex items-center justify-between px-2 mb-1 mt-1">
                <div>
                    <h1 className="text-[28px] font-black text-neutral-900 tracking-tight leading-none mb-1">Morning, Nico</h1>
                    <p className="text-[13px] font-bold text-neutral-400">Oct 24, 星期四</p>
                </div>
                <button className="flex items-center gap-1.5 bg-neutral-900 text-white px-5 py-2.5 rounded-[14px] text-[13px] font-bold shadow-md shadow-neutral-900/20 hover:bg-neutral-800 hover:-translate-y-0.5 transition-all active:scale-95">
                    <span className="text-lg leading-none mb-[2px]">+</span> 新建习惯
                </button>
            </div>

            {/* 2. TOP OVERVIEW (Bento Box Layout) */}
            <div className="w-full shrink-0 flex flex-col lg:flex-row gap-3 pb-0">
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

            {/* Main Content Area */}
            <div className="grid grid-cols-12 gap-3 flex-shrink-0 w-full h-[600px] xl:h-[600px]">
                <TimelineView />
                <HabitChainList />
                <HabitList />
            </div>
        </HabitLayout>
    );
};

/** 桥接组件：在 SettlementProvider 内部获取 pushSettlement，传给 HabitProvider */
const HabitWithSettlementBridge: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { pushSettlement } = useSettlementStore();
    const { fetchTodayOverview } = useStatsStore();
    return (
        <HabitProvider onSettlement={pushSettlement} onCheckInChange={fetchTodayOverview}>
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
