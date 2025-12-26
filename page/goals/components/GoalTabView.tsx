
import React, { useState, useEffect } from 'react';
import { Plus, ChevronRight, Folder, Loader2, CheckCircle, Calendar, Trash2 } from 'lucide-react';
import { goalApi, categoryApi } from '../api';
import { UserGoal, CategoryTreeItem } from '../types';
import CategorySelectionModal from './CategorySelectionModal';

interface GoalTabViewProps {
  onSelectGoal: (goalId: number) => void;
}

const GoalTabView: React.FC<GoalTabViewProps> = ({ onSelectGoal }) => {
  // Goals state
  const [goals, setGoals] = useState<UserGoal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Categories state
  const [categories, setCategories] = useState<CategoryTreeItem[]>([]);

  // Modal State
  const [showCategoryDialog, setShowCategoryDialog] = useState(false);
  const [editingGoal, setEditingGoal] = useState<UserGoal | null>(null);

  // Load goals and categories on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [goalsResponse, categoriesResponse] = await Promise.all([
          goalApi.getGoals(),
          categoryApi.getCategoryTree(2)
        ]);
        setGoals(goalsResponse.items);
        setCategories(categoriesResponse.data);
      } catch (err) {
        setError('Failed to load goals');
        console.error('Failed to load goals:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const openCategoryModal = (goal: UserGoal) => {
    setEditingGoal(goal);
    setShowCategoryDialog(true);
  };

  const handleApplyCategory = async (categoryId: string | null, subCategoryId: string | null) => {
    if (editingGoal) {
      try {
        // Call API to update category
        const updatedGoal = await goalApi.updateGoal(editingGoal.id, {
          linkToCategoryId: categoryId || undefined,
          linkToSubCategoryId: subCategoryId || undefined
        });

        // Update local state with the returned goal (which has category names)
        setGoals(prev => prev.map(g =>
          g.id === editingGoal.id ? updatedGoal : g
        ));
      } catch (err) {
        console.error('Failed to update goal category:', err);
      }
    }
    setShowCategoryDialog(false);
    setEditingGoal(null);
  };

  const handleCreateGoal = async () => {
    try {
      const newGoal = await goalApi.createGoal({
        name: 'New Goal',
        content: '',
        color: '#FFFFFF'
      });
      setGoals(prev => [...prev, newGoal]);
      // Navigate to detail view for editing
      onSelectGoal(newGoal.id);
    } catch (err) {
      console.error('Failed to create goal:', err);
    }
  };

  const handleDeleteGoal = async (goalId: number) => {
    if (!confirm('确定要删除这个目标吗？')) return;
    try {
      await goalApi.deleteGoal(goalId);
      setGoals(prev => prev.filter(g => g.id !== goalId));
    } catch (err) {
      console.error('Failed to delete goal:', err);
    }
  };

  // Helper function to find category info by name (backend returns names, not IDs)
  const findCategoryByName = (categoryName: string | undefined) => {
    if (!categoryName) return null;
    return categories.find(c => c.name === categoryName);
  };

  const findSubCategoryByName = (category: CategoryTreeItem | null, subCategoryName: string | undefined) => {
    if (!category || !subCategoryName || !category.subcategories) return null;
    return category.subcategories.find(s => s.name === subCategoryName);
  };

  // Helper to get category ID from name for modal (modal works with IDs)
  const findCategoryIdByName = (categoryName: string | undefined) => {
    const cat = findCategoryByName(categoryName);
    return cat?.id || null;
  };

  const findSubCategoryIdByName = (categoryName: string | undefined, subCategoryName: string | undefined) => {
    const cat = findCategoryByName(categoryName);
    const sub = findSubCategoryByName(cat, subCategoryName);
    return sub?.id || null;
  };

  // Format expected hours for display
  const formatHours = (hours: number | undefined) => {
    if (!hours) return '-';
    if (hours >= 24) {
      return `${Math.floor(hours / 24)}d ${hours % 24}h`;
    }
    return `${hours}h`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-red-500">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-10 animate-fade-in pb-20">
      <div className="flex justify-between items-center">
        <h3 className="text-2xl font-bold text-slate-800 tracking-tight">The Big Picture</h3>
        <button
          onClick={handleCreateGoal}
          className="flex items-center gap-2 px-8 py-4 bg-blue-600 text-white rounded-[1.25rem] text-[10px] font-bold uppercase tracking-widest shadow-xl shadow-blue-500/20 hover:scale-105 transition-all"
        >
          <Plus size={18} strokeWidth={2.5} /> New Mission
        </button>
      </div>

      {goals.length === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <p className="text-lg mb-4">No goals yet. Create your first mission!</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
          {goals.map(goal => {
            const activeCategory = findCategoryByName(goal.linkToCategory);
            const activeSubCategory = findSubCategoryByName(activeCategory, goal.linkToSubCategory);

            return (
              <div
                key={goal.id}
                className="p-8 rounded-[2.5rem] border border-slate-200/40 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.05)] hover:shadow-xl transition-all relative overflow-hidden group"
                style={{ backgroundColor: goal.color || '#FFFFFF' }}
              >
                <div className="relative z-10 h-full flex flex-col">

                  {/* Header Row: Status, Category & Actions */}
                  <div className="flex items-center justify-between mb-6 relative">
                    <div className="flex items-center gap-2 flex-wrap">
                      {/* Status Badge */}
                      <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-bold uppercase tracking-widest ${goal.status === 'completed'
                        ? 'bg-green-100 text-green-700 border border-green-200'
                        : goal.status === 'archived'
                          ? 'bg-slate-100 text-slate-500 border border-slate-200'
                          : 'bg-blue-50 text-blue-600 border border-blue-100'
                        }`}>
                        {goal.status === 'completed' && <CheckCircle size={12} />}
                        {goal.status === 'completed' ? '已完成' : goal.status === 'archived' ? '已归档' : '进行中'}
                      </div>

                      {/* Category Button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openCategoryModal(goal);
                        }}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-all hover:scale-105 active:scale-95 ${activeCategory
                          ? 'bg-white border-slate-200 shadow-sm text-slate-700'
                          : 'bg-slate-50 border-slate-200 border-dashed text-slate-400 hover:bg-white hover:border-blue-200 hover:text-blue-500'
                          }`}
                      >
                        {activeCategory ? (
                          <div className="w-2 h-2 rounded-full shadow-sm" style={{ backgroundColor: activeCategory.color }} />
                        ) : (
                          <Folder size={12} strokeWidth={2.5} />
                        )}
                        <span className="text-[10px] font-bold uppercase tracking-widest">
                          {activeCategory ? (
                            <span>{activeCategory.name} {activeSubCategory && <span className="text-slate-400">/ {activeSubCategory.name}</span>}</span>
                          ) : '分类'}
                        </span>
                      </button>
                    </div>

                    {/* Delete Button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteGoal(goal.id);
                      }}
                      className="p-2 rounded-xl text-slate-300 hover:text-red-500 hover:bg-red-50 transition-all opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>

                  {/* Title */}
                  <h4 className="text-2xl font-bold text-slate-800 mb-3">{goal.name}</h4>
                  <p className="text-sm text-slate-500 font-medium mb-6 leading-relaxed line-clamp-2">{goal.abstract || goal.content || ''}</p>

                  {/* Date Info Row */}
                  <div className="flex items-center gap-4 mb-6 text-[10px] text-slate-400 font-medium">
                    <div className="flex items-center gap-1.5">
                      <Calendar size={12} />
                      <span>创建: {goal.createdAt?.slice(0, 10) || '-'}</span>
                    </div>
                    {goal.expectedFinishedAt && (
                      <div className="flex items-center gap-1.5">
                        <span>→</span>
                        <span>预计: {goal.expectedFinishedAt}</span>
                      </div>
                    )}
                  </div>

                  {/* Footer: Effort & Action */}
                  <div className="mt-auto flex items-center justify-between">
                    <div className="flex flex-col">
                      <span className="text-[9px] text-slate-400 uppercase font-black tracking-widest mb-1 opacity-60">预计时长</span>
                      <span className="text-xl font-mono font-bold text-slate-800">{formatHours(goal.expectedHours)}</span>
                    </div>
                    <button
                      onClick={() => onSelectGoal(goal.id)}
                      className="w-12 h-12 bg-slate-50 text-slate-400 rounded-xl flex items-center justify-center hover:bg-blue-600 hover:text-white transition-all shadow-inner group-hover:scale-110 active:scale-95"
                    >
                      <ChevronRight size={24} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Category Selection Modal */}
      <CategorySelectionModal
        isOpen={showCategoryDialog}
        onClose={() => {
          setShowCategoryDialog(false);
          setEditingGoal(null);
        }}
        categories={categories.map(c => ({
          id: c.id,
          name: c.name,
          color: c.color,
          subCategories: c.subcategories?.map(s => ({ id: s.id, name: s.name })) || []
        }))}
        initialCategoryId={editingGoal ? findCategoryIdByName(editingGoal.linkToCategory) : undefined}
        initialSubCategoryId={editingGoal ? findSubCategoryIdByName(editingGoal.linkToCategory, editingGoal.linkToSubCategory) : undefined}
        onApply={handleApplyCategory}
      />
    </div>
  );
};

export default GoalTabView;
