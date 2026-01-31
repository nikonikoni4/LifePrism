import React, { createContext, useContext, useState, ReactNode } from 'react';

interface HabitPageContextType {
  selectedHabitId: string | null;
  setSelectedHabitId: (id: string | null) => void;
  selectedDate: Date;
  setSelectedDate: (date: Date) => void;
  filterHabitId: string | null;  // For heatmap filtering
  setFilterHabitId: (id: string | null) => void;
}

const HabitPageContext = createContext<HabitPageContextType | undefined>(undefined);

export const HabitPageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [selectedHabitId, setSelectedHabitId] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [filterHabitId, setFilterHabitId] = useState<string | null>(null);

  return (
    <HabitPageContext.Provider value={{
      selectedHabitId,
      setSelectedHabitId,
      selectedDate,
      setSelectedDate,
      filterHabitId,
      setFilterHabitId
    }}>
      {children}
    </HabitPageContext.Provider>
  );
};

export const useHabitPageContext = () => {
  const context = useContext(HabitPageContext);
  if (!context) {
    throw new Error('useHabitPageContext must be used within a HabitPageProvider');
  }
  return context;
};
