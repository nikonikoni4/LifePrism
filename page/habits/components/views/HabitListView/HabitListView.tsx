import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import { useHabitStore } from '../../../hooks/useHabitStore';
import { useHabitPageContext } from '../../../context/HabitPageContext';
import { Habit, CreateHabitForm } from '../../../types';
import HabitCard from './components/HabitCard';
import HabitStatsCard from './components/HabitStatsCard';
import HabitHeatmap from './components/HabitHeatmap';
import AddHabitModal from './components/AddHabitModal';
import HabitHistoryModal from './components/HabitHistoryModal';

// Background style matching GoalsV2
const viewBackground = {
  className: 'bg-gradient-to-br from-slate-50 via-amber-50/30 to-orange-50/20',
  style: {}
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
    <div className={`h-full relative flex flex-col ${viewBackground.className}`} style={viewBackground.style}>
      {/* Scrollable Container */}
      <div className="flex-1 h-full overflow-y-auto p-6 md:p-8 scrollbar-hide">
        <motion.main
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative z-10 pb-10 max-w-5xl mx-auto"
        >
          {/* Header */}
          <header className="mb-8 flex items-end justify-between">
            <div>
              <div className="text-xs font-bold text-amber-500 tracking-[0.2em] mb-2 uppercase flex items-center gap-2">
                <Zap size={12} />
                习惯养成
              </div>
              <h1 className="text-3xl md:text-4xl font-sans font-bold text-slate-900 tracking-tight">
                Habits<span className="text-slate-200">.</span>
              </h1>
            </div>
            <div className="hidden sm:block text-right">
              <div className="text-sm font-medium text-slate-400 mb-1">活跃习惯</div>
              <div className="text-3xl font-light tabular-nums text-slate-800">{activeHabits.length}</div>
            </div>
          </header>

          {/* Stats Card */}
          <HabitStatsCard stats={stats} className="mb-6" />

          {/* Heatmap */}
          <HabitHeatmap data={heatmapData} className="mb-8" />

          {/* Active Habits Section */}
          <section className="mb-10">
            <div className="flex items-center gap-4 mb-6">
              <h2 className="text-sm font-bold uppercase tracking-widest text-slate-400">进行中</h2>
              <div className="h-px flex-1 bg-gradient-to-r from-slate-200 to-transparent"></div>
            </div>

            {isLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-48 bg-white rounded-[1.25rem] animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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
                    className="h-48 rounded-[1.25rem] border-2 border-dashed border-slate-200 flex flex-col items-center justify-center gap-3 text-slate-400 hover:text-amber-500 hover:border-amber-200 transition-all group bg-slate-50/50"
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
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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
        </motion.main>
      </div>

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
