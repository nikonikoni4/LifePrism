
import React, { useState, useEffect, useCallback } from 'react';
import {
  Rocket,
  Target,
  Calendar,
  Plus,
  Trash2,
  BookOpen,
  Sparkles,
  Zap,
  Loader2,
  Check,
  ChevronDown,
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import { beingApi } from '../api';
import {
  WhoIWantToBeData,
  WhoIWantToBeItem,
  SpecificGoalsItem,
  BeingVersionInfo
} from '../types';

// --- 默认初始数据 ---
const INITIAL_DATA: WhoIWantToBeData = {
  whoIWantToBeItems: [
    { id: 1, whoIWantToBe: "" },
    { id: 2, whoIWantToBe: "" },
    { id: 3, whoIWantToBe: "" }
  ],
  specificGoalsItems: [
    { id: 1, specificGoals: "", whenWillIReachThem: "" },
    { id: 2, specificGoals: "", whenWillIReachThem: "" }
  ]
};

const WhoIWantToBeTab: React.FC = () => {
  const [data, setData] = useState<WhoIWantToBeData>(INITIAL_DATA);
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
      const result = await beingApi.getLatestTest('future');
      if (result) {
        setData(result.content as WhoIWantToBeData);
        setVersion(result.version);
      } else {
        setData(INITIAL_DATA);
        setVersion(null);
      }

      const versionList = await beingApi.getVersions('future');
      setVersions(versionList.versions);
    } catch (error) {
      console.error('[WhoIWantToBeTab] Load failed:', error);
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
      const result = await beingApi.getTestByVersion('future', ver);
      if (result) {
        setData(result.content as WhoIWantToBeData);
        setVersion(result.version);
      }
    } catch (error) {
      console.error('[WhoIWantToBeTab] Load version failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadLatestData();
  }, [loadLatestData]);

  // 保存数据
  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus('idle');
    try {
      if (version) {
        await beingApi.updateTest('future', version, data);
      } else {
        const result = await beingApi.createTest('future', data);
        setVersion(result.version);
        const versionList = await beingApi.getVersions('future');
        setVersions(versionList.versions);
      }
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('[WhoIWantToBeTab] Save failed:', error);
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
      const result = await beingApi.createTest('future', data);
      setVersion(result.version);
      const versionList = await beingApi.getVersions('future');
      setVersions(versionList.versions);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('[WhoIWantToBeTab] Create new failed:', error);
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  };

  // Handlers
  const handleIdentityChange = (id: number, val: string) => {
    setData(prev => ({
      ...prev,
      whoIWantToBeItems: prev.whoIWantToBeItems.map(i => i.id === id ? { ...i, whoIWantToBe: val } : i)
    }));
  };

  const addIdentity = () => setData(prev => ({ ...prev, whoIWantToBeItems: [...prev.whoIWantToBeItems, { id: Date.now(), whoIWantToBe: "" }] }));

  const removeIdentity = (id: number) => setData(prev => ({ ...prev, whoIWantToBeItems: prev.whoIWantToBeItems.filter(i => i.id !== id) }));

  const handleGoalChange = (id: number, field: keyof SpecificGoalsItem, val: string) => {
    setData(prev => ({
      ...prev,
      specificGoalsItems: prev.specificGoalsItems.map(i => i.id === id ? { ...i, [field]: val } : i)
    }));
  };

  const addGoal = () => setData(prev => ({ ...prev, specificGoalsItems: [...prev.specificGoalsItems, { id: Date.now(), specificGoals: "", whenWillIReachThem: "" }] }));

  const removeGoal = (id: number) => setData(prev => ({ ...prev, specificGoalsItems: prev.specificGoalsItems.filter(i => i.id !== id) }));

  if (isLoading) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 size={32} className="text-indigo-400 animate-spin" />
          <p className="text-slate-500 font-medium">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full overflow-y-auto no-scrollbar pb-20 px-4 md:px-12 pt-6 animate-fade-in font-sans">

      {/* Header */}
      <div className="max-w-3xl mx-auto text-center mb-12">
        <div className="flex items-center justify-center gap-4 mb-4">
          <div className="inline-flex items-center justify-center p-3 bg-indigo-50 rounded-full text-indigo-500 shadow-sm border border-indigo-100">
            <Rocket size={20} />
          </div>

          {/* Version Selector */}
          <div className="relative">
            <button
              onClick={() => setShowVersionDropdown(!showVersionDropdown)}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-50 hover:bg-indigo-100 rounded-full text-sm font-medium text-indigo-600 transition-colors"
            >
              {version ? `版本 ${version}` : '新版本'}
              <ChevronDown size={16} className={`transition-transform ${showVersionDropdown ? 'rotate-180' : ''}`} />
            </button>

            {showVersionDropdown && (
              <div className="absolute top-full mt-2 left-0 bg-white rounded-xl shadow-xl border border-indigo-100 overflow-hidden z-50 min-w-[160px]">
                {versions.length > 0 ? (
                  versions.map(v => (
                    <button
                      key={v.id}
                      onClick={() => loadVersion(v.version)}
                      className={`w-full px-4 py-2.5 text-left text-sm hover:bg-indigo-50 transition-colors flex items-center justify-between ${v.version === version ? 'bg-indigo-50 font-medium' : ''}`}
                    >
                      <span>版本 {v.version}</span>
                      {v.version === version && <Check size={14} className="text-indigo-500" />}
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-sm text-slate-400">暂无历史版本</div>
                )}
                <div className="border-t border-indigo-100">
                  <button
                    onClick={handleCreateNew}
                    className="w-full px-4 py-2.5 text-left text-sm text-indigo-600 hover:bg-indigo-50 transition-colors flex items-center gap-2"
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
            className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
            title="刷新"
          >
            <RefreshCw size={18} />
          </button>
        </div>

        <h2 className="text-3xl md:text-4xl font-bold text-slate-800 tracking-tight mb-4">Architecting Your Future</h2>
        <p className="text-slate-500 text-lg leading-relaxed font-medium">
          Define the identity you are stepping into and the milestones that mark the path.
        </p>
      </div>

      <div className="max-w-4xl mx-auto space-y-12">

        {/* Section 1: Future Identity */}
        <section className="bg-white rounded-[2.5rem] p-8 md:p-12 shadow-[0_8px_30px_rgb(0,0,0,0.02)] border border-indigo-50 relative overflow-hidden">
          {/* Decorative soft gradients */}
          <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-50/40 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none"></div>
          <div className="absolute bottom-0 left-0 w-80 h-80 bg-blue-50/40 rounded-full blur-3xl -ml-20 -mb-20 pointer-events-none"></div>

          <div className="relative z-10 mb-10 flex items-center gap-5 border-b border-slate-50 pb-6">
            <div className="w-14 h-14 bg-indigo-50 rounded-2xl flex items-center justify-center text-indigo-600 shadow-sm">
              <Sparkles size={26} strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-xl font-bold text-slate-800">Future Identity</h3>
              <p className="text-slate-400 text-sm font-medium mt-1">Who will you become?</p>
            </div>
          </div>

          <div className="space-y-4 relative z-10">
            {data.whoIWantToBeItems.map((item, index) => (
              <div key={item.id} className="group transition-all duration-300">
                <div className="flex items-center gap-4">
                  <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold text-xs shadow-sm shrink-0">
                    {index + 1}
                  </div>
                  <div className="flex-1 relative">
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 text-slate-400 font-medium text-sm pl-4 pointer-events-none select-none">I will become a...</span>
                    <input
                      type="text"
                      value={item.whoIWantToBe}
                      onChange={(e) => handleIdentityChange(item.id, e.target.value)}
                      className="w-full bg-slate-50 hover:bg-white focus:bg-white border border-transparent focus:border-indigo-200 rounded-2xl py-4 pl-36 pr-12 text-slate-700 font-bold outline-none transition-all placeholder-slate-300 shadow-sm focus:shadow-md focus:ring-4 focus:ring-indigo-50"
                      placeholder="visionary leader..."
                    />
                    <button
                      onClick={() => removeIdentity(item.id)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 p-2 text-slate-300 hover:text-red-400 hover:bg-red-50 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            ))}

            <div className="pl-12 pt-2">
              <button
                onClick={addIdentity}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-xs font-bold text-indigo-400 hover:text-indigo-600 hover:bg-indigo-50 transition-all border border-transparent hover:border-indigo-200 border-dashed tracking-wider uppercase"
              >
                <Plus size={14} /> Add Identity Statement
              </button>
            </div>
          </div>
        </section>

        {/* Section 2: Specific Goals */}
        <section className="space-y-8">
          <div className="flex items-center gap-5 px-2">
            <div className="w-14 h-14 bg-emerald-50 rounded-2xl flex items-center justify-center text-emerald-600 shadow-sm">
              <Target size={26} strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-xl font-bold text-slate-800">Concrete Milestones</h3>
              <p className="text-slate-400 text-sm font-medium mt-1">Tangible targets and deadlines.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6">
            {data.specificGoalsItems.map((item, index) => (
              <div key={item.id} className="bg-white rounded-[2rem] p-6 md:p-8 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.02)] border border-emerald-50/50 hover:border-emerald-200 hover:shadow-lg transition-all group relative">
                <button
                  onClick={() => removeGoal(item.id)}
                  className="absolute top-6 right-6 p-2 text-slate-300 hover:text-red-400 hover:bg-red-50 rounded-full opacity-0 group-hover:opacity-100 transition-all"
                >
                  <Trash2 size={18} />
                </button>

                <div className="flex flex-col md:flex-row gap-6 md:gap-8 items-start">
                  {/* Goal Input */}
                  <div className="flex-1 w-full space-y-2">
                    <label className="flex items-center gap-2 text-xs font-black text-slate-400 uppercase tracking-widest">
                      <Zap size={14} className="text-emerald-400" /> Specific Goal
                    </label>
                    <textarea
                      value={item.specificGoals}
                      onChange={(e) => handleGoalChange(item.id, 'specificGoals', e.target.value)}
                      className="w-full bg-slate-50 focus:bg-white border border-transparent focus:border-emerald-200 rounded-2xl p-4 text-slate-800 font-bold leading-relaxed resize-none outline-none transition-all placeholder-slate-300 text-lg min-h-[100px]"
                      placeholder="What exactly do you want to achieve?"
                    />
                  </div>

                  {/* Timeline Input */}
                  <div className="w-full md:w-1/3 space-y-2">
                    <label className="flex items-center gap-2 text-xs font-black text-slate-400 uppercase tracking-widest">
                      <Calendar size={14} className="text-blue-400" /> Deadline
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        value={item.whenWillIReachThem}
                        onChange={(e) => handleGoalChange(item.id, 'whenWillIReachThem', e.target.value)}
                        className="w-full bg-slate-50 focus:bg-white border border-transparent focus:border-blue-200 rounded-2xl p-4 text-slate-700 font-mono font-medium outline-none transition-all placeholder-slate-300"
                        placeholder="e.g. Dec 2025"
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}

            <button
              onClick={addGoal}
              className="w-full py-6 rounded-[2rem] border-2 border-dashed border-slate-200 text-slate-400 font-bold hover:border-emerald-300 hover:text-emerald-600 hover:bg-emerald-50/30 transition-all flex flex-col items-center justify-center gap-2"
            >
              <Plus size={24} />
              <span>Add New Milestone</span>
            </button>
          </div>
        </section>

        {/* Footer Action */}
        <div className="flex justify-center pt-8 pb-8">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className={`px-10 py-5 rounded-2xl font-bold shadow-[0_10px_20px_-5px_rgba(15,23,42,0.3)] hover:shadow-[0_15px_25px_-5px_rgba(15,23,42,0.4)] hover:-translate-y-1 transition-all flex items-center gap-3 text-sm tracking-wide ${saveStatus === 'success'
                ? 'bg-emerald-600 text-white'
                : saveStatus === 'error'
                  ? 'bg-red-600 text-white'
                  : 'bg-slate-900 text-white'
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
                <span>Save Future Self</span>
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
};

export default WhoIWantToBeTab;
