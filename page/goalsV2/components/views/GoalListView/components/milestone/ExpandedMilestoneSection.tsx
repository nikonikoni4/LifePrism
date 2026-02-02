import React, { useState } from 'react';
import { Pencil, Eye } from 'lucide-react';
import { MilestoneItem, EditableMilestone } from '../../../../../types';
import MilestoneAxis from './MilestoneAxis';
import MilestoneEditor from './MilestoneEditor';
import { convertToEditableMilestones } from './utils';

interface ExpandedMilestoneSectionProps {
  milestones: MilestoneItem[];
  onMilestoneToggle: (id: string, newState: number) => void;
  onMilestonesChange: (milestones: MilestoneItem[]) => void;
  accentColor?: string;
  progressBgClass?: string;
}

const ExpandedMilestoneSection: React.FC<ExpandedMilestoneSectionProps> = ({
  milestones,
  onMilestoneToggle,
  onMilestonesChange,
  accentColor = '#6366f1',
  progressBgClass = 'bg-indigo-500',
}) => {
  const [isEditMode, setIsEditMode] = useState(false);

  const handleEditableMilestonesChange = (editableMilestones: EditableMilestone[]) => {
    // Convert EditableMilestone back to MilestoneItem, preserving state and finishTime
    const updated: MilestoneItem[] = editableMilestones.map(em => {
      const existing = milestones.find(m => m.id === em.id);
      return {
        id: em.id,
        content: em.content,
        orderIndex: em.orderIndex,
        state: existing?.state || 0,
        finishTime: existing?.finishTime || null,
      };
    });
    onMilestonesChange(updated);
  };

  const hasMilestones = milestones && milestones.length > 0;

  return (
    <div className="space-y-3">
      {/* Header with toggle */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
          里程碑
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsEditMode(!isEditMode);
          }}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-slate-500 hover:bg-slate-100 transition-colors"
        >
          {isEditMode ? (
            <>
              <Eye size={12} />
              查看
            </>
          ) : (
            <>
              <Pencil size={12} />
              编辑
            </>
          )}
        </button>
      </div>

      {/* Content */}
      {isEditMode ? (
        <MilestoneEditor
          milestones={convertToEditableMilestones(milestones)}
          onChange={handleEditableMilestonesChange}
          label=""
          addButtonText="添加里程碑"
          maxHeight="16rem"
        />
      ) : hasMilestones ? (
        <MilestoneAxis
          milestones={milestones}
          onToggle={onMilestoneToggle}
          showLabel={false}
          completedClassName={`${progressBgClass} border-transparent text-white shadow-md`}
          lineCompletedClassName={progressBgClass}
        />
      ) : (
        <div className="text-center py-6 bg-slate-50 rounded-xl border border-dashed border-slate-200">
          <p className="text-sm text-slate-400 mb-2">暂无里程碑</p>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsEditMode(true);
            }}
            className="text-xs font-medium text-indigo-500 hover:text-indigo-600 transition-colors"
          >
            点击添加
          </button>
        </div>
      )}
    </div>
  );
};

export default ExpandedMilestoneSection;
