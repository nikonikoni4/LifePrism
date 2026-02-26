import React from 'react';
import { DualPaneLayout } from '../layout/DualPaneLayout';
import { CalendarView } from '../views/CalendarView/CalendarView';
import { DailyTaskView } from '../views/DailyTaskView/DailyTaskView';

export const CalendarDailyCombo: React.FC = () => {
  return (
    <DualPaneLayout 
      left={<CalendarView />} 
      right={<DailyTaskView />} 
    />
  );
};