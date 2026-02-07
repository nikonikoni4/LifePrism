import React, { useState, useEffect, useMemo } from 'react';
import { Check, Anchor, TrendingUp, Calendar, Zap, Layers, Clock, MapPin, Hash, ArrowRight, Activity } from 'lucide-react';

// --- 配色系统 (Swiss Style Colors) ---
const CATEGORY_THEMES = {
  'Morning Protocol': {
    primary: 'bg-blue-600',
    text: 'text-blue-600',
    border: 'border-blue-600',
    light: 'bg-blue-50',
    hover: 'hover:border-blue-600',
    shadow: 'hover:shadow-blue-600'
  },
  'Deep Work Block': {
    primary: 'bg-orange-500',
    text: 'text-orange-500',
    border: 'border-orange-500',
    light: 'bg-orange-50',
    hover: 'hover:border-orange-500',
    shadow: 'hover:shadow-orange-500'
  },
  'Learning Loop': {
    primary: 'bg-purple-600',
    text: 'text-purple-600',
    border: 'border-purple-600',
    light: 'bg-purple-50',
    hover: 'hover:border-purple-600',
    shadow: 'hover:shadow-purple-600'
  },
  'Shutdown Sequence': {
    primary: 'bg-indigo-900',
    text: 'text-indigo-900',
    border: 'border-indigo-900',
    light: 'bg-indigo-50',
    hover: 'hover:border-indigo-900',
    shadow: 'hover:shadow-indigo-900'
  }
};

const DEFAULT_THEME = {
  primary: 'bg-gray-900',
  text: 'text-gray-900',
  border: 'border-gray-900',
  light: 'bg-gray-50',
  hover: 'hover:border-gray-900',
  shadow: 'hover:shadow-gray-900'
};

// --- 数据模型 ---

const MOCK_HABITS = [
  {
    id: 'h1',
    name: '冥想 10分钟',
    anchor: '7:00 起床后',
    anchorType: 'time',
    level: 3,
    streak: 42,
    todayCompleted: false,
    frequency: 'daily',
    category: 'Morning Protocol'
  },
  {
    id: 'h2',
    name: '饮水 500ml',
    anchor: '冥想完成后',
    anchorType: 'event',
    level: 4,
    streak: 108,
    todayCompleted: true,
    frequency: 'daily',
    category: 'Morning Protocol'
  },
  {
    id: 'h3',
    name: '深度工作 90min',
    anchor: '到达工位',
    anchorType: 'scene',
    level: 1,
    streak: 5,
    todayCompleted: false,
    frequency: 'weekdays',
    category: 'Deep Work Block'
  },
  {
    id: 'h4',
    name: '阅读技术文档',
    anchor: '午饭后',
    anchorType: 'time',
    level: 0,
    streak: 2,
    todayCompleted: false,
    frequency: 'daily',
    category: 'Learning Loop'
  },
  {
    id: 'h5',
    name: 'GitHub 提交',
    anchor: '阅读完成后',
    anchorType: 'event',
    level: 2,
    streak: 15,
    todayCompleted: false,
    frequency: 'weekdays',
    category: 'Learning Loop'
  },
  {
    id: 'h6',
    name: '写反思日记',
    anchor: '22:00 睡前',
    anchorType: 'time',
    level: 2,
    streak: 21,
    todayCompleted: true,
    frequency: 'daily',
    category: 'Shutdown Sequence'
  }
];

// --- 辅助组件 ---

const LevelIndicator = ({ level, theme }) => {
  return (
    <div className="flex gap-1 items-end h-full">
      {[0, 1, 2, 3, 4].map((step) => (
        <div
          key={step}
          className={`w-1.5 transition-all duration-300 ${
            step <= level ? `${theme.primary} h-3` : 'bg-gray-200 h-1.5'
          }`}
        />
      ))}
    </div>
  );
};

