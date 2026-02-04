
import React, { useState } from 'react';
import { CapsuleNav } from './components/layout/CapsuleNav';
import { SinglePaneLayout } from './components/layout/SinglePaneLayout';
import { GoalListView } from './components/views/GoalListView/GoalListView';
import { PlanDocListView } from './components/views/PlanDocListView/PlanDocListView';
import { TaskPoolView } from './components/views/TaskPoolView/TaskPoolView';
import { CalendarView } from './components/views/CalendarView/CalendarView';
import { DailyTaskView } from './components/views/DailyTaskView/DailyTaskView';
import { GoalPlanCombo } from './components/combinations/GoalPlanCombo';
import { PlanPoolCombo } from './components/combinations/PlanPoolCombo';
import { PoolCalendarCombo } from './components/combinations/PoolCalendarCombo';
import { CalendarDailyCombo } from './components/combinations/CalendarDailyCombo';
import { ViewMode, ActiveTab } from './types';
import { GoalProvider } from './hooks/useGoalStore';
import { PlanDocProvider } from './hooks/usePlanDocStore';
import { TaskPoolProvider } from './hooks/useTaskPoolStore';
import { GoalPageProvider } from './context/GoalPageContext';

const GoalPageContent: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('dual');
  const [activeTab, setActiveTab] = useState<ActiveTab>('goals');

  const renderContent = () => {
    if (viewMode === 'dual') {
      switch (activeTab) {
        case 'goals': return <GoalPlanCombo />;
        case 'plans': return <PlanPoolCombo />;
        case 'pool': return <PoolCalendarCombo />;
        case 'assign': return <PoolCalendarCombo />;
        case 'daily': return <CalendarDailyCombo />;
        default: return <GoalPlanCombo />;
      }
    } else {
      switch (activeTab) {
        case 'goals': return <SinglePaneLayout><GoalListView /></SinglePaneLayout>;
        case 'plans': return <SinglePaneLayout><PlanDocListView /></SinglePaneLayout>;
        case 'pool': return <SinglePaneLayout><TaskPoolView /></SinglePaneLayout>;
        case 'assign': return <SinglePaneLayout><CalendarView /></SinglePaneLayout>;
        case 'daily': return <SinglePaneLayout><DailyTaskView /></SinglePaneLayout>;
        default: return <SinglePaneLayout><GoalListView /></SinglePaneLayout>;
      }
    }
  };

  return (
    <div className="h-screen flex flex-col aurora-bg text-aurora-text-primary font-body overflow-hidden">
      <div className="pt-4 px-6 pb-2 shrink-0">
        <CapsuleNav
          activeTab={activeTab}
          onTabChange={setActiveTab}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
        />
      </div>
      <div className="flex-1 overflow-hidden relative px-6 pb-6">
        {renderContent()}
      </div>
    </div>
  );
};

export const GoalsApp: React.FC = () => {
  return (
    <GoalProvider>
      <PlanDocProvider>
        <TaskPoolProvider>
          <GoalPageProvider>
            <GoalPageContent />
          </GoalPageProvider>
        </TaskPoolProvider>
      </PlanDocProvider>
    </GoalProvider>
  );
};
