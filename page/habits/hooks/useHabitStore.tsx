import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { Habit, HabitStats, HeatmapData, HabitCheckIn, CreateHabitForm } from '../types';
import { habitApi } from '../api';

interface HabitStoreContextType {
  // State
  habits: Habit[];
  stats: HabitStats | null;
  heatmapData: HeatmapData[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchHabits: () => Promise<void>;
  fetchStats: () => Promise<void>;
  fetchHeatmap: (habitId?: string) => Promise<void>;
  addHabit: (data: CreateHabitForm) => Promise<Habit>;
  updateHabit: (id: string, data: Partial<Habit>) => Promise<void>;
  deleteHabit: (id: string) => Promise<void>;
  checkIn: (habitId: string, date: string, note?: string) => Promise<HabitCheckIn>;
  uncheckIn: (habitId: string, date: string) => Promise<void>;
  pauseHabit: (id: string) => Promise<void>;
  resumeHabit: (id: string) => Promise<void>;
  archiveHabit: (id: string) => Promise<void>;
}

const HabitStoreContext = createContext<HabitStoreContextType | undefined>(undefined);

export const HabitProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [habits, setHabits] = useState<Habit[]>([]);
  const [stats, setStats] = useState<HabitStats | null>(null);
  const [heatmapData, setHeatmapData] = useState<HeatmapData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch habits
  const fetchHabits = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await habitApi.getHabits();
      setHabits(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取习惯列表失败');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const data = await habitApi.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  }, []);

  // Fetch heatmap
  const fetchHeatmap = useCallback(async (habitId?: string) => {
    try {
      const data = await habitApi.getHeatmap(habitId);
      setHeatmapData(data);
    } catch (err) {
      console.error('Failed to fetch heatmap:', err);
    }
  }, []);

  // Add habit
  const addHabit = useCallback(async (data: CreateHabitForm): Promise<Habit> => {
    const newHabit = await habitApi.createHabit(data);
    setHabits(prev => [...prev, newHabit]);
    // Refresh stats
    fetchStats();
    return newHabit;
  }, [fetchStats]);

  // Update habit
  const updateHabit = useCallback(async (id: string, data: Partial<Habit>) => {
    const updated = await habitApi.updateHabit(id, data);
    setHabits(prev => prev.map(h => h.id === id ? updated : h));
  }, []);

  // Delete habit
  const deleteHabit = useCallback(async (id: string) => {
    await habitApi.deleteHabit(id);
    setHabits(prev => prev.filter(h => h.id !== id));
    fetchStats();
  }, [fetchStats]);

  // Check in
  const checkIn = useCallback(async (habitId: string, date: string, note?: string): Promise<HabitCheckIn> => {
    const checkInRecord = await habitApi.checkIn(habitId, date, note);

    // Update habit's challenge progress if exists
    setHabits(prev => prev.map(h => {
      if (h.id === habitId && h.currentChallenge) {
        return {
          ...h,
          currentChallenge: {
            ...h.currentChallenge,
            completedCount: h.currentChallenge.completedCount + 1
          }
        };
      }
      return h;
    }));

    // Refresh stats and heatmap
    fetchStats();
    fetchHeatmap();

    return checkInRecord;
  }, [fetchStats, fetchHeatmap]);

  // Uncheck in
  const uncheckIn = useCallback(async (habitId: string, date: string) => {
    await habitApi.uncheckIn(habitId, date);

    // Update habit's challenge progress if exists
    setHabits(prev => prev.map(h => {
      if (h.id === habitId && h.currentChallenge && h.currentChallenge.completedCount > 0) {
        return {
          ...h,
          currentChallenge: {
            ...h.currentChallenge,
            completedCount: h.currentChallenge.completedCount - 1
          }
        };
      }
      return h;
    }));

    fetchStats();
    fetchHeatmap();
  }, [fetchStats, fetchHeatmap]);

  // Pause habit
  const pauseHabit = useCallback(async (id: string) => {
    const updated = await habitApi.pauseHabit(id);
    setHabits(prev => prev.map(h => h.id === id ? updated : h));
    fetchStats();
  }, [fetchStats]);

  // Resume habit
  const resumeHabit = useCallback(async (id: string) => {
    const updated = await habitApi.resumeHabit(id);
    setHabits(prev => prev.map(h => h.id === id ? updated : h));
    fetchStats();
  }, [fetchStats]);

  // Archive habit
  const archiveHabit = useCallback(async (id: string) => {
    const updated = await habitApi.archiveHabit(id);
    setHabits(prev => prev.map(h => h.id === id ? updated : h));
    fetchStats();
  }, [fetchStats]);

  // Initial fetch
  useEffect(() => {
    fetchHabits();
    fetchStats();
    fetchHeatmap();
  }, [fetchHabits, fetchStats, fetchHeatmap]);

  return (
    <HabitStoreContext.Provider value={{
      habits,
      stats,
      heatmapData,
      isLoading,
      error,
      fetchHabits,
      fetchStats,
      fetchHeatmap,
      addHabit,
      updateHabit,
      deleteHabit,
      checkIn,
      uncheckIn,
      pauseHabit,
      resumeHabit,
      archiveHabit
    }}>
      {children}
    </HabitStoreContext.Provider>
  );
};

export const useHabitStore = () => {
  const context = useContext(HabitStoreContext);
  if (!context) {
    throw new Error('useHabitStore must be used within a HabitProvider');
  }
  return context;
};
