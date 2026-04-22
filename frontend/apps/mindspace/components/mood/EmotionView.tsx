
import React, { useState, useMemo, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Heart, Cloud, Sun, Moon, Wind, Edit3, Trash2, Plus, X, Check, 
  Calendar, ChevronLeft, ChevronRight, Activity, PenTool, Hash, 
  Sparkles, Flame, ShieldAlert, Settings2, Settings, Sliders,
  Zap, Ghost, Star, Coffee, Music, Book, Camera, Gamepad, Smile, Meh, Frown,
  HelpCircle
} from 'lucide-react';
import EmotionRecord from './EmotionRecord';
import BlobBackground from '../BlobBackground';
import { MoodAPI } from './moodApi';
import { toMoodTypeUI, toMoodEntryUI } from './moodTransform';
import type { MoodTypeUI, MoodEntryUI, MoodImpactItem } from './types';

const ICON_MAP: Record<string, any> = { 
  Sun, Wind, Cloud, Moon, Heart, Plus, Flame, ShieldAlert, 
  Zap, Ghost, Star, Coffee, Music, Book, Camera, Gamepad, Smile, Meh, Frown 
};

const ICON_OPTIONS = [
  'Sun', 'Wind', 'Cloud', 'Moon', 'Heart', 'Flame', 'ShieldAlert', 
  'Star', 'Zap', 'Ghost', 'Coffee', 'Music', 'Book', 'Camera', 'Gamepad', 'Smile', 'Meh', 'Frown'
];

const COLOR_OPTIONS = [
  '#fed7aa', '#d1fae5', '#cbd5e1', '#fb7185', '#6366f1', '#a5b4fc', '#52525b', 
  '#fde047', '#93c5fd', '#fecaca', '#d9f99d', '#99f6e4', '#bae6fd', '#c7d2fe', '#e9d5ff', '#fbcfe8'
];

interface EmotionViewProps {
  onBack?: () => void;
  onNavigate?: (view: any) => void;
  onOpenGuide?: () => void;
}

