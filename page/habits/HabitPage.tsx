import React from 'react';
import { HabitProvider } from './hooks/useHabitStore';
import { HabitPageProvider } from './context/HabitPageContext';
import { HabitListView } from './components/views/HabitListView/HabitListView';

const HabitPageContent: React.FC = () => {
  return (
    <div className="h-screen flex flex-col">
      <div className="flex-1 overflow-hidden relative">
        <HabitListView />
      </div>
    </div>
  );
};

export const HabitPage: React.FC = () => {
  return (
    <HabitProvider>
      <HabitPageProvider>
        <HabitPageContent />
      </HabitPageProvider>
    </HabitProvider>
  );
};

export default HabitPage;
