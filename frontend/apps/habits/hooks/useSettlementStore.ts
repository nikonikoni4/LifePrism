import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { SettlementItem } from '../types/backend';
import { settlementApi } from '../apis/settlement';
import { checkinApi } from '../apis/checkin';

interface BackfillState {
    habitId: string;
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
    backfill: (habitId: string, date: string) => Promise<void>;
    /** 从列表中移除已处理的结算项 */
    dismissSettlement: (habitId: string) => void;
    /** 关闭弹窗 */
    closeDialog: () => void;
    /** 打开补录子视图 */
    openBackfill: (habitId: string) => void;
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

    const backfill = useCallback(async (habitId: string, date: string) => {
        setBackfillState(prev => prev ? { ...prev, isProcessing: true, error: null } : null);
        try {
            const res = await checkinApi.backfillCheckIn(habitId, { date });
            if (res.settlement) {
                setSettlements(prev =>
                    prev.map(s => s.habitId === habitId ? res.settlement! : s)
                );
            }
            setBackfillState(prev => prev ? { ...prev, isProcessing: false } : null);
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

    const openBackfill = useCallback((habitId: string) => {
        setBackfillState({ habitId, isProcessing: false, error: null });
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
