
import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { PlanDoc } from '../types';
import { planDocApi } from '../apis/planDoc';

interface PlanDocStoreContextType {
    planDocs: PlanDoc[];
    isLoading: boolean;
    error: string | null;
    fetchPlanDocs: () => Promise<void>;
    addPlanDoc: (doc: PlanDoc) => void;
    removePlanDocLocal: (id: string) => void;  // 仅从本地 store 移除，不调用后端
    updatePlanDoc: (doc: PlanDoc, newId?: string) => Promise<void>;
    deletePlanDoc: (id: string) => Promise<void>;
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

    // 仅从本地 store 移除，不调用后端 API（用于回滚乐观更新）
    const removePlanDocLocal = (id: string) => {
        setPlanDocs(prev => prev.filter(d => d.id !== id));
    };

    const updatePlanDoc = async (updatedDoc: PlanDoc, newId?: string) => {
        setError(null);
        // Optimistic update
        setPlanDocs(prev => prev.map(d => d.id === updatedDoc.id ? updatedDoc : d));

        try {
            // Only sync metadata fields
            await planDocApi.updatePlanDoc(updatedDoc.id, {
                status: updatedDoc.status
            }, newId);

            // If renamed, we need to refresh the list or manually update the ID in state because optimistic update above uses old ID
            if (newId) {
                setPlanDocs(prev => prev.map(d => d.id === updatedDoc.id ? { ...updatedDoc, id: newId } : d));
            }

        } catch (err) {
            console.error('[PlanDocStore] Failed to update plan doc:', err);
            setError(err instanceof Error ? err.message : 'Failed to update plan doc');
            // Revert on failure could be added here
            throw err;
        }
    };

    const deletePlanDoc = async (id: string) => {
        setError(null);
        try {
            const success = await planDocApi.deletePlanDoc(id);
            if (success) {
                setPlanDocs(prev => prev.filter(d => d.id !== id));
            } else {
                throw new Error('Delete operation failed');
            }
        } catch (err) {
            console.error('[PlanDocStore] Failed to delete plan doc:', err);
            setError(err instanceof Error ? err.message : 'Failed to delete plan doc');
            throw err;
        }
    };

    return React.createElement(
        PlanDocStoreContext.Provider,
        { value: { planDocs, isLoading, error, fetchPlanDocs, addPlanDoc, removePlanDocLocal, updatePlanDoc, deletePlanDoc } },
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
