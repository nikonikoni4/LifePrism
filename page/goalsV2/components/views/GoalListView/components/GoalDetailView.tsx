
import React from 'react';
import { motion } from 'framer-motion';
import {
  Clock, ChevronLeft, RefreshCw,
  MoreVertical, Sun, Moon, Coffee, Zap, Pencil
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
      <div className={`absolute left-[56px] top-0 bottom-0 w-px bg-gradient-to-b ${themeConfig.timelineLine}`} />

      <div className="space-y-8">
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
              <span className="text-xs font-bold text-slate-400 font-mono">{entry.date}</span>
              <MoodIcon mood={entry.mood} />
            </div>

            {/* Right: Content Card */}
            <div className={`flex-1 relative group`}>
              {/* Connector */}
              <div className="absolute left-[-25px] top-5 w-1.5 h-1.5 rounded-full bg-white border border-slate-200 shadow-sm z-20 group-hover:scale-125 transition-transform duration-300" />

              <div className="bg-white/60 backdrop-blur-md border border-white/60 p-5 rounded-2xl shadow-sm hover:shadow-md hover:bg-white/80 transition-all duration-300">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    {entry.tags?.map(tag => (
                      <span key={tag} className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${themeConfig.tag}`}>
                        {tag}
                      </span>
                    ))}
                  </div>
                  <span className="text-xs font-mono text-slate-300">{entry.time}</span>
                </div>

                <p className="text-slate-700 text-sm leading-relaxed mb-3">
                  {entry.content}
                </p>

                <div className="flex justify-end border-t border-slate-100/50 pt-2">
                  <span className="text-xs font-bold text-slate-400 flex items-center gap-1">
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
  theme: ThemeKey | string;
}

const GoalDetailView: React.FC<GoalDetailViewProps> = ({ goal, onClose, onUpdate, theme }) => {
  const themeConfig = THEMES[theme] || THEMES.indigo;

  const handleMilestoneToggle = (id: string, newState: number) => {
    if (!goal.milestones) return;

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
      <div className="sticky top-0 z-40 px-6 py-4 flex justify-between items-center bg-[#F8FAFC]/80 backdrop-blur-md">
        <button onClick={onClose} className="p-2 rounded-full hover:bg-slate-100 transition-colors text-slate-500">
          <ChevronLeft size={24} />
        </button>
        <div className="flex gap-2">
          <button className="p-2 rounded-full hover:bg-slate-100 transition-colors text-slate-400 hover:text-indigo-500">
            <RefreshCw size={20} />
          </button>
          <button className="p-2 rounded-full hover:bg-slate-100 transition-colors text-slate-400 hover:text-slate-800">
            <MoreVertical size={20} />
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 pb-32">
        {/* 1. The Horizon */}
        <section className="py-10 text-center relative">
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="mb-8"
          >
            <CategoryLabel theme={goal.theme}>{goal.category}</CategoryLabel>
            <h1 className="text-2xl md:text-3xl font-serif text-slate-900 mt-4 mb-2">{goal.title}</h1>
            <p className="text-slate-400 text-sm font-medium">{goal.startDate} — {goal.endDate}</p>
          </motion.div>

          <div className="grid grid-cols-2 gap-4 max-w-lg mx-auto mb-12">
            <div className="bg-white/40 border border-white/60 p-6 rounded-3xl backdrop-blur-sm">
              <div className={`text-2xl font-light tabular-nums mb-1 text-slate-800`}>{goal.timeInvested}</div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Total Hours</div>
            </div>
            <div className="bg-white/40 border border-white/60 p-6 rounded-3xl backdrop-blur-sm">
              <div className={`text-2xl font-light tabular-nums mb-1 text-slate-800`}>{goal.daysStarted || 0}</div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Days Active</div>
            </div>
          </div>
        </section>

        {/* 2. The Milestones Track */}
        <section className="mb-12">
          <MilestoneAxis
            milestones={goal.milestones || []}
            onToggle={handleMilestoneToggle}
            label="Milestones"
            completedClassName={`${themeConfig.progressBg} border-transparent text-white shadow-lg`}
            lineCompletedClassName={themeConfig.progressBg}
          />
        </section>

        {/* 3. The Reflection Timeline */}
        <section>
          <div className="flex items-center justify-between px-2 mb-8">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Journey Log</h3>
            <div className="h-px flex-1 bg-slate-200 ml-4 mr-4"></div>
            <span className="text-[10px] font-bold text-slate-300">{goal.journal?.length || 0} Records</span>
          </div>
          <ReflectionTimeline entries={goal.journal || []} theme={goal.theme} />
        </section>

      </div>

      {/* Floating Record Button */}
      <motion.button
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        className="fixed bottom-10 right-8 w-14 h-14 bg-slate-900 text-white rounded-full shadow-2xl flex items-center justify-center z-50 hover:bg-slate-800"
      >
        <Pencil size={20} />
      </motion.button>

    </motion.div>
  );
};

export default GoalDetailView;
