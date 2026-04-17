import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Settings, History, ChevronLeft, ChevronRight, X, HelpCircle, Save } from 'lucide-react';
import { toast } from '../../../../core/components';
import { MarkdownEditor } from '@my-ui-kit/core';
import type { MarkdownEditorRef } from '@my-ui-kit/core';
import DiaryTagBar from './DiaryTagBar';
import SettingsPopover from './SettingsPopover';
import TemplateManager from './TemplateManager';
import { DiaryAPI } from './diaryApi';
import { BG_PRESETS } from './diaryConstants';
import type { DiaryItem, MoodLevel, ImportanceLevel } from './diaryTypes';
import { toLocalDateString } from '../../../../core/utils/dateUtils';

/**
 * JournalView - 禅意日记书写空间
 * 集成 MarkdownEditor、心情/重要程度标签、模板管理
 */

interface JournalViewProps {
  onBack?: () => void;
  onOpenGuide?: () => void;
}

const STORAGE_KEY_HSL = 'diary-bg-hsl';

const JournalView: React.FC<JournalViewProps> = ({ onBack, onOpenGuide }) => {
  // 日记数据
  const [diary, setDiary] = useState<DiaryItem | null>(null);
  const [content, setContent] = useState('');
  const [activeDate, setActiveDate] = useState(new Date());
  const [loading, setLoading] = useState(false);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);

  // UI 状态
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [settingsView, setSettingsView] = useState(false);
  const [showSettingsPopover, setShowSettingsPopover] = useState(false);
  const [showTemplateManager, setShowTemplateManager] = useState(false);
  const [shouldScrollToDate, setShouldScrollToDate] = useState(true);

  // 背景色（localStorage 持久化）
  const [hsl, setHsl] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_HSL);
      return saved ? JSON.parse(saved) : { h: 200, s: 15, l: 92 };
    } catch { return { h: 200, s: 15, l: 92 }; }
  });
  const bgColor = `hsl(${hsl.h}, ${hsl.s}%, ${hsl.l}%)`;
  const neutralDark = '#262626';

  const editorRef = useRef<MarkdownEditorRef>(null);
  const settingsBtnRef = useRef<HTMLButtonElement>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 编辑器重挂载/切日期时的水合保护期，忽略编辑器内部初始化 onChange 噪音
  const isHydratingEditorRef = useRef(true);
  const hydrationReleaseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 用于在日期切换时 flush 挂起的保存，存储当前待保存的 {date, content}
  const pendingSaveRef = useRef<{ dateStr: string; content: string } | null>(null);
  // 追踪正在执行中的保存请求，避免 flush 遗漏 in-flight 请求
  const inflightSaveRef = useRef<Promise<void> | null>(null);
  // 区分首次挂载加载 vs 后续日期切换：首次加载不 flush（避免虚假空内容覆盖）
  const isInitialLoadRef = useRef(true);

  // ========== 日期格式化 ==========
  const formatDate = toLocalDateString;

  const isSameDay = (d1: Date, d2: Date) =>
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate();

  // ========== Flush 挂起的保存 ==========
  // 返回值：true 表示实际执行了保存（pending 被写入或 inflight 请求被等待）
  const flushPendingSave = useCallback(async (): Promise<boolean> => {
    let didSave = false;
    // 取消定时器
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    // 等待正在执行中的保存请求完成
    if (inflightSaveRef.current) {
      await inflightSaveRef.current;
      inflightSaveRef.current = null;
    }
    // 如果有挂起的保存数据（定时器还没触发的），立即执行保存
    const pending = pendingSaveRef.current;
    if (pending) {
      pendingSaveRef.current = null;
      try {
        await DiaryAPI.saveContent(pending.dateStr, { content: pending.content });
        didSave = true;
      } catch (e) {
        console.error('flush 保存日记内容失败:', e);
        toast.error('自动保存失败，请重试');
      }
    }
    return didSave;
  }, []);

  // ========== 加载日记 ==========
  const loadDiary = useCallback(async (date: Date) => {
    const dateStr = formatDate(date);
    try {
      isHydratingEditorRef.current = true;
      // 先进入 loading 状态隐藏编辑器，防止 flush 期间用户继续输入导致跨日期写入
      setLoading(true);
      if (isInitialLoadRef.current) {
        // 首次挂载：丢弃由 MarkdownEditor 初始化（value='' → onUpdate → handleContentChange('')）
        // 产生的虚假 pending 数据，避免空内容覆盖后端已保存的日记
        if (saveTimerRef.current) {
          clearTimeout(saveTimerRef.current);
          saveTimerRef.current = null;
        }
        pendingSaveRef.current = null;
        // 仍需等待 inflight 请求完成（虽然首次挂载极少有 inflight）
        if (inflightSaveRef.current) {
          await inflightSaveRef.current;
          inflightSaveRef.current = null;
        }
      } else {
        // 后续日期切换：正常 flush 上一个日期挂起的保存，确保数据不丢失
        const saved = await flushPendingSave();
        if (saved) toast.success('日记已自动保存');
      }
      const data = await DiaryAPI.getDiary(dateStr);
      setDiary(data);
      const newContent = data.content || '';
      setContent(newContent);
      // 同步到编辑器
      if (editorRef.current) {
        editorRef.current.setMarkdown(newContent);
      }
    } catch (e) {
      console.error('加载日记失败:', e);
      setDiary(null);
      setContent('');
      if (editorRef.current) {
        editorRef.current.setMarkdown('');
      }
    } finally {
      setLoading(false);
      if (hydrationReleaseTimerRef.current) {
        clearTimeout(hydrationReleaseTimerRef.current);
      }
      hydrationReleaseTimerRef.current = setTimeout(() => {
        isHydratingEditorRef.current = false;
        isInitialLoadRef.current = false;
        hydrationReleaseTimerRef.current = null;
      }, 0);
    }
  }, [flushPendingSave]);

  useEffect(() => { loadDiary(activeDate); }, [activeDate, loadDiary]);

  // ========== 保存背景色 ==========
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_HSL, JSON.stringify(hsl));
  }, [hsl]);

  // ========== 内容自动保存（防抖 1.5s） ==========
  const handleContentChange = useCallback((md: string) => {
    if (isHydratingEditorRef.current) return;
    // 双重防护：loadDiary 尚未完成首次加载时，忽略编辑器初始化产生的噪音内容
    // 这处理 MarkdownEditor 的 onUpdate 比 loadDiary useEffect 更晚触发的竞态情况
    if (isInitialLoadRef.current && (md === '' || md === '\n\n')) return;
    setContent(md);
    const dateStr = formatDate(activeDate);
    // 记录待保存数据，供 flush 使用
    pendingSaveRef.current = { dateStr, content: md };
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      // 定时器触发时清除 pending 标记和定时器引用
      pendingSaveRef.current = null;
      saveTimerRef.current = null;
      // 将保存请求存入 inflightSaveRef，供 flush 追踪
      const savePromise = (async () => {
        try {
          const updated = await DiaryAPI.saveContent(dateStr, { content: md });
          setDiary(prev => prev ? { ...prev, word_count: updated.word_count, updated_at: updated.updated_at } : prev);
          toast.success('日记已自动保存');
        } catch (e) {
          console.error('保存日记内容失败:', e);
          toast.error('自动保存失败，请重试');
        } finally {
          // 请求完成后清除 inflight 引用
          if (inflightSaveRef.current === savePromise) {
            inflightSaveRef.current = null;
          }
        }
      })();
      inflightSaveRef.current = savePromise;
    }, 1500);
  }, [activeDate]);

  // 组件卸载时 flush 挂起的保存（退出日记界面时）
  useEffect(() => () => {
    if (hydrationReleaseTimerRef.current) {
      clearTimeout(hydrationReleaseTimerRef.current);
      hydrationReleaseTimerRef.current = null;
    }
    flushPendingSave();
  }, [flushPendingSave]);

  // ========== 手动保存（按钮 / Ctrl+S） ==========
  const handleManualSave = useCallback(async () => {
    const hasPending = !!pendingSaveRef.current;
    const hasInflight = !!inflightSaveRef.current;
    // 如果既没有 pending 也没有 inflight，说明无新改动
    if (!hasPending && !hasInflight) {
      toast.info('无新改动');
      return;
    }
    try {
      // 取消防抖定时器，取当前 pending 内容立即保存
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
      // 等待任何 inflight 请求
      if (inflightSaveRef.current) {
        await inflightSaveRef.current;
        inflightSaveRef.current = null;
      }
      // 若还有 pending 内容则立即保存（使用 pending.dateStr 而非 activeDate，防止日期切换时写错日期）
      const pending = pendingSaveRef.current;
      if (pending) {
        pendingSaveRef.current = null;
        const updated = await DiaryAPI.saveContent(pending.dateStr, { content: pending.content });
        setDiary(prev => prev ? { ...prev, word_count: updated.word_count, updated_at: updated.updated_at } : prev);
      }
      toast.success('日记已保存');
    } catch (e) {
      console.error('手动保存日记失败:', e);
      toast.error('保存失败，请重试');
    }
  }, []);

  // ========== Ctrl+S 全局快捷键 ==========
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        handleManualSave();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleManualSave]);

  // ========== AI 总结 ==========
  const handleGenerateSummary = useCallback(async () => {
    const dateStr = formatDate(activeDate);
    if (!content.trim()) {
      toast.info('日记为空，无法总结');
      return;
    }

    try {
      setIsGeneratingSummary(true);
      await flushPendingSave();
      const response = await DiaryAPI.generateAiSummary(dateStr);
      setDiary(prev => prev ? { ...prev, ai_summary: response.content } : prev);
      toast.success('AI 总结已生成');
    } catch (e) {
      console.error('生成日记 AI 总结失败:', e);
      toast.error('AI 总结生成失败');
    } finally {
      setIsGeneratingSummary(false);
    }
  }, [activeDate, content, flushPendingSave]);

  // ========== Meta 更新 ==========
  const handleMoodChange = async (mood: MoodLevel) => {
    const dateStr = formatDate(activeDate);
    try {
      const updated = await DiaryAPI.updateMeta(dateStr, { mood });
      setDiary(prev => prev ? { ...prev, mood: updated.mood } : prev);
    } catch (e) { console.error('更新心情失败:', e); }
  };

  const handleImportanceChange = async (importance: ImportanceLevel) => {
    const dateStr = formatDate(activeDate);
    try {
      const updated = await DiaryAPI.updateMeta(dateStr, { importance });
      setDiary(prev => prev ? { ...prev, importance: updated.importance } : prev);
    } catch (e) { console.error('更新重要程度失败:', e); }
  };

  const handleCustomTagsChange = async (tags: string[]) => {
    const dateStr = formatDate(activeDate);
    try {
      const updated = await DiaryAPI.updateMeta(dateStr, { custom_tags: tags });
      setDiary(prev => prev ? { ...prev, custom_tags: updated.custom_tags } : prev);
    } catch (e) { console.error('更新自定义标签失败:', e); }
  };

  // ========== 模板应用 ==========
  const handleApplyTemplate = (templateContent: string) => {
    const newContent = content ? `${content}\n\n${templateContent}` : templateContent;
    setContent(newContent);
    if (editorRef.current) {
      editorRef.current.setMarkdown(newContent);
    }
    handleContentChange(newContent);
  };

  // ========== HSL 控制 ==========
  const handleHslChange = (key: string, value: string) => {
    setHsl((prev: any) => ({ ...prev, [key]: parseInt(value) }));
  };

  const handleBackToToday = () => {
    setActiveDate(new Date());
    setSettingsView(false);
    setShouldScrollToDate(true);
  };

  // ========== 初始定位与滚动 ==========
  useEffect(() => {
    if (settingsView || !shouldScrollToDate) return;
    const timer = setTimeout(() => {
      const scrollId = `diary-date-${activeDate.getFullYear()}-${activeDate.getMonth()}-${activeDate.getDate()}`;
      const el = document.getElementById(scrollId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      setShouldScrollToDate(false);
    }, 100);
    return () => clearTimeout(timer);
  }, [activeDate, settingsView, shouldScrollToDate]);

  // ========== 月历数据 ==========
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
    const day = new Date(year, month, 1).getDay();
    return day === 0 ? 6 : day - 1;
  };

  // ========== MonthBlock 子组件 ==========
  const MonthBlock = ({ date }: { date: Date }) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const totalDays = getDaysInMonth(year, month);
    const startOffset = getFirstDayOfMonth(year, month);
    const monthName = date.toLocaleString('zh-CN', { month: 'long' });

    const days: (number | null)[] = [];
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
            const currentDate = new Date(year, month, day);
            const isActive = isSameDay(activeDate, currentDate);
            return (
              <button
                key={`${year}-${month}-${day}`}
                id={`diary-date-${year}-${month}-${day}`}
                onClick={() => setActiveDate(currentDate)}
                className={`aspect-square rounded-full flex items-center justify-center transition-all duration-300 relative text-sm group ${isActive
                  ? 'text-white scale-110 shadow-[0_8px_20px_-5px_rgba(0,0,0,0.3)] z-10'
                  : 'hover:bg-black/10 hover:scale-110 hover:shadow-sm text-gray-500 hover:text-black active:scale-95'
                  }`}
                style={{ backgroundColor: isActive ? neutralDark : 'transparent' }}
              >
                {day}
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  // ========== 渲染 ==========
  return (
    <div className="flex h-screen w-full font-sans overflow-hidden relative transition-colors duration-1000" style={{ backgroundColor: bgColor }}>
      {/* 背景纹理 */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden select-none z-0">
        <div className="absolute inset-0 opacity-[0.05]" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }} />
      </div>

      {/* 侧边栏切换按钮 */}
      <button
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        className={`fixed top-[37px] z-50 p-2.5 rounded-full border border-black/5 bg-white/40 backdrop-blur-xl shadow-sm hover:shadow-md hover:scale-105 active:scale-95 transition-all duration-700 ease-[cubic-bezier(0.23,1,0.32,1)] ${isSidebarOpen ? 'left-[300px] md:left-[364px]' : 'left-8'
          } text-gray-700 hover:text-black`}
      >
        {isSidebarOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
      </button>

      {/* 左侧侧边栏 */}
      <aside className={`fixed inset-y-0 left-0 z-40 bg-white/40 backdrop-blur-2xl border-r border-black/[0.03] transition-all duration-700 ease-[cubic-bezier(0.23,1,0.32,1)] transform ${isSidebarOpen ? 'translate-x-0 w-80 md:w-96' : '-translate-x-full w-80 md:w-96'
        }`}>
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
                      { label: '亮度', key: 'l', max: 100, bg: `linear-gradient(to right, #333, hsl(${hsl.h}, ${hsl.s}%, 50%), #fff)` },
                    ].map(slider => (
                      <div key={slider.key} className="space-y-2">
                        <div className="flex justify-between text-[9px] text-gray-400 uppercase font-medium tracking-tighter">
                          <span>{slider.label}</span>
                          <span>{(hsl as any)[slider.key]}{slider.key === 'h' ? '°' : '%'}</span>
                        </div>
                        <input
                          type="range" min="0" max={slider.max}
                          value={(hsl as any)[slider.key]}
                          onChange={e => handleHslChange(slider.key, e.target.value)}
                          className="w-full h-[3px] rounded-full appearance-none cursor-pointer bg-black/5"
                          style={{ background: slider.bg }}
                        />
                      </div>
                    ))}
                  </div>
                  <div className="pt-4 flex flex-col items-center space-y-5">
                    <div className="w-12 h-12 rounded-full border-4 border-white shadow-xl transition-all duration-500" style={{ backgroundColor: bgColor }} />
                    <div className="flex flex-wrap justify-center gap-3">
                      {BG_PRESETS.map(p => (
                        <button
                          key={p.name}
                          onClick={() => setHsl({ h: p.h, s: p.s, l: p.l })}
                          className="w-5 h-5 rounded-full border-2 border-white shadow-sm transition-all hover:scale-125 hover:shadow-md"
                          style={{ backgroundColor: `hsl(${p.h}, ${p.s}%, ${p.l}%)` }}
                        />
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

          <div className="p-10 flex justify-around text-gray-500 opacity-80 shrink-0 border-t border-black/[0.02] relative z-30">
            <button
              ref={settingsBtnRef}
              onClick={() => setShowSettingsPopover(!showSettingsPopover)}
              title="设置"
              className={`p-2 rounded-full transition-all duration-500 ${showSettingsPopover ? 'bg-black text-white rotate-180 scale-110 opacity-100' : 'hover:text-black hover:bg-black/5'
                }`}
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

            {/* 设置上拉菜单 */}
            <SettingsPopover
              open={showSettingsPopover}
              onClose={() => setShowSettingsPopover(false)}
              onSelectColor={() => setSettingsView(true)}
              onSelectTemplate={() => setShowTemplateManager(true)}
              anchorRect={settingsBtnRef.current?.getBoundingClientRect()}
            />
          </div>
        </div>
      </aside>

      {/* 主体书写区 */}
      <main className={`flex-1 relative flex flex-col z-10 transition-all duration-700 ease-[cubic-bezier(0.23,1,0.32,1)] ${isSidebarOpen ? 'ml-80 md:ml-96' : 'ml-0'
        }`}>
        {/* 顶部：日期 + 标签 + 操作 */}
        <header className="px-12 md:px-24 pt-8 pb-4 shrink-0 relative z-10">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-baseline space-x-6">
              <h1 className="text-[32px] font-serif italic text-gray-800 tracking-tight leading-none">
                {formatDate(activeDate)}
              </h1>
              <span className="text-[10px] font-bold uppercase tracking-[0.4em] opacity-30 text-black leading-none">
                {diary?.word_count || 0} 字
              </span>
            </div>
            <div className="flex space-x-4 text-gray-400/50 items-center">
              {/* 保存按钮 */}
              <button
                onClick={handleManualSave}
                title="保存 (Ctrl+S)"
                className="p-2.5 rounded-full transition-all duration-300 hover:scale-105 active:scale-95 bg-white/50 text-slate-600 hover:bg-white hover:text-emerald-600 hover:shadow-md backdrop-blur-sm border border-transparent hover:border-emerald-100"
                aria-label="保存日记"
              >
                <Save size={18} strokeWidth={2} />
              </button>
              {onOpenGuide && (
                <button
                  onClick={onOpenGuide}
                  className="p-2.5 rounded-full transition-all duration-300 hover:scale-105 active:scale-95 bg-white/50 text-slate-600 hover:bg-white hover:text-indigo-600 hover:shadow-md backdrop-blur-sm border border-transparent hover:border-indigo-100"
                  aria-label="User Guide"
                >
                  <HelpCircle size={18} strokeWidth={2} />
                </button>
              )}
              {onBack && (
                <button onClick={onBack} className="hover:text-black hover:-translate-y-0.5 transition-all" title="退出">
                  <X size={20} />
                </button>
              )}
            </div>
          </div>

          {/* 标签栏 */}
          <DiaryTagBar
            mood={diary?.mood || null}
            importance={diary?.importance || null}
            customTags={diary?.custom_tags || []}
            onMoodChange={handleMoodChange}
            onImportanceChange={handleImportanceChange}
            onCustomTagsChange={handleCustomTagsChange}
          />

        </header>

        {/* 滚动区域：包含 AI 总结和编辑区 */}
        <section className="flex-1 overflow-y-auto no-scrollbar relative z-10 flex flex-col">
          {/* AI 总结 */}
          <div className="px-12 md:px-24 shrink-0">
            <div className="mt-6 mb-2 pb-5 border-b border-gray-800/20">
              {!diary?.ai_summary && !isGeneratingSummary ? (
                <button
                  onClick={handleGenerateSummary}
                  className="flex items-center text-[12px] font-medium tracking-[0.25em] text-gray-400 hover:text-black transition-colors duration-300 group"
                >
                  <span className="mr-1.5 opacity-50 group-hover:opacity-100 transition-opacity">✨</span> 
                  生成 AI 总结
                </button>
              ) : (
                <div className="w-full">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-2 text-[12px] font-medium tracking-[0.2em] text-gray-400">
                      <span className="opacity-80">✨</span>
                      <span>{isGeneratingSummary ? '正在凝练思绪...' : 'AI 总结'}</span>
                    </div>
                    {!isGeneratingSummary && (
                      <button
                        onClick={handleGenerateSummary}
                        title="重新生成总结"
                        className="text-[10px] text-gray-300 hover:text-gray-600 tracking-[0.1em] transition-colors"
                      >
                        重新生成
                      </button>
                    )}
                  </div>
                  {diary?.ai_summary && (
                    <div className="pl-4 border-l-2 border-gray-800/20 whitespace-pre-wrap text-[14px] leading-[2.2] text-gray-700 font-serif italic">
                      {diary.ai_summary}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 编辑区 */}
          <div className="flex-1 px-12 md:px-24 py-6 flex flex-col">
            {loading ? (
              <div className="flex items-center justify-center flex-1">
                <p className="text-[12px] text-gray-300 italic tracking-wider">加载中...</p>
              </div>
            ) : (
              <div className="diary-editor flex-1">
                <MarkdownEditor
                  ref={editorRef}
                  value={content}
                  onChange={handleContentChange}
                  placeholder="在此处，开启一段与自我的深谈..."
                  minHeight="100%"
                />
              </div>
            )}
          </div>
        </section>

        {/* 底部 */}
        <footer className="h-14 px-12 md:px-24 flex items-center justify-between relative z-10 opacity-20 select-none border-t border-black/[0.01]">
          <div className="flex space-x-4 text-[9px] uppercase tracking-[0.5em] text-gray-500 font-bold">
            <span>Inner Dialogue</span>
            <span>·</span>
            <span>Continuum</span>
          </div>
          <div className="text-[11px] font-serif italic">文字是通往内心的阶梯</div>
        </footer>
      </main>

      {/* 模板管理弹窗 */}
      <TemplateManager
        open={showTemplateManager}
        onClose={() => setShowTemplateManager(false)}
        onApplyTemplate={handleApplyTemplate}
      />

      <style dangerouslySetInnerHTML={{
        __html: `
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        .font-serif { font-family: ui-serif, Georgia, Cambria, "Times New Roman", Times, serif; }
        ::selection { background: rgba(0,0,0,0.08); color: ${neutralDark}; }
        input[type=range] { -webkit-appearance: none; }
        input[type=range]::-webkit-slider-thumb {
          -webkit-appearance: none;
          height: 12px; width: 12px; border-radius: 50%; background: white;
          box-shadow: 0 2px 6px rgba(0,0,0,0.15); cursor: pointer; border: 1.5px solid #eee;
          margin-top: -4.5px; transition: transform 0.2s;
        }
        input[type=range]::-webkit-slider-thumb:hover { transform: scale(1.2); }
        /* MarkdownEditor 禅意样式覆盖 */
        .diary-editor .mdxeditor {
          background: transparent !important;
          border: none !important;
          font-family: ui-serif, Georgia, Cambria, "Times New Roman", Times, serif;
        }
        .diary-editor .mdxeditor [role="toolbar"] {
          background: transparent !important;
          border-bottom: 1px solid rgba(0,0,0,0.03) !important;
          opacity: 0.5;
          transition: opacity 0.3s;
        }
        .diary-editor .mdxeditor [role="toolbar"]:hover {
          opacity: 1;
        }
        .diary-editor .mdxeditor [contenteditable] {
          font-size: 18px !important;
          line-height: 2 !important;
          color: #1f2937 !important;
          padding: 0 !important;
        }
        .diary-editor .mdxeditor [contenteditable] p {
          margin-bottom: 0.8em;
        }
        .diary-pill:hover {
          background: var(--pill-hover-bg) !important;
          border-color: var(--pill-hover-border) !important;
          color: var(--pill-hover-color) !important;
        }
      `}} />
    </div>
  );
};

export default JournalView;
