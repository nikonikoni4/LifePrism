import React, { useState } from 'react';
import { Check, Plus, Trophy } from 'lucide-react';
import { MOCK_GOALS } from '../../constants';
import { GoalItem } from '../../types';

const GoalsWidget: React.FC = () => {
  const [goals, setGoals] = useState<GoalItem[]>(MOCK_GOALS);

  const toggleGoal = (id: string) => {
    setGoals(prev => prev.map(g => 
      g.id === id ? { ...g, completed: !g.completed } : g
    ));
  };

  const completedCount = goals.filter(g => g.completed).length;
  const totalCount = goals.length;
  const progress = Math.round((completedCount / totalCount) * 100);

  const getTagStyle = (tag?: string) => {
    switch(tag?.toLowerCase()) {
        case 'dev': return 'bg-indigo-100 text-indigo-700 border-indigo-200';
        case 'work': return 'bg-blue-100 text-blue-700 border-blue-200';
        case 'health': return 'bg-green-100 text-green-700 border-green-200';
        case 'self': return 'bg-amber-100 text-amber-700 border-amber-200';
        default: return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 flex flex-col h-full relative overflow-hidden">
      {/* Decorative Elements */}
      <div className="absolute -top-12 -right-12 w-48 h-48 bg-gradient-to-br from-blue-50 to-purple-50 rounded-full blur-3xl pointer-events-none opacity-60"></div>

      {/* Header / Identity */}
      <div className="flex justify-between items-start mb-8 z-10">
        <div>
          <div className="inline-flex items-center px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-slate-600 text-xs font-bold uppercase tracking-wide mb-3">
            Full Stack Developer
          </div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Today's Focus</h2>
          <p className="text-slate-500 text-sm mt-1 font-medium">Your daily mission control.</p>
        </div>
        <div className="w-14 h-14 rounded-2xl bg-orange-50 border border-orange-100 flex items-center justify-center text-orange-500 shadow-sm">
          <Trophy size={24} strokeWidth={2.5} />
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-8 z-10">
        <div className="flex justify-between items-end mb-2">
          <span className="text-sm font-semibold text-slate-700">Daily Progress</span>
          <span className="text-2xl font-bold text-slate-900">{progress}%</span>
        </div>
        <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden shadow-inner">
            <div 
                className="h-full bg-morandi-blue rounded-full transition-all duration-1000 ease-out shadow-sm"
                style={{ width: `${progress}%` }}
            ></div>
        </div>
      </div>

      {/* Tasks List */}
      <div className="flex-1 overflow-y-auto no-scrollbar space-y-3 z-10 pr-2">
        {goals.map((goal) => (
          <div 
            key={goal.id}
            onClick={() => toggleGoal(goal.id)}
            className={`group flex items-center p-3.5 rounded-2xl border transition-all duration-200 cursor-pointer ${
              goal.completed 
                ? 'bg-gray-50 border-transparent opacity-60' 
                : 'bg-white border-gray-100 hover:border-blue-200 hover:shadow-md hover:shadow-blue-500/5'
            }`}
          >
            <div className={`w-6 h-6 rounded-lg border-2 mr-4 flex-shrink-0 flex items-center justify-center transition-all duration-300 ${
              goal.completed 
                ? 'bg-morandi-blue border-morandi-blue scale-100' 
                : 'border-gray-300 bg-white group-hover:border-morandi-blue'
            }`}>
              {goal.completed && <Check size={14} className="text-white" strokeWidth={3} />}
            </div>
            
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-0.5">
                  <p className={`text-sm font-semibold truncate transition-all ${
                    goal.completed ? 'text-gray-400 line-through decoration-2' : 'text-slate-700'
                  }`}>
                    {goal.text}
                  </p>
                  {goal.trackedTime && !goal.completed && (
                    <span className="ml-2 flex-shrink-0 text-[10px] font-mono font-medium bg-blue-50 text-blue-600 px-2 py-0.5 rounded-md border border-blue-100">
                        {goal.trackedTime}
                    </span>
                  )}
              </div>
              <div className="flex items-center gap-2">
                 {goal.tag && (
                     <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wider ${getTagStyle(goal.tag)}`}>
                        {goal.tag}
                     </span>
                 )}
              </div>
            </div>
          </div>
        ))}
        
        {/* Add Button */}
        <button className="w-full py-3.5 mt-2 rounded-2xl border-2 border-dashed border-gray-200 text-gray-400 hover:text-morandi-blue hover:border-morandi-blue/40 hover:bg-blue-50/30 transition-all flex items-center justify-center gap-2 text-sm font-bold">
            <Plus size={18} />
            Add Task
        </button>
      </div>
    </div>
  );
};

export default GoalsWidget;