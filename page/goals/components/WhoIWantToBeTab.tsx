
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Rocket,
  Target,
  Calendar,
  Plus,
  Trash2,
  BookOpen,
  Sparkles,
  Compass,
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

  // 防止 StrictMode 重复请求
  const hasFetched = useRef(false);

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
            style={{ backgroundColor: '#F3F0EB', color: '#9A8F80' }}
          >
            <Compass size={22} strokeWidth={1.5} />
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
          构建你的未来
        </h2>
        <p className="text-lg leading-relaxed" style={{ color: '#9B9590' }}>
          定义你正在迈向的身份，以及标记道路的里程碑。
        </p>
      </div>

      <div className="max-w-2xl mx-auto space-y-12">

        {/* Section 1: Future Identity */}
        <section
          className="rounded-[2rem] p-8 md:p-10 relative overflow-hidden"
          style={{
            backgroundColor: '#FFFFFF',
            boxShadow: '0 4px 30px -8px rgba(139, 126, 109, 0.12)',
            border: '1px solid #F0EDE8'
          }}
        >
          {/* Subtle warm gradient overlay */}
          <div
            className="absolute top-0 right-0 w-64 h-64 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none opacity-25"
            style={{ backgroundColor: '#EDE8E0' }}
          />
          <div
            className="absolute bottom-0 left-0 w-48 h-48 rounded-full blur-3xl -ml-10 -mb-10 pointer-events-none opacity-20"
            style={{ backgroundColor: '#E8EDE6' }}
          />

          <div className="relative z-10 mb-8 flex items-center gap-4 pb-6" style={{ borderBottom: '1px solid #F5F3EE' }}>
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center"
              style={{ backgroundColor: '#F5F3EE', color: '#A89F91' }}
            >
              <Sparkles size={22} strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-lg font-semibold" style={{ color: '#3D3A36' }}>未来的身份</h3>
              <p className="text-sm mt-0.5" style={{ color: '#9B9590' }}>你将成为谁？</p>
            </div>
          </div>

          <div className="space-y-4 relative z-10">
            {data.whoIWantToBeItems.map((item, index) => (
              <div key={item.id} className="group transition-all duration-300">
                <div className="flex items-center gap-4">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium shrink-0"
                    style={{ backgroundColor: '#F5F3EE', color: '#A89F91' }}
                  >
                    {index + 1}
                  </div>
                  <div className="flex-1 relative">
                    <span
                      className="absolute left-4 top-1/2 -translate-y-1/2 text-sm pointer-events-none select-none"
                      style={{ color: '#C5B9A8' }}
                    >
                      我将成为...
                    </span>
                    <input
                      type="text"
                      value={item.whoIWantToBe}
                      onChange={(e) => handleIdentityChange(item.id, e.target.value)}
                      className="w-full rounded-xl py-4 pl-28 pr-12 text-base font-medium outline-none transition-all duration-200"
                      style={{
                        backgroundColor: '#FAF9F7',
                        color: '#3D3A36',
                        border: '1px solid transparent'
                      }}
                      onFocus={(e) => {
                        e.target.style.backgroundColor = '#FFFFFF';
                        e.target.style.border = '1px solid #E8E4DD';
                        e.target.style.boxShadow = '0 2px 12px -4px rgba(139, 126, 109, 0.15)';
                      }}
                      onBlur={(e) => {
                        e.target.style.backgroundColor = '#FAF9F7';
                        e.target.style.border = '1px solid transparent';
                        e.target.style.boxShadow = 'none';
                      }}
                      placeholder="有远见的领导者..."
                    />
                    <button
                      onClick={() => removeIdentity(item.id)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-200"
                      style={{ color: '#C5B9A8' }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            ))}

            <div className="pl-12 pt-3">
              <button
                onClick={addIdentity}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200"
                style={{
                  color: '#A89F91',
                  border: '1px dashed #D9D4CC'
                }}
              >
                <Plus size={16} /> 添加身份宣言
              </button>
            </div>
          </div>
        </section>

        {/* Section 2: Concrete Milestones */}
        <section className="space-y-6">
          <div className="flex items-center gap-4 px-2 mb-8">
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center"
              style={{ backgroundColor: '#F2F5F0', color: '#8A9A7E' }}
            >
              <Target size={22} strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-lg font-semibold" style={{ color: '#3D3A36' }}>具体的里程碑</h3>
              <p className="text-sm mt-0.5" style={{ color: '#9B9590' }}>切实的目标和期限</p>
            </div>
          </div>

          <div className="space-y-5">
            {data.specificGoalsItems.map((item, index) => (
              <div
                key={item.id}
                className="rounded-[2rem] p-6 md:p-8 relative group transition-all duration-300"
                style={{
                  backgroundColor: '#FFFFFF',
                  boxShadow: '0 2px 20px -6px rgba(139, 126, 109, 0.1)',
                  border: '1px solid #F0EDE8'
                }}
              >
                <button
                  onClick={() => removeGoal(item.id)}
                  className="absolute top-6 right-6 p-2 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200"
                  style={{ color: '#C5B9A8' }}
                >
                  <Trash2 size={18} />
                </button>

                {/* Vertical Stack */}
                <div className="space-y-5">
                  {/* Goal Input */}
                  <div className="space-y-3">
                    <label
                      className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider"
                      style={{ color: '#9B9590' }}
                    >
                      <Rocket size={14} style={{ color: '#A89F91' }} /> 具体目标
                    </label>
                    <textarea
                      value={item.specificGoals}
                      onChange={(e) => handleGoalChange(item.id, 'specificGoals', e.target.value)}
                      className="w-full rounded-xl p-4 text-base leading-relaxed resize-none outline-none transition-all duration-200 min-h-[90px]"
                      style={{
                        backgroundColor: '#FAF9F7',
                        color: '#3D3A36',
                        border: '1px solid transparent'
                      }}
                      onFocus={(e) => {
                        e.target.style.backgroundColor = '#FFFFFF';
                        e.target.style.border = '1px solid #E8E4DD';
                      }}
                      onBlur={(e) => {
                        e.target.style.backgroundColor = '#FAF9F7';
                        e.target.style.border = '1px solid transparent';
                      }}
                      placeholder="你具体想要实现什么？"
                    />
                  </div>

                  {/* Timeline Input */}
                  <div className="space-y-3">
                    <label
                      className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider"
                      style={{ color: '#9B9590' }}
                    >
                      <Calendar size={14} style={{ color: '#9AADB8' }} /> 期限
                    </label>
                    <input
                      type="text"
                      value={item.whenWillIReachThem}
                      onChange={(e) => handleGoalChange(item.id, 'whenWillIReachThem', e.target.value)}
                      className="w-full md:w-1/2 rounded-xl p-4 text-base outline-none transition-all duration-200"
                      style={{
                        backgroundColor: '#F7FAFB',
                        color: '#3D3A36',
                        border: '1px solid transparent',
                        fontFamily: "'SF Mono', 'Monaco', monospace"
                      }}
                      onFocus={(e) => {
                        e.target.style.backgroundColor = '#FFFFFF';
                        e.target.style.border = '1px solid #D8E5EA';
                      }}
                      onBlur={(e) => {
                        e.target.style.backgroundColor = '#F7FAFB';
                        e.target.style.border = '1px solid transparent';
                      }}
                      placeholder="例如：2025年12月"
                    />
                  </div>
                </div>
              </div>
            ))}

            {/* Add Goal Button */}
            <button
              onClick={addGoal}
              className="w-full py-6 rounded-[2rem] font-medium flex flex-col items-center justify-center gap-2 transition-all duration-300"
              style={{
                border: '2px dashed #D9D4CC',
                color: '#A89F91'
              }}
            >
              <Plus size={22} />
              <span>添加新里程碑</span>
            </button>
          </div>
        </section>

        {/* Footer Action */}
        <div className="flex justify-center pt-8 pb-8">
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
                <span>保存未来愿景</span>
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
};

export default WhoIWantToBeTab;
