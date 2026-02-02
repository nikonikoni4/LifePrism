import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Calendar, Check, ChevronDown, ChevronUp, Trash2, Maximize2,
  Quote, HeartHandshake, Clock
} from 'lucide-react';
import { Goal, ThemeKey, MilestoneItem, JournalEntry } from '../../../../types';
import { THEMES } from '../../../../hooks/useGoalStore';
import { formatDateForDisplay } from '../../../../api';
import InlineEditableTitle from './InlineEditableTitle';
import InlineEditableTextarea from './InlineEditableTextarea';
import MilestoneProgressBar from './milestone/MilestoneProgressBar';
import ExpandedMilestoneSection from './milestone/ExpandedMilestoneSection';
import QuickConfigPanel from './QuickConfigPanel';
import JournalPreview from './JournalPreview';

interface GoalCardV2Props {
  goal: Goal;
  isExpanded: boolean;
  onToggleExpand: (id: string) => void;
  onUpdate: (goal: Goal) => Promise<void>;
  onDelete: (id: string) => void;
  onToggleStatus: (id: string) => void;
  onMilestoneToggle: (goalId: string, milestoneId: string, state: number) => Promise<void>;
  onAddJournal: (goalId: string, journal: Omit<JournalEntry, 'id'>) => Promise<void>;
  onFocusMode?: (id: string) => void;
}

export const CategoryLabel = ({ children }: { children: React.ReactNode }) => {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/70 text-[10px] font-bold tracking-wider uppercase text-slate-600 backdrop-blur-sm">
      {children}
    </span>
  );
};

