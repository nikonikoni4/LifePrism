import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Clock, ChevronLeft, Calendar, Target, Quote, HeartHandshake
} from 'lucide-react';
import { Goal, JournalEntry, ThemeKey, MilestoneItem } from '../../../../types';
import { THEMES } from '../../../../hooks/useGoalStore';
import { CategoryLabel } from './GoalCardV2';
import { formatDateForDisplay } from '../../../../api';
import QuickConfigPanel from './QuickConfigPanel';
import MilestoneSection from './milestone/MilestoneSection';
import JournalPreview from './JournalPreview';
import InlineEditableTitle from './InlineEditableTitle';
import InlineEditableTextarea from './InlineEditableTextarea';

interface GoalDetailViewProps {
  goal: Goal;
  onClose: () => void;
  onUpdate: (goal: Goal) => void;
  onMilestoneToggle?: (goalId: string, milestoneId: string, state: number) => Promise<void>;
  onMilestonesChange?: (goalId: string, milestones: MilestoneItem[]) => Promise<void>;
  onAddJournal?: (goalId: string, journal: Omit<JournalEntry, 'id'>) => Promise<void>;
  theme: ThemeKey | string;
}

const GoalDetailView: React.FC<GoalDetailViewProps> = ({
  goal,
  onClose,
  onUpdate,
  onMilestoneToggle,
  onMilestonesChange,
  onAddJournal,
  theme
}) => {
  const themeConfig = THEMES[theme] || THEMES.indigo;
  const [isSaving, setIsSaving] = useState(false);
  const [pendingChanges, setPendingChanges] = useState<Partial<Goal>>({});

  // Calculate days started
  const daysStarted = goal.startDate
    ? Math.max(0, Math.floor((Date.now() - new Date(goal.startDate).getTime()) / (1000 * 60 * 60 * 24)))
    : 0;

  // Merge pending changes with goal for display
  const displayGoal = { ...goal, ...pendingChanges };

  // Field change handler
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
  const handleMilestoneToggle = async (id: string, newState: number) => {
    if (onMilestoneToggle) {
      try {
        await onMilestoneToggle(goal.id, id, newState);
      } catch (err) {
        console.error('Failed to update milestone:', err);
      }
    }
  };

  // Handle milestones change (from editor modal)
  const handleMilestonesChange = async (milestones: MilestoneItem[]) => {
    if (onMilestonesChange) {
      try {
        await onMilestonesChange(goal.id, milestones);
      } catch (err) {
        console.error('Failed to update milestones:', err);
      }
    }
  };

  // Handle journal add
  const handleAddJournal = async (journal: Omit<JournalEntry, 'id'>) => {
    if (onAddJournal) {
      await onAddJournal(goal.id, journal);
    }
  };

  const hasPendingChanges = Object.keys(pendingChanges).length > 0;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 overflow-y-auto"
      style={{
        background: `linear-gradient(135deg, ${themeConfig.accentColor}10 0%, ${themeConfig.accentColor}20 100%)`,
      }}
    >
      {/* Top Nav */}
      <div
        className="sticky top-0 z-40 px-6 py-4 flex justify-between items-center backdrop-blur-md border-b"
        style={{
          backgroundColor: `${themeConfig.accentColor}08`,
          borderColor: `${themeConfig.accentColor}20`,
        }}
      >
        <button
          onClick={onClose}
          className="p-2 rounded-xl hover:bg-white/50 transition-colors text-slate-500"
        >
          <ChevronLeft size={24} />
        </button>
        <div className="flex items-center gap-2">
          <CategoryLabel>{displayGoal.category || '未分类'}</CategoryLabel>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 pb-32">
        {/* Header Section */}
        <section className="py-8">
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="mb-6"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-xl" style={{ backgroundColor: `${themeConfig.accentColor}15` }}>
                <Target size={20} style={{ color: themeConfig.accentColor }} />
              </div>
            </div>
            <InlineEditableTitle
              value={displayGoal.title}
              onChange={(value) => handleFieldChange('title', value)}
              className="text-2xl font-bold leading-snug text-slate-800 mb-2"
            />
            <div className="flex items-center gap-1.5 text-sm text-slate-500">
              <Calendar size={14} />
              <span className="font-medium">
                {formatDateForDisplay(displayGoal.startDate)} — {formatDateForDisplay(displayGoal.endDate)}
              </span>
            </div>
          </motion.div>

          {/* Stats Cards */}
          <div className="grid grid-cols-2 gap-4 mb-8">
            <div className="bg-white/80 backdrop-blur-sm rounded-[1.25rem] border border-white/50 p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-1">
                <Calendar size={16} className="text-slate-400" />
                <span className="text-xs font-medium text-slate-400">已进行</span>
              </div>
              <div className="text-2xl font-bold text-slate-800 tabular-nums">
                {daysStarted}
                <span className="text-sm font-medium text-slate-400 ml-1">天</span>
              </div>
            </div>
            <div className="bg-white/80 backdrop-blur-sm rounded-[1.25rem] border border-white/50 p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-1">
                <Clock size={16} className="text-slate-400" />
                <span className="text-xs font-medium text-slate-400">已投入</span>
              </div>
              <div className="text-2xl font-bold text-slate-800 tabular-nums">
                {displayGoal.timeInvested}
                <span className="text-sm font-medium text-slate-400 ml-1">小时</span>
              </div>
            </div>
          </div>
        </section>

        {/* Core Drive Section */}
        <section className="mb-8 space-y-4">
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
        </section>

        {/* Quick Config Panel - Default Expanded */}
        <section className="mb-8">
          <QuickConfigPanel
            theme={displayGoal.theme}
            category={displayGoal.category}
            startDate={displayGoal.startDate}
            endDate={displayGoal.endDate}
            timeInvested={displayGoal.timeInvested}
            onThemeChange={(value) => handleFieldChange('theme', value)}
            onCategoryChange={(value) => handleFieldChange('category', value)}
            onStartDateChange={(value) => handleFieldChange('startDate', value)}
            onEndDateChange={(value) => handleFieldChange('endDate', value)}
            onTimeInvestedChange={(value) => handleFieldChange('timeInvested', value)}
            defaultExpanded={true}
          />
        </section>

        {/* Milestones Section */}
        <section className="mb-8">
          <MilestoneSection
            milestones={goal.milestones || []}
            onMilestoneToggle={handleMilestoneToggle}
            onMilestonesChange={handleMilestonesChange}
            completedClassName={`${themeConfig.progressBg} border-transparent text-white shadow-md`}
            lineCompletedClassName={themeConfig.progressBg}
          />
        </section>

        {/* Journal Section */}
        <section className="mb-8">
          <JournalPreview
            goalId={goal.id}
            journals={goal.journal || []}
            onAddJournal={handleAddJournal}
            themeTag={themeConfig.tag}
            maxDisplay={5}
          />
        </section>

        {/* Save Button - Fixed at bottom when there are pending changes */}
        {hasPendingChanges && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="fixed bottom-0 left-0 right-0 p-4 bg-white/80 backdrop-blur-md border-t border-slate-200 z-50"
          >
            <div className="max-w-3xl mx-auto">
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="w-full py-3 bg-slate-900 text-white rounded-xl font-medium shadow-lg shadow-slate-900/20 hover:bg-slate-800 active:scale-[0.98] transition-all text-sm disabled:opacity-70 flex items-center justify-center gap-2"
              >
                {isSaving ? '保存中...' : '保存更改'}
              </button>
            </div>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
};

export default GoalDetailView;