const AnchorIcon = ({ type }) => {
  switch (type) {
    case 'time': return <Clock size={14} className="opacity-70" />;
    case 'scene': return <MapPin size={14} className="opacity-70" />;
    case 'event': return <Zap size={14} className="opacity-70" />;
    default: return <Hash size={14} className="opacity-70" />;
  }
};

const HeatmapBlock = ({ active }) => {
  // 使用更有活力的绿色系
  const opacity = active ? Math.random() * 0.7 + 0.3 : 0.05;
  return (
    <div 
      className={`w-full pt-[100%] relative border-r border-b border-white transition-opacity duration-500 ${active ? 'bg-emerald-500' : 'bg-gray-200'}`}
      style={{ opacity: active ? opacity : 1 }}
    />
  );
};

// --- 核心组件：习惯卡片 ---

const HabitCard = ({ habit, onToggle }) => {
  const theme = CATEGORY_THEMES[habit.category] || DEFAULT_THEME;

  return (
    <div 
      className={`group relative bg-white border-2 border-gray-100 p-0 overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,0.1)] hover:border-transparent ${theme.shadow}`}
      // 自定义阴影颜色需要在 CSS 中处理或使用 style，这里为了简洁使用 tailwind 默认阴影配合 theme 颜色
      style={{
        '--theme-color': theme.text.replace('text-', 'var(--color-') // 简化的逻辑，实际项目中可能需要更严谨的颜色映射
      }}
    >
      {/* 彩色装饰条 (Color Accent) */}
      <div className={`absolute top-0 left-0 w-full h-1 ${theme.primary}`} />

      {/* 结构性连接线 - 现在带有颜色 */}
      <div className="absolute top-0 left-0 w-1 h-full bg-gray-50 z-0">
         <div className={`w-full transition-all duration-500 ease-out ${habit.todayCompleted ? `h-full ${theme.primary}` : 'h-0'}`} />
      </div>

      <div className="relative z-10 p-5 pl-7 flex flex-col h-full justify-between">
        
        {/* Header: Anchor & Level */}
        <div className="flex justify-between items-start mb-3">
          <div className={`flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider px-2 py-1 rounded-sm ${theme.light} ${theme.text}`}>
            <AnchorIcon type={habit.anchorType} />
            <span>{habit.anchor}</span>
          </div>
          <LevelIndicator level={habit.level} theme={theme} />
        </div>

        {/* Main Info */}
        <div className="mb-4">
          <h3 className={`text-xl font-bold font-display tracking-tight text-gray-900 transition-colors duration-300 ${habit.todayCompleted ? 'line-through text-gray-400' : ''}`}>
            {habit.name}
          </h3>
          <div className="flex items-center gap-2 mt-1">
             <span className="text-xs font-mono text-gray-400 group-hover:text-gray-600 transition-colors">Streak: {habit.streak}d</span>
             {habit.level === 4 && <span className={`text-[10px] ${theme.primary} text-white px-1 font-bold`}>MASTERED</span>}
          </div>
        </div>

        {/* Action Area */}
        <div className="flex items-center justify-between mt-auto">
          <div className="text-xs text-gray-400 font-mono">
             {habit.frequency.toUpperCase()}
          </div>
          
          <button
            onClick={() => onToggle(habit.id)}
            className={`
              relative w-10 h-10 border-2 flex items-center justify-center rounded-sm
              transition-all duration-150 active:translate-y-1 active:shadow-none
              ${habit.todayCompleted 
                ? `${theme.primary} border-transparent text-white shadow-none` 
                : `bg-white border-gray-200 text-gray-300 hover:text-gray-900 hover:border-gray-900 hover:bg-gray-50`}
            `}
          >
            <div className={`transform transition-transform duration-300 ${habit.todayCompleted ? 'scale-100 rotate-0' : 'scale-0 -rotate-45'}`}>
              <Check size={20} strokeWidth={4} />
            </div>
          </button>
        </div>
      </div>

      {/* 进度背景纹理 */}
      <div 
        className={`absolute inset-0 pointer-events-none opacity-[0.03] mix-blend-multiply bg-[url('https://www.transparenttextures.com/patterns/graphy.png')]`}
      />
    </div>
  );
};