const GoalCardV2: React.FC<GoalCardV2Props> = ({
  goal,
  isExpanded,
  onToggleExpand,
  onUpdate,
  onDelete,
  onToggleStatus,
  onMilestoneToggle,
  onAddJournal,
  onFocusMode,
}) => {
  const [isSaving, setIsSaving] = useState(false);
  const [pendingChanges, setPendingChanges] = useState<Partial<Goal>>({});

  const isCompleted = goal.status === 'completed';
  const theme = THEMES[goal.theme] || THEMES.indigo;

  // Calculate days started
  const daysStarted = goal.startDate
    ? Math.max(0, Math.floor((Date.now() - new Date(goal.startDate).getTime()) / (1000 * 60 * 60 * 24)))
    : 0;

  // Merge pending changes with goal for display
  const displayGoal = { ...goal, ...pendingChanges };

  // Debounced update handler
  const handleFieldChange = useCallback((field: keyof Goal, value: any) => {
    setPendingChanges(prev => ({ ...prev, [field]: value }));
  }, []);

  // Save all pending changes
  const handleSave = async () => {
    if (Object.keys(pendingChanges).length === 0) return;

    setIsSaving(true);
    try {
      await onUpdate({ ...goal, ...pendingChanges });
      setPendingChanges({});
    } catch (err) {
      console.error('Failed to save goal:', err);
    } finally {
      setIsSaving(false);
    }
  };

  // Handle milestone state toggle
  const handleMilestoneToggle = async (milestoneId: string, newState: number) => {
    try {
      await onMilestoneToggle(goal.id, milestoneId, newState);
    } catch (err) {
      console.error('Failed to toggle milestone:', err);
    }
  };

  // Handle milestones change (from editor)
  const handleMilestonesChange = (milestones: MilestoneItem[]) => {
    handleFieldChange('milestones', milestones);
  };

  // Handle journal add
  const handleAddJournal = async (journal: Omit<JournalEntry, 'id'>) => {
    await onAddJournal(goal.id, journal);
  };

  const hasPendingChanges = Object.keys(pendingChanges).length > 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={`relative rounded-[1.25rem] transition-all duration-300 overflow-hidden ${
        isCompleted ? 'opacity-60 grayscale' : ''
      }`}
      style={{
        background: isCompleted
          ? '#f1f5f9'
          : `linear-gradient(135deg, ${theme.accentColor}10 0%, ${theme.accentColor}20 100%)`,
        border: `1px solid ${isCompleted ? '#e2e8f0' : theme.accentColor}20`,
      }}
    >
      {/* Theme Color Bar */}
      <div
        className="h-1 w-full"
        style={{ backgroundColor: theme.accentColor }}
      />

      <div className="p-5">
        {/* Header: Category & Actions */}
        <div className="flex items-start justify-between mb-3">
          <CategoryLabel>{displayGoal.category || '未分类'}</CategoryLabel>

          {/* Action Buttons - Always visible */}
          <div className="flex items-center gap-1">
            {onFocusMode && (
              <button
                onClick={(e) => { e.stopPropagation(); onFocusMode(goal.id); }}
                className="p-1.5 hover:bg-white/50 rounded-lg transition-colors text-slate-400 hover:text-slate-600"
                title="专注模式"
              >
                <Maximize2 size={14} />
              </button>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(goal.id); }}
              className="p-1.5 hover:bg-red-100/50 rounded-lg transition-colors text-slate-400 hover:text-red-500"
              title="删除"
            >
              <Trash2 size={14} />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onToggleStatus(goal.id); }}
              className="p-1.5 rounded-lg transition-colors flex items-center justify-center"
              style={{
                backgroundColor: isCompleted ? '#e2e8f0' : `${theme.accentColor}20`,
                color: isCompleted ? '#94a3b8' : theme.accentColor,
              }}
              title={isCompleted ? '标记为进行中' : '标记为完成'}
            >
              <Check size={14} />
            </button>
          </div>
        </div>

        {/* Title - Inline Editable */}
        <div className="mb-4">
          <InlineEditableTitle
            value={displayGoal.title}
            onChange={(value) => handleFieldChange('title', value)}
            className="text-lg font-semibold leading-snug text-slate-800"
            isCompleted={isCompleted}
          />
        </div>

        {/* Stats Row */}
        <div className="flex items-center gap-4 mb-4">
          {/* Time Invested */}
          <div className="flex items-center gap-2 px-3 py-2 bg-white/60 rounded-xl">
            <Clock size={14} className="text-slate-400" />
            <span className="text-lg font-bold tabular-nums text-slate-800">
              {displayGoal.timeInvested}
            </span>
            <span className="text-[10px] font-medium text-slate-400 uppercase">
              {displayGoal.unit || 'HRS'}
            </span>
          </div>

          {/* Days Started */}
          <div className="flex items-center gap-2 px-3 py-2 bg-white/60 rounded-xl">
            <Calendar size={14} className="text-slate-400" />
            <span className="text-lg font-bold tabular-nums text-slate-800">
              {daysStarted}
            </span>
            <span className="text-[10px] font-medium text-slate-400">天</span>
          </div>

          {/* Milestone Progress */}
          {displayGoal.milestones && displayGoal.milestones.length > 0 && (
            <div className="flex items-center gap-2 px-3 py-2 bg-white/60 rounded-xl">
              <MilestoneProgressBar
                milestones={displayGoal.milestones}
                accentColor={theme.accentColor}
              />
            </div>
          )}
        </div>

        {/* Date Range */}
        <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-4">
          <Calendar size={12} />
          <span className="font-medium">
            {formatDateForDisplay(displayGoal.startDate)} — {formatDateForDisplay(displayGoal.endDate)}
          </span>
        </div>

        {/* Expand/Collapse Button */}
        <button
          onClick={() => onToggleExpand(goal.id)}
          className="w-full flex items-center justify-center gap-2 py-2 text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-white/50 rounded-xl transition-colors"
        >
          {isExpanded ? (
            <>
              收起详情 <ChevronUp size={16} />
            </>
          ) : (
            <>
              展开详情 <ChevronDown size={16} />
            </>
          )}
        </button>

        {/* Expanded Section */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="pt-4 space-y-5 border-t border-slate-200/50 mt-4">
                {/* Milestones Section */}
                <ExpandedMilestoneSection
                  milestones={displayGoal.milestones || []}
                  onMilestoneToggle={handleMilestoneToggle}
                  onMilestonesChange={handleMilestonesChange}
                  accentColor={theme.accentColor}
                  progressBgClass={theme.progressBg}
                />

                {/* Core Drive Section */}
                <div className="space-y-4">
                  <InlineEditableTextarea
                    value={displayGoal.value}
                    onChange={(value) => handleFieldChange('value', value)}
                    label="价值意义"
                    icon={
                      <div className="w-6 h-6 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-500">
                        <Quote size={10} />
                      </div>
                    }
                    placeholder="这个目标对你有什么意义？"
                  />

                  <InlineEditableTextarea
                    value={displayGoal.commitment}
                    onChange={(value) => handleFieldChange('commitment', value)}
                    label="每日承诺"
                    icon={
                      <div className="w-6 h-6 rounded-lg bg-rose-50 flex items-center justify-center text-rose-500">
                        <HeartHandshake size={10} />
                      </div>
                    }
                    placeholder="你每天会做什么来推进这个目标？"
                  />
                </div>

                {/* Quick Config Panel */}
                <QuickConfigPanel
                  theme={displayGoal.theme}
                  category={displayGoal.category}
                  startDate={displayGoal.startDate}
                  endDate={displayGoal.endDate}
                  trackTimeAutomatically={displayGoal.trackTimeAutomatically}
                  timeInvested={displayGoal.timeInvested}
                  onThemeChange={(value) => handleFieldChange('theme', value)}
                  onCategoryChange={(value) => handleFieldChange('category', value)}
                  onStartDateChange={(value) => handleFieldChange('startDate', value)}
                  onEndDateChange={(value) => handleFieldChange('endDate', value)}
                  onTrackModeChange={(value) => handleFieldChange('trackTimeAutomatically', value)}
                  onTimeInvestedChange={(value) => handleFieldChange('timeInvested', value)}
                />

                {/* Journal Preview */}
                <JournalPreview
                  goalId={goal.id}
                  journals={goal.journal || []}
                  onAddJournal={handleAddJournal}
                  themeTag={theme.tag}
                />

                {/* Save Button */}
                {hasPendingChanges && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="pt-4 border-t border-slate-200/50"
                  >
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSave();
                      }}
                      disabled={isSaving}
                      className="w-full py-3 bg-slate-900 text-white rounded-xl font-medium shadow-lg shadow-slate-900/20 hover:bg-slate-800 active:scale-[0.98] transition-all text-sm disabled:opacity-70 flex items-center justify-center gap-2"
                    >
                      {isSaving ? '保存中...' : '保存更改'}
                    </button>
                  </motion.div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

export default GoalCardV2;
