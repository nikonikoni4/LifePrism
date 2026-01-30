import React from 'react';
import { DualPaneLayout } from '../layout/DualPaneLayout';
import { PlanDocListView } from '../views/PlanDocListView/PlanDocListView';
import { TaskPoolView } from '../views/TaskPoolView/TaskPoolView';

export const PlanPoolCombo: React.FC = () => {
  return (
    <DualPaneLayout 
      left={<PlanDocListView />} 
      right={<TaskPoolView />} 
    />
  );
};