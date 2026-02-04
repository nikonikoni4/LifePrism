import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, ChevronUp, ChevronDown, RefreshCw, AlertCircle, Target } from 'lucide-react';
import { useGoalStore } from '../../../hooks/useGoalStore';
import { useGoalPageContext } from '../../../context/GoalPageContext';
import { Goal } from '../../../types';
import { viewBackground } from '../../shared/backgroundStyles';
import GoalCardV2 from './components/GoalCardV2';
import AddGoalModal from './components/AddGoalModal';
import GoalDetailView from './components/GoalDetailView';

export const GoalListView: React.FC = () => {
  const { goals, isLoading, error, fetchGoals, addGoal, updateGoal, deleteGoal, toggleGoalStatus, updateMilestoneState, updateMilestones, addJournal } = useGoalStore();
  const { selectedGoalId, setSelectedGoalId } = useGoalPageContext();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCompletedExpanded, setIsCompletedExpanded] = useState(false);

  // Derived state
  const activeGoals = goals.filter(g => g.status === 'active');
  const completedGoals = goals.filter(g => g.status === 'completed');
  const selectedGoal = goals.find(g => g.id === selectedGoalId) || null;

  // Handlers
  const handleCardClick = (id: string) => {
    setSelectedGoalId(id);
  };

  const handleCloseDetail = () => {
    setSelectedGoalId(null);
  };

  const openAddModal = () => {
    setIsModalOpen(true);
  };

  const handleSaveGoal = async (goal: Goal) => {
    try {
      await addGoal(goal);
    } catch (err) {
      console.error('Failed to save goal:', err);
    }
  };

  const handleUpdateGoal = async (goal: Goal) => {
    try {
      await updateGoal(goal);
    } catch (err) {
      console.error('Failed to update goal:', err);
    }
  };

  const handleToggleStatus = async (id: string) => {
    try {
      await toggleGoalStatus(id);
    } catch (err) {
      console.error('Failed to toggle status:', err);
    }
  };

  const handleDeleteGoal = async (id: string) => {
    if (window.confirm('确定要删除这个目标吗？')) {
      try {
        await deleteGoal(id);
      } catch (err) {
        console.error('Failed to delete goal:', err);
      }
    }
  };

  return (
    <div className={`h-full relative flex flex-col ${viewBackground.className}`} style={viewBackground.style}>
      {/* Scrollable Container */}
      <div className="flex-1 h-full overflow-y-auto p-6 md:p-8 scrollbar-hide">
        <AnimatePresence mode="wait">
          {/* Loading State */}
          {isLoading && !selectedGoal && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center h-full gap-4"
            >
              <RefreshCw size={32} className="text-slate-400 animate-spin" />
              <p className="text-slate-400 text-sm font-medium">加载目标中...</p>
            </motion.div>
          )}

          {/* Error State */}
          {error && !isLoading && !selectedGoal && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center h-full gap-4"
            >
              <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center">
                <AlertCircle size={32} className="text-red-500" />
              </div>
              <p className="text-slate-600 text-sm font-medium">{error}</p>
              <button
                onClick={() => fetchGoals()}
                className="px-4 py-2 bg-slate-900 text-white rounded-xl text-sm font-medium hover:bg-slate-800 transition-colors flex items-center gap-2"
              >
                <RefreshCw size={14} />
                重试
              </button>
            </motion.div>
          )}

          {!isLoading && !error && !selectedGoal && (
            <motion.main
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="relative z-10 pb-10 max-w-5xl mx-auto"
            >
              {/* Header */}
              <header className="mb-8">
                <div className="flex items-center gap-4 mb-2">
                  <div className="p-2.5 bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl text-indigo-600">
                    <Target size={28} />
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                      目标管理
                    </h1>
                    <p className="text-slate-500 text-sm font-medium">
                      追踪你的长期目标，保持专注
                    </p>
                  </div>
                </div>
              </header>

              {/* Stats Summary */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
                <div className="bg-white rounded-[1.25rem] border border-slate-100 p-4">
                  <div className="text-2xl font-bold text-slate-800 tabular-nums">{activeGoals.length}</div>
                  <div className="text-xs font-medium text-slate-400">进行中</div>
                </div>
                <div className="bg-white rounded-[1.25rem] border border-slate-100 p-4">
                  <div className="text-2xl font-bold text-slate-800 tabular-nums">{completedGoals.length}</div>
                  <div className="text-xs font-medium text-slate-400">已完成</div>
                </div>
                <div className="bg-white rounded-[1.25rem] border border-slate-100 p-4">
                  <div className="text-2xl font-bold text-slate-800 tabular-nums">
                    {goals.reduce((sum, g) => sum + (parseInt(g.timeInvested) || 0), 0)}
                  </div>
                  <div className="text-xs font-medium text-slate-400">总投入小时</div>
                </div>
                <div className="bg-white rounded-[1.25rem] border border-slate-100 p-4">
                  <div className="text-2xl font-bold text-slate-800 tabular-nums">
                    {goals.reduce((sum, g) => sum + (g.milestones?.filter(m => m.state === 1).length || 0), 0)}
                  </div>
                  <div className="text-xs font-medium text-slate-400">里程碑完成</div>
                </div>
              </div>

              {/* Active Goals Section */}
              <section className="mb-10">
                <div className="flex items-center gap-4 mb-5">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">进行中</h2>
                  <div className="h-px flex-1 bg-slate-200"></div>
                  <span className="text-xs font-bold text-slate-400 tabular-nums">{activeGoals.length}</span>
                </div>

                <div className="grid grid-cols-1 gap-4">
                  <AnimatePresence mode='popLayout'>
                    {activeGoals.map(goal => (
                      <GoalCardV2
                        key={goal.id}
                        goal={goal}
                        onClick={handleCardClick}
                        onDelete={handleDeleteGoal}
                        onToggleStatus={handleToggleStatus}
                      />
                    ))}

                    {/* Add Button */}
                    <motion.button
                      onClick={openAddModal}
                      layout
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      whileHover={{ y: -2, borderColor: '#6366f1' }}
                      whileTap={{ scale: 0.98 }}
                      className="w-full min-h-[180px] rounded-[1.25rem] border-2 border-dashed border-slate-200 flex flex-col items-center justify-center gap-3 text-slate-400 hover:text-indigo-500 transition-all bg-white/50"
                    >
                      <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center group-hover:bg-indigo-100 transition-colors">
                        <Plus size={24} />
                      </div>
                      <span className="font-semibold text-sm">添加新目标</span>
                    </motion.button>
                  </AnimatePresence>
                </div>
              </section>

              {/* Completed Goals Section */}
              {completedGoals.length > 0 && (
                <section className="border-t border-slate-200 pt-8">
                  <button
                    onClick={() => setIsCompletedExpanded(!isCompletedExpanded)}
                    className="w-full flex items-center gap-4 group mb-5"
                  >
                    <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 group-hover:text-slate-600 transition-colors">
                      已完成
                    </h2>
                    <div className="h-px flex-1 bg-slate-200 group-hover:bg-slate-300 transition-colors"></div>
                    <div className="flex items-center gap-2 text-slate-400 group-hover:text-slate-600 transition-colors">
                      <span className="text-xs font-bold tabular-nums">{completedGoals.length}</span>
                      {isCompletedExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </div>
                  </button>

                  <AnimatePresence>
                    {isCompletedExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="grid grid-cols-1 gap-4">
                          {completedGoals.map(goal => (
                            <GoalCardV2
                              key={goal.id}
                              goal={goal}
                              onClick={handleCardClick}
                              onDelete={handleDeleteGoal}
                              onToggleStatus={handleToggleStatus}
                            />
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </section>
              )}
            </motion.main>
          )}
        </AnimatePresence>
      </div>

      {/* Add Modal (simplified - create only) */}
      <AnimatePresence>
        {isModalOpen && (
          <AddGoalModal
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
            onSave={handleSaveGoal}
            goalToEdit={null}
          />
        )}
      </AnimatePresence>

      {/* Detail View (Focus Mode) */}
      <AnimatePresence>
        {selectedGoal && (
          <GoalDetailView
            goal={selectedGoal}
            onClose={handleCloseDetail}
            theme={selectedGoal.theme}
            onUpdate={handleUpdateGoal}
            onMilestoneToggle={updateMilestoneState}
            onMilestonesChange={updateMilestones}
            onAddJournal={addJournal}
          />
        )}
      </AnimatePresence>
    </div>
  );
};
