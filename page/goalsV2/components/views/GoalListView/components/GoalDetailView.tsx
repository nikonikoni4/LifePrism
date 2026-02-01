
import React from 'react';
import { motion } from 'framer-motion';
import {
  Clock, ChevronLeft, RefreshCw,
  MoreVertical, Sun, Moon, Coffee, Zap, Pencil, Target
} from 'lucide-react';
import { Goal, JournalEntry, ThemeKey } from '../../../../types';
import { THEMES } from '../../../../hooks/useGoalStore';
import { viewBackground } from '../../../shared/backgroundStyles';
import MilestoneAxis from './milestone/MilestoneAxis';
import { CategoryLabel } from './GoalCard';

// --- Reflection Timeline Component ---
const ReflectionTimeline = ({ entries, theme }: { entries: JournalEntry[], theme: ThemeKey | string }) => {
  const themeConfig = THEMES[theme] || THEMES.indigo;

  const MoodIcon = ({ mood }: { mood: string }) => {
    switch (mood) {
      case 'joy': return <div className="w-6 h-6 rounded-full bg-amber-100 text-amber-500 flex items-center justify-center"><Sun size={14} /></div>;
      case 'calm': return <div className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-500 flex items-center justify-center"><Coffee size={14} /></div>;
      case 'frustrated': return <div className="w-6 h-6 rounded-full bg-rose-100 text-rose-500 flex items-center justify-center"><Zap size={14} /></div>;
      default: return <div className="w-6 h-6 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center"><Moon size={14} /></div>;
    }
  };

  return (
    <div className="relative pl-4 pr-4 pb-20">
      {/* Vertical Line */}
      <div className="absolute left-[56px] top-0 bottom-0 w-px bg-slate-200" />

      <div className="space-y-6">
        {entries.map((entry, i) => (
          <motion.div
            key={entry.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className="relative flex gap-6"
          >
            {/* Left: Date & Mood */}
            <div className="flex flex-col items-end gap-2 w-10 pt-2 shrink-0 z-10">
              <span className="text-xs font-semibold text-slate-400">{entry.date}</span>
              <MoodIcon mood={entry.mood} />
            </div>

            {/* Right: Content Card */}
            <div className="flex-1 relative group">
              {/* Connector */}
              <div className="absolute left-[-25px] top-5 w-2 h-2 rounded-full bg-white border-2 border-slate-300 z-20 group-hover:border-slate-400 transition-colors" />

              <div className="bg-white border border-slate-100 p-5 rounded-[1.25rem] hover:border-slate-200 hover:shadow-sm transition-all duration-200">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    {entry.tags?.map(tag => (
                      <span key={tag} className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${themeConfig.tag}`}>
                        {tag}
                      </span>
                    ))}
                  </div>
                  <span className="text-xs font-medium text-slate-300">{entry.time}</span>
                </div>

                <p className="text-slate-700 text-sm leading-relaxed mb-3">
                  {entry.content}
                </p>

                <div className="flex justify-end border-t border-slate-100 pt-2">
                  <span className="text-xs font-semibold text-slate-400 flex items-center gap-1">
                    <Clock size={10} /> +{entry.duration}h
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

// --- Goal Detail View Component ---
interface GoalDetailViewProps {
  goal: Goal;
  onClose: () => void;
  onUpdate: (goal: Goal) => void;
  onMilestoneToggle?: (goalId: string, milestoneId: string, state: number) => Promise<void>;
  theme: ThemeKey | string;
}

const GoalDetailView: React.FC<GoalDetailViewProps> = ({ goal, onClose, onUpdate, onMilestoneToggle, theme }) => {
  const themeConfig = THEMES[theme] || THEMES.indigo;

  const handleMilestoneToggle = async (id: string, newState: number) => {
    if (!goal.milestones) return;

    // If API handler is provided, use it
    if (onMilestoneToggle) {
      try {
        await onMilestoneToggle(goal.id, id, newState);
      } catch (err) {
        console.error('Failed to update milestone:', err);
      }
      return;
    }

    // Fallback to local update (for backwards compatibility)
    const updatedMilestones = goal.milestones.map(m =>
      m.id === id
        ? { ...m, state: newState, finishTime: newState === 1 ? new Date().toLocaleDateString('en-US', { month: '2-digit', day: '2-digit' }) : null }
        : m
    );

    onUpdate({
      ...goal,
      milestones: updatedMilestones
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className={`fixed inset-0 z-50 overflow-y-auto ${viewBackground.className}`}
      style={viewBackground.style}
    >

      {/* Top Nav */}
      <div className="sticky top-0 z-40 px-6 py-4 flex justify-between items-center bg-[#F8FAFC]/80 backdrop-blur-md border-b border-slate-100">
        <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100 transition-colors text-slate-500">
          <ChevronLeft size={24} />
        </button>
        <div className="flex gap-2">
          <button className="p-2 rounded-xl hover:bg-slate-100 transition-colors text-slate-400 hover:text-slate-600">
            <RefreshCw size={20} />
          </button>
          <button className="p-2 rounded-xl hover:bg-slate-100 transition-colors text-slate-400 hover:text-slate-600">
            <MoreVertical size={20} />
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 pb-32">
        {/* Header Section */}
        <section className="py-8">
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="mb-8"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-xl" style={{ backgroundColor: `${themeConfig.accentColor}15` }}>
                <Target size={20} style={{ color: themeConfig.accentColor }} />
              </div>
              <CategoryLabel theme={goal.theme}>{goal.category}</CategoryLabel>
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">{goal.title}</h1>
            <p className="text-slate-400 text-sm font-medium">{goal.startDate} — {goal.endDate}</p>
          </motion.div>

          {/* Stats Cards */}
          <div className="grid grid-cols-2 gap-4 mb-8">
            <div className="bg-white rounded-[1.25rem] border border-slate-100 p-5">
              <div className="text-2xl font-bold text-slate-800 tabular-nums mb-1">{goal.timeInvested}</div>
              <div className="text-xs font-medium text-slate-400">总投入小时</div>
            </div>
            <div className="bg-white rounded-[1.25rem] border border-slate-100 p-5">
              <div className="text-2xl font-bold text-slate-800 tabular-nums mb-1">{goal.daysStarted || 0}</div>
              <div className="text-xs font-medium text-slate-400">活跃天数</div>
            </div>
          </div>
        </section>

        {/* Milestones Section */}
        <section className="mb-10">
          <MilestoneAxis
            milestones={goal.milestones || []}
            onToggle={handleMilestoneToggle}
            label="里程碑"
            completedClassName={`${themeConfig.progressBg} border-transparent text-white shadow-md`}
            lineCompletedClassName={themeConfig.progressBg}
          />
        </section>

        {/* Journal Timeline Section */}
        <section>
          <div className="flex items-center justify-between px-2 mb-6">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500">日志记录</h3>
            <div className="h-px flex-1 bg-slate-200 ml-4 mr-4"></div>
            <span className="text-xs font-semibold text-slate-400 tabular-nums">{goal.journal?.length || 0} 条</span>
          </div>
          <ReflectionTimeline entries={goal.journal || []} theme={goal.theme} />
        </section>

      </div>

      {/* Floating Record Button */}
      <motion.button
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className="fixed bottom-8 right-8 w-14 h-14 bg-slate-900 text-white rounded-2xl shadow-xl shadow-slate-900/20 flex items-center justify-center z-50 hover:bg-slate-800 transition-colors"
      >
        <Pencil size={20} />
      </motion.button>

    </motion.div>
  );
};

export default GoalDetailView;
