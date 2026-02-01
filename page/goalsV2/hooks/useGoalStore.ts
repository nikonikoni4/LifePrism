import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { Goal, ThemeKey } from '../types';
import { goalsV2Api } from '../api';

// Constants
export const THEMES: Record<string, { label: string; accentColor: string; gradient: string; title: string; progressBg: string; meta: string; container: string; button: string; timelineLine: string; tag: string }> = {
    indigo: {
        label: 'Indigo',
        accentColor: '#6366f1',
        gradient: 'from-indigo-500/10 to-indigo-600/10',
        title: 'text-indigo-900',
        progressBg: 'bg-indigo-500',
        meta: 'text-indigo-400',
        container: 'bg-white border-indigo-100 hover:border-indigo-300',
        button: 'bg-indigo-50 text-indigo-500 hover:bg-indigo-500 hover:text-white border-indigo-100',
        timelineLine: 'from-indigo-200 via-indigo-100 to-transparent',
        tag: 'bg-indigo-50 text-indigo-600'
    },
    rose: {
        label: 'Rose',
        accentColor: '#f43f5e',
        gradient: 'from-rose-500/10 to-rose-600/10',
        title: 'text-rose-900',
        progressBg: 'bg-rose-500',
        meta: 'text-rose-400',
        container: 'bg-white border-rose-100 hover:border-rose-300',
        button: 'bg-rose-50 text-rose-500 hover:bg-rose-500 hover:text-white border-rose-100',
        timelineLine: 'from-rose-200 via-rose-100 to-transparent',
        tag: 'bg-rose-50 text-rose-600'
    },
    amber: {
        label: 'Amber',
        accentColor: '#f59e0b',
        gradient: 'from-amber-500/10 to-amber-600/10',
        title: 'text-amber-900',
        progressBg: 'bg-amber-500',
        meta: 'text-amber-400',
        container: 'bg-white border-amber-100 hover:border-amber-300',
        button: 'bg-amber-50 text-amber-500 hover:bg-amber-500 hover:text-white border-amber-100',
        timelineLine: 'from-amber-200 via-amber-100 to-transparent',
        tag: 'bg-amber-50 text-amber-600'
    },
    emerald: {
        label: 'Emerald',
        accentColor: '#10b981',
        gradient: 'from-emerald-500/10 to-emerald-600/10',
        title: 'text-emerald-900',
        progressBg: 'bg-emerald-500',
        meta: 'text-emerald-400',
        container: 'bg-white border-emerald-100 hover:border-emerald-300',
        button: 'bg-emerald-50 text-emerald-500 hover:bg-emerald-500 hover:text-white border-emerald-100',
        timelineLine: 'from-emerald-200 via-emerald-100 to-transparent',
        tag: 'bg-emerald-50 text-emerald-600'
    },
    violet: {
        label: 'Violet',
        accentColor: '#8b5cf6',
        gradient: 'from-violet-500/10 to-violet-600/10',
        title: 'text-violet-900',
        progressBg: 'bg-violet-500',
        meta: 'text-violet-400',
        container: 'bg-white border-violet-100 hover:border-violet-300',
        button: 'bg-violet-50 text-violet-500 hover:bg-violet-500 hover:text-white border-violet-100',
        timelineLine: 'from-violet-200 via-violet-100 to-transparent',
        tag: 'bg-violet-50 text-violet-600'
    },
    cyan: {
        label: 'Cyan',
        accentColor: '#06b6d4',
        gradient: 'from-cyan-500/10 to-cyan-600/10',
        title: 'text-cyan-900',
        progressBg: 'bg-cyan-500',
        meta: 'text-cyan-400',
        container: 'bg-white border-cyan-100 hover:border-cyan-300',
        button: 'bg-cyan-50 text-cyan-500 hover:bg-cyan-500 hover:text-white border-cyan-100',
        timelineLine: 'from-cyan-200 via-cyan-100 to-transparent',
        tag: 'bg-cyan-50 text-cyan-600'
    }
};

export const PAST_VALUES = [
    "To achieve financial freedom and security.",
    "To master a skill that brings me joy.",
    "To build a legacy for my family.",
    "To improve my physical and mental health.",
    "To contribute meaningfully to my community."
];

