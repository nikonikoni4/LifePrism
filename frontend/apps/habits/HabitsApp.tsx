import React from 'react';
import { HabitProvider } from './hooks/useHabitStore';
import { HabitPageProvider } from './context/HabitPageContext';
import { HabitListView } from './components/views/HabitListView/HabitListView';

const HabitsAppContent: React.FC = () => {
    return (
        <div className="h-screen flex flex-col">
            <div className="flex-1 overflow-hidden relative">
                <HabitListView />
            </div>
        </div>
    );
};

export const HabitsApp: React.FC = () => {
    return (
        <HabitProvider>
            <HabitPageProvider>
                <HabitsAppContent />
            </HabitPageProvider>
        </HabitProvider>
    );
};

export default HabitsApp;
