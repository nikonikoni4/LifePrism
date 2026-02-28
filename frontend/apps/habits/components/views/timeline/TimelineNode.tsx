import React from 'react';
import { Check } from 'lucide-react';
import { TimelineEvent } from '../../../types/views';

interface TimelineNodeProps {
    event: TimelineEvent;
    hourHeight: number;
}

const timeToHour = (timeStr: string) => {
    const [hours, minutes] = timeStr.split(':').map(Number);
    return hours + minutes / 60;
};

export const TimelineNode: React.FC<TimelineNodeProps> = ({ event, hourHeight }) => {
    const startHour = timeToHour(event.startTime);
    const endHour = timeToHour(event.endTime);
    // Use top/height from event if present (algo 6.5), else calculate basic hour
    const top = event.top !== undefined ? event.top : startHour * hourHeight;
    const height = event.height !== undefined ? event.height : Math.max((endHour - startHour) * hourHeight, 24);

    const isHabit = !!event.associatedHabitId;

    return (
        <div className="absolute left-0 right-0 group z-10" style={{ top, height }}>
            {/* Event Specific Time */}
            <div className="absolute top-0 left-0 w-8 text-right text-[9px] font-bold text-emerald-600 font-mono mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                {event.startTime}
            </div>

            {/* Node Dot */}
            <div className={`absolute top-1.5 left-[46px] w-2 h-2 rounded-full -translate-x-1/2 ${isHabit ? 'bg-emerald-500 ring-2 ring-[#F4F5F7]' : 'bg-neutral-400'}`} />

            {/* Content Block */}
            <div className={`absolute left-[56px] right-2 top-0 bottom-0 ${isHabit ? 'bg-emerald-500/10 border-l-[3px] border-emerald-500 rounded-r-xl px-3 py-1.5 flex flex-col justify-center overflow-hidden transition-all hover:bg-emerald-500/20 shadow-sm' : 'px-2 py-1 flex items-start'}`}>
                <div className="flex items-center justify-between w-full">
                    <p className={`text-[11px] font-bold tracking-tight truncate ${isHabit ? 'text-emerald-900' : 'text-neutral-600'}`}>
                        {event.title}
                    </p>
                    {isHabit && <Check size={12} className="text-emerald-500 flex-shrink-0" />}
                </div>
                {isHabit && height >= 40 && (
                    <p className="text-[9px] text-emerald-700/60 font-medium mt-0.5">{event.startTime} - {event.endTime}</p>
                )}
            </div>
        </div>
    );
};
