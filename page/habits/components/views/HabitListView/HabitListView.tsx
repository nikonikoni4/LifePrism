import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, ChevronDown, ChevronUp, Sprout, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { useHabitStore } from '../../../hooks/useHabitStore';
import { useHabitPageContext } from '../../../context/HabitPageContext';
import { Habit, CreateHabitForm, HabitStats } from '../../../types';
import HabitCard from './components/HabitCard';
import HabitHeatmap from './components/HabitHeatmap';
import AddHabitModal from './components/AddHabitModal';
import HabitHistoryModal from './components/HabitHistoryModal';
import { AnchorTimeline } from './components/AnchorTimeline';
import { HabitChainFlow } from './components/HabitChainFlow';

// Background style matching GoalsV2 - using teal instead of amber
const viewBackground = {
  className: 'bg-gradient-to-br from-slate-50 via-teal-50/30 to-cyan-50/20',
  style: {}
};

// Lightweight Today Progress Bar component
const TodayProgressBar: React.FC<{ stats: HabitStats | null }> = ({ stats }) => {
  if (!stats) {
    return (
      <div className="bg-white rounded-2xl border border-slate-100 p-4 mb-6">
        <div className="animate-pulse">
          <div className="h-4 bg-slate-200 rounded w-1/3 mb-2" />
          <div className="h-2 bg-slate-100 rounded-full" />
        </div>
      </div>
    );
  }

  const total = stats.todayCompleted + stats.todayPending;
  const percent = total > 0 ? (stats.todayCompleted / total) * 100 : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-2xl border border-slate-100 p-4 mb-6"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-slate-700">今日进度</span>
        <span className="text-sm text-slate-500">
          {stats.todayCompleted}/{total} · 待完成 {stats.todayPending}
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="h-full bg-teal-500 rounded-full"
        />
      </div>
    </motion.div>
  );
};

// Stats Footer component
const StatsFooter: React.FC<{ stats: HabitStats | null }> = ({ stats }) => {
  if (!stats) return null;

  return (
    <div className="mt-8 pt-6 border-t border-slate-200 text-center text-sm text-slate-500">
      <span>{stats.activeHabitsCount} 个活跃</span>
      <span className="mx-2">·</span>
      <span>{Math.round(stats.weeklyCompletionRate * 100)}% 本周完成率</span>
      <span className="mx-2">·</span>
      <span>{stats.totalCheckIns} 次累计打卡</span>
      <span className="mx-2">·</span>
      <span>{stats.currentStreak} 天连续</span>
    </div>
  );
};

