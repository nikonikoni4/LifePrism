import React from 'react';
import { Flag, Check } from 'lucide-react';
import { MilestoneItem } from '../../../../../types';

export interface MilestoneAxisProps {
    milestones: MilestoneItem[];
    onToggle: (id: string, newState: number) => void;
    label?: string;
    showLabel?: boolean;
    completedClassName?: string;
    pendingClassName?: string;
    lineCompletedClassName?: string;
    linePendingClassName?: string;
}

const MilestoneAxis: React.FC<MilestoneAxisProps> = ({
    milestones,
    onToggle,
    label = 'Milestones',
    showLabel = true,
    completedClassName = 'bg-green-500 border-green-600 text-white shadow-lg shadow-green-200',
    pendingClassName = 'bg-white border-slate-300 text-slate-400 hover:border-blue-400 hover:text-blue-500',
    lineCompletedClassName = 'bg-green-400',
    linePendingClassName = 'bg-slate-200'
}) => {
    if (!milestones || milestones.length === 0) return null;

    const sortedMilestones = [...milestones].sort((a, b) => a.orderIndex - b.orderIndex);

    return (
        <div className="mb-6 p-4 bg-gradient-to-r from-slate-50 to-white rounded-2xl border border-slate-100">
            {showLabel && (
                <div className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4 flex items-center gap-2">
                    <Flag size={12} />
                    {label}
                </div>
            )}
            <div className="flex items-center w-full overflow-x-auto py-2 scrollbar-hide">
                {sortedMilestones.map((milestone, index) => (
                    <React.Fragment key={milestone.id}>
                        {index > 0 && (
                            <div className={`flex-1 min-w-[20px] h-0.5 transition-colors ${sortedMilestones[index - 1].state === 1 ? lineCompletedClassName : linePendingClassName
                                }`} />
                        )}

                        <div className="flex flex-col items-center flex-shrink-0 group">
                            <button
                                onClick={() => onToggle(milestone.id, milestone.state === 1 ? 0 : 1)}
                                className={`relative w-10 h-10 rounded-full border-2 flex items-center justify-center transition-all duration-300 hover:scale-110 ${milestone.state === 1 ? completedClassName : pendingClassName
                                    }`}
                                title={milestone.content}
                            >
                                {milestone.state === 1 ? (
                                    <Check size={18} strokeWidth={3} />
                                ) : (
                                    <span className="text-xs font-bold">{index + 1}</span>
                                )}
                            </button>

                            <div className="mt-2 max-w-[100px] text-center">
                                <p className="text-[10px] text-slate-500 font-medium truncate px-1" title={milestone.content}>
                                    {milestone.content || `Milestone ${index + 1}`}
                                </p>
                                {milestone.finishTime && (
                                    <p className="text-[9px] text-green-500 font-medium mt-0.5">
                                        {milestone.finishTime}
                                    </p>
                                )}
                            </div>
                        </div>
                    </React.Fragment>
                ))}
            </div>
        </div>
    );
};

export default MilestoneAxis;