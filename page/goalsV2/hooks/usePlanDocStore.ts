
import React, { createContext, useContext, useState, ReactNode } from 'react';
import { PlanDoc } from '../components/shared/types';

const INITIAL_PLANS: PlanDoc[] = [
    {
        id: 'p1',
        goalId: '1', // Matches Master React goal
        title: 'React Learning Roadmap',
        content: '# React Learning Roadmap\n\n## Core Concepts\n- [ ] JSX & Rendering\n- [ ] State & Props\n- [ ] Hooks (useEffect, useState)\n\n## Advanced\n- [ ] Server Components\n- [ ] Suspense\n- [ ] Transitions',
        createdAt: '2024-01-15',
        updatedAt: '2024-01-16',
        status: 'active'
    },
    {
        id: 'p2',
        goalId: '1', 
        title: 'Project Ideas Draft',
        content: '# Project Ideas\n\n1. Todo App with AI\n2. Weather Dashboard\n3. E-commerce Store',
        createdAt: '2024-01-20',
        updatedAt: '2024-01-20',
        status: 'active'
    },
    {
        id: 'p3',
        goalId: '2', // Matches Half Marathon goal
        title: 'Training Schedule 12-Week',
        content: '# 12 Week Plan\n\n- Week 1: Easy runs\n- Week 2: Increase distance\n- Week 3: Interval training',
        createdAt: '2024-02-01',
        updatedAt: '2024-02-01',
        status: 'active'
    }
];

interface PlanDocStoreContextType {
    planDocs: PlanDoc[];
    addPlanDoc: (doc: PlanDoc) => void;
    updatePlanDoc: (doc: PlanDoc) => void;
    deletePlanDoc: (id: string) => void;
}

const PlanDocStoreContext = createContext<PlanDocStoreContextType | undefined>(undefined);

export const PlanDocProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [planDocs, setPlanDocs] = useState<PlanDoc[]>(INITIAL_PLANS);

    const addPlanDoc = (doc: PlanDoc) => {
        setPlanDocs(prev => [...prev, doc]);
    };

    const updatePlanDoc = (updatedDoc: PlanDoc) => {
        setPlanDocs(prev => prev.map(d => d.id === updatedDoc.id ? updatedDoc : d));
    };

    const deletePlanDoc = (id: string) => {
        setPlanDocs(prev => prev.filter(d => d.id !== id));
    };

    return React.createElement(
        PlanDocStoreContext.Provider,
        { value: { planDocs, addPlanDoc, updatePlanDoc, deletePlanDoc } },
        children
    );
};

export const usePlanDocStore = () => {
    const context = useContext(PlanDocStoreContext);
    if (!context) {
        throw new Error("usePlanDocStore must be used within a PlanDocProvider");
    }
    return context;
};