// --- 布局组件：锚点分组 ---

const AnchorGroup = ({ title, habits, onToggle }) => {
  // 获取该组的主题色
  const theme = CATEGORY_THEMES[habits[0]?.category] || DEFAULT_THEME;

  return (
    <div className="mb-12">
      <div className="flex items-center gap-4 mb-6">
        {/* 彩色方块锚点 */}
        <div className={`w-4 h-4 ${theme.primary} shadow-sm transform rotate-45`}></div>
        <h2 className={`text-sm font-mono font-bold uppercase tracking-widest ${theme.text}`}>{title}</h2>
        <div className={`h-[2px] flex-grow opacity-20 ${theme.primary}`}></div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {habits.map(habit => (
          <HabitCard key={habit.id} habit={habit} onToggle={onToggle} />
        ))}
      </div>
    </div>
  );
};

// --- 主应用 ---

export default function HabitSystem() {
  const [habits, setHabits] = useState(MOCK_HABITS);

  const toggleHabit = (id) => {
    setHabits(habits.map(h => {
      if (h.id === id) {
        return {
          ...h,
          todayCompleted: !h.todayCompleted,
          streak: !h.todayCompleted ? h.streak + 1 : h.streak - 1
        };
      }
      return h;
    }));
  };

  const groupedHabits = useMemo(() => {
    const groups = {};
    habits.forEach(h => {
      if (!groups[h.category]) groups[h.category] = [];
      groups[h.category].push(h);
    });
    return groups;
  }, [habits]);

  const totalHabits = habits.length;
  const completedToday = habits.filter(h => h.todayCompleted).length;
  const completionRate = Math.round((completedToday / totalHabits) * 100);

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-gray-900 font-sans selection:bg-emerald-200 selection:text-emerald-900">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap');
        
        .font-display { font-family: 'Space Grotesk', sans-serif; }
        .font-mono { font-family: 'Space Mono', monospace; }
        
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #f1f1f1; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
      `}</style>

      {/* Sidebar - 现在使用更柔和的灰色边框 */}
      <aside className="fixed left-0 top-0 h-full w-20 bg-white border-r border-gray-200 hidden lg:flex flex-col items-center py-8 z-50 shadow-sm">
        <div className="mb-12">
          <div className="w-10 h-10 bg-gray-900 text-white flex items-center justify-center font-display font-bold text-xl rounded-lg">H</div>
        </div>
        
        <nav className="flex flex-col gap-8 w-full">
          {[
            { icon: Layers, active: true },
            { icon: TrendingUp, active: false },
            { icon: Calendar, active: false },
            { icon: Anchor, active: false },
          ].map((item, idx) => (
            <button key={idx} className={`w-full h-12 flex items-center justify-center transition-all relative ${item.active ? 'text-gray-900 bg-gray-50' : 'text-gray-400 hover:text-gray-600'}`}>
              {item.active && <div className="absolute left-0 w-1 h-8 bg-gray-900 rounded-r-full" />}
              <item.icon size={24} strokeWidth={item.active ? 2.5 : 2} />
            </button>
          ))}
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="lg:pl-20 min-h-screen">
        
        {/* Top Bar */}
        <header className="bg-white/80 border-b border-gray-200 p-8 sticky top-0 z-40 backdrop-blur-md">
          <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-xs font-mono text-gray-400 uppercase tracking-widest">System v1.0</span>
              </div>
              <h1 className="text-4xl md:text-5xl font-display font-bold tracking-tighter text-gray-900">
                Habit<span className="text-emerald-500">_</span>Structure
              </h1>
            </div>

            {/* Stats Dashboard with Color */}
            <div className="flex gap-10">
               <div className="flex flex-col items-end group cursor-pointer">
                 <span className="text-[10px] font-mono font-bold text-gray-400 mb-1 group-hover:text-blue-500 transition-colors">COMPLETION</span>
                 <span className="text-3xl font-display font-bold group-hover:text-blue-600 transition-colors">{completionRate}%</span>
               </div>
               <div className="flex flex-col items-end group cursor-pointer">
                 <span className="text-[10px] font-mono font-bold text-gray-400 mb-1 group-hover:text-orange-500 transition-colors">TOTAL STREAK</span>
                 <span className="text-3xl font-display font-bold group-hover:text-orange-500 transition-colors">192<span className="text-lg text-gray-300 group-hover:text-orange-300">d</span></span>
               </div>
               <div className="hidden md:flex flex-col items-end group cursor-pointer">
                 <span className="text-[10px] font-mono font-bold text-gray-400 mb-1 group-hover:text-purple-500 transition-colors">ANCHORS</span>
                 <span className="text-3xl font-display font-bold group-hover:text-purple-500 transition-colors">3<span className="text-lg text-gray-300 group-hover:text-purple-300">sets</span></span>
               </div>
            </div>
          </div>
          
          {/* Colored Progress Line */}
          <div className="absolute bottom-0 left-0 h-[3px] bg-gradient-to-r from-blue-500 via-purple-500 to-orange-500 transition-all duration-1000 ease-out" style={{ width: `${completionRate}%` }}></div>
        </header>

        <div className="p-8 max-w-6xl mx-auto">
          
          {/* Section 1: Heatmap (Emerald Style) */}
          <section className="mb-16 border border-gray-200 p-6 bg-white rounded-lg shadow-sm">
             <div className="flex justify-between items-center mb-4">
                <h3 className="font-mono text-xs font-bold uppercase text-gray-400 flex items-center gap-2">
                  <Activity size={14} className="text-emerald-500"/> Consistency Rhythm
                </h3>
                <div className="flex gap-2 text-[10px] font-mono text-gray-400 items-center">
                  <span>DORMANT</span>
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-200 rounded-[1px]"></div>
                    <div className="w-2 h-2 bg-emerald-200 rounded-[1px]"></div>
                    <div className="w-2 h-2 bg-emerald-400 rounded-[1px]"></div>
                    <div className="w-2 h-2 bg-emerald-600 rounded-[1px]"></div>
                  </div>
                  <span>ACTIVE</span>
                </div>
             </div>
             
             {/* Heatmap Grid */}
             <div className="flex gap-1 overflow-x-auto pb-2 mask-linear">
                {/* 简化模拟：生成52列 */}
                {Array.from({ length: 52 }).map((_, colIndex) => (
                  <div key={colIndex} className="flex flex-col gap-1">
                    {Array.from({ length: 7 }).map((_, rowIndex) => (
                      <div 
                        key={rowIndex} 
                        className={`w-3 h-3 rounded-[2px] transition-colors duration-300 ${
                          Math.random() > 0.7 
                            ? `bg-emerald-${[200, 300, 400, 500, 600][Math.floor(Math.random()*5)]}` 
                            : 'bg-gray-100'
                        }`}
                      />
                    ))}
                  </div>
                ))}
             </div>
          </section>

          {/* Section 2: Habit Cards */}
          <div className="space-y-8">
            {Object.keys(groupedHabits).map((category) => (
              <AnchorGroup 
                key={category} 
                title={category} 
                habits={groupedHabits[category]} 
                onToggle={toggleHabit} 
              />
            ))}
          </div>

          <div className="mt-24 pt-10 border-t border-gray-100 flex justify-center text-center">
             <p className="font-mono text-[10px] text-gray-400 uppercase tracking-[0.2em] hover:text-gray-900 transition-colors cursor-default">
               Designed for longevity • Mind Space v1.0
             </p>
          </div>
          
        </div>
      </main>

      {/* 调整后的背景点阵 */}
      <div className="fixed inset-0 pointer-events-none z-[-1]" style={{ 
        backgroundImage: 'radial-gradient(#cbd5e1 1px, transparent 1px)', 
        backgroundSize: '32px 32px',
        opacity: 0.4 
      }}></div>
      
    </div>
  );
}