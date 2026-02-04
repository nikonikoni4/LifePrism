import React from 'react';
import { MilestoneItem } from '../../../../../types';

interface MilestoneProgressBarProps {
  milestones: MilestoneItem[];
  accentColor?: string;
  showCount?: boolean;
  maxDots?: number;
}

const MilestoneProgressBar: React.FC<MilestoneProgressBarProps> = ({
  milestones,
  accentColor = '#6366f1',
  showCount = true,
  maxDots = 6,
}) => {
  if (!milestones || milestones.length === 0) {
    return null;
  }

  const sortedMilestones = [...milestones].sort((a, b) => a.orderIndex - b.orderIndex);
  const completedCount = milestones.filter(m => m.state === 1).length;
  const totalCount = milestones.length;

  // If too many milestones, show abbreviated version
  const displayMilestones = sortedMilestones.length > maxDots
    ? sortedMilestones.slice(0, maxDots)
    : sortedMilestones;
  const hasMore = sortedMilestones.length > maxDots;

  return (
    <div className="flex items-center gap-2">
      {/* Dot indicators */}
      <div className="flex items-center gap-1">
        {displayMilestones.map((milestone, index) => (
          <React.Fragment key={milestone.id}>
            {index > 0 && (
              <div
                className="w-2 h-0.5 rounded-full transition-colors"
                style={{
                  backgroundColor: displayMilestones[index - 1].state === 1
                    ? accentColor
                    : '#e2e8f0'
                }}
              />
            )}
            <div
              className="w-2.5 h-2.5 rounded-full transition-all"
              style={{
                backgroundColor: milestone.state === 1 ? accentColor : 'transparent',
                border: `2px solid ${milestone.state === 1 ? accentColor : '#cbd5e1'}`,
              }}
              title={milestone.content}
            />
          </React.Fragment>
        ))}
        {hasMore && (
          <span className="text-[10px] text-slate-400 ml-0.5">...</span>
        )}
      </div>

      {/* Count label */}
      {showCount && (
        <span className="text-xs font-semibold text-slate-500 tabular-nums">
          {completedCount}/{totalCount}
        </span>
      )}
    </div>
  );
};

export default MilestoneProgressBar;
