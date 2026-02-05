import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, ChevronDown, ChevronUp, Sprout, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { useHabitStore } from '../../../hooks/useHabitStore';
import { useHabitPageContext } from '../../../context/HabitPageContext';
import { Habit, CreateHabitForm } from '../../../types';
import HabitCard from './components/HabitCard';
import HabitHeatmap from './components/HabitHeatmap';
import StatCards from './components/StatCards';
import WeeklyChart from './components/WeeklyChart';
import AddHabitModal from './components/AddHabitModal';
import HabitHistoryModal from './components/HabitHistoryModal';
import { AnchorTimeline } from './components/AnchorTimeline';
import { HabitChainFlow } from './components/HabitChainFlow';

// Warm amber gradient background
const viewBackground = {
  className: 'bg-gradient-to-br from-amber-50/40 via-yellow-50/20 to-orange-50/10',
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

  const { setSelectedHabitId } = useHabitPageContext();

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
    <div className={`h-full relative flex ${viewBackground.className}`}>
      {/* Main Content Area - Left Side */}
      <div className={`flex-1 h-full overflow-y-auto p-6 md:p-8 scrollbar-hide transition-all duration-300 ${
        isTimelinePanelOpen ? 'lg:pr-4' : ''
      }`}>
        <motion.main
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative z-10 pb-10 max-w-5xl"
        >
          {/* Header */}
          <header className="mb-8 flex items-end justify-between">
            <div>
              <div className="text-xs font-bold text-amber-600 tracking-[0.2em] mb-2 uppercase flex items-center gap-2">
                <Sprout size={12} />
                习惯养成
              </div>
              <h1 className="text-3xl md:text-4xl font-sans font-bold text-stone-900 tracking-tight">
                习惯养成（开发中）
              </h1>
              <p className="text-sm text-stone-400 mt-1">坚持每一天，成就更好的自己</p>
            </div>
            <div className="hidden sm:flex items-center gap-4">
              {/* Timeline Panel Toggle - Only visible on lg screens */}
              <button
                onClick={() => setIsTimelinePanelOpen(!isTimelinePanelOpen)}
                className="hidden lg:flex items-center gap-1 px-3 py-2 rounded-xl bg-white border border-stone-200 text-stone-500 hover:text-amber-600 hover:border-amber-200 transition-colors"
                title={isTimelinePanelOpen ? '收起时间轴' : '展开时间轴'}
              >
                {isTimelinePanelOpen ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
              </button>
            </div>
          </header>

          {/* Stat Cards - Top Row */}
          <StatCards stats={stats} activeHabitsCount={activeHabits.length} />

          {/* Charts Row - Bento Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            <WeeklyChart data={heatmapData} />
            <HabitHeatmap data={heatmapData} />
          </div>

          {/* Habit Chain Flow */}
          <HabitChainFlow className="mb-6" />

          {/* Active Habits Section */}
          <section className="mb-10">
            <div className="flex items-center gap-4 mb-6">
              <h2 className="text-sm font-bold uppercase tracking-widest text-stone-400">进行中</h2>
              <div className="h-px flex-1 bg-gradient-to-r from-stone-200 to-transparent"></div>
            </div>

            {isLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-52 bg-white rounded-3xl animate-pulse" />
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
                    whileHover={{ scale: 1.02, backgroundColor: 'rgba(254, 243, 199, 0.5)' }}
                    whileTap={{ scale: 0.98 }}
                    className="h-52 rounded-3xl border-2 border-dashed border-stone-200 flex flex-col items-center justify-center gap-3 text-stone-400 hover:text-amber-500 hover:border-amber-300 transition-all group bg-white/50"
                  >
                    <div className="w-14 h-14 rounded-2xl bg-white shadow-sm flex items-center justify-center group-hover:scale-110 group-hover:shadow-md group-hover:shadow-amber-200/50 transition-all duration-300">
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
            <section className="mt-12 border-t border-stone-100/50 pt-8">
              <button
                onClick={() => setIsPausedExpanded(!isPausedExpanded)}
                className="w-full flex items-center gap-4 group mb-6 hover:opacity-80 transition-opacity"
              >
                <h2 className="text-sm font-bold uppercase tracking-widest text-stone-400 group-hover:text-stone-600 transition-colors">
                  已暂停
                </h2>
                <div className="h-px flex-1 bg-stone-100 group-hover:bg-stone-200 transition-colors"></div>
                <div className="flex items-center gap-2 text-stone-300 group-hover:text-stone-500 transition-colors">
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
          {stats && (
            <div className="mt-8 pt-6 border-t border-stone-200 text-center text-sm text-stone-500">
              <span>{stats.activeHabitsCount} 个活跃</span>
              <span className="mx-2">·</span>
              <span>{Math.round(stats.weeklyCompletionRate * 100)}% 本周完成率</span>
              <span className="mx-2">·</span>
              <span>{stats.totalCheckIns} 次累计打卡</span>
              <span className="mx-2">·</span>
              <span>{stats.currentStreak} 天连续</span>
            </div>
          )}
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
            className="hidden lg:block h-full border-l border-stone-100 bg-white/60 backdrop-blur-sm overflow-hidden"
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
        className="lg:hidden fixed bottom-6 right-6 z-20 w-14 h-14 rounded-full bg-amber-400 text-white shadow-lg shadow-amber-400/30 flex items-center justify-center hover:bg-amber-500 transition-colors"
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
                <h3 className="font-semibold text-stone-800">时间锚点</h3>
                <button
                  onClick={() => setIsTimelinePanelOpen(false)}
                  className="p-2 rounded-lg hover:bg-stone-100 transition-colors"
                >
                  <PanelRightClose size={20} className="text-stone-500" />
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
