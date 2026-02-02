
import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { PlanDoc } from '../types';
import { planDocApi } from '../api';

interface PlanDocStoreContextType {
    planDocs: PlanDoc[];
    isLoading: boolean;
    error: string | null;
    fetchPlanDocs: () => Promise<void>;
    addPlanDoc: (doc: PlanDoc) => void;
    updatePlanDoc: (doc: PlanDoc) => void;
    deletePlanDoc: (id: string) => void;
}

const PlanDocStoreContext = createContext<PlanDocStoreContextType | undefined>(undefined);

export const PlanDocProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [planDocs, setPlanDocs] = useState<PlanDoc[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchPlanDocs = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await planDocApi.getPlanDocs();
            setPlanDocs(data);
        } catch (err) {
            console.error('[PlanDocStore] Failed to fetch plan docs:', err);
            setError(err instanceof Error ? err.message : 'Failed to fetch plan docs');
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Fetch plan docs on mount
    useEffect(() => {
        fetchPlanDocs();
    }, [fetchPlanDocs]);

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
        { value: { planDocs, isLoading, error, fetchPlanDocs, addPlanDoc, updatePlanDoc, deletePlanDoc } },
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
