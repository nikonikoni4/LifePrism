import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { HabitChain, HabitChainNode } from '../types/entities';
import { chainApi } from '../apis/chain';
import {
    CreateChainRequest,
    UpdateChainRequest,
    CreateChainNodeRequest,
    UpdateChainNodeRequest,
    ReorderNodeItem
} from '../types/backend';

interface ChainStoreContextType {
    chains: HabitChain[];
    isLoading: boolean;
    error: string | null;

    fetchChains: () => Promise<void>;
    createChain: (request: CreateChainRequest) => Promise<void>;
    updateChain: (chainId: number, request: UpdateChainRequest) => Promise<void>;
    deleteChain: (chainId: number) => Promise<void>;

    addNode: (chainId: number, request: CreateChainNodeRequest) => Promise<void>;
    updateNode: (chainId: number, nodeId: number, request: UpdateChainNodeRequest) => Promise<void>;
    deleteNode: (chainId: number, nodeId: number) => Promise<void>;
    reorderNodes: (chainId: number, newOrders: ReorderNodeItem[]) => Promise<void>;
}

const ChainStoreContext = createContext<ChainStoreContextType | undefined>(undefined);

export const ChainProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [chains, setChains] = useState<HabitChain[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchChains = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await chainApi.getChains();
            setChains(data.chains as HabitChain[]);
        } catch (err) {
            console.error('[ChainStore] Failed to fetch chains:', err);
            setError(err instanceof Error ? err.message : 'Failed to fetch chains');
        } finally {
            setIsLoading(false);
        }
    }, []);

    const createChain = async (request: CreateChainRequest) => {
        setError(null);
        try {
            const created = await chainApi.createChain(request);
            setChains(prev => [...prev, created as HabitChain]);
        } catch (err) {
            console.error('[ChainStore] Failed to create chain:', err);
            setError(err instanceof Error ? err.message : 'Failed to create chain');
            throw err;
        }
    };

    const updateChain = async (chainId: number, request: UpdateChainRequest) => {
        setError(null);
        try {
            const updated = await chainApi.updateChain(chainId, request);
            setChains(prev => prev.map(c => c.id === chainId ? (updated as HabitChain) : c));
        } catch (err) {
            console.error('[ChainStore] Failed to update chain:', err);
            setError(err instanceof Error ? err.message : 'Failed to update chain');
            throw err;
        }
    };

    const deleteChain = async (chainId: number) => {
        setError(null);
        try {
            await chainApi.deleteChain(chainId);
            setChains(prev => prev.filter(c => c.id !== chainId));
        } catch (err) {
            console.error('[ChainStore] Failed to delete chain:', err);
            setError(err instanceof Error ? err.message : 'Failed to delete chain');
            throw err;
        }
    };

    const addNode = async (chainId: number, request: CreateChainNodeRequest) => {
        setError(null);
        try {
            await chainApi.addChainNode(chainId, request);
            // Always re-fetch to get correct sortOrder from server and avoid UI flicker
            await fetchChains();
        } catch (err) {
            console.error('[ChainStore] Failed to add node:', err);
            setError(err instanceof Error ? err.message : 'Failed to add node');
            throw err;
        }
    };

    const updateNode = async (chainId: number, nodeId: number, request: UpdateChainNodeRequest) => {
        setError(null);
        try {
            const updatedNode = await chainApi.updateChainNode(chainId, nodeId, request);
            setChains(prev => prev.map(c => {
                if (c.id === chainId) {
                    return {
                        ...c,
                        nodes: c.nodes.map(n => n.id === nodeId ? (updatedNode as HabitChainNode) : n)
                    };
                }
                return c;
            }));
        } catch (err) {
            console.error('[ChainStore] Failed to update node:', err);
            setError(err instanceof Error ? err.message : 'Failed to update node');
            throw err;
        }
    };

    const deleteNode = async (chainId: number, nodeId: number) => {
        setError(null);
        try {
            await chainApi.deleteChainNode(chainId, nodeId);
            setChains(prev => prev.map(c => {
                if (c.id === chainId) {
                    return {
                        ...c,
                        nodes: c.nodes.filter(n => n.id !== nodeId)
                    };
                }
                return c;
            }));
        } catch (err) {
            console.error('[ChainStore] Failed to delete node:', err);
            setError(err instanceof Error ? err.message : 'Failed to delete node');
            throw err;
        }
    };

    const reorderNodes = async (chainId: number, newOrders: ReorderNodeItem[]) => {
        setError(null);
        // Optimistic update locally
        setChains(prev => prev.map(c => {
            if (c.id === chainId) {
                const nodesCopy = [...c.nodes];
                newOrders.forEach(order => {
                    const node = nodesCopy.find(n => n.id === order.nodeId);
                    if (node) {
                        node.sortOrder = order.sortOrder;
                    }
                });
                nodesCopy.sort((a, b) => a.sortOrder - b.sortOrder);
                return { ...c, nodes: nodesCopy };
            }
            return c;
        }));

        try {
            await chainApi.reorderNodes(chainId, { nodes: newOrders });
        } catch (err) {
            console.error('[ChainStore] Failed to reorder nodes:', err);
            setError(err instanceof Error ? err.message : 'Failed to reorder nodes');
            // Rollback could be done here by re-fetching
            await fetchChains();
            throw err;
        }
    };

    const value: ChainStoreContextType = {
        chains,
        isLoading,
        error,
        fetchChains,
        createChain,
        updateChain,
        deleteChain,
        addNode,
        updateNode,
        deleteNode,
        reorderNodes
    };

    return React.createElement(
        ChainStoreContext.Provider,
        { value },
        children
    );
};

export const useChainStore = () => {
    const context = useContext(ChainStoreContext);
    if (!context) {
        throw new Error("useChainStore must be used within a ChainProvider");
    }
    return context;
};
