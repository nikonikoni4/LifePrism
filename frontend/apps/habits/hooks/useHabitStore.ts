import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Habit } from '../types/entities';
import { habitApi } from '../apis/habit';
import { checkinApi } from '../apis/checkin';
import { CreateHabitRequest, UpdateHabitRequest, SettlementItem } from '../types/backend';
import { format } from 'date-fns';

interface HabitStoreContextType {
    activeHabits: Habit[];
    pausedHabits: Habit[];
    isLoading: boolean;
    error: string | null;

    fetchHabits: () => Promise<void>;
    createHabit: (request: CreateHabitRequest) => Promise<void>;
    updateHabit: (habitId: string, request: UpdateHabitRequest) => Promise<void>;
    deleteHabit: (habitId: string) => Promise<void>;
    pauseHabit: (habitId: string) => Promise<void>;
    resumeHabit: (habitId: string) => Promise<void>;

    checkIn: (habitId: string) => Promise<void>;
    undoCheckIn: (habitId: string) => Promise<void>;
}

const HabitStoreContext = createContext<HabitStoreContextType | undefined>(undefined);

interface HabitProviderProps {
    children: ReactNode;
    onSettlement?: (item: SettlementItem) => void;
    onCheckInChange?: () => void;
}

export const HabitProvider: React.FC<HabitProviderProps> = ({ children, onSettlement, onCheckInChange }) => {
    const [activeHabits, setActiveHabits] = useState<Habit[]>([]);
    const [pausedHabits, setPausedHabits] = useState<Habit[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchHabits = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            // Fetch all habits 
            const data = await habitApi.getHabits();

            const active: Habit[] = [];
            const paused: Habit[] = [];

            data.habits.forEach(item => {
                if (item.status === 'paused') {
                    paused.push(item as Habit);
                } else {
                    active.push(item as Habit);
                }
            });

            setActiveHabits(active);
            setPausedHabits(paused);
        } catch (err) {
            console.error('[HabitStore] Failed to fetch habits:', err);
            setError(err instanceof Error ? err.message : 'Failed to fetch habits');
        } finally {
            setIsLoading(false);
        }
    }, []);

    const createHabit = async (request: CreateHabitRequest) => {
        setError(null);
        try {
            const created = await habitApi.createHabit(request);
            setActiveHabits(prev => [...prev, created as Habit]);
        } catch (err) {
            console.error('[HabitStore] Failed to create habit:', err);
            setError(err instanceof Error ? err.message : 'Failed to create habit');
            throw err;
        }
    };

    const updateHabit = async (habitId: string, request: UpdateHabitRequest) => {
        setError(null);
        try {
            const updated = await habitApi.updateHabit(habitId, request);

            // 先从两个列表都移除，再加入正确的列表
            setActiveHabits(prev => prev.filter(h => h.id !== habitId));
            setPausedHabits(prev => prev.filter(h => h.id !== habitId));

            if (updated.status === 'paused') {
                setPausedHabits(prev => [...prev, updated as Habit]);
            } else {
                setActiveHabits(prev => [...prev, updated as Habit]);
            }
        } catch (err) {
            console.error('[HabitStore] Failed to update habit:', err);
            setError(err instanceof Error ? err.message : 'Failed to update habit');
            throw err;
        }
    };

    const deleteHabit = async (habitId: string) => {
        setError(null);
        try {
            await habitApi.deleteHabit(habitId);
            setActiveHabits(prev => prev.filter(h => h.id !== habitId));
            setPausedHabits(prev => prev.filter(h => h.id !== habitId));
        } catch (err) {
            console.error('[HabitStore] Failed to delete habit:', err);
            setError(err instanceof Error ? err.message : 'Failed to delete habit');
            throw err;
        }
    };

    const pauseHabit = async (habitId: string) => {
        setError(null);
        try {
            const paused = await habitApi.pauseHabit(habitId);
            setActiveHabits(prev => prev.filter(h => h.id !== habitId));
            setPausedHabits(prev => [...prev, paused as Habit]);
        } catch (err) {
            console.error('[HabitStore] Failed to pause habit:', err);
            setError(err instanceof Error ? err.message : 'Failed to pause habit');
            throw err;
        }
    };

    const resumeHabit = async (habitId: string) => {
        setError(null);
        try {
            const resumed = await habitApi.resumeHabit(habitId);
            setPausedHabits(prev => prev.filter(h => h.id !== habitId));
            setActiveHabits(prev => [...prev, resumed as Habit]);
        } catch (err) {
            console.error('[HabitStore] Failed to resume habit:', err);
            setError(err instanceof Error ? err.message : 'Failed to resume habit');
            throw err;
        }
    };

    const checkIn = async (habitId: string) => {
        setError(null);
        const previousActive = [...activeHabits];

        // 先检查是否存在于 activeHabits 中
        if (!activeHabits.some(h => h.id === habitId)) return;

        // Optimistic update
        setActiveHabits(prev => prev.map(h => {
            if (h.id === habitId) {
                const newCompletedCount = h.currentChallenge ? h.currentChallenge.completedCount + 1 : 1;
                return {
                    ...h,
                    isCheckingIn: true,
                    todayCompleted: true,
                    currentChallenge: h.currentChallenge ? {
                        ...h.currentChallenge,
                        completedCount: newCompletedCount
                    } : null
                };
            }
            return h;
        }));

        try {
            const checkInRes = await checkinApi.checkInToday(habitId);
            // Replace with the updated habit returned from server
            setActiveHabits(prev => prev.map(h => {
                if (h.id === habitId && checkInRes.habit) {
                    return checkInRes.habit as Habit;
                }
                // reset checking in state if habit info didn't come back
                if (h.id === habitId) {
                    const { isCheckingIn, ...rest } = h;
                    return rest;
                }
                return h;
            }));

            if (checkInRes.settlement && onSettlement) {
                onSettlement(checkInRes.settlement);
            }
            onCheckInChange?.();
        } catch (err) {
            console.error('[HabitStore] Failed to check in:', err);
            setError(err instanceof Error ? err.message : 'Failed to check in');
            // Rollback
            setActiveHabits(previousActive);
            throw err;
        }
    };

    const undoCheckIn = async (habitId: string) => {
        setError(null);
        const previousActive = [...activeHabits];
        const today = format(new Date(), 'yyyy-MM-dd');

        // 先检查是否存在于 activeHabits 中
        if (!activeHabits.some(h => h.id === habitId)) return;

        // Optimistic update
        setActiveHabits(prev => prev.map(h => {
            if (h.id === habitId) {
                const newCompletedCount = h.currentChallenge
                    ? Math.max(0, h.currentChallenge.completedCount - 1)
                    : 0;
                return {
                    ...h,
                    isCheckingIn: true,
                    todayCompleted: false,
                    currentChallenge: h.currentChallenge ? {
                        ...h.currentChallenge,
                        completedCount: newCompletedCount
                    } : null
                };
            }
            return h;
        }));

        try {
            const cancelRes = await checkinApi.undoCheckIn(habitId, today);
            // Replace with the updated habit returned from server
            setActiveHabits(prev => prev.map(h => {
                if (h.id === habitId && cancelRes.habit) {
                    return cancelRes.habit as Habit;
                }
                if (h.id === habitId) {
                    const { isCheckingIn, ...rest } = h;
                    return rest;
                }
                return h;
            }));
            onCheckInChange?.();
        } catch (err) {
            console.error('[HabitStore] Failed to undo check in:', err);
            setError(err instanceof Error ? err.message : 'Failed to undo check in');
            // Rollback
            setActiveHabits(previousActive);
            throw err;
        }
    };

    const value: HabitStoreContextType = {
        activeHabits,
        pausedHabits,
        isLoading,
        error,
        fetchHabits,
        createHabit,
        updateHabit,
        deleteHabit,
        pauseHabit,
        resumeHabit,
        checkIn,
        undoCheckIn
    };

    return React.createElement(
        HabitStoreContext.Provider,
        { value },
        children
    );
};

export const useHabitStore = () => {
    const context = useContext(HabitStoreContext);
    if (!context) {
        throw new Error("useHabitStore must be used within a HabitProvider");
    }
    return context;
};
