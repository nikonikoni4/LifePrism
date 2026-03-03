import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { BackfillAvailabilityDay, SettlementItem } from '../types/backend';
import { settlementApi } from '../apis/settlement';
import { checkinApi } from '../apis/checkin';

interface BackfillState {
    habitId: string;
    challengeId: string;
    days: BackfillAvailabilityDay[];
    isLoading: boolean;
    isProcessing: boolean;
    error: string | null;
}

interface SettlementStoreContextType {
    /** 待处理的结算列表 */
    settlements: SettlementItem[];
    /** 弹窗是否打开 */
    isDialogOpen: boolean;
    /** 是否正在加载结算检查 */
    isChecking: boolean;
    /** 当前正在补录的状态 */
    backfillState: BackfillState | null;

    /** 页面加载时检查结算 */
    checkSettlements: () => Promise<void>;
    /** 从 checkIn/undoCheckIn 响应中推入结算项 */
    pushSettlement: (item: SettlementItem) => void;
    /** 执行补录 */
    backfill: (habitId: string, challengeId: string, dates: string[]) => Promise<void>;
    /** 从列表中移除已处理的结算项 */
    dismissSettlement: (habitId: string) => void;
    /** 关闭弹窗 */
    closeDialog: () => void;
    /** 打开补录子视图 */
    openBackfill: (habitId: string, challengeId: string) => Promise<void>;
    /** 关闭补录子视图 */
    closeBackfill: () => void;
}

const SettlementStoreContext = createContext<SettlementStoreContextType | undefined>(undefined);

export const SettlementProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [settlements, setSettlements] = useState<SettlementItem[]>([]);
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [isChecking, setIsChecking] = useState(false);
    const [backfillState, setBackfillState] = useState<BackfillState | null>(null);

    const checkSettlements = useCallback(async () => {
        setIsChecking(true);
        try {
            const items = await settlementApi.checkSettlements();
            if (items.length > 0) {
                setSettlements(items);
                setIsDialogOpen(true);
            }
        } catch (err) {
            console.error('[SettlementStore] Failed to check settlements:', err);
        } finally {
            setIsChecking(false);
        }
    }, []);

    const pushSettlement = useCallback((item: SettlementItem) => {
        setSettlements(prev => {
            if (prev.some(s => s.habitId === item.habitId)) {
                return prev;
            }
            return [...prev, item];
        });
        setIsDialogOpen(true);
    }, []);

    const backfill = useCallback(async (habitId: string, challengeId: string, dates: string[]) => {
        if (dates.length === 0) {
            return;
        }
        setBackfillState(prev => prev ? { ...prev, isProcessing: true, error: null } : null);
        try {
            const res = await checkinApi.backfillCheckIn(
                habitId,
                { challengeId, items: dates.map(date => ({ date })) },
            );
            const latestSettlement = [...res.results]
                .reverse()
                .find(item => item.settlement !== null)
                ?.settlement ?? null;
            if (latestSettlement) {
                setSettlements(prev =>
                    prev.map(s => s.habitId === habitId ? latestSettlement : s)
                );
            }
            const failedItems = res.results.filter(item => item.status === 'failed');
            const failedMessage = failedItems.length > 0
                ? `补录完成，${failedItems.length} 个日期失败`
                : null;
            try {
                const availability = await checkinApi.getBackfillAvailability({ habitId, challengeId });
                setBackfillState(prev => prev ? {
                    ...prev,
                    isProcessing: false,
                    isLoading: false,
                    days: availability.days,
                    error: failedMessage,
                } : null);
            } catch {
                setBackfillState(prev => prev ? { ...prev, isProcessing: false, error: failedMessage } : null);
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : '补录失败';
            setBackfillState(prev => prev ? { ...prev, isProcessing: false, error: msg } : null);
            throw err;
        }
    }, []);

    const dismissSettlement = useCallback((habitId: string) => {
        setSettlements(prev => prev.filter(s => s.habitId !== habitId));
    }, []);

    const closeDialog = useCallback(() => {
        setIsDialogOpen(false);
        setSettlements([]);
        setBackfillState(null);
    }, []);

    const openBackfill = useCallback(async (habitId: string, challengeId: string) => {
        setIsDialogOpen(true);
        setBackfillState({
            habitId,
            challengeId,
            days: [],
            isLoading: true,
            isProcessing: false,
            error: null,
        });
        try {
            const availability = await checkinApi.getBackfillAvailability({ habitId, challengeId });
            setBackfillState(prev => prev ? {
                ...prev,
                days: availability.days,
                isLoading: false,
                error: null,
            } : null);
        } catch (err) {
            const msg = err instanceof Error ? err.message : '加载补录日期失败';
            setBackfillState(prev => prev ? { ...prev, isLoading: false, error: msg } : null);
        }
    }, []);

    const closeBackfill = useCallback(() => {
        setBackfillState(null);
    }, []);

    const value: SettlementStoreContextType = {
        settlements,
        isDialogOpen,
        isChecking,
        backfillState,
        checkSettlements,
        pushSettlement,
        backfill,
        dismissSettlement,
        closeDialog,
        openBackfill,
        closeBackfill,
    };

    return React.createElement(SettlementStoreContext.Provider, { value }, children);
};

export const useSettlementStore = () => {
    const context = useContext(SettlementStoreContext);
    if (!context) {
        throw new Error('useSettlementStore must be used within a SettlementProvider');
    }
    return context;
};
