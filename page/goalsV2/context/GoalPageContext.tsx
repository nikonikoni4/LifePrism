
import React, { createContext, useContext, useState, ReactNode } from 'react';

interface GoalPageContextType {
    selectedGoalId: string | null;
    setSelectedGoalId: (id: string | null) => void;
    selectedPlanDocId: string | null;
    setSelectedPlanDocId: (id: string | null) => void;
    selectedDate: Date;
    setSelectedDate: (date: Date) => void;
}

const GoalPageContext = createContext<GoalPageContextType | undefined>(undefined);

export const GoalPageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);
    const [selectedPlanDocId, setSelectedPlanDocId] = useState<string | null>(null);
    const [selectedDate, setSelectedDate] = useState<Date>(new Date());

    return (
        <GoalPageContext.Provider value={{
            selectedGoalId,
            setSelectedGoalId,
            selectedPlanDocId,
            setSelectedPlanDocId,
            selectedDate,
            setSelectedDate
        }}>
            {children}
        </GoalPageContext.Provider>
    );
};

export const useGoalPageContext = () => {
    const context = useContext(GoalPageContext);
    if (!context) {
        throw new Error("useGoalPageContext must be used within a GoalPageProvider");
    }
    return context;
};
