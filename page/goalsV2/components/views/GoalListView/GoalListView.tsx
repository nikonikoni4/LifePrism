import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, ChevronUp, ChevronDown } from 'lucide-react';
import { useGoalStore } from '../../../hooks/useGoalStore';
import { useGoalPageContext } from '../../../context/GoalPageContext';
import { Goal } from '../../shared/types';
import { viewBackground } from '../../shared/background';
import GoalCard from './components/GoalCard';
import AddGoalModal from './components/AddGoalModal';
import GoalDetailView from './components/GoalDetailView';

export const GoalListView: React.FC = () => {
  const { goals, addGoal, updateGoal, deleteGoal, toggleGoalStatus } = useGoalStore();
  const { selectedGoalId, setSelectedGoalId } = useGoalPageContext();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingGoal, setEditingGoal] = useState<Goal | null>(null);
  const [isCompletedExpanded, setIsCompletedExpanded] = useState(false);

  // Derived state
  const activeGoals = goals.filter(g => g.status === 'active');
  const completedGoals = goals.filter(g => g.status === 'completed');
  const selectedGoal = goals.find(g => g.id === selectedGoalId) || null;

  // Handlers
  const handleGoalClick = (id: string) => {
    setSelectedGoalId(id);
  };

  const handleCloseDetail = () => {
    setSelectedGoalId(null);
  };

  const openAddModal = () => {
    setEditingGoal(null);
    setIsModalOpen(true);
  };

  const openEditModal = (goal: Goal) => {
    setEditingGoal(goal);
    setIsModalOpen(true);
  };

  const handleSaveGoal = (goal: Goal) => {
    if (goals.some(g => g.id === goal.id)) {
      updateGoal(goal);
    } else {
      addGoal(goal);
    }
  };

  return (
    <div className={`h-full relative flex flex-col ${viewBackground.className}`} style={viewBackground.style}>
      {/* Scrollable Container with Padding */}
      <div className="flex-1 h-full overflow-y-auto p-6 md:p-8 scrollbar-hide">
        <AnimatePresence mode="wait">
          {!selectedGoal && (
            <motion.main
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="relative z-10 pb-10"
            >
              <header className="mb-8 flex items-end justify-between">
                <div>
                  <div className="text-xs font-bold text-indigo-500 tracking-[0.2em] mb-2 uppercase">Your Dashboard</div>
                  <h1 className="text-3xl md:text-4xl font-serif text-slate-900 tracking-tight">Focus<span className="text-slate-200">.</span></h1>
                </div>
                <div className="hidden sm:block text-right">
                  <div className="text-sm font-medium text-slate-400 mb-1">Active Targets</div>
                  <div className="text-3xl font-light tabular-nums text-slate-800">{activeGoals.length}</div>
                </div>
              </header>

              {/* Active Goals Section */}
              <section className="mb-10">
                <div className="flex items-center gap-4 mb-6">
                  <h2 className="text-sm font-bold uppercase tracking-widest text-slate-400">In Progress</h2>
                  <div className="h-px flex-1 bg-gradient-to-r from-slate-200 to-transparent"></div>
                </div>

                {/* Use grid-cols-1 by default, 2 columns only on very large screens or single pane view */}
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                  <AnimatePresence mode='popLayout'>
                    {activeGoals.map(goal => (
                      <GoalCard
                        key={goal.id}
                        goal={goal}
                        onClick={() => handleGoalClick(goal.id)}
                        onToggleStatus={toggleGoalStatus}
                      />
                    ))}

                    {/* Add Button */}
                    <motion.button
                      onClick={openAddModal}
                      whileHover={{ scale: 1.02, backgroundColor: 'rgba(241, 245, 249, 0.8)' }}
                      whileTap={{ scale: 0.98 }}
                      className="w-full h-60 rounded-[1.5rem] border-2 border-dashed border-slate-200 flex flex-col items-center justify-center gap-4 text-slate-400 hover:text-indigo-500 hover:border-indigo-200 transition-all group bg-slate-50/50"
                    >
                      <div className="w-14 h-14 rounded-full bg-white shadow-sm flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                        <Plus size={28} />
                      </div>
                      <span className="font-bold tracking-widest text-xs uppercase">New Target</span>
                    </motion.button>
                  </AnimatePresence>
                </div>
              </section>

              {/* Completed Goals Section */}
              <section className="mt-12 border-t border-slate-100/50 pt-8">
                <button
                  onClick={() => setIsCompletedExpanded(!isCompletedExpanded)}
                  className="w-full flex items-center gap-4 group mb-6 hover:opacity-80 transition-opacity"
                >
                  <h2 className="text-sm font-bold uppercase tracking-widest text-slate-400 group-hover:text-slate-600 transition-colors">
                    Archived
                  </h2>
                  <div className="h-px flex-1 bg-slate-100 group-hover:bg-slate-200 transition-colors"></div>
                  <div className="flex items-center gap-2 text-slate-300 group-hover:text-slate-500 transition-colors">
                    <span className="text-xs font-bold">{completedGoals.length}</span>
                    {isCompletedExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </div>
                </button>

                <AnimatePresence>
                  {isCompletedExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                        {completedGoals.map(goal => (
                          <GoalCard
                            key={goal.id}
                            goal={goal}
                            onClick={() => handleGoalClick(goal.id)}
                            onToggleStatus={toggleGoalStatus}
                          />
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </section>
            </motion.main>
          )}
        </AnimatePresence>
      </div>

      {/* Add/Edit Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <AddGoalModal
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
            onSave={handleSaveGoal}
            goalToEdit={editingGoal}
          />
        )}
      </AnimatePresence>

      {/* Detail View */}
      <AnimatePresence>
        {selectedGoal && (
          <GoalDetailView
            goal={selectedGoal}
            onClose={handleCloseDetail}
            theme={selectedGoal.theme}
            onUpdate={updateGoal}
          />
        )}
      </AnimatePresence>
    </div>
  );
};
