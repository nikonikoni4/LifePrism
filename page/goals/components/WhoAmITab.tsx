
import React, { useState, useEffect, useCallback, useRef } from 'react';
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

// --- Calming Question Section Component ---
interface QuestionBlockProps {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
  items: { id: number; value: string }[];
  placeholder: string;
  inputPrefix: string;
  inputBg: string;
  onChange: (id: number, val: string) => void;
  onAdd: () => void;
  onDelete: (id: number) => void;
}

const QuestionBlock: React.FC<QuestionBlockProps> = ({
  title,
  subtitle,
  icon,
  iconBg,
  iconColor,
  items,
  placeholder,
  inputPrefix,
  inputBg,
  onChange,
  onAdd,
  onDelete
}) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 mb-6">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ backgroundColor: iconBg, color: iconColor }}
        >
          {icon}
        </div>
        <div>
          <h3 className="text-base font-semibold" style={{ color: '#3D3A36' }}>{title}</h3>
          <p className="text-sm" style={{ color: '#9B9590' }}>{subtitle}</p>
        </div>
      </div>

      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={item.id} className="group transition-all duration-300">
            <div className="flex items-center gap-3">
              <span
                className="text-sm font-medium w-5 text-center shrink-0"
                style={{ color: '#C5B9A8' }}
              >
                {index + 1}
              </span>
              <div className="flex-1 relative">
                <span
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-sm pointer-events-none select-none"
                  style={{ color: '#C5B9A8' }}
                >
                  {inputPrefix}
                </span>
                <input
                  type="text"
                  value={item.value}
                  onChange={(e) => onChange(item.id, e.target.value)}
                  className="w-full rounded-xl py-3.5 pl-20 pr-10 text-base outline-none transition-all duration-200"
                  style={{
                    backgroundColor: inputBg,
                    color: '#3D3A36',
                    border: '1px solid transparent'
                  }}
                  onFocus={(e) => {
                    e.target.style.backgroundColor = '#FFFFFF';
                    e.target.style.border = '1px solid #E8E4DD';
                    e.target.style.boxShadow = '0 2px 12px -4px rgba(139, 126, 109, 0.12)';
                  }}
                  onBlur={(e) => {
                    e.target.style.backgroundColor = inputBg;
                    e.target.style.border = '1px solid transparent';
                    e.target.style.boxShadow = 'none';
                  }}
                  placeholder={placeholder}
                />
                <button
                  onClick={() => onDelete(item.id)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-200"
                  style={{ color: '#C5B9A8' }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}

        <div className="pl-8 pt-2">
          <button
            onClick={onAdd}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all duration-200"
            style={{
              color: '#A89F91',
              border: '1px dashed #D9D4CC'
            }}
          >
            <Plus size={14} /> 添加
          </button>
        </div>
      </div>
    </div>
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

  // 防止 StrictMode 重复请求
  const hasFetched = useRef(false);

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

  // 初始加载 - 使用 hasFetched 防止重复请求
  useEffect(() => {
    if (hasFetched.current) return;
    hasFetched.current = true;
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
  const handleWhoAmIChange = (id: number, val: string) => {
    setData(prev => ({
      ...prev,
      whoAmIItems: prev.whoAmIItems.map(i => i.id === id ? { ...i, whoAmI: val } : i)
    }));
  };
  const addWhoAmI = () => setData(prev => ({ ...prev, whoAmIItems: [...prev.whoAmIItems, { id: Date.now(), whoAmI: "" }] }));
  const delWhoAmI = (id: number) => setData(prev => ({ ...prev, whoAmIItems: prev.whoAmIItems.filter(i => i.id !== id) }));

  const handleTimeChange = (id: number, val: string) => {
    setData(prev => ({
      ...prev,
      whatTimeItems: prev.whatTimeItems.map(i => i.id === id ? { ...i, whatTime: val } : i)
    }));
  };
  const addTime = () => setData(prev => ({ ...prev, whatTimeItems: [...prev.whatTimeItems, { id: Date.now(), whatTime: "" }] }));
  const delTime = (id: number) => setData(prev => ({ ...prev, whatTimeItems: prev.whatTimeItems.filter(i => i.id !== id) }));

  const handleWhereChange = (id: number, val: string) => {
    setData(prev => ({
      ...prev,
      whereAmIItems: prev.whereAmIItems.map(i => i.id === id ? { ...i, whereAmI: val } : i)
    }));
  };
  const addWhere = () => setData(prev => ({ ...prev, whereAmIItems: [...prev.whereAmIItems, { id: Date.now(), whereAmI: "" }] }));
  const delWhere = (id: number) => setData(prev => ({ ...prev, whereAmIItems: prev.whereAmIItems.filter(i => i.id !== id) }));

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
      <div className="h-full w-full flex items-center justify-center" style={{ backgroundColor: '#FDFBF9' }}>
        <div className="flex flex-col items-center gap-4">
          <Loader2 size={32} className="animate-spin" style={{ color: '#A89F91' }} />
          <p className="font-medium" style={{ color: '#9B9590' }}>加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="h-full w-full overflow-y-auto no-scrollbar pb-24 px-6 md:px-16 pt-8 animate-fade-in font-sans"
      style={{ backgroundColor: '#FDFBF9' }}
    >

      {/* Header */}
      <div className="max-w-2xl mx-auto text-center mb-16">
        <div className="flex items-center justify-center gap-4 mb-6">
          <div
            className="inline-flex items-center justify-center w-12 h-12 rounded-full"
            style={{ backgroundColor: '#F5F3EE', color: '#A89F91' }}
          >
            <Anchor size={22} strokeWidth={1.5} />
          </div>

          {/* Version Selector */}
          <div className="relative">
            <button
              onClick={() => setShowVersionDropdown(!showVersionDropdown)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium transition-all duration-200"
              style={{
                backgroundColor: '#F5F3EE',
                color: '#7A746B',
                border: '1px solid #E8E4DD'
              }}
            >
              {version ? `版本 ${version}` : '新版本'}
              <ChevronDown size={16} className={`transition-transform duration-200 ${showVersionDropdown ? 'rotate-180' : ''}`} />
            </button>

            {showVersionDropdown && (
              <div
                className="absolute top-full mt-2 left-0 rounded-2xl overflow-hidden z-50 min-w-[160px]"
                style={{
                  backgroundColor: '#FFFFFF',
                  boxShadow: '0 10px 40px -10px rgba(139, 126, 109, 0.2)',
                  border: '1px solid #E8E4DD'
                }}
              >
                {versions.length > 0 ? (
                  versions.map(v => (
                    <button
                      key={v.id}
                      onClick={() => loadVersion(v.version)}
                      className="w-full px-4 py-3 text-left text-sm transition-colors flex items-center justify-between"
                      style={{
                        backgroundColor: v.version === version ? '#F5F3EE' : 'transparent',
                        color: '#5C574F'
                      }}
                    >
                      <span>版本 {v.version}</span>
                      {v.version === version && <Check size={14} style={{ color: '#A89F91' }} />}
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-sm" style={{ color: '#9B9590' }}>暂无历史版本</div>
                )}
                <div style={{ borderTop: '1px solid #E8E4DD' }}>
                  <button
                    onClick={handleCreateNew}
                    className="w-full px-4 py-3 text-left text-sm transition-colors flex items-center gap-2"
                    style={{ color: '#8B7355' }}
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
            className="p-2.5 rounded-xl transition-all duration-200"
            style={{ color: '#A89F91' }}
            title="刷新"
          >
            <RefreshCw size={18} />
          </button>
        </div>

        <h2
          className="text-3xl md:text-4xl font-semibold tracking-tight mb-4"
          style={{ color: '#3D3A36' }}
        >
          锚定当下
        </h2>
        <p className="text-lg leading-relaxed" style={{ color: '#9B9590' }}>
          一次真实的自我检视，扎根于身份、环境与情绪。
        </p>
      </div>

      {/* Single Unified Card */}
      <div
        className="max-w-2xl mx-auto rounded-[2rem] p-8 md:p-10 relative overflow-hidden"
        style={{
          backgroundColor: '#FFFFFF',
          boxShadow: '0 4px 30px -8px rgba(139, 126, 109, 0.12)',
          border: '1px solid #F0EDE8'
        }}
      >
        {/* Subtle warm gradient overlay */}
        <div
          className="absolute top-0 right-0 w-64 h-64 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none opacity-20"
          style={{ backgroundColor: '#F5EFE6' }}
        />

        <div className="relative z-10 space-y-10">

          {/* 1. Who Am I */}
          <QuestionBlock
            title="我现在是谁？"
            subtitle="角色、状态或隐喻"
            icon={<Fingerprint size={20} strokeWidth={1.5} />}
            iconBg="#FBF6EE"
            iconColor="#C4A574"
            items={data.whoAmIItems.map(i => ({ id: i.id, value: i.whoAmI }))}
            placeholder="一个探索者、一个学习者..."
            inputPrefix="我是..."
            inputBg="#FAF9F7"
            onChange={handleWhoAmIChange}
            onAdd={addWhoAmI}
            onDelete={delWhoAmI}
          />

          {/* Divider */}
          <div style={{ height: '1px', backgroundColor: '#F0EDE8' }} />

          {/* 2. What Time */}
          <QuestionBlock
            title="现在是什么时刻？"
            subtitle="人生阶段、季节或字面时间"
            icon={<Clock size={20} strokeWidth={1.5} />}
            iconBg="#F5F3EE"
            iconColor="#9BA8A0"
            items={data.whatTimeItems.map(i => ({ id: i.id, value: i.whatTime }))}
            placeholder="成长的时刻、转变的季节..."
            inputPrefix="是..."
            inputBg="#F9FAF8"
            onChange={handleTimeChange}
            onAdd={addTime}
            onDelete={delTime}
          />

          {/* Divider */}
          <div style={{ height: '1px', backgroundColor: '#F0EDE8' }} />

          {/* 3. Where Am I */}
          <QuestionBlock
            title="我在哪里？"
            subtitle="环境、感官或精神状态"
            icon={<MapPin size={20} strokeWidth={1.5} />}
            iconBg="#F3F5F4"
            iconColor="#8AA09A"
            items={data.whereAmIItems.map(i => ({ id: i.id, value: i.whereAmI }))}
            placeholder="在家中、在思考中、在路上..."
            inputPrefix="在..."
            inputBg="#F8FAF9"
            onChange={handleWhereChange}
            onAdd={addWhere}
            onDelete={delWhere}
          />

          {/* Divider */}
          <div style={{ height: '1px', backgroundColor: '#F0EDE8' }} />

          {/* 4. Feelings */}
          <QuestionBlock
            title="我的感受如何？"
            subtitle="真实的情绪、身体感受"
            icon={<Heart size={20} strokeWidth={1.5} />}
            iconBg="#FBF5F5"
            iconColor="#BFA5A0"
            items={data.howAmIFeelingItems.map(i => ({ id: i.id, value: i.howAmIFeeling }))}
            placeholder="平静、期待、有些疲惫..."
            inputPrefix="感到..."
            inputBg="#FCF9F9"
            onChange={handleFeelingChange}
            onAdd={addFeeling}
            onDelete={delFeeling}
          />

        </div>
      </div>

      {/* Footer Action */}
      <div className="flex justify-center pt-12 pb-8">
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="px-10 py-4 rounded-2xl font-semibold transition-all duration-300 flex items-center gap-3 text-base"
          style={{
            backgroundColor: saveStatus === 'success' ? '#7A9A6D' : saveStatus === 'error' ? '#B07070' : '#5C574F',
            color: '#FFFFFF',
            boxShadow: '0 8px 24px -8px rgba(92, 87, 79, 0.35)',
            opacity: isSaving ? 0.7 : 1
          }}
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
              <span>保存当下</span>
            </>
          )}
        </button>
      </div>

    </div>
  );
};

export default WhoAmITab;
