import React from 'react';
import { ActiveTab, ViewMode } from '../shared/types';
import { Target, FileText, Layers, Calendar, CheckSquare, Columns, Maximize, ChevronLeft, ChevronRight } from 'lucide-react';

interface CapsuleNavProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
}

export const CapsuleNav: React.FC<CapsuleNavProps> = ({
  activeTab,
  onTabChange,
  viewMode,
  onViewModeChange,
}) => {
  const singleTabs: { id: ActiveTab; label: string; icon: React.ReactNode }[] = [
    { id: 'goals', label: '目标', icon: <Target size={16} /> },
    { id: 'plans', label: '计划书', icon: <FileText size={16} /> },
    { id: 'pool', label: '任务池', icon: <Layers size={16} /> },
    { id: 'assign', label: '任务分配', icon: <Calendar size={16} /> },
    { id: 'daily', label: '每日任务', icon: <CheckSquare size={16} /> },
  ];

  const dualTabs: { id: ActiveTab; label: string; icon: React.ReactNode }[] = [
    { 
      id: 'goals', 
      label: '目标 — 计划', 
      icon: <div className="flex items-center gap-0.5"><Target size={14} /><span className="opacity-40">/</span><FileText size={14} /></div> 
    },
    { 
      id: 'plans', 
      label: '计划 — 任务', 
      icon: <div className="flex items-center gap-0.5"><FileText size={14} /><span className="opacity-40">/</span><Layers size={14} /></div> 
    },
    { 
      id: 'pool', 
      label: '任务 — 日历', 
      icon: <div className="flex items-center gap-0.5"><Layers size={14} /><span className="opacity-40">/</span><Calendar size={14} /></div> 
    },
    { 
      id: 'daily', 
      label: '日历 — 每日', 
      icon: <div className="flex items-center gap-0.5"><Calendar size={14} /><span className="opacity-40">/</span><CheckSquare size={14} /></div> 
    },
  ];

  const currentTabs = viewMode === 'dual' ? dualTabs : singleTabs;

  // Handle previous/next navigation
  const handleNav = (direction: 'prev' | 'next') => {
    let currentIndex = currentTabs.findIndex(t => t.id === activeTab);
    
    // Fallback if 'assign' is active but mapping to 'pool' in dual mode
    if (currentIndex === -1 && viewMode === 'dual' && activeTab === 'assign') {
        currentIndex = currentTabs.findIndex(t => t.id === 'pool');
    }
    
    if (currentIndex === -1) currentIndex = 0; // Safety fallback

    let newIndex;
    if (direction === 'next') {
        newIndex = (currentIndex + 1) % currentTabs.length;
    } else {
        newIndex = (currentIndex - 1 + currentTabs.length) % currentTabs.length;
    }
    onTabChange(currentTabs[newIndex].id);
  };

  return (
    <div className="h-16 bg-white/90 backdrop-blur-md rounded-[20px] shadow-soft-md border border-white/50 flex items-center justify-between px-6 transition-all duration-300 hover:shadow-soft-lg">
      <div className="flex items-center space-x-2 shrink-0">
         <div className="w-8 h-8 rounded-lg bg-gradient-aurora flex items-center justify-center text-white font-heading font-bold text-base shadow-md">
            G
         </div>
         <span className="font-heading font-bold text-lg text-aurora-text-primary tracking-tight hidden md:inline">
            GoalMaster
         </span>
      </div>

      <div className="flex-1 flex justify-center items-center gap-2 md:gap-4 overflow-hidden px-2">
        {/* Navigation Arrows */}
        <button 
            onClick={() => handleNav('prev')}
            className="p-2 rounded-full text-aurora-text-subtle hover:text-aurora-primary hover:bg-white hover:shadow-soft-sm active:scale-95 transition-all duration-200 hidden md:block shrink-0"
        >
            <ChevronLeft size={20} />
        </button>

        <div className="bg-aurora-bg p-1.5 rounded-[16px] flex space-x-1 shadow-inner-light border border-slate-100 overflow-x-auto scrollbar-hide w-full md:w-auto">
          {currentTabs.map((tab) => {
            // Highlight logic: 
            // 1. Direct match
            // 2. Dual mode mapping: assign -> pool (PoolCalendarCombo)
            const isActive = activeTab === tab.id || (viewMode === 'dual' && tab.id === 'pool' && activeTab === 'assign');
            
            return (
                <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`
                    flex items-center space-x-2 px-3 md:px-5 py-2 rounded-[12px] text-sm font-medium transition-all duration-300 ease-out whitespace-nowrap shrink-0
                    ${
                    isActive
                        ? 'bg-gradient-aurora text-white shadow-soft-md transform scale-[1.02]'
                        : 'text-aurora-text-muted hover:text-aurora-text-primary hover:bg-white hover:shadow-soft-sm'
                    }
                `}
                >
                <span className={isActive ? 'opacity-100' : 'opacity-70'}>{tab.icon}</span>
                <span>{tab.label}</span>
                </button>
            );
          })}
        </div>

        <button 
            onClick={() => handleNav('next')}
            className="p-2 rounded-full text-aurora-text-subtle hover:text-aurora-primary hover:bg-white hover:shadow-soft-sm active:scale-95 transition-all duration-200 hidden md:block shrink-0"
        >
            <ChevronRight size={20} />
        </button>
      </div>

      <div className="flex items-center space-x-2 border-l border-slate-200 pl-4 ml-2 hidden sm:flex shrink-0">
        <button
          onClick={() => onViewModeChange('single')}
          className={`p-2 rounded-lg transition-all duration-200 ${viewMode === 'single' ? 'bg-aurora-primary/10 text-aurora-primary' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'}`}
          title="Single Column View"
        >
          <Maximize size={18} />
        </button>
        <button
          onClick={() => onViewModeChange('dual')}
          className={`p-2 rounded-lg transition-all duration-200 ${viewMode === 'dual' ? 'bg-aurora-primary/10 text-aurora-primary' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'}`}
          title="Dual Column View"
        >
          <Columns size={18} />
        </button>
      </div>
    </div>
  );
};