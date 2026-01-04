
import React, { useState, useEffect, useCallback } from 'react';
import {
  History,
  Sparkles,
  BookOpen,
  Plus,
  Feather,
  Sun,
  CloudRain,
  Leaf,
  ArrowRight,
  Loader2,
  Check,
  ChevronDown,
  AlertCircle,
  Trash2,
  RefreshCw
} from 'lucide-react';
import { beingApi } from '../api';
import {
  WhoWasIData,
  WhoWasIItem,
  PositivePastReframingItem,
  BeingVersionInfo
} from '../types';

// --- 默认初始数据 ---
const INITIAL_DATA: WhoWasIData = {
  whoWasIItems: [
    { id: 1, content: "", judgeItems: [] },
    { id: 2, content: "", judgeItems: [] },
    { id: 3, content: "", judgeItems: [] }
  ],
  positivePastReframingItems: [
    { id: 1, negativePast: "", positiveTakeaways: "", howPositiveTakeawaysHelpMe: "" },
    { id: 2, negativePast: "", positiveTakeaways: "", howPositiveTakeawaysHelpMe: "" },
    { id: 3, negativePast: "", positiveTakeaways: "", howPositiveTakeawaysHelpMe: "" }
  ]
};

// --- Component ---

const WhoWasITab: React.FC = () => {
  const [data, setData] = useState<WhoWasIData>(INITIAL_DATA);
  const [version, setVersion] = useState<number | null>(null);
  const [versions, setVersions] = useState<BeingVersionInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [showVersionDropdown, setShowVersionDropdown] = useState(false);

  // 加载最新版本数据
  const loadLatestData = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await beingApi.getLatestTest('past');
      if (result) {
        setData(result.content as WhoWasIData);
        setVersion(result.version);
      } else {
        // 没有数据，使用初始数据
        setData(INITIAL_DATA);
        setVersion(null);
      }

      // 加载版本列表
      const versionList = await beingApi.getVersions('past');
      setVersions(versionList.versions);
    } catch (error) {
      console.error('[WhoWasITab] Load failed:', error);
      setData(INITIAL_DATA);
      setVersion(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 加载指定版本
  const loadVersion = async (ver: number) => {
    setIsLoading(true);
    setShowVersionDropdown(false);
    try {
      const result = await beingApi.getTestByVersion('past', ver);
      if (result) {
        setData(result.content as WhoWasIData);
        setVersion(result.version);
      }
    } catch (error) {
      console.error('[WhoWasITab] Load version failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // 初始加载
  useEffect(() => {
    loadLatestData();
  }, [loadLatestData]);

  // 保存数据
  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus('idle');
    try {
      if (version) {
        // 更新现有版本
        await beingApi.updateTest('past', version, data);
      } else {
        // 创建新版本
        const result = await beingApi.createTest('past', data);
        setVersion(result.version);
        // 刷新版本列表
        const versionList = await beingApi.getVersions('past');
        setVersions(versionList.versions);
      }
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('[WhoWasITab] Save failed:', error);
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  // 创建新版本
  const handleCreateNew = async () => {
    setIsSaving(true);
    try {
      const result = await beingApi.createTest('past', data);
      setVersion(result.version);
      // 刷新版本列表
      const versionList = await beingApi.getVersions('past');
      setVersions(versionList.versions);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('[WhoWasITab] Create new failed:', error);
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  };

  // Handlers
  const handleWhoWasIChange = (id: number, val: string) => {
    setData(prev => ({
      ...prev,
      whoWasIItems: prev.whoWasIItems.map(item =>
        item.id === id ? { ...item, content: val } : item
      )
    }));
  };

  const handleAddStatement = () => {
    setData(prev => ({
      ...prev,
      whoWasIItems: [
        ...prev.whoWasIItems,
        { id: Date.now(), content: "", judgeItems: [] }
      ]
    }));
  };

  const handleDeleteStatement = (id: number) => {
    setData(prev => ({
      ...prev,
      whoWasIItems: prev.whoWasIItems.filter(item => item.id !== id)
    }));
  };

  const handleReframeChange = (id: number, field: keyof PositivePastReframingItem, val: string) => {
    setData(prev => ({
      ...prev,
      positivePastReframingItems: prev.positivePastReframingItems.map(item =>
        item.id === id ? { ...item, [field]: val } : item
      )
    }));
  };

  const handleAddReframe = () => {
    setData(prev => ({
      ...prev,
      positivePastReframingItems: [
        ...prev.positivePastReframingItems,
        { id: Date.now(), negativePast: "", positiveTakeaways: "", howPositiveTakeawaysHelpMe: "" }
      ]
    }));
  };

  const handleDeleteReframe = (id: number) => {
    setData(prev => ({
      ...prev,
      positivePastReframingItems: prev.positivePastReframingItems.filter(item => item.id !== id)
    }));
  };

  if (isLoading) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 size={32} className="text-stone-400 animate-spin" />
          <p className="text-stone-500 font-medium">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full overflow-y-auto no-scrollbar pb-20 px-4 md:px-12 pt-6 animate-fade-in font-sans">

      {/* Header - Centered & Calming */}
      <div className="max-w-3xl mx-auto text-center mb-12">
        <div className="flex items-center justify-center gap-4 mb-4">
          <div className="inline-flex items-center justify-center p-3 bg-stone-100/50 rounded-full text-stone-500 shadow-sm border border-stone-100">
            <Feather size={20} />
          </div>

          {/* Version Selector */}
          <div className="relative">
            <button
              onClick={() => setShowVersionDropdown(!showVersionDropdown)}
              className="flex items-center gap-2 px-4 py-2 bg-stone-100 hover:bg-stone-200 rounded-full text-sm font-medium text-stone-600 transition-colors"
            >
              {version ? `版本 ${version}` : '新版本'}
              <ChevronDown size={16} className={`transition-transform ${showVersionDropdown ? 'rotate-180' : ''}`} />
            </button>

            {showVersionDropdown && (
              <div className="absolute top-full mt-2 left-0 bg-white rounded-xl shadow-xl border border-stone-100 overflow-hidden z-50 min-w-[160px]">
                {versions.length > 0 ? (
                  versions.map(v => (
                    <button
                      key={v.id}
                      onClick={() => loadVersion(v.version)}
                      className={`w-full px-4 py-2.5 text-left text-sm hover:bg-stone-50 transition-colors flex items-center justify-between ${v.version === version ? 'bg-stone-50 font-medium' : ''}`}
                    >
                      <span>版本 {v.version}</span>
                      {v.version === version && <Check size={14} className="text-stone-500" />}
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-sm text-stone-400">暂无历史版本</div>
                )}
                <div className="border-t border-stone-100">
                  <button
                    onClick={handleCreateNew}
                    className="w-full px-4 py-2.5 text-left text-sm text-amber-600 hover:bg-amber-50 transition-colors flex items-center gap-2"
                  >
                    <Plus size={14} />
                    创建新版本
                  </button>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={loadLatestData}
            className="p-2 text-stone-400 hover:text-stone-600 hover:bg-stone-100 rounded-lg transition-colors"
            title="刷新"
          >
            <RefreshCw size={18} />
          </button>
        </div>

        <h2 className="text-3xl md:text-4xl font-bold text-stone-800 tracking-tight mb-4">The Journey of You</h2>
        <p className="text-stone-500 text-lg leading-relaxed font-medium">
          Honoring who you were to understand who you are becoming. <br />
          <span className="text-sm opacity-70 italic font-normal">Take a deep breath. There are no wrong answers here.</span>
        </p>
      </div>

      <div className="max-w-4xl mx-auto space-y-12">

        {/* Section 1: Identity Evolution */}
        <section className="bg-white rounded-[2.5rem] p-8 md:p-12 shadow-[0_8px_30px_rgb(0,0,0,0.02)] border border-stone-100 relative overflow-hidden">
          {/* Decorative soft gradients */}
          <div className="absolute top-0 right-0 w-80 h-80 bg-orange-50/30 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none"></div>
          <div className="absolute bottom-0 left-0 w-80 h-80 bg-stone-100/30 rounded-full blur-3xl -ml-20 -mb-20 pointer-events-none"></div>

          <div className="relative z-10 mb-10 flex items-center gap-5 border-b border-stone-50 pb-6">
            <div className="w-14 h-14 bg-[#F5F5F4] rounded-2xl flex items-center justify-center text-stone-600 shadow-sm">
              <History size={26} strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-xl font-bold text-stone-800">Past Narratives</h3>
              <p className="text-stone-400 text-sm font-medium mt-1">What old stories are you ready to acknowledge?</p>
            </div>
          </div>

          <div className="space-y-6 relative z-10">
            {data.whoWasIItems.map((item, index) => (
              <div key={item.id} className="group transition-all duration-300">
                <div className="flex items-baseline gap-4">
                  <span className="text-xs font-bold text-stone-300 font-mono w-6 text-right pt-4">{index + 1}</span>
                  <div className="flex-1 relative">
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 text-stone-400 font-medium text-sm pl-4 pointer-events-none select-none">I used to be...</span>
                    <input
                      type="text"
                      value={item.content}
                      onChange={(e) => handleWhoWasIChange(item.id, e.target.value)}
                      className="w-full bg-[#FAFAF9] hover:bg-[#F5F5F4] focus:bg-white border border-transparent focus:border-stone-200 rounded-2xl py-4 pl-32 pr-12 text-stone-700 font-medium outline-none transition-all placeholder-stone-300 shadow-sm focus:shadow-md focus:ring-4 focus:ring-stone-50"
                      placeholder="timid, defined by grades, afraid of conflict..."
                    />
                    <button
                      onClick={() => handleDeleteStatement(item.id)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 p-2 text-stone-300 hover:text-red-400 hover:bg-red-50 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            ))}

            <div className="pl-12 pt-2">
              <button
                onClick={handleAddStatement}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-xs font-bold text-stone-400 hover:text-stone-600 hover:bg-stone-50 transition-all border border-transparent hover:border-stone-200 border-dashed tracking-wider uppercase"
              >
                <Plus size={14} /> Add reflection
              </button>
            </div>
          </div>
        </section>

        {/* Section 2: Reframing */}
        <section className="space-y-8">
          <div className="flex items-center justify-between px-2">
            <div className="flex items-center gap-5">
              <div className="w-14 h-14 bg-amber-50 rounded-2xl flex items-center justify-center text-amber-600/80 shadow-sm">
                <Sun size={26} strokeWidth={1.5} />
              </div>
              <div>
                <h3 className="text-xl font-bold text-stone-800">Growth Through Perspective</h3>
                <p className="text-stone-400 text-sm font-medium mt-1">Transforming heavy memories into light.</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-10">
            {data.positivePastReframingItems.map((item, index) => (
              <div key={item.id} className="bg-white rounded-[2.5rem] p-2 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.02)] border border-stone-100 hover:shadow-[0_8px_30px_-4px_rgba(0,0,0,0.05)] transition-shadow duration-500 group relative">

                {/* Delete Button */}
                <button
                  onClick={() => handleDeleteReframe(item.id)}
                  className="absolute top-4 right-4 p-2 text-stone-300 hover:text-red-400 hover:bg-red-50 rounded-full opacity-0 group-hover:opacity-100 transition-all z-20"
                >
                  <Trash2 size={18} />
                </button>

                {/* Inner Container */}
                <div className="flex flex-col md:flex-row h-full">
                  {/* Left: The Challenge */}
                  <div className="flex-1 p-6 md:p-8 space-y-4 bg-[#FEF2F2]/30 rounded-[2rem] md:rounded-r-none md:rounded-l-[2rem] border-b md:border-b-0 md:border-r border-rose-100/50">
                    <div className="flex items-center gap-2 text-rose-400/80 mb-2">
                      <CloudRain size={18} />
                      <span className="text-[10px] font-black uppercase tracking-widest">The Challenge</span>
                    </div>
                    <textarea
                      value={item.negativePast}
                      onChange={(e) => handleReframeChange(item.id, 'negativePast', e.target.value)}
                      className="w-full bg-white/60 focus:bg-white border border-transparent focus:border-rose-100 rounded-2xl p-4 text-stone-700 leading-relaxed resize-none outline-none transition-all placeholder-rose-200 text-sm min-h-[140px]"
                      placeholder="Describe a difficult moment from your past..."
                    />
                  </div>

                  {/* Middle Connector (Desktop) */}
                  <div className="hidden md:flex flex-col justify-center -mx-4 z-10 relative">
                    <div className="w-10 h-10 bg-white rounded-full border border-stone-100 shadow-sm flex items-center justify-center text-stone-300">
                      <ArrowRight size={16} />
                    </div>
                  </div>

                  {/* Right: The Gift (Split) */}
                  <div className="flex-[1.6] p-6 md:p-8 flex flex-col gap-6">
                    {/* Lesson */}
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-emerald-600/70">
                        <Leaf size={16} />
                        <span className="text-[10px] font-black uppercase tracking-widest">The Hidden Gift</span>
                      </div>
                      <textarea
                        value={item.positiveTakeaways}
                        onChange={(e) => handleReframeChange(item.id, 'positiveTakeaways', e.target.value)}
                        className="w-full bg-emerald-50/20 focus:bg-emerald-50/50 border border-transparent focus:border-emerald-100 rounded-2xl p-4 text-stone-700 leading-relaxed resize-none outline-none transition-all placeholder-emerald-200/50 text-sm h-24"
                        placeholder="What strength or lesson did this experience reveal in you?"
                      />
                    </div>

                    {/* Application */}
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-blue-500/70">
                        <Sparkles size={16} />
                        <span className="text-[10px] font-black uppercase tracking-widest">Wisdom for Today</span>
                      </div>
                      <textarea
                        value={item.howPositiveTakeawaysHelpMe}
                        onChange={(e) => handleReframeChange(item.id, 'howPositiveTakeawaysHelpMe', e.target.value)}
                        className="w-full bg-blue-50/20 focus:bg-blue-50/50 border border-transparent focus:border-blue-100 rounded-2xl p-4 text-stone-700 leading-relaxed resize-none outline-none transition-all placeholder-blue-200/50 text-sm h-24"
                        placeholder="How does this help you move forward fearlessly?"
                      />
                    </div>
                  </div>
                </div>

              </div>
            ))}

            {/* Add Reframe Button */}
            <button
              onClick={handleAddReframe}
              className="w-full py-6 rounded-[2rem] border-2 border-dashed border-stone-200 text-stone-400 font-bold hover:border-amber-300 hover:text-amber-600 hover:bg-amber-50/30 transition-all flex flex-col items-center justify-center gap-2"
            >
              <Plus size={24} />
              <span>Add New Story</span>
            </button>
          </div>
        </section>

        {/* Footer Action */}
        <div className="flex justify-center pt-8 pb-8">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className={`px-10 py-5 rounded-2xl font-bold shadow-[0_10px_20px_-5px_rgba(68,64,60,0.2)] hover:shadow-[0_15px_25px_-5px_rgba(68,64,60,0.3)] hover:-translate-y-1 transition-all flex items-center gap-3 text-sm tracking-wide ${saveStatus === 'success'
                ? 'bg-emerald-600 text-white'
                : saveStatus === 'error'
                  ? 'bg-red-600 text-white'
                  : 'bg-stone-800 text-[#FAF9F6]'
              } ${isSaving ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {isSaving ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                <span>保存中...</span>
              </>
            ) : saveStatus === 'success' ? (
              <>
                <Check size={18} />
                <span>保存成功</span>
              </>
            ) : saveStatus === 'error' ? (
              <>
                <AlertCircle size={18} />
                <span>保存失败</span>
              </>
            ) : (
              <>
                <BookOpen size={18} />
                <span>Save Reflections</span>
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
};

export default WhoWasITab;
