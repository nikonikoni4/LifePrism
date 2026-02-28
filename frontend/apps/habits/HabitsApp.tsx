import React, { useEffect } from 'react';
import { HabitLayout } from './components/layout/HabitLayout';

// Store Providers
import { HabitProvider, useHabitStore } from './hooks/useHabitStore';
import { ChainProvider, useChainStore } from './hooks/useChainStore';
import { TimelineProvider } from './hooks/useTimelineStore';
import { SettlementProvider, useSettlementStore } from './hooks/useSettlementStore';
import { StatsProvider, useStatsStore } from './hooks/useStatsStore';

// View Components
import { TodayDashboard } from './components/views/overview/TodayDashboard';
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

            {/* 1. TOP OVERVIEW (Modular Cards Grid) */}
            <div className="w-full shrink-0 grid grid-cols-1 md:grid-cols-3 gap-3 pb-0">
                <TodayDashboard />
                <Heatmap />
                <TrendsChart />
            </div>

            {/* Main Content Area */}
            <div className="flex-1 grid grid-cols-12 gap-3 min-h-0 overflow-hidden">
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
                        <HabitWithSettlementBridge>
                            <TimelineProvider>
                                <HabitsAppContent />
                            </TimelineProvider>
                        </HabitWithSettlementBridge>
                    </StatsProvider>
                </SettlementProvider>
            </ChainProvider>
        </ToastProvider>
    );
};

export default HabitsApp;
