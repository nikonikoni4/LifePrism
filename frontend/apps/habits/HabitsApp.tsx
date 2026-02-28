import React, { useEffect } from 'react';
import { HabitLayout } from './components/layout/HabitLayout';

// Store Providers
import { HabitProvider, useHabitStore } from './hooks/useHabitStore';
import { ChainProvider, useChainStore } from './hooks/useChainStore';
import { TimelineProvider } from './hooks/useTimelineStore';

// View Components
import { TodayDashboard } from './components/views/overview/TodayDashboard';
import { Heatmap } from './components/views/overview/Heatmap';
import { TrendsChart } from './components/views/overview/TrendsChart';
import { TimelineView } from './components/views/timeline/TimelineView';
import { HabitChainList } from './components/views/chains/HabitChainList';
import { HabitList } from './components/views/habits/HabitList';

const HabitsAppContent: React.FC = () => {
    const { fetchHabits } = useHabitStore();
    const { fetchChains } = useChainStore();

    useEffect(() => {
        // Initial data fetch
        fetchHabits();
        fetchChains();
    }, [fetchHabits, fetchChains]);

    return (
        <HabitLayout>
            {/* 1. TOP OVERVIEW (Modular Cards Grid) */}
            <div className="w-full shrink-0 grid grid-cols-1 md:grid-cols-3 gap-3 pb-0">
                <TodayDashboard />
                <Heatmap />
                <TrendsChart />
            </div>

            {/* Main Content Area */}
            <div className="flex-1 grid grid-cols-12 gap-3 min-h-0 overflow-hidden">
                {/* 2. LEFT SIDEBAR - Timeline */}
                <TimelineView />

                {/* 3. MIDDLE COLUMN - Activity Chains */}
                <HabitChainList />

                {/* 4. RIGHT CONTENT AREA - Active Habits */}
                <HabitList />
            </div>
        </HabitLayout>
    );
};

export const HabitsApp: React.FC = () => {
    return (
        <ChainProvider>
            <HabitProvider>
                <TimelineProvider>
                    <HabitsAppContent />
                </TimelineProvider>
            </HabitProvider>
        </ChainProvider>
    );
};

export default HabitsApp;