export const HabitListView: React.FC = () => {
  const {
    habits,
    stats,
    heatmapData,
    isLoading,
    addHabit,
    updateHabit,
    deleteHabit,
    checkIn,
    pauseHabit,
    resumeHabit
  } = useHabitStore();

  const { selectedHabitId, setSelectedHabitId } = useHabitPageContext();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingHabit, setEditingHabit] = useState<Habit | null>(null);
  const [historyHabitId, setHistoryHabitId] = useState<string | null>(null);
  const [isPausedExpanded, setIsPausedExpanded] = useState(false);
  const [checkedToday, setCheckedToday] = useState<Set<string>>(new Set());
  const [isTimelinePanelOpen, setIsTimelinePanelOpen] = useState(true);

  // Derived state
  const activeHabits = useMemo(() =>
    habits.filter(h => h.status === 'active'),
    [habits]
  );

  const pausedHabits = useMemo(() =>
    habits.filter(h => h.status === 'paused'),
    [habits]
  );

  // Handlers
  const handleAddHabit = async (data: CreateHabitForm) => {
    await addHabit(data);
  };

  const handleEditHabit = (habit: Habit) => {
    setEditingHabit(habit);
    setIsModalOpen(true);
  };

  const handleSaveHabit = async (data: CreateHabitForm) => {
    if (editingHabit) {
      await updateHabit(editingHabit.id, data);
    } else {
      await addHabit(data);
    }
    setEditingHabit(null);
  };

  const handleCheckIn = async (habitId: string) => {
    const today = new Date().toISOString().split('T')[0];
    await checkIn(habitId, today);
    setCheckedToday(prev => new Set([...prev, habitId]));
  };

  const handlePause = async (habitId: string) => {
    await pauseHabit(habitId);
  };

  const handleResume = async (habitId: string) => {
    await resumeHabit(habitId);
  };

  const handleDelete = async (habitId: string) => {
    if (window.confirm('确定要删除这个习惯吗？此操作不可撤销。')) {
      await deleteHabit(habitId);
    }
  };

  const handleViewHistory = (habitId: string) => {
    setHistoryHabitId(habitId);
  };

  const openAddModal = () => {
    setEditingHabit(null);
    setIsModalOpen(true);
  };

  return (
    <div className={`h-full relative flex ${viewBackground.className}`} style={viewBackground.style}>
      {/* Main Content Area - Left Side */}
      <div className={`flex-1 h-full overflow-y-auto p-6 md:p-8 scrollbar-hide transition-all duration-300 ${
        isTimelinePanelOpen ? 'lg:pr-4' : ''
      }`}>
        <motion.main
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative z-10 pb-10 max-w-4xl"
        >
          {/* Header */}
          <header className="mb-8 flex items-end justify-between">
            <div>
              <div className="text-xs font-bold text-teal-600 tracking-[0.2em] mb-2 uppercase flex items-center gap-2">
                <Sprout size={12} />
                习惯养成
              </div>
              <h1 className="text-3xl md:text-4xl font-sans font-bold text-slate-900 tracking-tight">
                习惯养成
              </h1>
              <p className="text-sm text-slate-400 mt-1">坚持每一天，成就更好的自己</p>
            </div>
            <div className="hidden sm:flex items-center gap-4">
              <div className="text-right">
                <div className="text-sm font-medium text-slate-400 mb-1">活跃习惯</div>
                <div className="text-3xl font-light tabular-nums text-slate-800">{activeHabits.length}</div>
              </div>
              {/* Timeline Panel Toggle - Only visible on lg screens */}
              <button
                onClick={() => setIsTimelinePanelOpen(!isTimelinePanelOpen)}
                className="hidden lg:flex items-center gap-1 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-500 hover:text-teal-600 hover:border-teal-200 transition-colors"
                title={isTimelinePanelOpen ? '收起时间轴' : '展开时间轴'}
              >
                {isTimelinePanelOpen ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
              </button>
            </div>
          </header>

          {/* Heatmap - at the top */}
          <HabitHeatmap data={heatmapData} className="mb-6" />

          {/* Today Progress Bar */}
          <TodayProgressBar stats={stats} />

          {/* Habit Chain Flow - New Component */}
          <HabitChainFlow className="mb-6" />

          {/* Active Habits Section */}
          <section className="mb-10">
            <div className="flex items-center gap-4 mb-6">
              <h2 className="text-sm font-bold uppercase tracking-widest text-slate-400">进行中</h2>
              <div className="h-px flex-1 bg-gradient-to-r from-slate-200 to-transparent"></div>
            </div>

            {isLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-48 bg-white rounded-[1.25rem] animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <AnimatePresence mode="popLayout">
                  {activeHabits.map(habit => (
                    <HabitCard
                      key={habit.id}
                      habit={habit}
                      onCheckIn={handleCheckIn}
                      onEdit={handleEditHabit}
                      onPause={handlePause}
                      onResume={handleResume}
                      onViewHistory={handleViewHistory}
                      onDelete={handleDelete}
                      isCheckedToday={checkedToday.has(habit.id)}
                    />
                  ))}

                  {/* Add Button */}
                  <motion.button
                    layout
                    onClick={openAddModal}
                    whileHover={{ scale: 1.02, backgroundColor: 'rgba(241, 245, 249, 0.8)' }}
                    whileTap={{ scale: 0.98 }}
                    className="h-48 rounded-[1.25rem] border-2 border-dashed border-slate-200 flex flex-col items-center justify-center gap-3 text-slate-400 hover:text-teal-500 hover:border-teal-200 transition-all group bg-slate-50/50"
                  >
                    <div className="w-12 h-12 rounded-full bg-white shadow-sm flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                      <Plus size={24} />
                    </div>
                    <span className="font-bold tracking-widest text-xs uppercase">新增习惯</span>
                  </motion.button>
                </AnimatePresence>
              </div>
            )}
          </section>

          {/* Paused Habits Section */}
          {pausedHabits.length > 0 && (
            <section className="mt-12 border-t border-slate-100/50 pt-8">
              <button
                onClick={() => setIsPausedExpanded(!isPausedExpanded)}
                className="w-full flex items-center gap-4 group mb-6 hover:opacity-80 transition-opacity"
              >
                <h2 className="text-sm font-bold uppercase tracking-widest text-slate-400 group-hover:text-slate-600 transition-colors">
                  已暂停
                </h2>
                <div className="h-px flex-1 bg-slate-100 group-hover:bg-slate-200 transition-colors"></div>
                <div className="flex items-center gap-2 text-slate-300 group-hover:text-slate-500 transition-colors">
                  <span className="text-xs font-bold">{pausedHabits.length}</span>
                  {isPausedExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </div>
              </button>

              <AnimatePresence>
                {isPausedExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {pausedHabits.map(habit => (
                        <HabitCard
                          key={habit.id}
                          habit={habit}
                          onCheckIn={handleCheckIn}
                          onEdit={handleEditHabit}
                          onPause={handlePause}
                          onResume={handleResume}
                          onViewHistory={handleViewHistory}
                          onDelete={handleDelete}
                        />
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </section>
          )}

          {/* Stats Footer */}
          <StatsFooter stats={stats} />
        </motion.main>
      </div>

      {/* Right Side Panel - Timeline (Desktop Only) */}
      <AnimatePresence>
        {isTimelinePanelOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 360, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="hidden lg:block h-full border-l border-slate-100 bg-white/50 backdrop-blur-sm overflow-hidden"
          >
            <div className="h-full overflow-y-auto p-4 scrollbar-hide">
              <AnchorTimeline />
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Mobile Timeline Toggle Button */}
      <button
        onClick={() => setIsTimelinePanelOpen(!isTimelinePanelOpen)}
        className="lg:hidden fixed bottom-6 right-6 z-20 w-14 h-14 rounded-full bg-teal-500 text-white shadow-lg flex items-center justify-center hover:bg-teal-600 transition-colors"
      >
        {isTimelinePanelOpen ? <PanelRightClose size={24} /> : <PanelRightOpen size={24} />}
      </button>

      {/* Mobile Timeline Drawer */}
      <AnimatePresence>
        {isTimelinePanelOpen && (
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="lg:hidden fixed inset-y-0 right-0 w-[85%] max-w-sm bg-white shadow-2xl z-30 overflow-hidden"
          >
            <div className="h-full overflow-y-auto p-4 scrollbar-hide">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-slate-800">时间锚点</h3>
                <button
                  onClick={() => setIsTimelinePanelOpen(false)}
                  className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  <PanelRightClose size={20} className="text-slate-500" />
                </button>
              </div>
              <AnchorTimeline />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Mobile Overlay */}
      <AnimatePresence>
        {isTimelinePanelOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsTimelinePanelOpen(false)}
            className="lg:hidden fixed inset-0 bg-black/30 z-20"
          />
        )}
      </AnimatePresence>

      {/* Add/Edit Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <AddHabitModal
            isOpen={isModalOpen}
            onClose={() => { setIsModalOpen(false); setEditingHabit(null); }}
            onSave={handleSaveHabit}
            habitToEdit={editingHabit}
          />
        )}
      </AnimatePresence>

      {/* History Modal */}
      <AnimatePresence>
        {historyHabitId && (
          <HabitHistoryModal
            isOpen={!!historyHabitId}
            onClose={() => setHistoryHabitId(null)}
            habitId={historyHabitId}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default HabitListView;
