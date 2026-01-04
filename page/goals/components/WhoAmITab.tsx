
import React, { useState, useEffect, useCallback } from 'react';
import {
  Fingerprint,
  Clock,
  MapPin,
  Heart,
  Plus,
  BookOpen,
  Anchor,
  Trash2,
  Loader2,
  Check,
  ChevronDown,
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import { beingApi } from '../api';
import {
  WhoAmIData,
  WhoAmIItem,
  WhatTimeItem,
  WhereAmIItem,
  HowAmIFeelingItem,
  BeingVersionInfo
} from '../types';

// --- 默认初始数据 ---
const INITIAL_DATA: WhoAmIData = {
  whoAmIItems: [
    { id: 1, whoAmI: "" },
    { id: 2, whoAmI: "" },
    { id: 3, whoAmI: "" }
  ],
  whatTimeItems: [
    { id: 1, whatTime: "" },
    { id: 2, whatTime: "" },
    { id: 3, whatTime: "" }
  ],
  whereAmIItems: [
    { id: 1, whereAmI: "" },
    { id: 2, whereAmI: "" },
    { id: 3, whereAmI: "" }
  ],
  howAmIFeelingItems: [
    { id: 1, howAmIFeeling: "" },
    { id: 2, howAmIFeeling: "" },
    { id: 3, howAmIFeeling: "" }
  ]
};

// --- Generic Section Component ---

interface SectionProps {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  items: { id: number; value: string }[];
  placeholder: string;
  colorTheme: 'orange' | 'blue' | 'emerald' | 'rose';
  onChange: (id: number, val: string) => void;
  onAdd: () => void;
  onDelete: (id: number) => void;
}

const QuestionSection: React.FC<SectionProps> = ({
  title,
  subtitle,
  icon,
  items,
  placeholder,
  colorTheme,
  onChange,
  onAdd,
  onDelete
}) => {
  // Theme configurations
  const themes = {
    orange: {
      bg: 'bg-orange-50/50',
      border: 'border-orange-100',
      iconBg: 'bg-orange-100',
      iconColor: 'text-orange-600',
      focusRing: 'focus:ring-orange-100',
      blob: 'bg-orange-100/40'
    },
    blue: {
      bg: 'bg-blue-50/50',
      border: 'border-blue-100',
      iconBg: 'bg-blue-100',
      iconColor: 'text-blue-600',
      focusRing: 'focus:ring-blue-100',
      blob: 'bg-blue-100/40'
    },
    emerald: {
      bg: 'bg-emerald-50/50',
      border: 'border-emerald-100',
      iconBg: 'bg-emerald-100',
      iconColor: 'text-emerald-600',
      focusRing: 'focus:ring-emerald-100',
      blob: 'bg-emerald-100/40'
    },
    rose: {
      bg: 'bg-rose-50/50',
      border: 'border-rose-100',
      iconBg: 'bg-rose-100',
      iconColor: 'text-rose-600',
      focusRing: 'focus:ring-rose-100',
      blob: 'bg-rose-100/40'
    }
  };

  const t = themes[colorTheme];

  return (
    <section className={`w-full rounded-[2.5rem] p-8 md:p-10 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.02)] border ${t.border} relative overflow-hidden bg-white transition-all hover:shadow-lg`}>
      {/* Decorative Blob */}
      <div className={`absolute top-0 right-0 w-full h-full ${t.blob} rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none opacity-20`}></div>

      <div className="relative z-10 mb-8 flex items-center gap-5 border-b border-gray-50 pb-6">
        <div className={`w-14 h-14 ${t.iconBg} rounded-2xl flex items-center justify-center ${t.iconColor} shadow-sm shrink-0`}>
          {icon}
        </div>
        <div>
          <h3 className="text-xl font-bold text-slate-800">{title}</h3>
          <p className="text-slate-400 text-sm font-medium mt-1">{subtitle}</p>
        </div>
      </div>

      <div className="space-y-4 relative z-10">
        {items.map((item, index) => (
          <div key={item.id} className="group transition-all duration-300">
            <div className="flex items-center gap-4">
              <span className="text-xs font-bold text-slate-300 font-mono w-6 text-right shrink-0">{index + 1}</span>
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={item.value}
                  onChange={(e) => onChange(item.id, e.target.value)}
                  className={`w-full bg-slate-50 hover:bg-white focus:bg-white border border-transparent ${t.focusRing.replace('focus:ring', 'focus:border')} rounded-xl py-3.5 px-5 text-slate-700 font-medium outline-none transition-all placeholder-slate-300 shadow-sm focus:shadow-md focus:ring-4`}
                  placeholder={placeholder}
                />
                <button
                  onClick={() => onDelete(item.id)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-slate-300 hover:text-red-400 hover:bg-red-50 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          </div>
        ))}

        <div className="pl-10 pt-2">
          <button
            onClick={onAdd}
            className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-slate-400 hover:${t.iconColor} hover:bg-slate-50 transition-all border border-transparent hover:border-slate-200 border-dashed tracking-wider uppercase`}
          >
            <Plus size={14} /> Add Item
          </button>
        </div>
      </div>
    </section>
  );
};

const WhoAmITab: React.FC = () => {
  const [data, setData] = useState<WhoAmIData>(INITIAL_DATA);
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
      const result = await beingApi.getLatestTest('present');
      if (result) {
        setData(result.content as WhoAmIData);
        setVersion(result.version);
      } else {
        setData(INITIAL_DATA);
        setVersion(null);
      }

      const versionList = await beingApi.getVersions('present');
      setVersions(versionList.versions);
    } catch (error) {
      console.error('[WhoAmITab] Load failed:', error);
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
      const result = await beingApi.getTestByVersion('present', ver);
      if (result) {
        setData(result.content as WhoAmIData);
        setVersion(result.version);
      }
    } catch (error) {
      console.error('[WhoAmITab] Load version failed:', error);
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
        await beingApi.updateTest('present', version, data);
      } else {
        const result = await beingApi.createTest('present', data);
        setVersion(result.version);
        const versionList = await beingApi.getVersions('present');
        setVersions(versionList.versions);
      }
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('[WhoAmITab] Save failed:', error);
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
      const result = await beingApi.createTest('present', data);
      setVersion(result.version);
      const versionList = await beingApi.getVersions('present');
      setVersions(versionList.versions);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('[WhoAmITab] Create new failed:', error);
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  };

  // --- Handlers ---

  // 1. Who Am I
  const handleWhoAmIChange = (id: number, val: string) => {
    setData(prev => ({
      ...prev,
      whoAmIItems: prev.whoAmIItems.map(i => i.id === id ? { ...i, whoAmI: val } : i)
    }));
  };
  const addWhoAmI = () => setData(prev => ({ ...prev, whoAmIItems: [...prev.whoAmIItems, { id: Date.now(), whoAmI: "" }] }));
  const delWhoAmI = (id: number) => setData(prev => ({ ...prev, whoAmIItems: prev.whoAmIItems.filter(i => i.id !== id) }));

  // 2. What Time
  const handleTimeChange = (id: number, val: string) => {
    setData(prev => ({
      ...prev,
      whatTimeItems: prev.whatTimeItems.map(i => i.id === id ? { ...i, whatTime: val } : i)
    }));
  };
  const addTime = () => setData(prev => ({ ...prev, whatTimeItems: [...prev.whatTimeItems, { id: Date.now(), whatTime: "" }] }));
  const delTime = (id: number) => setData(prev => ({ ...prev, whatTimeItems: prev.whatTimeItems.filter(i => i.id !== id) }));

  // 3. Where Am I
  const handleWhereChange = (id: number, val: string) => {
    setData(prev => ({
      ...prev,
      whereAmIItems: prev.whereAmIItems.map(i => i.id === id ? { ...i, whereAmI: val } : i)
    }));
  };
  const addWhere = () => setData(prev => ({ ...prev, whereAmIItems: [...prev.whereAmIItems, { id: Date.now(), whereAmI: "" }] }));
  const delWhere = (id: number) => setData(prev => ({ ...prev, whereAmIItems: prev.whereAmIItems.filter(i => i.id !== id) }));

  // 4. Feelings
  const handleFeelingChange = (id: number, val: string) => {
    setData(prev => ({
      ...prev,
      howAmIFeelingItems: prev.howAmIFeelingItems.map(i => i.id === id ? { ...i, howAmIFeeling: val } : i)
    }));
  };
  const addFeeling = () => setData(prev => ({ ...prev, howAmIFeelingItems: [...prev.howAmIFeelingItems, { id: Date.now(), howAmIFeeling: "" }] }));
  const delFeeling = (id: number) => setData(prev => ({ ...prev, howAmIFeelingItems: prev.howAmIFeelingItems.filter(i => i.id !== id) }));

  if (isLoading) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 size={32} className="text-slate-400 animate-spin" />
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
          <div className="inline-flex items-center justify-center p-3 bg-slate-100/50 rounded-full text-slate-500 shadow-sm border border-slate-100">
            <Anchor size={20} />
          </div>

          {/* Version Selector */}
          <div className="relative">
            <button
              onClick={() => setShowVersionDropdown(!showVersionDropdown)}
              className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-full text-sm font-medium text-slate-600 transition-colors"
            >
              {version ? `版本 ${version}` : '新版本'}
              <ChevronDown size={16} className={`transition-transform ${showVersionDropdown ? 'rotate-180' : ''}`} />
            </button>

            {showVersionDropdown && (
              <div className="absolute top-full mt-2 left-0 bg-white rounded-xl shadow-xl border border-slate-100 overflow-hidden z-50 min-w-[160px]">
                {versions.length > 0 ? (
                  versions.map(v => (
                    <button
                      key={v.id}
                      onClick={() => loadVersion(v.version)}
                      className={`w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 transition-colors flex items-center justify-between ${v.version === version ? 'bg-slate-50 font-medium' : ''}`}
                    >
                      <span>版本 {v.version}</span>
                      {v.version === version && <Check size={14} className="text-slate-500" />}
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-sm text-slate-400">暂无历史版本</div>
                )}
                <div className="border-t border-slate-100">
                  <button
                    onClick={handleCreateNew}
                    className="w-full px-4 py-2.5 text-left text-sm text-orange-600 hover:bg-orange-50 transition-colors flex items-center gap-2"
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
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            title="刷新"
          >
            <RefreshCw size={18} />
          </button>
        </div>

        <h2 className="text-3xl md:text-4xl font-bold text-slate-800 tracking-tight mb-4">Anchoring in the Now</h2>
        <p className="text-slate-500 text-lg leading-relaxed font-medium">
          A reality check to ground your identity, environment, and emotions.
        </p>
      </div>

      <div className="w-full flex flex-col gap-8">

        {/* 1. Who Am I */}
        <QuestionSection
          title="Who am I now?"
          subtitle="Roles, states of being, or metaphors."
          icon={<Fingerprint size={24} />}
          items={data.whoAmIItems.map(i => ({ id: i.id, value: i.whoAmI }))}
          placeholder="I am..."
          colorTheme="orange"
          onChange={handleWhoAmIChange}
          onAdd={addWhoAmI}
          onDelete={delWhoAmI}
        />

        {/* 2. What Time */}
        <QuestionSection
          title="What time is it?"
          subtitle="Life stage, season, or literal time."
          icon={<Clock size={24} />}
          items={data.whatTimeItems.map(i => ({ id: i.id, value: i.whatTime }))}
          placeholder="It is the time of..."
          colorTheme="blue"
          onChange={handleTimeChange}
          onAdd={addTime}
          onDelete={delTime}
        />

        {/* 3. Where Am I */}
        <QuestionSection
          title="Where am I?"
          subtitle="Environment, senses, or headspace."
          icon={<MapPin size={24} />}
          items={data.whereAmIItems.map(i => ({ id: i.id, value: i.whereAmI }))}
          placeholder="I am in..."
          colorTheme="emerald"
          onChange={handleWhereChange}
          onAdd={addWhere}
          onDelete={delWhere}
        />

        {/* 4. Feelings */}
        <QuestionSection
          title="How am I feeling?"
          subtitle="True emotions, bodily sensations."
          icon={<Heart size={24} />}
          items={data.howAmIFeelingItems.map(i => ({ id: i.id, value: i.howAmIFeeling }))}
          placeholder="I feel..."
          colorTheme="rose"
          onChange={handleFeelingChange}
          onAdd={addFeeling}
          onDelete={delFeeling}
        />

      </div>

      {/* Footer Action */}
      <div className="flex justify-center pt-12 pb-8">
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
              <span>Save Current State</span>
            </>
          )}
        </button>
      </div>

    </div>
  );
};

export default WhoAmITab;