const EmotionView: React.FC<EmotionViewProps> = ({ onBack, onNavigate, onOpenGuide }) => {
  const [moods, setMoods] = useState<MoodTypeUI[]>([]);
  const [impactCategories, setImpactCategories] = useState<MoodImpactItem[]>([]);
  const [entries, setEntries] = useState<MoodEntryUI[]>([]);
  const [view, setView] = useState('present');
  const [activeMood, setActiveMood] = useState<MoodTypeUI | null>(null);
  const [selectedImpacts, setSelectedImpacts] = useState<string[]>([]);
  const [note, setNote] = useState('');
  const [step, setStep] = useState('mood');
  const [isAbsorbing, setIsAbsorbing] = useState(false);
  const [journeyPulse, setJourneyPulse] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const [isManagingMoods, setIsManagingMoods] = useState(false);
  const [editingMood, setEditingMood] = useState<any>(null);
  const [editingEntryId, setEditingEntryId] = useState<string | null>(null);

  // 构建 typesMap 用于 entry 转换
  const typesMap = useMemo(() => new Map(moods.map(m => [m.id, m])), [moods]);

  const sortedMoods = useMemo(() => {
    return [...moods].sort((a, b) => b.sort_order - a.sort_order);
  }, [moods]);

  // 初始化数据加载
  useEffect(() => {
    const loadData = async () => {
      try {
        const [typesData, impactsData, entriesData] = await Promise.all([
          MoodAPI.getTypes(),
          MoodAPI.getImpacts(),
          MoodAPI.getEntries(),
        ]);
        const moodTypes = typesData.map(toMoodTypeUI);
        const map = new Map(moodTypes.map(t => [t.id, t]));
        setMoods(moodTypes);
        setImpactCategories(impactsData);
        setEntries(entriesData.map(e => toMoodEntryUI(e, map)));
      } catch (err) {
        console.error('加载心情数据失败:', err);
      } finally {
        setIsLoading(false);
      }
    };
    loadData();
  }, []);

  const defaultMood: MoodTypeUI = sortedMoods[0] ?? { id: '', name: '', icon: 'Sun', color: '#cbd5e1', score: 50, is_dark: 0, sort_order: 0, created_at: '', text: '', isDark: false, glow: '#cbd5e199' };
  const currentMood = activeMood || (entries.length > 0 ? entries[entries.length - 1].mood : defaultMood);
  const isWriting = step === 'write';
  const isDarkTheme = currentMood.isDark;
  const isRecordView = view === 'record';

  const themeStyles = {
    '--theme-bg': isRecordView ? '#ffffff' : currentMood.color,
    '--theme-text': isRecordView ? '#1e293b' : (isDarkTheme ? '#ffffff' : '#1e293b'),
    '--theme-text-muted': isRecordView ? '#94a3b8' : (isDarkTheme ? 'rgba(255,255,255,0.4)' : 'rgba(30,41,59,0.3)'),
    '--theme-ui-bg': isRecordView ? '#ffffff' : (isDarkTheme ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.9)'),
    '--theme-ui-border': isRecordView ? '#e2e8f0' : (isDarkTheme ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,1)'),
    '--theme-accent': isRecordView ? '#4f46e5' : (isDarkTheme ? '#ffffff' : '#000000'),
    '--theme-accent-text': isRecordView ? '#ffffff' : (isDarkTheme ? '#000000' : '#ffffff'),
    transition: 'all 2000ms cubic-bezier(0.4, 0, 0.2, 1)'
  } as React.CSSProperties;

  const saveEntry = async () => {
    if (!activeMood || isAbsorbing) return;
    setIsAbsorbing(true);
    try {
      if (editingEntryId) {
        const updated = await MoodAPI.updateEntry(editingEntryId, {
          mood_type_id: activeMood.id,
          content: note || undefined,
          factors: selectedImpacts,
        });
        const updatedUI = toMoodEntryUI(updated, typesMap);
        setEntries(prev => prev.map(e => e.id === editingEntryId ? updatedUI : e));
      } else {
        const created = await MoodAPI.createEntry({
          mood_type_id: activeMood.id,
          content: note || undefined,
          factors: selectedImpacts,
        });
        const createdUI = toMoodEntryUI(created, typesMap);
        setEntries(prev => [...prev, createdUI]);
      }
      setJourneyPulse(true);
      setTimeout(() => setJourneyPulse(false), 600);
    } catch (err) {
      console.error('保存心情记录失败:', err);
    }
    // 延迟关闭动画
    setTimeout(() => {
      setIsAbsorbing(false);
      resetPresentState();
    }, 1100);
  };

  const resetPresentState = () => {
    setActiveMood(null);
    setSelectedImpacts([]);
    setNote('');
    setStep('mood');
    setEditingEntryId(null);
  };

  const handleEditEntry = (entry: any) => {
    setActiveMood(entry.mood);
    setSelectedImpacts(entry.impacts || []);
    setNote(entry.note || '');
    setEditingEntryId(entry.id);
    setView('present');
    setStep('write');
  };

  const handleDeleteEntry = async (id: string) => {
    if (!(await window.electronAPI.showConfirm({ message: "确定要删除这条记录吗？" }))) {
      return;
    }
    try {
      await MoodAPI.deleteEntry(id);
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch (err) {
      console.error('删除心情记录失败:', err);
    }
  };

  const toggleImpact = (impact: string) => {
    if (selectedImpacts.includes(impact)) {
      setSelectedImpacts(selectedImpacts.filter(i => i !== impact));
    } else {
      setSelectedImpacts([...selectedImpacts, impact]);
    }
  };

  const handleSaveMood = async (moodData: any) => {
    if (!moodData.text.trim()) return;

    const darkColors = ['#52525b', '#fb7185', '#6366f1', '#a5b4fc', '#8589c9'];
    const isDark = darkColors.includes(moodData.color);

    try {
      if (moodData.id) {
        const updated = await MoodAPI.updateType(moodData.id, {
          name: moodData.text,
          icon: moodData.icon,
          color: moodData.color,
          score: moodData.score,
          is_dark: isDark ? 1 : 0,
        });
        const updatedUI = toMoodTypeUI(updated);
        setMoods(prev => prev.map(m => m.id === moodData.id ? updatedUI : m));
      } else {
        const created = await MoodAPI.createType({
          name: moodData.text,
          icon: moodData.icon,
          color: moodData.color,
          score: moodData.score,
          is_dark: isDark ? 1 : 0,
        });
        const createdUI = toMoodTypeUI(created);
        setMoods(prev => [...prev, createdUI]);
      }
    } catch (err) {
      console.error('保存心情类型失败:', err);
    }
    setEditingMood(null);
  };

  const deleteMood = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await MoodAPI.deleteType(id);
      setMoods(prev => prev.filter(m => m.id !== id));
    } catch (err: any) {
      window.electronAPI.showAlert({ message: err.message || '删除失败，该心情类型下可能有关联记录' });
    }
  };

  return (
    <div 
      className="fixed inset-0 overflow-hidden font-sans select-none" 
      style={themeStyles}
    >
      <div className="absolute inset-0 bg-[var(--theme-bg)] transition-colors duration-[2000ms]" />

      {/* Blob Background for Record View */}
      {isRecordView && (
        <div className="absolute inset-0 z-0">
          <BlobBackground />
        </div>
      )}

      {/* Dynamic Glow for Present View */}
      {!isRecordView && (
        <motion.div 
          animate={{ 
            opacity: isWriting || isAbsorbing || isManagingMoods ? 0.15 : 0.4, 
            filter: isWriting || isAbsorbing || isManagingMoods ? 'blur(180px)' : 'blur(140px)' 
          }} 
          className="absolute inset-0 pointer-events-none"
        >
          <motion.div 
            animate={{ scale: [1, 1.1, 1], rotate: [0, 20, 0] }} 
            transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }} 
            className="absolute -top-1/4 -left-1/4 w-[120vw] h-[120vw] rounded-full" 
            style={{ backgroundColor: currentMood.glow }} 
          />
        </motion.div>
      )}

      <AnimatePresence>
        {(isWriting || isManagingMoods) && !isAbsorbing && (
          <motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }} 
            className="absolute inset-0 z-40 bg-black/5 backdrop-blur-3xl pointer-events-none" 
          />
        )}
      </AnimatePresence>

      <motion.nav 
        animate={{ 
          opacity: (isWriting && !isAbsorbing) || isManagingMoods ? 0 : 1, 
          y: (isWriting && !isAbsorbing) || isManagingMoods ? -20 : 0 
        }} 
        className="absolute top-0 left-0 right-0 p-8 flex justify-between items-center z-50 text-[var(--theme-text)]"
      >
        <button onClick={() => { setView('present'); resetPresentState(); }} className={`text-[10px] tracking-[0.4em] uppercase transition-all ${view === 'present' ? 'opacity-100 font-bold' : 'opacity-30 hover:opacity-100'}`}>当下 Present</button>
        
        <div className="flex items-center gap-6 md:gap-8">
            <button 
              onClick={() => setView('record')} 
              className={`relative text-[10px] tracking-[0.4em] uppercase transition-all ${view === 'record' ? 'opacity-100 font-bold' : 'opacity-30 hover:opacity-100'}`}
            >
              <motion.span animate={journeyPulse ? { scale: [1, 1.2, 1] } : {}} className="inline-block">心情记录 Mood Record</motion.span>
              {journeyPulse && (
                <motion.span initial={{ scale: 0.5, opacity: 1 }} animate={{ scale: 2.5, opacity: 0 }} className="absolute inset-0 bg-white rounded-full blur-md" />
              )}
            </button>

            {/* Separator */}
            <div className="h-3 w-[1px] bg-[var(--theme-text)] opacity-20 hidden md:block" />

            {onOpenGuide && (
              <button 
                onClick={onOpenGuide}
                className="p-3 rounded-full transition-all duration-300 hover:scale-105 active:scale-95 bg-white/50 text-slate-600 hover:bg-white hover:text-indigo-600 hover:shadow-md backdrop-blur-sm border border-transparent hover:border-indigo-100"
                aria-label="User Guide"
              >
                <HelpCircle size={20} strokeWidth={2} />
              </button>
            )}

            {/* Close Button */}
            <button 
                onClick={onBack}
                className="p-2 -mr-2 rounded-full opacity-40 hover:opacity-100 hover:scale-110 transition-all focus:outline-none"
                aria-label="Exit"
            >
                <X size={20} />
            </button>
        </div>
      </motion.nav>

      <main className="relative h-full w-full flex flex-col items-center justify-center p-6 z-[45] text-[var(--theme-text)]">
        {isLoading ? (
          <div className="flex items-center justify-center h-full opacity-40">
            <span className="text-[10px] tracking-[0.4em] uppercase animate-pulse">Loading...</span>
          </div>
        ) : (
        <AnimatePresence mode="wait">
          {view === 'present' ? (
            <motion.div key="present" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="w-full max-w-2xl flex flex-col items-center">
              
              {step === 'mood' && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center w-full">
                  <div className="flex items-center gap-4 mb-16">
                    <h1 className="text-3xl font-extralight tracking-tight opacity-70 text-center">此刻，觉察你的心境</h1>
                    <button 
                      onClick={() => setIsManagingMoods(true)}
                      className="p-2 rounded-full hover:bg-black/5 transition-colors opacity-30 hover:opacity-100"
                    >
                      <Settings2 size={18} strokeWidth={1.5} />
                    </button>
                  </div>

                  <div className="flex flex-wrap justify-center gap-8 md:gap-10 mb-20 px-10">
                    {sortedMoods.map((m) => {
                      const IconComponent = ICON_MAP[m.icon] || Plus;
                      return (
                        <button key={m.id} onClick={() => { setActiveMood(m); setStep('impact'); }} className="group relative flex flex-col items-center gap-4 transition-all duration-700 opacity-40 hover:opacity-100 hover:scale-110 focus:outline-none">
                          <IconComponent strokeWidth={0.8} size={32} />
                          <span className="text-[9px] tracking-[0.2em] absolute -bottom-8 opacity-0 group-hover:opacity-100 transition-all uppercase whitespace-nowrap text-[var(--theme-text)]">{m.text}</span>
                        </button>
                      );
                    })}
                  </div>
                </motion.div>
              )}

              {step === 'impact' && (
                <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center w-full">
                  <h2 className="text-2xl font-extralight mb-4 tracking-tight opacity-80 text-center">是什么在影响你的心绪？</h2>
                  <p className="text-[10px] tracking-[0.3em] mb-12 uppercase opacity-40">生命中的波动皆有定数</p>
                  
                  <div className="flex flex-wrap justify-center gap-3 mb-16 max-w-xl">
                    {impactCategories.map((impact) => (
                      <button
                        key={impact.id}
                        onClick={() => toggleImpact(impact.name)}
                        className={`px-5 py-2 rounded-full text-[11px] tracking-widest transition-all duration-500 border focus:outline-none ${
                          selectedImpacts.includes(impact.name)
                          ? 'bg-[var(--theme-accent)] text-[var(--theme-accent-text)] border-[var(--theme-accent)] shadow-lg scale-105'
                          : 'bg-[var(--theme-ui-bg)] border-[var(--theme-ui-border)] opacity-60 hover:opacity-100'
                        }`}
                      >
                        {impact.name}
                      </button>
                    ))}
                    <button
                      onClick={async () => {
                        const newImpact = prompt("添加新的影响因素:");
                        if (newImpact && !impactCategories.some(i => i.name === newImpact)) {
                          try {
                            const created = await MoodAPI.createImpact({ name: newImpact });
                            setImpactCategories(prev => [...prev, created]);
                          } catch (err) {
                            console.error('添加影响因素失败:', err);
                          }
                        }
                      }}
                      className="px-5 py-2 rounded-full text-[11px] tracking-widest border border-dashed opacity-40 hover:opacity-100 flex items-center gap-2 focus:outline-none"
                    >
                      <Plus size={12} /> 添加
                    </button>
                  </div>

                  <div className="flex gap-10 items-center">
                    <button onClick={() => setStep('mood')} className="text-[10px] uppercase tracking-[0.4em] opacity-40 hover:opacity-100 transition-all focus:outline-none">返回</button>
                    <button onClick={() => setStep('write')} className="px-10 py-3 rounded-full text-[10px] uppercase tracking-[0.4em] font-bold shadow-xl transition-all bg-[var(--theme-accent)] text-[var(--theme-accent-text)] focus:outline-none">下一步</button>
                  </div>
                </motion.div>
              )}

              {step === 'write' && (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.95 }} 
                  animate={isAbsorbing ? { 
                    scale: 0.05, 
                    x: '38vw', 
                    y: '-42vh', 
                    opacity: 0,
                    filter: "blur(30px)"
                  } : { opacity: 1, scale: 1, x: 0, y: 0, filter: "blur(0px)" }}
                  transition={{ 
                    duration: 1.1, 
                    ease: [0.34, 1.56, 0.64, 1] 
                  }}
                  className="w-full max-w-xl flex flex-col items-center relative z-50"
                >
                  <motion.div layoutId="writer-canvas" className="w-full relative p-1 backdrop-blur-md rounded-[48px] shadow-2xl border bg-[var(--theme-ui-bg)] border-[var(--theme-ui-border)]">
                    <div className="absolute top-8 left-12 flex items-center gap-4">
                      {(() => {
                        const WritingIcon = ICON_MAP[activeMood.icon] || Plus;
                        return <WritingIcon size={14} strokeWidth={1.5} className="opacity-40" />;
                      })()}
                      <div className="flex flex-wrap gap-2">
                        {selectedImpacts.map(i => (
                          <span key={i} className="text-[8px] tracking-widest uppercase px-2 py-0.5 rounded bg-[var(--theme-accent)]/5 text-[var(--theme-text-muted)]">{i}</span>
                        ))}
                      </div>
                    </div>
                    <textarea 
                      autoFocus 
                      disabled={isAbsorbing}
                      value={note} 
                      onChange={(e) => setNote(e.target.value)} 
                      placeholder="不留痕迹地倾诉..." 
                      className="w-full bg-transparent border-none focus:ring-0 focus:outline-none text-2xl font-extralight text-center min-h-[380px] pt-32 pb-16 px-12 resize-none leading-relaxed placeholder:opacity-20 text-[var(--theme-text)] shadow-none" 
                    />
                    
                    {isAbsorbing && (
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <motion.div initial={{ opacity: 0 }} animate={{ scale: [1, 2], opacity: [0, 1, 0] }} className="text-[var(--theme-text-muted)]">
                          <Sparkles size={100} strokeWidth={0.5} />
                        </motion.div>
                      </div>
                    )}
                  </motion.div>
                  
                  <AnimatePresence>
                    {!isAbsorbing && (
                      <motion.div exit={{ opacity: 0, y: 10 }} className="flex gap-12 mt-12">
                        <button onClick={() => setStep('impact')} className="text-[10px] uppercase tracking-[0.4em] opacity-40 hover:opacity-100 transition-all focus:outline-none">修改缘由</button>
                        <button onClick={saveEntry} className="px-12 py-4 rounded-full text-[10px] uppercase tracking-[0.4em] font-bold shadow-2xl hover:scale-105 transition-all bg-[var(--theme-accent)] text-[var(--theme-accent-text)] focus:outline-none">
                          {editingEntryId ? '更新记录' : '封存记叙'}
                        </button>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              )}
            </motion.div>
          ) : (
            <motion.div key="record" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="w-full h-full flex flex-col items-center">
               <EmotionRecord 
                entries={entries} 
                onNavigate={onNavigate}
                onEdit={handleEditEntry}
                onDelete={handleDeleteEntry}
              />
            </motion.div>
          )}
        </AnimatePresence>
        )}

        {/* 情绪管理 Overlay */}
        <AnimatePresence>
          {isManagingMoods && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.9 }} 
              animate={{ opacity: 1, scale: 1 }} 
              exit={{ opacity: 0, scale: 0.9 }}
              className="absolute inset-0 z-[60] flex items-center justify-center p-6"
            >
              <div className="w-full max-w-lg bg-[var(--theme-ui-bg)] border border-[var(--theme-ui-border)] backdrop-blur-xl rounded-[40px] p-10 shadow-2xl">
                <div className="flex justify-between items-center mb-10">
                  <h3 className="text-xl font-extralight tracking-widest opacity-80 uppercase">
                    {editingMood ? (editingMood === 'new' ? '新增心境' : '编辑心境') : '管理心境类别'}
                  </h3>
                  <button onClick={() => { setIsManagingMoods(false); setEditingMood(null); }} className="opacity-40 hover:opacity-100 focus:outline-none"><X size={20} /></button>
                </div>

                {!editingMood ? (
                  <>
                    <div className="grid grid-cols-2 gap-4 mb-10 max-h-[40vh] overflow-y-auto custom-scrollbar pr-2">
                      {sortedMoods.map((m) => {
                        const Icon = ICON_MAP[m.icon] || Plus;
                        return (
                          <div 
                            key={m.id} 
                            onClick={() => setEditingMood({...m})}
                            className="flex items-center justify-between p-4 rounded-3xl bg-black/5 hover:bg-black/10 cursor-pointer transition-all border border-transparent hover:border-black/5"
                          >
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full flex items-center justify-center shadow-inner" style={{ backgroundColor: m.color }}>
                                <Icon size={14} className={m.isDark ? 'text-white' : 'text-slate-800'} />
                              </div>
                              <div className="flex flex-col">
                                <span className="text-sm font-light leading-none">{m.text}</span>
                                <span className="text-[8px] opacity-30 mt-1 uppercase tracking-tighter font-bold">Score: {m.score}</span>
                              </div>
                            </div>
                            {moods.length > 1 && (
                              <button 
                                onClick={(e) => deleteMood(m.id, e)} 
                                className="p-2 opacity-10 hover:opacity-100 text-red-500 hover:bg-red-50 rounded-full transition-all focus:outline-none"
                              >
                                <Trash2 size={12} />
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    <button 
                      onClick={() => setEditingMood('new')}
                      className="w-full py-4 rounded-3xl border border-dashed border-[var(--theme-text)]/20 text-[10px] uppercase tracking-[0.4em] opacity-40 hover:opacity-100 hover:bg-black/5 transition-all flex items-center justify-center gap-2 focus:outline-none"
                    >
                      <Plus size={14} /> 新增心境
                    </button>
                  </>
                ) : (
                  <MoodEditor 
                    initialData={editingMood === 'new' ? { text: '', icon: 'Sun', color: '#fed7aa', score: 50 } : editingMood}
                    onCancel={() => setEditingMood(null)}
                    onSave={handleSaveMood}
                  />
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </main>

      <footer className="absolute bottom-10 left-0 right-0 flex justify-center pointer-events-none">
        <p className="text-[9px] tracking-[0.6em] uppercase opacity-20 italic transition-opacity duration-1000" style={{ opacity: isAbsorbing || isManagingMoods ? 0 : 0.2 }}>Less is More · 因缘汇聚</p>
      </footer>

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 1px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: var(--theme-text-muted); }
        textarea:focus { outline: none; }
        * { -webkit-tap-highlight-color: transparent; outline: none !important; }
        input[type='range'] { accent-color: var(--theme-accent); }
      `}</style>
    </div>
  );
};

const MoodEditor = ({ initialData, onCancel, onSave }: any) => {
  const [data, setData] = useState(initialData);

  const handleRangeChange = (visualValue: number) => {
    const actualScore = 100 - visualValue;
    setData({...data, score: actualScore});
  };

  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-3">
          <div className="flex justify-between items-center h-4">
            <label className="text-[10px] uppercase tracking-widest opacity-40">名称</label>
          </div>
          <div className="h-14 flex items-center bg-black/[0.02] rounded-2xl px-4 border border-black/[0.01]">
            <input 
              type="text" 
              maxLength={4}
              placeholder="心境名称"
              value={data.text}
              onChange={(e) => setData({...data, text: e.target.value})}
              className="w-full bg-transparent border-none p-0 text-lg font-extralight focus:ring-0 focus:outline-none placeholder:opacity-20 shadow-none outline-none"
            />
          </div>
        </div>
        
        <div className="space-y-3">
          <div className="flex justify-between items-center h-4">
            <label className="text-[10px] uppercase tracking-widest opacity-40">权重 (Score)</label>
            <span className="text-[10px] opacity-100 font-bold">{data.score}</span>
          </div>
          <div className="h-14 flex items-center bg-black/[0.02] rounded-2xl px-4 border border-black/[0.01]">
            <input 
              type="range" 
              min="0" max="100" 
              step="5"
              value={100 - data.score}
              onChange={(e) => handleRangeChange(parseInt(e.target.value))}
              className="w-full cursor-pointer h-1 rounded-full appearance-none bg-slate-200 focus:outline-none focus:ring-0"
            />
          </div>
        </div>
      </div>
      
      <div className="space-y-3">
        <label className="text-[10px] uppercase tracking-widest opacity-40">选择图标</label>
        <div className="flex flex-wrap gap-2 max-h-[120px] overflow-y-auto custom-scrollbar pr-2">
          {ICON_OPTIONS.map(iconName => {
            const Icon = ICON_MAP[iconName];
            return (
              <button 
                key={iconName}
                onClick={() => setData({...data, icon: iconName})}
                className={`p-3 rounded-2xl transition-all focus:outline-none ${data.icon === iconName ? 'bg-[var(--theme-text)] text-[var(--theme-bg)] shadow-lg' : 'bg-black/5 opacity-40 hover:opacity-70'}`}
              >
                <Icon size={18} />
              </button>
            );
          })}
        </div>
      </div>

      <div className="space-y-3">
        <label className="text-[10px] uppercase tracking-widest opacity-40">视觉配色</label>
        <div className="flex flex-wrap gap-2.5">
          {COLOR_OPTIONS.map(color => (
            <button 
              key={color}
              onClick={() => setData({...data, color})}
              className={`w-10 h-10 rounded-full transition-all border-2 flex items-center justify-center focus:outline-none ${data.color === color ? 'border-[var(--theme-text)] scale-110' : 'border-transparent opacity-60'}`}
              style={{ backgroundColor: color }}
            >
              {data.color === color && <Check size={14} className={['#52525b', '#fb7185', '#6366f1', '#8589c9'].includes(color) ? 'text-white' : 'text-slate-800'} />}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-4 pt-4">
        <button onClick={onCancel} className="flex-1 py-4 rounded-3xl text-[10px] uppercase tracking-widest opacity-40 hover:bg-black/5 transition-all focus:outline-none">取消</button>
        <button 
          onClick={() => onSave(data)}
          className="flex-1 py-4 rounded-3xl bg-[var(--theme-accent)] text-[var(--theme-accent-text)] text-[10px] uppercase tracking-[0.4em] font-bold shadow-xl hover:scale-[1.02] transition-all focus:outline-none"
        >
          保存设置
        </button>
      </div>
    </motion.div>
  );
};

export default EmotionView;
    