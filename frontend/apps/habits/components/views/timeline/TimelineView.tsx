import React, { useEffect, useRef } from 'react';
import { useTimelineStore } from '../../../hooks/useTimelineStore';
import { TimelineNode } from './TimelineNode';
import { HOUR_HEIGHT } from '../../../constants';

export const TimelineView: React.FC = () => {
    const { timelineEvents } = useTimelineStore();
    const timelineRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (timelineRef.current) {
            const now = new Date();
            const currentHour = now.getHours() + now.getMinutes() / 60;
            // scroll to (currentHour - 1) so we have a bit of context visually
            timelineRef.current.scrollTop = Math.max(0, (currentHour - 1) * HOUR_HEIGHT);
        }
    }, []);

    return (
        <div className="col-span-12 lg:col-span-3 bg-white rounded-[24px] p-6 h-full flex flex-col overflow-hidden shadow-sm border border-neutral-100">
            <div className="flex justify-between items-center mb-6 shrink-0">
                <h2 className="text-xs font-bold text-neutral-400 uppercase tracking-widest">
                    Timeline
                </h2>
                <button className="text-neutral-400 hover:text-neutral-600">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 block animate-pulse"></span>
                </button>
            </div>

            <div
                ref={timelineRef}
                className="flex-1 overflow-y-auto no-scrollbar relative w-full scroll-smooth"
            >
                <div className="relative w-full" style={{ height: `${24 * HOUR_HEIGHT}px` }}>
                    {/* Vertical Line */}
                    <div className="absolute left-[45px] top-0 bottom-0 w-[2px] bg-neutral-200/80 z-0" />

                    {/* Background Hour Indicators */}
                    {Array.from({ length: 24 }).map((_, i) => (
                        <div key={i} className="absolute left-0 right-0 border-t border-neutral-200/50 z-0" style={{ top: i * HOUR_HEIGHT, height: HOUR_HEIGHT }}>
                            <div className="absolute top-[-8px] left-0 w-8 text-right text-[10px] font-bold text-neutral-300 font-mono">
                                {String(i).padStart(2, '0')}:00
                            </div>
                        </div>
                    ))}

                    {/* Current Time Indicator Line */}
                    <div
                        className="absolute left-[45px] right-0 flex items-center z-20 pointer-events-none"
                        style={{ top: (new Date().getHours() + new Date().getMinutes() / 60) * HOUR_HEIGHT }}
                    >
                        <div className="w-2 h-2 rounded-full bg-red-500 -ml-[3px]" />
                        <div className="flex-1 h-[2px] bg-red-500/50" />
                    </div>

                    {/* Events */}
                    {timelineEvents.map(event => (
                        <TimelineNode key={event.id} event={event} hourHeight={HOUR_HEIGHT} />
                    ))}
                </div>
            </div>
        </div>
    );
};
