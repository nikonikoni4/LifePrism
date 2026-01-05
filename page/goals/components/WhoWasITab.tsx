
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Plus,
  Loader2,
  Check,
  ChevronDown,
  AlertCircle,
  Trash2,
  RefreshCw,
  BookOpen
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

// --- 手绘装饰组件 ---
const LeafDecoration: React.FC<{ className?: string; style?: React.CSSProperties }> = ({ className, style }) => (
  <svg className={className} style={style} width="40" height="50" viewBox="0 0 40 50" fill="none">
    <path d="M20 5 C10 15, 5 30, 20 45 C35 30, 30 15, 20 5" stroke="#7A9A6D" strokeWidth="2" fill="#A8C99B" opacity="0.6" />
    <path d="M20 10 L20 40" stroke="#7A9A6D" strokeWidth="1.5" />
    <path d="M15 20 L20 25 M25 15 L20 20 M15 30 L20 35 M25 28 L20 32" stroke="#7A9A6D" strokeWidth="1" />
  </svg>
);

const PlantPot: React.FC<{ className?: string; style?: React.CSSProperties }> = ({ className, style }) => (
  <svg className={className} style={style} width="50" height="70" viewBox="0 0 50 70" fill="none">
    {/* Pot */}
    <path d="M12 45 L38 45 L35 65 L15 65 Z" fill="#C4825A" stroke="#9A6B4A" strokeWidth="1.5" />
    <ellipse cx="25" cy="45" rx="13" ry="4" fill="#D4956B" />
    {/* Plant stems */}
    <path d="M22 45 C20 35, 15 30, 12 20" stroke="#5D7A4F" strokeWidth="2" fill="none" />
    <path d="M25 45 C25 35, 28 25, 25 15" stroke="#6A8A5A" strokeWidth="2" fill="none" />
    <path d="M28 45 C30 35, 35 30, 38 22" stroke="#5D7A4F" strokeWidth="2" fill="none" />
    {/* Leaves */}
    <ellipse cx="12" cy="18" rx="6" ry="10" fill="#8AB87A" transform="rotate(-20 12 18)" />
    <ellipse cx="25" cy="12" rx="5" ry="8" fill="#9AC88A" />
    <ellipse cx="38" cy="20" rx="6" ry="9" fill="#8AB87A" transform="rotate(25 38 20)" />
  </svg>
);

const CoffeeCup: React.FC<{ className?: string; style?: React.CSSProperties }> = ({ className, style }) => (
  <svg className={className} style={style} width="45" height="45" viewBox="0 0 45 45" fill="none">
    {/* Saucer */}
    <ellipse cx="22" cy="38" rx="18" ry="5" fill="#E8DDD0" stroke="#C4B8A8" strokeWidth="1" />
    {/* Cup body */}
    <path d="M8 18 L10 35 L34 35 L36 18 Z" fill="#F5EDE4" stroke="#C4B8A8" strokeWidth="1.5" />
    {/* Handle */}
    <path d="M36 22 C42 22, 42 32, 36 32" stroke="#C4B8A8" strokeWidth="2" fill="none" />
    {/* Coffee */}
    <ellipse cx="22" cy="20" rx="12" ry="4" fill="#8B7355" />
    {/* Steam */}
    <path d="M18 12 C16 8, 20 6, 18 2" stroke="#C4B8A8" strokeWidth="1.5" fill="none" opacity="0.5" />
    <path d="M24 10 C22 6, 26 4, 24 0" stroke="#C4B8A8" strokeWidth="1.5" fill="none" opacity="0.5" />
  </svg>
);

const RibbonBanner: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => (
  <div className={`relative ${className}`}>
    {/* Left ribbon end */}
    <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-4 w-6 h-full">
      <svg viewBox="0 0 24 40" className="w-full h-full">
        <path d="M24 0 L4 0 C0 0, 0 4, 4 8 L8 20 L4 32 C0 36, 0 40, 4 40 L24 40" fill="#B8A891" stroke="#9A8A71" strokeWidth="1" />
      </svg>
    </div>
    {/* Main banner */}
    <div
      className="px-8 py-4 text-center relative z-10"
      style={{
        background: 'linear-gradient(180deg, #C9BBAA 0%, #B8A891 50%, #A89A81 100%)',
        borderTop: '2px solid #A89A71',
        borderBottom: '2px solid #8A7A61',
        boxShadow: 'inset 0 2px 4px rgba(255,255,255,0.2), inset 0 -2px 4px rgba(0,0,0,0.1)'
      }}
    >
      {children}
    </div>
    {/* Right ribbon end */}
    <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-4 w-6 h-full">
      <svg viewBox="0 0 24 40" className="w-full h-full">
        <path d="M0 0 L20 0 C24 0, 24 4, 20 8 L16 20 L20 32 C24 36, 24 40, 20 40 L0 40" fill="#B8A891" stroke="#9A8A71" strokeWidth="1" />
      </svg>
    </div>
  </div>
);