export const PAST_COMMITMENTS = [
    "I will dedicate 30 minutes every morning.",
    "I will write code every single day.",
    "I will read 10 pages before bed.",
    "I will exercise 4 times a week.",
    "I will track my progress every Sunday."
];

interface GoalStoreContextType {
    goals: Goal[];
    isLoading: boolean;
    error: string | null;
    fetchGoals: () => Promise<void>;
    addGoal: (goal: Goal) => Promise<void>;
    updateGoal: (goal: Goal) => Promise<void>;
    deleteGoal: (id: string) => Promise<void>;
    toggleGoalStatus: (id: string) => Promise<void>;
    updateMilestoneState: (goalId: string, milestoneId: string, state: number) => Promise<void>;
}

const GoalStoreContext = createContext<GoalStoreContextType | undefined>(undefined);

export const GoalProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [goals, setGoals] = useState<Goal[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchGoals = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await goalsV2Api.getGoals();
            setGoals(data);
        } catch (err) {
            console.error('[GoalStore] Failed to fetch goals:', err);
            setError(err instanceof Error ? err.message : 'Failed to fetch goals');
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Fetch goals on mount
    useEffect(() => {
        fetchGoals();
    }, [fetchGoals]);

    const addGoal = async (goal: Goal) => {
        setError(null);
        try {
            const created = await goalsV2Api.createGoal(goal);
            setGoals(prev => [...prev, created]);
        } catch (err) {
            console.error('[GoalStore] Failed to create goal:', err);
            setError(err instanceof Error ? err.message : 'Failed to create goal');
            throw err;
        }
    };

    const updateGoal = async (updatedGoal: Goal) => {
        setError(null);
        try {
            const updated = await goalsV2Api.updateGoal(updatedGoal.id, updatedGoal);
            setGoals(prev => prev.map(g => g.id === updated.id ? updated : g));
        } catch (err) {
            console.error('[GoalStore] Failed to update goal:', err);
            setError(err instanceof Error ? err.message : 'Failed to update goal');
            throw err;
        }
    };

    const deleteGoal = async (id: string) => {
        setError(null);
        try {
            const success = await goalsV2Api.deleteGoal(id);
            if (success) {
                setGoals(prev => prev.filter(g => g.id !== id));
            } else {
                throw new Error('Delete operation failed');
            }
        } catch (err) {
            console.error('[GoalStore] Failed to delete goal:', err);
            setError(err instanceof Error ? err.message : 'Failed to delete goal');
            throw err;
        }
    };

    const toggleGoalStatus = async (id: string) => {
        setError(null);
        const goal = goals.find(g => g.id === id);
        if (!goal) return;

        const newStatus = goal.status === 'active' ? 'completed' : 'active';
        try {
            const updated = await goalsV2Api.updateGoal(id, { status: newStatus });
            setGoals(prev => prev.map(g => g.id === updated.id ? updated : g));
        } catch (err) {
            console.error('[GoalStore] Failed to toggle goal status:', err);
            setError(err instanceof Error ? err.message : 'Failed to toggle goal status');
            throw err;
        }
    };

    const updateMilestoneState = async (goalId: string, milestoneId: string, state: number) => {
        setError(null);
        try {
            const updated = await goalsV2Api.updateMilestoneState(goalId, milestoneId, state);
            setGoals(prev => prev.map(g => g.id === updated.id ? updated : g));
        } catch (err) {
            console.error('[GoalStore] Failed to update milestone:', err);
            setError(err instanceof Error ? err.message : 'Failed to update milestone');
            throw err;
        }
    };

    // Use React.createElement to avoid JSX in .ts file
    return React.createElement(
        GoalStoreContext.Provider,
        {
            value: {
                goals,
                isLoading,
                error,
                fetchGoals,
                addGoal,
                updateGoal,
                deleteGoal,
                toggleGoalStatus,
                updateMilestoneState
            }
        },
        children
    );
};

export const useGoalStore = () => {
    const context = useContext(GoalStoreContext);
    if (!context) {
        throw new Error("useGoalStore must be used within a GoalProvider");
    }
    return context;
};
