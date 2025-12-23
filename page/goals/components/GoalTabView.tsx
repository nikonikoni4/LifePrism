
import React, { useState } from 'react';
import { Plus, ChevronRight, Folder } from 'lucide-react';
import { MOCK_GOALS_LIST, MOCK_CATEGORIES } from '../api';
import { UserGoal } from '../types';

interface GoalTabViewProps {
  onSelectGoal: (goalId: string) => void;
}

const GoalTabView: React.FC<GoalTabViewProps> = ({ onSelectGoal }) => {
  // Use local state to handle updates for immediate UI feedback
  const [goals, setGoals] = useState<UserGoal[]>(MOCK_GOALS_LIST);
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null);

  const handleCategoryChange = (goalId: string, categoryId: string) => {
    setGoals(prev => prev.map(g =>
      g.id === goalId ? { ...g, categoryId: categoryId || undefined } : g
    ));
    setOpenDropdownId(null);
  };

  return (
    <div className="space-y-10 animate-fade-in pb-20">
      <div className="flex justify-between items-center">
        <h3 className="text-2xl font-bold text-slate-800 tracking-tight">The Big Picture</h3>
        <button className="flex items-center gap-2 px-8 py-4 bg-blue-600 text-white rounded-[1.25rem] text-[10px] font-bold uppercase tracking-widest shadow-xl shadow-blue-500/20 hover:scale-105 transition-all">
          <Plus size={18} strokeWidth={2.5} /> New Mission
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
        {goals.map(goal => {
          const activeCategory = MOCK_CATEGORIES.find(c => c.id === goal.categoryId);
          const isDropdownOpen = openDropdownId === goal.id;

          return (
            <div key={goal.id} className="p-10 rounded-[3rem] bg-white border border-slate-200/40 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.05)] hover:shadow-xl transition-all relative overflow-visible group">
              <div className="absolute -top-10 -right-10 w-48 h-48 bg-blue-50 rounded-full blur-3xl opacity-30 group-hover:scale-125 transition-transform" />
              <div className="relative z-10 h-full flex flex-col">

                {/* Header Row: Alias & Category & Date */}
                <div className="flex items-center justify-between mb-8 relative">
                  <div className="flex items-center gap-2 flex-wrap">
                    {/* Alias Tag */}
                    <span className="px-4 py-1.5 bg-blue-50 text-blue-600 text-[10px] font-bold uppercase tracking-widest rounded-xl border border-blue-100 whitespace-nowrap">
                      {goal.alias || 'Goal'}
                    </span>

                    {/* Custom Category Dropdown */}
                    <div className="relative">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenDropdownId(isDropdownOpen ? null : goal.id);
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
                          {activeCategory ? activeCategory.name : 'Link Category'}
                        </span>
                      </button>

                      {/* Dropdown Menu */}
                      {isDropdownOpen && (
                        <>
                          <div className="fixed inset-0 z-40 cursor-default" onClick={(e) => { e.stopPropagation(); setOpenDropdownId(null); }} />
                          <div className="absolute top-full left-0 mt-2 w-48 bg-white/90 backdrop-blur-xl border border-white/40 shadow-2xl rounded-2xl overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-200 p-2 ring-1 ring-black/5">
                            <div className="px-3 py-2 text-[9px] font-black text-slate-300 uppercase tracking-widest">Select Category</div>
                            <div className="space-y-1">
                              <button
                                onClick={(e) => { e.stopPropagation(); handleCategoryChange(goal.id, ''); }}
                                className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-bold transition-all ${!goal.categoryId
                                    ? 'bg-slate-100 text-slate-800'
                                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                                  }`}
                              >
                                <div className="w-2 h-2 rounded-full border border-slate-300"></div>
                                No Category
                              </button>
                              {MOCK_CATEGORIES.map(c => (
                                <button
                                  key={c.id}
                                  onClick={(e) => { e.stopPropagation(); handleCategoryChange(goal.id, c.id); }}
                                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-bold transition-all ${goal.categoryId === c.id
                                      ? 'bg-slate-100 text-slate-800'
                                      : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                                    }`}
                                >
                                  <div className="w-2 h-2 rounded-full shadow-sm" style={{ backgroundColor: c.color }}></div>
                                  {c.name}
                                </button>
                              ))}
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  <span className="text-[10px] text-slate-400 font-mono font-semibold whitespace-nowrap ml-2">
                    {goal.expectedFinishedAt}
                  </span>
                </div>

                <h4 className="text-3xl font-bold text-slate-800 mb-5">{goal.name}</h4>
                <p className="text-base text-slate-500 font-medium mb-10 leading-relaxed line-clamp-3">{goal.content}</p>

                <div className="mt-auto flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-[9px] text-slate-400 uppercase font-black tracking-widest mb-1.5 opacity-60">Estimated Effort</span>
                    <span className="text-2xl font-mono font-bold text-slate-800">{goal.estimatedDuration}</span>
                  </div>
                  <button
                    onClick={() => onSelectGoal(goal.id)}
                    className="w-14 h-14 bg-slate-50 text-slate-400 rounded-2xl flex items-center justify-center hover:bg-blue-600 hover:text-white transition-all shadow-inner group-hover:scale-110 active:scale-95"
                  >
                    <ChevronRight size={28} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default GoalTabView;
