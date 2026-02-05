
import React, { useState, useEffect, useRef } from 'react';
import { Wind, Heart, Compass, History, Edit3, Settings, ChevronLeft, ChevronRight, Menu, X, Palette, Sliders, RotateCcw, Eye, PenLine, HelpCircle } from 'lucide-react';

/**
 * Life Matrix - 禅意书写空间
 * 更新：引入 Markdown 实时渲染功能。
 * 使用 marked.js 库将纯文本转换为精美的排版。
 */

interface JournalViewProps {
  onBack?: () => void;
  onOpenGuide?: () => void;
}

const JournalView: React.FC<JournalViewProps> = ({ onBack, onOpenGuide }) => {
  const [content, setContent] = useState("");
  const [activeDate, setActiveDate] = useState(new Date()); 
  const [isSidebarOpen, setIsSidebarOpen] = useState(true); 
  const [settingsView, setSettingsView] = useState(false); 
  const [isPreview, setIsPreview] = useState(false); // 控制预览/编辑模式
  const [markedLoaded, setMarkedLoaded] = useState(false);

  // HSL 背景色状态
  const [hsl, setHsl] = useState({ h: 200, s: 15, l: 92 });
  const bgColor = `hsl(${hsl.h}, ${hsl.s}%, ${hsl.l}%)`;
  const neutralDark = '#262626';

  // 1. 动态加载 marked.js 库
  useEffect(() => {
    if ((window as any).marked) {
      setMarkedLoaded(true);
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/marked/4.3.0/marked.min.js';
    script.async = true;
    script.onload = () => setMarkedLoaded(true);
    document.body.appendChild(script);
  }, []);

  // 禅意预设颜色
  const presets = [
    { name: '象牙', h: 30, s: 15, l: 96 },
    { name: '薄墨', h: 0, s: 0, l: 92 },
    { name: '青磁', h: 170, s: 10, l: 92 },
    { name: '淡樱', h: 350, s: 20, l: 96 },
    { name: '枯草', h: 55, s: 15, l: 93 }
  ];

  const [monthList] = useState(() => {
    const list = [];
    const now = new Date();
    for (let i = -3; i <= 3; i++) {
      list.push(new Date(now.getFullYear(), now.getMonth() + i, 1));
    }
    return list;
  });

  const getDaysInMonth = (year: number, month: number) => new Date(year, month + 1, 0).getDate();
  const getFirstDayOfMonth = (year: number, month: number) => {
    let day = new Date(year, month, 1).getDay();
    return day === 0 ? 6 : day - 1; 
  };

  const handleHslChange = (key: string, value: string) => {
    setHsl(prev => ({ ...prev, [key]: parseInt(value) }));
  };

  const formatDate = (date: Date) => {
    return date.toISOString().split('T')[0];
  };

  const isSameDay = (d1: Date, d2: Date) => {
    return d1.getFullYear() === d2.getFullYear() &&
           d1.getMonth() === d2.getMonth() &&
           d1.getDate() === d2.getDate();
  };

  const handleBackToToday = () => {
    setActiveDate(new Date());
    setSettingsView(false);
  };

  // 渲染 Markdown
  const renderMarkdown = () => {
    if (!markedLoaded || !(window as any).marked) return { __html: content };
    return { __html: (window as any).marked.parse(content) };
  };

  const MonthBlock = ({ date }: { date: Date }) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const totalDays = getDaysInMonth(year, month);
    const startOffset = getFirstDayOfMonth(year, month);
    const monthName = date.toLocaleString('zh-CN', { month: 'long' });

    const days = [];
    for (let i = 0; i < startOffset; i++) days.push(null);
    for (let i = 1; i <= totalDays; i++) days.push(i);

    return (
      <div className="mb-12 last:mb-20">
        <div className="sticky top-0 z-20 py-3 mb-4 flex items-baseline space-x-2 border-b border-black/5 bg-white/20 backdrop-blur-md">
          <span className="text-lg font-serif text-gray-800 italic tracking-wide">{monthName}</span>
          <span className="text-xs font-mono text-gray-400 tracking-widest uppercase">{year}</span>
        </div>

        <div className="grid grid-cols-7 mb-4 text-center opacity-10">
          {['一', '二', '三', '四', '五', '六', '日'].map(d => (
            <span key={d} className="text-xs font-bold">{d}</span>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-y-3 gap-x-2">
          {days.map((day, idx) => {
            if (day === null) return <div key={`empty-${idx}`} className="aspect-square" />;
            const currentDate = new Date(year, month, Number(day));
            const isActive = isSameDay(activeDate, currentDate);
            
            return (
              <button
                key={`${year}-${month}-${day}`}
                onClick={() => setActiveDate(currentDate)}
                className={`
                  aspect-square rounded-full flex items-center justify-center transition-all duration-300 relative text-sm group
                  ${isActive 
                    ? 'text-white scale-110 shadow-[0_8px_20px_-5px_rgba(0,0,0,0.3)] z-10' 
                    : 'hover:bg-black/10 hover:scale-110 hover:shadow-sm text-gray-500 hover:text-black active:scale-95'
                  }
                `}
                style={{ backgroundColor: isActive ? neutralDark : 'transparent' }}
              >
                {day}
                {Number(day) % 11 === 0 && !isActive && (
                  <div className="absolute bottom-1.5 w-0.5 h-0.5 rounded-full bg-black/20 group-hover:bg-black/40" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-screen w-full font-sans overflow-hidden relative transition-colors duration-1000" style={{ backgroundColor: bgColor }}>
      
      {/* 背景纹理 */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden select-none z-0">
        <div className="absolute inset-0 opacity-[0.05]" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }} />
      </div>
      
      {/* 侧边栏切换按钮 */}
      <button 
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        className={`
          fixed top-[37px] z-50 p-2.5 rounded-full border border-black/5 bg-white/40 backdrop-blur-xl shadow-sm hover:shadow-md hover:scale-105 active:scale-95 transition-all duration-700 ease-[cubic-bezier(0.23,1,0.32,1)]
          ${isSidebarOpen ? 'left-[300px] md:left-[364px]' : 'left-8'}
          text-gray-700 hover:text-black
        `}
      >
        {isSidebarOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
      </button>

      {/* 1. 左侧侧边栏 - Increased width (w-80 / w-96) */}
      <aside className={`fixed inset-y-0 left-0 z-40 bg-white/40 backdrop-blur-2xl border-r border-black/[0.03] transition-all duration-700 ease-[cubic-bezier(0.23,1,0.32,1)] transform ${isSidebarOpen ? 'translate-x-0 w-80 md:w-96' : '-translate-x-full w-80 md:w-96'}`}>
        <div className="flex flex-col h-full">
          <header className="h-28 px-10 flex flex-col justify-center shrink-0 border-b border-black/[0.02]">
            <h2 className="text-xs font-bold tracking-[0.5em] uppercase opacity-40 text-black leading-none">Matrix</h2>
            <p className="text-xl font-serif mt-2 italic text-gray-400 opacity-60 leading-none">时间长廊</p>
          </header>

          <div className="flex-1 overflow-y-auto no-scrollbar px-10 relative scroll-smooth py-8">
            {!settingsView ? (
              <div className="animate-in fade-in slide-in-from-left-2 duration-700">
                {monthList.map(m => <MonthBlock key={m.toISOString()} date={m} />)}
              </div>
            ) : (
              <div className="flex flex-col h-full space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
                <div className="text-center w-full space-y-6">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">氛围实验室</p>
                  <div className="space-y-5 px-2">
                    {[
                      { label: '色相', key: 'h', max: 360, bg: 'linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000)' },
                      { label: '饱和', key: 's', max: 100, bg: `linear-gradient(to right, #888, hsl(${hsl.h}, 100%, 50%))` },
                      { label: '亮度', key: 'l', max: 100, bg: `linear-gradient(to right, #333, hsl(${hsl.h}, ${hsl.s}%, 50%), #fff)` }
                    ].map(slider => (
                      <div key={slider.key} className="space-y-2">
                        <div className="flex justify-between text-[9px] text-gray-400 uppercase font-medium tracking-tighter">
                          <span>{slider.label}</span><span>{(hsl as any)[slider.key]}{slider.key === 'h' ? '°' : '%'}</span>
                        </div>
                        <input type="range" min="0" max={slider.max} value={(hsl as any)[slider.key]} onChange={(e) => handleHslChange(slider.key, e.target.value)}
                          className="w-full h-[3px] rounded-full appearance-none cursor-pointer bg-black/5" style={{ background: slider.bg }} />
                      </div>
                    ))}
                  </div>

                  <div className="pt-4 flex flex-col items-center space-y-5">
                    <div className="w-12 h-12 rounded-full border-4 border-white shadow-xl transition-all duration-500" style={{ backgroundColor: bgColor }} />
                    <div className="flex flex-wrap justify-center gap-3">
                      {presets.map(p => (
                        <button key={p.name} onClick={() => setHsl({ h: p.h, s: p.s, l: p.l })}
                          className="w-5 h-5 rounded-full border-2 border-white shadow-sm transition-all hover:scale-125 hover:shadow-md"
                          style={{ backgroundColor: `hsl(${p.h}, ${p.s}%, ${p.l}%)` }} />
                      ))}
                    </div>
                  </div>
                </div>
                
                <button 
                  onClick={() => setSettingsView(false)} 
                  className="w-full py-3 bg-black text-white text-[10px] font-bold rounded-xl uppercase tracking-[0.3em] hover:bg-gray-800 hover:shadow-lg active:scale-[0.98] transition-all shadow-md"
                >
                  确定
                </button>
              </div>
            )}
          </div>

          <div className="p-10 flex justify-around text-gray-500 opacity-80 shrink-0 border-t border-black/[0.02]">
            <button 
              onClick={() => setSettingsView(!settingsView)} 
              title="设置氛围"
              className={`p-2 rounded-full transition-all duration-500 ${settingsView ? 'bg-black text-white rotate-180 scale-110 opacity-100' : 'hover:text-black hover:bg-black/5'}`}
            >
              <Settings size={18} />
            </button>
            <button 
              onClick={handleBackToToday}
              title="回到今天"
              className="p-2 rounded-full hover:text-black hover:bg-black/5 transition-all active:scale-90"
            >
              <History size={18} />
            </button>
          </div>
        </div>
      </aside>

      {/* 2. 主体书写区 - Adjusted margins for wider sidebar */}
      <main className={`flex-1 relative flex flex-col z-10 transition-all duration-700 ease-[cubic-bezier(0.23,1,0.32,1)] ${isSidebarOpen ? 'ml-80 md:ml-96' : 'ml-0'}`}>
        <header className="h-28 flex items-center px-12 md:px-24 justify-between shrink-0 relative z-10 border-b border-black/[0.02]">
          <div className="flex flex-col">
            <div className="flex items-baseline space-x-6 animate-in slide-in-from-top-4 duration-1000">
              <h1 className="text-[32px] font-serif italic text-gray-800 tracking-tight leading-none">{formatDate(activeDate)}</h1>
              <span className="text-[10px] font-bold uppercase tracking-[0.4em] opacity-30 text-black leading-none">
                {content.length} 字的觉察
              </span>
            </div>
          </div>
          
          {/* 右上角功能区：增加编辑/预览切换 */}
          <div className="flex space-x-6 text-gray-400/50 items-center">
             <button 
               onClick={() => setIsPreview(!isPreview)} 
               title={isPreview ? "回到编辑" : "预览排版"}
               className={`transition-all ${isPreview ? 'text-black scale-110' : 'hover:text-black'}`}
             >
                {isPreview ? <PenLine size={20} /> : <Eye size={20} />}
             </button>
             <button className="hover:text-black hover:-translate-y-0.5 transition-all"><Wind size={20} /></button>
             <button className="hover:text-red-400 hover:-translate-y-0.5 transition-all"><Heart size={20} /></button>

             {onOpenGuide && (
               <button 
                  onClick={onOpenGuide}
                  className="p-3 rounded-full transition-all duration-300 hover:scale-105 active:scale-95 bg-white/50 text-slate-600 hover:bg-white hover:text-indigo-600 hover:shadow-md backdrop-blur-sm border border-transparent hover:border-indigo-100"
                  aria-label="User Guide"
               >
                  <HelpCircle size={20} strokeWidth={2} />
               </button>
             )}

             {onBack && (
               <button onClick={onBack} className="hover:text-black hover:-translate-y-0.5 transition-all" title="退出">
                 <X size={20} />
               </button>
             )}
          </div>
        </header>

        <section className="flex-1 px-12 md:px-24 py-8 overflow-y-auto no-scrollbar relative z-10 scroll-smooth">
          {isPreview ? (
            /* 预览模式：Markdown 渲染内容 */
            <div 
              className="markdown-body font-serif text-[20px] leading-[2] text-gray-800 animate-in fade-in slide-in-from-bottom-2 duration-500"
              dangerouslySetInnerHTML={renderMarkdown()}
            />
          ) : (
            /* 编辑模式：纯文本输入 */
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="在此处，开启一段与自我的深谈..."
              className="w-full h-full text-[24px] leading-[2.2] text-gray-800 bg-transparent border-none focus:ring-0 outline-none resize-none font-serif placeholder-gray-300 transition-all"
              autoFocus
              style={{ caretColor: neutralDark }}
            />
          )}
        </section>
        
        <footer className="h-16 px-12 md:px-24 flex items-center justify-between relative z-10 opacity-20 select-none border-t border-black/[0.01]">
          <div className="flex space-x-4 text-[9px] uppercase tracking-[0.5em] text-gray-500 font-bold">
            <span>Inner Dialogue</span>
            <span>•</span>
            <span>Continuum</span>
          </div>
          <div className="text-[11px] font-serif italic">文字是通往内心的阶梯</div>
        </footer>
      </main>

      <style dangerouslySetInnerHTML={{ __html: `
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        textarea:focus { outline: none; }
        .font-serif { font-family: ui-serif, Georgia, Cambria, "Times New Roman", Times, serif; }
        ::selection { background: rgba(0,0,0,0.08); color: ${neutralDark}; }

        /* Markdown 样式微调 */
        .markdown-body h1 { font-size: 2em; font-style: italic; margin-bottom: 0.5em; border-bottom: 1px solid rgba(0,0,0,0.05); padding-bottom: 0.2em; }
        .markdown-body h2 { font-size: 1.5em; margin-top: 1.5em; margin-bottom: 0.5em; opacity: 0.8; }
        .markdown-body p { margin-bottom: 1.5em; }
        .markdown-body blockquote { border-left: 3px solid rgba(0,0,0,0.1); padding-left: 1.5em; font-style: italic; color: #666; margin: 2em 0; }
        .markdown-body ul { list-style-type: disc; padding-left: 1.5em; margin-bottom: 1.5em; }
        .markdown-body strong { font-weight: 600; color: #000; }
        .markdown-body code { background: rgba(0,0,0,0.05); padding: 0.2em 0.4em; border-radius: 4px; font-family: monospace; font-size: 0.9em; }

        input[type=range] { -webkit-appearance: none; }
        input[type=range]::-webkit-slider-thumb {
          -webkit-appearance: none;
          height: 12px; width: 12px; border-radius: 50%; background: white;
          box-shadow: 0 2px 6px rgba(0,0,0,0.15); cursor: pointer; border: 1.5px solid #eee;
          margin-top: -4.5px; transition: transform 0.2s;
        }
        input[type=range]::-webkit-slider-thumb:hover { transform: scale(1.2); }
      `}} />
    </div>
  );
};

export default JournalView;
