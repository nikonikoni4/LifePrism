import React, { createContext, useContext, useMemo, ReactNode } from 'react';
import { useChainStore } from './useChainStore';
import { TimelineEvent } from '../types/views';
import { PIXELS_PER_MINUTE, MIN_NODE_HEIGHT } from '../constants';

interface TimelineStoreContextType {
    timelineEvents: TimelineEvent[];
}

const TimelineStoreContext = createContext<TimelineStoreContextType | undefined>(undefined);

// Helper to parse HH:mm (or legacy ISO string) to minutes since midnight
const parseTimeToMinutes = (timeStr: string): number => {
    // Check if it's already HH:mm
    if (/^\d{2}:\d{2}$/.test(timeStr)) {
        const [h, m] = timeStr.split(':').map(Number);
        return (h || 0) * 60 + (m || 0);
    }

    // Fallback: parse as Date if it's an ISO string (legacy DB data)
    try {
        const d = new Date(timeStr);
        if (!isNaN(d.getTime())) {
            return d.getHours() * 60 + d.getMinutes();
        }
    } catch (e) { }

    return 0;
};

// Helper to format minutes to HH:mm
const formatMinutesToTime = (minutes: number): string => {
    const h = Math.floor(minutes / 60);
    const m = Math.floor(minutes % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
};

export const TimelineProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const { chains } = useChainStore();

    const timelineEvents = useMemo(() => {
        const events: TimelineEvent[] = [];

        const activeChains = chains.filter(c => c.showInTimeline);

        activeChains.forEach(chain => {
            const nodes = [...chain.nodes].sort((a, b) => a.sortOrder - b.sortOrder);
            if (nodes.length === 0) return;

            // 使用后端计算返回的 calculated_time（若无则用 trigger_time）
            nodes.forEach((node) => {
                const displayTime = node.calculatedTime || node.triggerTime || "00:00";
                const minutes = parseTimeToMinutes(displayTime);

                events.push({
                    id: `${chain.id}_${node.id}`,
                    title: node.name,
                    startTime: displayTime,
                    endTime: formatMinutesToTime(minutes + 30),  // 默认30min
                    associatedHabitId: node.habitId,
                    height: MIN_NODE_HEIGHT,
                    top: minutes * PIXELS_PER_MINUTE
                });
            });
        });

        return events;
    }, [chains]);

    const value: TimelineStoreContextType = {
        timelineEvents
    };

    return React.createElement(
        TimelineStoreContext.Provider,
        { value },
        children
    );
};

export const useTimelineStore = () => {
    const context = useContext(TimelineStoreContext);
    if (!context) {
        throw new Error("useTimelineStore must be used within a TimelineProvider");
    }
    return context;
};
