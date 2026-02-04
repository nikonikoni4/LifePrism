import React, { useState } from 'react';
import { Pencil } from 'lucide-react';
import { MilestoneItem } from '../../../../../types';
import MilestoneAxis from './MilestoneAxis';
import MilestoneEditorModal from './MilestoneEditorModal';

interface MilestoneSectionProps {
  milestones: MilestoneItem[];
  onMilestoneToggle: (id: string, newState: number) => void;
  onMilestonesChange: (milestones: MilestoneItem[]) => void;
  completedClassName?: string;
  lineCompletedClassName?: string;
}

const MilestoneSection: React.FC<MilestoneSectionProps> = ({
  milestones,
  onMilestoneToggle,
  onMilestonesChange,
  completedClassName,
  lineCompletedClassName,
}) => {
  const [isEditorOpen, setIsEditorOpen] = useState(false);

  if (!milestones || milestones.length === 0) {
    return (
      <div className="mb-6 p-4 bg-gradient-to-r from-slate-50 to-white rounded-2xl border border-slate-100">
        <div className="flex items-center justify-between mb-4">
          <div className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] flex items-center gap-2">
            里程碑
          </div>
          <button
            onClick={() => setIsEditorOpen(true)}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-indigo-500 hover:bg-indigo-50 transition-colors"
          >
            <Pencil size={12} />
            添加
          </button>
        </div>
        <div className="text-center py-4 text-sm text-slate-400">
          暂无里程碑，点击添加
        </div>

        {isEditorOpen && (
          <MilestoneEditorModal
            milestones={milestones}
            onSave={onMilestonesChange}
            onClose={() => setIsEditorOpen(false)}
          />
        )}
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Edit Button - positioned at top right */}
      <div className="absolute top-4 right-4 z-10">
        <button
          onClick={() => setIsEditorOpen(true)}
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-indigo-500 hover:bg-indigo-50 transition-colors"
        >
          <Pencil size={12} />
          编辑
        </button>
      </div>

      <MilestoneAxis
        milestones={milestones}
        onToggle={onMilestoneToggle}
        label="里程碑"
        completedClassName={completedClassName}
        lineCompletedClassName={lineCompletedClassName}
      />

      {isEditorOpen && (
        <MilestoneEditorModal
          milestones={milestones}
          onSave={onMilestonesChange}
          onClose={() => setIsEditorOpen(false)}
        />
      )}
    </div>
  );
};

export default MilestoneSection;
