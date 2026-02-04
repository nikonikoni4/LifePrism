import React from 'react';
import { DualPaneLayout } from '../layout/DualPaneLayout';
import { GoalListView } from '../views/GoalListView/GoalListView';
import { PlanDocListView } from '../views/PlanDocListView/PlanDocListView';

export const GoalPlanCombo: React.FC = () => {
  return (
    <DualPaneLayout 
      left={<GoalListView />} 
      right={<PlanDocListView />} 
    />
  );
};