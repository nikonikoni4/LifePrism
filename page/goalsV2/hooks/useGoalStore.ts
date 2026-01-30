import React, { createContext, useContext, useState, ReactNode } from 'react';
import { Goal, ThemeKey } from '../components/shared/types';

// Constants
export const THEMES: Record<string, { label: string; gradient: string; title: string; progressBg: string; meta: string; container: string; button: string; timelineLine: string; tag: string }> = {
    indigo: {
        label: 'Indigo',
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

export const INITIAL_GOALS: Goal[] = [
    {
        id: '1',
        title: 'Master React & Frontend Architecture',
        category: 'Career',
        theme: 'indigo',
        timeInvested: '42',
        unit: 'HRS',
        startDate: '01.15',
        endDate: '06.30',
        value: 'To become a world-class engineer.',
        commitment: 'Code daily.',
        details: 'Deep dive into React 19, Server Components, and advanced patterns.',
        status: 'active',
        milestones: [
            { id: 'm1', content: 'Complete React Docs', state: 1, finishTime: '01.20', orderIndex: 0 },
            { id: 'm2', content: 'Build 3 Practice Apps', state: 0, finishTime: null, orderIndex: 1 },
            { id: 'm3', content: 'Contribute to Open Source', state: 0, finishTime: null, orderIndex: 2 }
        ],
        journal: [
            { id: 'j1', date: 'Jan 15', time: '09:00 AM', content: 'Started the journey. Feeling excited!', mood: 'joy', duration: 2, tags: ['Start'] },
            { id: 'j2', date: 'Jan 16', time: '08:30 PM', content: 'Struggled with useEffect today, but made progress.', mood: 'frustrated', duration: 3, tags: ['Learning'] }
        ]
    },
    {
        id: '2',
        title: 'Run a Half Marathon',
        category: 'Health',
        theme: 'rose',
        timeInvested: '15',
        unit: 'HRS',
        startDate: '02.01',
        endDate: '05.15',
        value: 'To push my physical limits.',
        commitment: 'Run 4x a week.',
        details: 'Follow the 12-week training plan.',
        status: 'active',
        milestones: [
            { id: 'm1', content: 'Run 5k without stopping', state: 1, finishTime: '02.10', orderIndex: 0 },
            { id: 'm2', content: 'Run 10k', state: 0, finishTime: null, orderIndex: 1 }
        ],
        journal: []
    }
];

interface GoalStoreContextType {
    goals: Goal[];
    addGoal: (goal: Goal) => void;
    updateGoal: (goal: Goal) => void;
    deleteGoal: (id: string) => void;
    toggleGoalStatus: (id: string) => void;
}

const GoalStoreContext = createContext<GoalStoreContextType | undefined>(undefined);

export const GoalProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [goals, setGoals] = useState<Goal[]>(INITIAL_GOALS);

    const addGoal = (goal: Goal) => {
        setGoals(prev => [...prev, goal]);
    };

    const updateGoal = (updatedGoal: Goal) => {
        setGoals(prev => prev.map(g => g.id === updatedGoal.id ? updatedGoal : g));
    };

    const deleteGoal = (id: string) => {
        setGoals(prev => prev.filter(g => g.id !== id));
    };

    const toggleGoalStatus = (id: string) => {
        setGoals(prev => prev.map(g => {
            if (g.id === id) {
                return { ...g, status: g.status === 'active' ? 'completed' : 'active' };
            }
            return g;
        }));
    };

    // Use React.createElement to avoid JSX in .ts file
    return React.createElement(
        GoalStoreContext.Provider,
        { value: { goals, addGoal, updateGoal, deleteGoal, toggleGoalStatus } },
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