
import React, { createContext, useContext, useState, ReactNode } from 'react';
import { TodoItem } from '../components/shared/components/todoItem/types';
import { INITIAL_POOL_TASKS } from '../components/views/TaskPoolView/mockData';

// Re-export type for consumers
export type { TodoItem };

interface TaskPoolStoreContextType {
    tasks: TodoItem[];
    addTask: (task: TodoItem) => void;
    updateTask: (id: number, updates: Partial<TodoItem>) => void;
    deleteTask: (id: number) => void;
    moveTaskToPool: (id: number) => void;
    scheduleTask: (id: number, date: string) => void;
}

const TaskPoolStoreContext = createContext<TaskPoolStoreContextType | undefined>(undefined);

export const TaskPoolProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [tasks, setTasks] = useState<TodoItem[]>(INITIAL_POOL_TASKS);

    const addTask = (task: TodoItem) => setTasks(prev => [...prev, task]);
    
    const updateTask = (id: number, updates: Partial<TodoItem>) => {
        setTasks(prev => prev.map(t => t.id === id ? { ...t, ...updates } : t));
    };

    const deleteTask = (id: number) => {
        // Simple delete, in a real app might need to delete children recursively
        setTasks(prev => prev.filter(t => t.id !== id));
    };

    const moveTaskToPool = (id: number) => {
        setTasks(prev => prev.map(t => t.id === id ? { 
            ...t, 
            state: 'pool', 
            scheduledDate: null 
        } : t));
    };

    const scheduleTask = (id: number, date: string) => {
        setTasks(prev => prev.map(t => t.id === id ? { 
            ...t, 
            state: 'scheduled', 
            scheduledDate: date 
        } : t));
    };

    return React.createElement(
        TaskPoolStoreContext.Provider,
        { value: { tasks, addTask, updateTask, deleteTask, moveTaskToPool, scheduleTask } },
        children
    );
};

export const useTaskPoolStore = () => {
    const context = useContext(TaskPoolStoreContext);
    if (!context) {
        throw new Error("useTaskPoolStore must be used within a TaskPoolProvider");
    }
    return context;
};
