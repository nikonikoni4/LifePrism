import React, { createContext, useContext, useMemo, ReactNode } from 'react';
import { useChainStore } from './useChainStore';
import { TimelineEvent } from '../types/views';
import { PIXELS_PER_MINUTE, MIN_NODE_HEIGHT, MIN_ANCHOR_GAP } from '../constants';

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

        // Process each chain to compute its nodes' absolute positions
        const activeChains = chains.filter(c => c.showInTimeline);

        activeChains.forEach(chain => {
            const nodes = [...chain.nodes].sort((a, b) => a.sortOrder - b.sortOrder);
            if (nodes.length === 0) return;

            // Step 1: Identify anchors
            const anchors: { index: number; minutes: number; y: number }[] = [];

            nodes.forEach((node, idx) => {
                if (node.triggerTime) {
                    anchors.push({
                        index: idx,
                        minutes: parseTimeToMinutes(node.triggerTime),
                        y: parseTimeToMinutes(node.triggerTime) * PIXELS_PER_MINUTE
                    });
                }
            });

            // Adjust anchors if gap < MIN_ANCHOR_GAP
            for (let i = 1; i < anchors.length; i++) {
                const prev = anchors[i - 1];
                const curr = anchors[i];
                if (curr.y - prev.y < MIN_ANCHOR_GAP) {
                    curr.y = prev.y + MIN_ANCHOR_GAP;
                }
            }

            // Step 2, 3, 4: Assign positions to all nodes
            const nodeLayouts: { y: number; height: number; endTimeMinutes: number }[] = Array(nodes.length).fill(null);

            if (anchors.length === 0) {
                // Should not happen according to business rules (first node must have time if showInTimeline),
                // but fallback: start at current time or 0
                let currentY = 0;
                let currentMinutes = 0;
                for (let i = 0; i < nodes.length; i++) {
                    nodeLayouts[i] = { y: currentY, height: MIN_NODE_HEIGHT, endTimeMinutes: currentMinutes + (MIN_NODE_HEIGHT / PIXELS_PER_MINUTE) };
                    currentY += MIN_NODE_HEIGHT;
                    currentMinutes += (MIN_NODE_HEIGHT / PIXELS_PER_MINUTE);
                }
            } else {
                // Layout nodes segment by segment
                let anchorIdx = 0;

                // Before first anchor (should be empty, but just in case)
                let firstAnchor = anchors[0];
                let preAnchorY = firstAnchor.y - (firstAnchor.index * MIN_NODE_HEIGHT);
                let preAnchorMinutes = firstAnchor.minutes - (firstAnchor.index * (MIN_NODE_HEIGHT / PIXELS_PER_MINUTE));
                for (let i = 0; i < firstAnchor.index; i++) {
                    nodeLayouts[i] = {
                        y: preAnchorY,
                        height: MIN_NODE_HEIGHT,
                        endTimeMinutes: preAnchorMinutes + (MIN_NODE_HEIGHT / PIXELS_PER_MINUTE)
                    };
                    preAnchorY += MIN_NODE_HEIGHT;
                    preAnchorMinutes += (MIN_NODE_HEIGHT / PIXELS_PER_MINUTE);
                }

                // Between anchors
                for (let a = 0; a < anchors.length - 1; a++) {
                    const currAnchor = anchors[a];
                    const nextAnchor = anchors[a + 1];
                    const nodesBetween = nextAnchor.index - currAnchor.index - 1;

                    if (nodesBetween === 0) {
                        nodeLayouts[currAnchor.index] = {
                            y: currAnchor.y,
                            height: nextAnchor.y - currAnchor.y,
                            endTimeMinutes: nextAnchor.minutes
                        };
                    } else {
                        // Distribute space
                        const totalSpace = nextAnchor.y - currAnchor.y;
                        const spacePerNode = totalSpace / (nodesBetween + 1);
                        const actualNodeHeight = Math.max(MIN_NODE_HEIGHT, spacePerNode);

                        // If actualNodeHeight > spacePerNode, it pushes nextAnchor down (not implemented fully to ripple, just overlap/push conceptually)
                        let currentY = currAnchor.y;
                        let currentMins = currAnchor.minutes;
                        const minMinutes = actualNodeHeight / PIXELS_PER_MINUTE;

                        for (let i = currAnchor.index; i < nextAnchor.index; i++) {
                            nodeLayouts[i] = {
                                y: currentY,
                                height: actualNodeHeight,
                                endTimeMinutes: currentMins + minMinutes
                            };
                            currentY += actualNodeHeight;
                            currentMins += minMinutes;
                        }

                        // If it pushed next anchor down, update next anchor (simple forward correction)
                        if (currentY > nextAnchor.y) {
                            nextAnchor.y = currentY;
                            // not strictly updating minutes here, just visual Y
                        }
                    }
                }

                // Last anchor and trailing nodes
                const lastAnchor = anchors[anchors.length - 1];
                let currentY = lastAnchor.y;
                let currentMins = lastAnchor.minutes;

                for (let i = lastAnchor.index; i < nodes.length; i++) {
                    nodeLayouts[i] = {
                        y: currentY,
                        height: MIN_NODE_HEIGHT,
                        endTimeMinutes: currentMins + (MIN_NODE_HEIGHT / PIXELS_PER_MINUTE)
                    };
                    currentY += MIN_NODE_HEIGHT;
                    currentMins += (MIN_NODE_HEIGHT / PIXELS_PER_MINUTE);
                }
            }

            // Map to TimelineEvent
            nodes.forEach((node, idx) => {
                const layout = nodeLayouts[idx];
                const startTimeMinutes = layout.y / PIXELS_PER_MINUTE; // approximated backwards from Y to show absolute time if shifted
                events.push({
                    id: `${chain.id}_${node.id}`,
                    title: node.name,
                    startTime: formatMinutesToTime(startTimeMinutes),
                    endTime: formatMinutesToTime(layout.endTimeMinutes),
                    associatedHabitId: node.habitId,
                    height: layout.height,
                    top: layout.y
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