// --- Component ---

const WhoWasITab: React.FC = () => {
  const [data, setData] = useState<WhoWasIData>(INITIAL_DATA);
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
      const result = await beingApi.getLatestTest('past');
      if (result) {
        setData(result.content as WhoWasIData);
        setVersion(result.version);
      } else {
        setData(INITIAL_DATA);
        setVersion(null);
      }
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
        await beingApi.updateTest('past', version, data);
      } else {
        const result = await beingApi.createTest('past', data);
        setVersion(result.version);
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
      <div className="h-full w-full flex items-center justify-center" style={{ backgroundColor: '#E8E0D4' }}>
        <div className="flex flex-col items-center gap-4">
          <Loader2 size={32} className="animate-spin" style={{ color: '#7A6B5A' }} />
          <p className="font-medium" style={{ color: '#7A6B5A', fontFamily: "'Ma Shan Zheng', cursive" }}>加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="h-full w-full overflow-y-auto no-scrollbar relative"
      style={{
        background: 'linear-gradient(135deg, #D4C4B0 0%, #E8DCC8 50%, #D8CDB8 100%)',
        fontFamily: "'Ma Shan Zheng', 'Noto Serif SC', serif"
      }}
    >
      {/* Google Font Import */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&family=Noto+Serif+SC:wght@400;600&display=swap');
        
        .journal-page {
          background: linear-gradient(to right, 
            #F5EDE0 0%, 
            #FDF8F0 2%, 
            #FDF8F0 98%, 
            #E8DFD0 100%
          );
          box-shadow: 
            -8px 0 20px rgba(0,0,0,0.15),
            8px 0 20px rgba(0,0,0,0.1),
            inset 3px 0 10px rgba(0,0,0,0.05);
        }

        .notebook-line {
          background-image: repeating-linear-gradient(
            transparent,
            transparent 31px,
            #C9BDA8 31px,
            #C9BDA8 32px
          );
        }

        .handwriting-input {
          background: transparent;
          border: none;
          border-bottom: 2px solid #B8A890;
          font-family: 'Ma Shan Zheng', cursive;
          font-size: 1.25rem;
          color: #4A4035;
          outline: none;
          transition: border-color 0.2s;
        }

        .handwriting-input:focus {
          border-bottom-color: #8B7355;
        }

        .handwriting-input::placeholder {
          color: #B8A890;
          font-style: italic;
        }

        .handwriting-textarea {
          background: transparent;
          border: none;
          border-bottom: 2px dashed #C9BDA8;
          font-family: 'Ma Shan Zheng', cursive;
          font-size: 1.1rem;
          color: #4A4035;
          outline: none;
          resize: none;
          line-height: 2;
        }

        .handwriting-textarea:focus {
          border-bottom-color: #8B7355;
        }

        .paper-edge-left {
          background: linear-gradient(to right, #C4B8A8 0%, transparent 100%);
        }

        .paper-edge-right {
          background: linear-gradient(to left, #C4B8A8 0%, transparent 100%);
        }
      `}</style>

      {/* 日记本外框装饰 */}
      <div className="absolute inset-0 pointer-events-none">
        {/* 左侧装饰 */}
        <PlantPot className="absolute left-4 top-20" style={{ opacity: 0.8 }} />
        <LeafDecoration className="absolute left-8 top-1/3" style={{ opacity: 0.6, transform: 'rotate(-15deg)' }} />
        <LeafDecoration className="absolute left-6 bottom-32" style={{ opacity: 0.5, transform: 'rotate(10deg) scale(0.8)' }} />

        {/* 右侧装饰 */}
        <CoffeeCup className="absolute right-6 top-24" style={{ opacity: 0.8 }} />
        <PlantPot className="absolute right-8 top-1/2" style={{ opacity: 0.7, transform: 'scale(0.9)' }} />
        <LeafDecoration className="absolute right-4 bottom-40" style={{ opacity: 0.6, transform: 'rotate(20deg)' }} />
      </div>

      {/* 日记本主体 */}
      <div className="relative max-w-4xl mx-auto my-8 px-4">
        <div className="journal-page rounded-lg p-8 md:p-12 min-h-[calc(100vh-4rem)] relative">

          {/* 纸张边缘装饰线 */}
          <div className="absolute left-12 top-0 bottom-0 w-px bg-red-300 opacity-40"></div>
          <div className="absolute left-14 top-0 bottom-0 w-px bg-red-300 opacity-30"></div>

          {/* 版本选择器 - 右上角 */}
          <div className="absolute top-4 right-4 flex items-center gap-2">
            <button
              onClick={loadLatestData}
              className="p-2 rounded-full transition-all duration-200 hover:bg-amber-100"
              style={{ color: '#7A6B5A' }}
              title="刷新"
            >
              <RefreshCw size={18} />
            </button>
            <div className="relative">
              <button
                onClick={() => setShowVersionDropdown(!showVersionDropdown)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm transition-all duration-200"
                style={{
                  backgroundColor: 'rgba(184, 168, 144, 0.3)',
                  color: '#5A4A3A',
                  border: '1px solid #C9BDA8'
                }}
              >
                {version ? `版本 ${version}` : '新版本'}
                <ChevronDown size={14} className={`transition-transform duration-200 ${showVersionDropdown ? 'rotate-180' : ''}`} />
              </button>

              {showVersionDropdown && (
                <div
                  className="absolute top-full mt-2 right-0 rounded-xl overflow-hidden z-50 min-w-[140px]"
                  style={{
                    backgroundColor: '#FDF8F0',
                    boxShadow: '0 8px 24px -8px rgba(90, 74, 58, 0.3)',
                    border: '1px solid #C9BDA8'
                  }}
                >
                  {versions.length > 0 ? (
                    versions.map(v => (
                      <button
                        key={v.id}
                        onClick={() => loadVersion(v.version)}
                        className="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between hover:bg-amber-50"
                        style={{ color: '#5A4A3A' }}
                      >
                        <span>版本 {v.version}</span>
                        {v.version === version && <Check size={14} style={{ color: '#7A9A6D' }} />}
                      </button>
                    ))
                  ) : (
                    <div className="px-4 py-2.5 text-sm" style={{ color: '#9A8A7A' }}>暂无历史版本</div>
                  )}
                  <div style={{ borderTop: '1px solid #D9CDB8' }}>
                    <button
                      onClick={handleCreateNew}
                      className="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center gap-2 hover:bg-amber-50"
                      style={{ color: '#7A6B5A' }}
                    >
                      <Plus size={14} />
                      创建新版本
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 主标题 */}
          <div className="text-center mb-12 pt-8">
            <h1
              className="text-4xl md:text-5xl font-bold mb-4"
              style={{
                color: '#4A3A2A',
                fontFamily: "'Ma Shan Zheng', cursive",
                textShadow: '2px 2px 4px rgba(0,0,0,0.1)'
              }}
            >
              改变你对过去的态度：
            </h1>
          </div>

          {/* 第一部分：我曾经是谁 */}
          <div className="mb-12 pl-16">
            <h2
              className="text-2xl mb-6"
              style={{
                color: '#5A4A3A',
                fontFamily: "'Ma Shan Zheng', cursive"
              }}
            >
              测试："我曾经是谁？"
            </h2>

            <div className="space-y-4">
              {data.whoWasIItems.map((item, index) => (
                <div key={item.id} className="flex items-center gap-4 group">
                  <span
                    className="text-lg font-medium"
                    style={{ color: '#8B7355', fontFamily: "'Ma Shan Zheng', cursive" }}
                  >
                    我曾经:
                  </span>
                  <div className="flex-1 relative">
                    <input
                      type="text"
                      value={item.content}
                      onChange={(e) => handleWhoWasIChange(item.id, e.target.value)}
                      className="handwriting-input w-full py-2"
                      placeholder="胆小、被成绩定义、害怕冲突..."
                    />
                    <button
                      onClick={() => handleDeleteStatement(item.id)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ color: '#B8A890' }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}

              <button
                onClick={handleAddStatement}
                className="inline-flex items-center gap-2 px-4 py-2 mt-2 text-sm transition-all duration-200 rounded-lg hover:bg-amber-50"
                style={{
                  color: '#8B7355',
                  border: '1px dashed #C9BDA8',
                  fontFamily: "'Ma Shan Zheng', cursive"
                }}
              >
                <Plus size={16} /> 添加回忆
              </button>
            </div>
          </div>

          {/* 横幅分隔 */}
          <div className="my-12 flex justify-center">
            <RibbonBanner className="max-w-2xl w-full">
              <p
                className="text-lg"
                style={{
                  color: '#4A3A2A',
                  fontFamily: "'Ma Shan Zheng', cursive",
                  textShadow: '1px 1px 2px rgba(255,255,255,0.3)'
                }}
              >
                放下过去，努力向前，并不意味着遗忘过去，这只意味着和过去和解
              </p>
            </RibbonBanner>
          </div>

          {/* 第二部分：积极重构过去清单 */}
          <div className="pl-16">
            <h2
              className="text-2xl mb-4"
              style={{
                color: '#5A4A3A',
                fontFamily: "'Ma Shan Zheng', cursive"
              }}
            >
              积极重构过去清单
            </h2>
            <p
              className="mb-8"
              style={{
                color: '#7A6B5A',
                fontFamily: "'Noto Serif SC', serif",
                fontSize: '1rem'
              }}
            >
              请列出三件在你生活里发生的重要的负面事件：
            </p>

            <div className="space-y-10">
              {data.positivePastReframingItems.map((item, index) => (
                <div key={item.id} className="relative group">
                  <div className="space-y-4">
                    {/* 事件 */}
                    <div className="flex items-start gap-4">
                      <span
                        className="text-lg font-medium shrink-0 pt-2"
                        style={{ color: '#8B7355', fontFamily: "'Ma Shan Zheng', cursive" }}
                      >
                        事件 {index + 1}:
                      </span>
                      <div className="flex-1">
                        <textarea
                          value={item.negativePast}
                          onChange={(e) => handleReframeChange(item.id, 'negativePast', e.target.value)}
                          className="handwriting-textarea w-full min-h-[60px]"
                          placeholder="描述过去的一段困难经历..."
                        />
                      </div>
                    </div>

                    {/* 隐藏的礼物 */}
                    <div className="flex items-start gap-4 ml-8">
                      <span
                        className="text-base font-medium shrink-0 pt-2"
                        style={{ color: '#7A9A6D', fontFamily: "'Ma Shan Zheng', cursive" }}
                      >
                        🌱 隐藏的礼物:
                      </span>
                      <div className="flex-1">
                        <textarea
                          value={item.positiveTakeaways}
                          onChange={(e) => handleReframeChange(item.id, 'positiveTakeaways', e.target.value)}
                          className="handwriting-textarea w-full min-h-[50px]"
                          placeholder="这段经历让你收获了什么力量或教训？"
                        />
                      </div>
                    </div>

                    {/* 今日的智慧 */}
                    <div className="flex items-start gap-4 ml-8">
                      <span
                        className="text-base font-medium shrink-0 pt-2"
                        style={{ color: '#9AADB8', fontFamily: "'Ma Shan Zheng', cursive" }}
                      >
                        ✨ 今日的智慧:
                      </span>
                      <div className="flex-1">
                        <textarea
                          value={item.howPositiveTakeawaysHelpMe}
                          onChange={(e) => handleReframeChange(item.id, 'howPositiveTakeawaysHelpMe', e.target.value)}
                          className="handwriting-textarea w-full min-h-[50px]"
                          placeholder="这些收获如何帮助你无畏前行？"
                        />
                      </div>
                    </div>
                  </div>

                  {/* 删除按钮 */}
                  <button
                    onClick={() => handleDeleteReframe(item.id)}
                    className="absolute -right-2 top-0 p-2 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-50"
                    style={{ color: '#C5A090' }}
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              ))}

              {/* 添加新故事按钮 */}
              <button
                onClick={handleAddReframe}
                className="w-full py-4 rounded-lg flex flex-col items-center justify-center gap-2 transition-all duration-200 hover:bg-amber-50"
                style={{
                  border: '2px dashed #C9BDA8',
                  color: '#8B7355',
                  fontFamily: "'Ma Shan Zheng', cursive"
                }}
              >
                <Plus size={20} />
                <span>添加新故事</span>
              </button>
            </div>
          </div>

          {/* 保存按钮 */}
          <div className="flex justify-center pt-12 pb-8">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-10 py-4 rounded-xl font-semibold transition-all duration-300 flex items-center gap-3 text-lg"
              style={{
                backgroundColor: saveStatus === 'success' ? '#7A9A6D' : saveStatus === 'error' ? '#B07070' : '#6A5A4A',
                color: '#FDF8F0',
                boxShadow: '0 6px 20px -6px rgba(90, 74, 58, 0.4)',
                opacity: isSaving ? 0.7 : 1,
                fontFamily: "'Ma Shan Zheng', cursive"
              }}
            >
              {isSaving ? (
                <>
                  <Loader2 size={20} className="animate-spin" />
                  <span>保存中...</span>
                </>
              ) : saveStatus === 'success' ? (
                <>
                  <Check size={20} />
                  <span>保存成功</span>
                </>
              ) : saveStatus === 'error' ? (
                <>
                  <AlertCircle size={20} />
                  <span>保存失败</span>
                </>
              ) : (
                <>
                  <BookOpen size={20} />
                  <span>保存回忆</span>
                </>
              )}
            </button>
          </div>

        </div>
      </div>
    </div>
  );
};

export default WhoWasITab;
