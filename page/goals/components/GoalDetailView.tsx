
import React, { useState } from 'react';
import { ChevronLeft, Save, Clock, Calendar, Hash, AlignLeft, Tag, Folder } from 'lucide-react';
import { UserGoal } from '../types';
import { MOCK_CATEGORIES } from '../api';

interface GoalDetailViewProps {
  goal: UserGoal;
  onBack: () => void;
  onSave: (updatedGoal: UserGoal) => void;
}

const GoalDetailView: React.FC<GoalDetailViewProps> = ({ goal, onBack, onSave }) => {
  const [formData, setFormData] = useState<UserGoal>(goal);

  const handleChange = (field: keyof UserGoal, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] bg-white rounded-[2.5rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden animate-fade-in relative">

      {/* Decorative Background Blob */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-blue-50/50 to-purple-50/50 rounded-full blur-3xl -z-10 translate-x-1/3 -translate-y-1/3 pointer-events-none" />

      {/* Header Toolbar */}
      <div className="flex items-center justify-between px-8 py-6 border-b border-slate-50 bg-white/80 backdrop-blur-md sticky top-0 z-20">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-slate-800 transition-all group"
        >
          <div className="p-2.5 rounded-2xl bg-slate-50 group-hover:bg-slate-100 transition-colors">
            <ChevronLeft size={20} />
          </div>
          <span className="font-bold text-xs uppercase tracking-widest">Back to Goals</span>
        </button>

        <button
          onClick={() => onSave(formData)}
          className="flex items-center gap-2 px-6 py-3 bg-slate-900 text-white rounded-xl font-bold text-xs uppercase tracking-wider hover:bg-blue-600 hover:shadow-lg hover:shadow-blue-500/20 transition-all transform active:scale-95"
        >
          <Save size={16} />
          Save Changes
        </button>
      </div>

      {/* Main Content Scrollable Area */}
      <div className="flex-1 overflow-y-auto no-scrollbar p-8 md:p-12 w-full max-w-5xl mx-auto">

        {/* Alias / Tag Input (Pill Style) */}
        <div className="mb-8 animate-fade-in" style={{ animationDelay: '50ms' }}>
          <div className="inline-flex items-center gap-2 text-blue-600 bg-blue-50 px-4 py-2 rounded-xl border border-blue-100 focus-within:ring-2 focus-within:ring-blue-200 transition-all shadow-sm">
            <Hash size={14} className="opacity-50" />
            <input
              type="text"
              value={formData.alias || ''}
              onChange={(e) => handleChange('alias', e.target.value)}
              placeholder="ALIAS"
              className="bg-transparent border-none outline-none text-xs font-black uppercase tracking-widest placeholder-blue-300 w-32"
            />
          </div>
        </div>

        {/* Title Input (Huge) */}
        <div className="mb-10 animate-fade-in" style={{ animationDelay: '100ms' }}>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => handleChange('name', e.target.value)}
            placeholder="Enter Goal Title..."
            className="w-full text-4xl md:text-6xl font-black text-slate-800 bg-transparent border-none outline-none placeholder-slate-200 leading-tight tracking-tight"
          />
        </div>

        {/* Metadata Row */}
        <div className="flex flex-wrap items-center gap-6 mb-12 text-slate-400 font-medium text-sm border-y border-dashed border-slate-100 py-6 animate-fade-in" style={{ animationDelay: '150ms' }}>
          {/* Date Picker */}
          <div className="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-xl border border-slate-100">
            <Calendar size={16} className="text-slate-400" />
            <div className="flex flex-col">
              <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Target Date</span>
              <input
                type="date"
                value={formData.expectedFinishedAt}
                onChange={(e) => handleChange('expectedFinishedAt', e.target.value)}
                className="bg-transparent text-slate-700 font-bold font-mono text-xs focus:outline-none p-0 w-28 cursor-pointer"
              />
            </div>
          </div>

          {/* Estimate Input */}
          <div className="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-xl border border-slate-100">
            <Clock size={16} className="text-slate-400" />
            <div className="flex flex-col">
              <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Estimate</span>
              <input
                type="text"
                value={formData.estimatedDuration}
                onChange={(e) => handleChange('estimatedDuration', e.target.value)}
                className="bg-transparent text-slate-700 font-bold font-mono text-xs w-20 focus:outline-none placeholder-slate-300"
                placeholder="e.g. 60h"
              />
            </div>
          </div>

          {/* Category Selector */}
          <div className="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-xl border border-slate-100">
            <Folder size={16} className="text-slate-400" />
            <div className="flex flex-col">
              <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Category</span>
              <select
                value={formData.categoryId || ''}
                onChange={(e) => handleChange('categoryId', e.target.value)}
                className="bg-transparent text-slate-700 font-bold text-xs w-32 focus:outline-none cursor-pointer -ml-1"
              >
                <option value="" className="text-slate-400">Uncategorized</option>
                {MOCK_CATEGORIES.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Main Description Textarea */}
        <div className="h-full min-h-[400px] animate-fade-in relative" style={{ animationDelay: '200ms' }}>
          <div className="absolute -left-8 top-1 text-slate-200">
            <AlignLeft size={24} />
          </div>
          <textarea
            value={formData.content}
            onChange={(e) => handleChange('content', e.target.value)}
            placeholder="Describe your goal, milestones, and motivation here..."
            className="w-full h-full min-h-[500px] resize-none outline-none text-lg md:text-xl text-slate-600 font-medium leading-relaxed bg-transparent placeholder-slate-200 pl-2 no-scrollbar"
          />
        </div>
      </div>
    </div>
  );
};

export default GoalDetailView;
