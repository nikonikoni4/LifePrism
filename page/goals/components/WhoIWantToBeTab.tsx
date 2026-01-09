
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
  RefreshCw,
  Palette
} from 'lucide-react';
import { beingApi } from '../api';
import {
  WhoIWantToBeData,
  WhoIWantToBeItem,
  SpecificGoalsItem,
  BeingVersionInfo
} from '../types';

// --- Types & Constants ---
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

// --- Theme Definition ---
interface ThemeType {
  id: string;
  name: string;
  colors: {
    bg: string;
    cardBg: string;
    textMain: string;
    textSub: string;
    textMuted: string;
    border: string;
    inputBg: string;
    inputHoverBg: string;
    inputFocusBg: string;
    inputPlaceholder: string;
    inputRing: string;
    actionBtnBg: string;
    actionBtnText: string;
    actionBtnBorder: string;
    danger: string;
    success: string;
    primaryBtnBg: string;
    primaryBtnText: string;
    glowColor: string;
    sections: {
      iconBg: string;
      iconColor: string;
    }[];
  }
}

const THEMES: Record<string, ThemeType> = {
  soft: {
    id: 'soft',
    name: '雅致',
    colors: {
      bg: '#FDFBF9',
      cardBg: '#FFFFFF',
      textMain: '#2C2A26',
      textSub: '#5C574F',
      textMuted: '#8B7E74',
      border: '#E8E4DD',
      inputBg: '#FAF9F7',
      inputHoverBg: '#F5F5F5',
      inputFocusBg: '#FFFFFF',
      inputPlaceholder: '#A89F91',
      inputRing: 'rgba(139, 126, 109, 0.12)',
      actionBtnBg: '#F5F3EE',
      actionBtnText: '#5C574F',
      actionBtnBorder: '#E8E4DD',
      danger: '#B07070',
      success: '#7A9A6D',
      primaryBtnBg: '#5C574F',
      primaryBtnText: '#FFFFFF',
      glowColor: '#F5EFE6',
      sections: [
        { iconBg: '#FBF6EE', iconColor: '#AF9164' },
        { iconBg: '#F5F3EE', iconColor: '#89968E' },
        { iconBg: '#F3F5F4', iconColor: '#7A8C86' },
        { iconBg: '#FBF5F5', iconColor: '#AC908C' }
      ]
    }
  },
  balanced: {
    id: 'balanced',
    name: '温润',
    colors: {
      bg: '#F7F6F5', // Stone-50ish, cleaner than soft, warmer than contrast
      cardBg: '#FFFFFF',
      textMain: '#292524', // Stone-800
      textSub: '#44403C',  // Stone-700
      textMuted: '#78716C', // Stone-500
      border: '#E7E5E4',   // Stone-200
      inputBg: '#F5F5F4',  // Stone-100
      inputHoverBg: '#E7E5E4',
      inputFocusBg: '#FFFFFF',
      inputPlaceholder: '#A8A29E',
      inputRing: 'rgba(68, 64, 60, 0.1)',
      actionBtnBg: '#FFFFFF',
      actionBtnText: '#44403C',
      actionBtnBorder: '#E7E5E4',
      danger: '#DC2626',
      success: '#16A34A',
      primaryBtnBg: '#44403C',
      primaryBtnText: '#FFFFFF',
      glowColor: '#E7E5E4',
      sections: [
        { iconBg: '#FFF7ED', iconColor: '#C2410C' }, // Orange-ish/Stone blend
        { iconBg: '#F0FDF4', iconColor: '#15803D' }, // Green
        { iconBg: '#ECFEFF', iconColor: '#0E7490' }, // Cyan
        { iconBg: '#FFF1F2', iconColor: '#BE123C' }  // Rose
      ]
    }
  },
  contrast: {
    id: 'contrast',
    name: '清晰',
    colors: {
      bg: '#F2F4F6',
      cardBg: '#FFFFFF',
      textMain: '#111827',
      textSub: '#374151',
      textMuted: '#6B7280',
      border: '#D1D5DB',
      inputBg: '#F3F4F6',
      inputHoverBg: '#E5E7EB',
      inputFocusBg: '#FFFFFF',
      inputPlaceholder: '#9CA3AF',
      inputRing: 'rgba(0, 0, 0, 0.1)',
      actionBtnBg: '#FFFFFF',
      actionBtnText: '#111827',
      actionBtnBorder: '#D1D5DB',
      danger: '#DC2626',
      success: '#16A34A',
      primaryBtnBg: '#111827',
      primaryBtnText: '#FFFFFF',
      glowColor: '#E5E7EB',
      sections: [
        { iconBg: '#FEF3C7', iconColor: '#B45309' },
        { iconBg: '#D1FAE5', iconColor: '#047857' },
        { iconBg: '#CFFAFE', iconColor: '#0891B2' },
        { iconBg: '#FCE7F3', iconColor: '#BE185D' }
      ]
    }
  },
  dark: {
    id: 'dark',
    name: '暗夜',
    colors: {
      bg: '#18181B',
      cardBg: '#27272A',
      textMain: '#F4F4F5',
      textSub: '#A1A1AA',
      textMuted: '#71717A',
      border: '#3F3F46',
      inputBg: '#3F3F46',
      inputHoverBg: '#52525B',
      inputFocusBg: '#27272A',
      inputPlaceholder: '#71717A',
      inputRing: 'rgba(255, 255, 255, 0.1)',
      actionBtnBg: '#3F3F46',
      actionBtnText: '#E4E4E7',
      actionBtnBorder: '#52525B',
      danger: '#EF4444',
      success: '#22C55E',
      primaryBtnBg: '#E4E4E7',
      primaryBtnText: '#18181B',
      glowColor: '#3F3F46',
      sections: [
        { iconBg: 'rgba(196, 165, 116, 0.15)', iconColor: '#E6C995' },
        { iconBg: 'rgba(155, 168, 160, 0.15)', iconColor: '#B8C0B8' },
        { iconBg: 'rgba(138, 160, 154, 0.15)', iconColor: '#A8BCB6' },
        { iconBg: 'rgba(191, 165, 160, 0.15)', iconColor: '#D0B0B0' }
      ]
    }
  }
};

// --- Theme Context Hook (Local simplified) ---
const useTheme = () => {
  const [themeId, setThemeId] = useState<string>(() => {
    return localStorage.getItem('whoAmI_theme') || 'contrast';
  });

  const setTheme = (id: string) => {
    if (THEMES[id]) {
      setThemeId(id);
      localStorage.setItem('whoAmI_theme', id);
    }
  };

  return {
    theme: THEMES[themeId],
    currentThemeId: themeId,
    setTheme
  };
};

const WhoIWantToBeTab: React.FC = () => {
  const [data, setData] = useState<WhoIWantToBeData>(INITIAL_DATA);
  const [version, setVersion] = useState<number | null>(null);
  const [versions, setVersions] = useState<BeingVersionInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [showVersionDropdown, setShowVersionDropdown] = useState(false);
  const [showThemeDropdown, setShowThemeDropdown] = useState(false);

  const { theme, currentThemeId, setTheme } = useTheme();
  const colors = theme.colors;

  // Choose section colors for variety
  const identitySectionColors = theme.colors.sections[0];
  const goalSectionColors = theme.colors.sections[1];

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
      setIsSaving(false);
    }
  };

  // Create new version
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

  // Delete version
  const handleDeleteVersion = async (verToDelete: number) => {
    if (!window.confirm(`确定要删除版本 ${verToDelete} 吗？此操作无法撤销。`)) return;

    try {
      await beingApi.deleteTest('future', verToDelete);

      // If deleted current version, reload everything (which fetches latest)
      if (version === verToDelete) {
        await loadLatestData();
      } else {
        // Just refresh list
        const versionList = await beingApi.getVersions('future');
        setVersions(versionList.versions);
      }
    } catch (error) {
      console.error('[WhoIWantToBeTab] Delete version failed:', error);
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
      <div className="h-full w-full flex items-center justify-center transition-colors duration-300" style={{ backgroundColor: colors.bg }}>
        <div className="flex flex-col items-center gap-4">
          <Loader2 size={32} className="animate-spin" style={{ color: colors.textMuted }} />
          <p className="font-medium" style={{ color: colors.textSub }}>加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="h-full w-full overflow-y-auto no-scrollbar pb-24 px-6 md:px-16 pt-8 animate-fade-in font-sans transition-colors duration-300"
      style={{ backgroundColor: colors.bg }}
    >

      {/* Header */}
      <div className="max-w-2xl mx-auto text-center mb-16">
        <div className="flex items-center justify-center gap-4 mb-6">
          <div
            className="inline-flex items-center justify-center w-12 h-12 rounded-full transition-colors duration-300"
            style={{ backgroundColor: colors.actionBtnBg, color: colors.actionBtnText }}
          >
            <Compass size={22} strokeWidth={1.5} />
          </div>

          {/* Version Selector */}
          <div className="relative">
            <button
              onClick={() => {
                setShowVersionDropdown(!showVersionDropdown);
                setShowThemeDropdown(false);
              }}
              className="flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium transition-all duration-200"
              style={{
                backgroundColor: colors.actionBtnBg,
                color: colors.actionBtnText,
                border: `1px solid ${colors.actionBtnBorder}`
              }}
            >
              {version ? `版本 ${version}` : '新版本'}
              <ChevronDown size={16} className={`transition-transform duration-200 ${showVersionDropdown ? 'rotate-180' : ''}`} />
            </button>

            {showVersionDropdown && (
              <div
                className="absolute top-full mt-2 left-0 rounded-2xl overflow-hidden z-50 min-w-[160px]"
                style={{
                  backgroundColor: colors.cardBg,
                  boxShadow: '0 10px 40px -10px rgba(0,0,0,0.1)',
                  border: `1px solid ${colors.border}`
                }}
              >
                <div className="max-h-[240px] overflow-y-auto no-scrollbar">
                  {versions.length > 0 ? (
                    versions.map(v => (
                      <div
                        key={v.id}
                        className="w-full px-4 py-3 text-left text-sm transition-colors flex items-center justify-between group hover:bg-opacity-50"
                        style={{
                          backgroundColor: v.version === version ? colors.actionBtnBg : 'transparent',
                          color: colors.textSub
                        }}
                      >
                        <button
                          onClick={() => loadVersion(v.version)}
                          className="flex-1 text-left flex items-center justify-between"
                        >
                          <span>版本 {v.version}</span>
                          {v.version === version && <Check size={14} style={{ color: colors.textMain }} />}
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteVersion(v.version);
                          }}
                          className="ml-2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-500 transition-all"
                          title="删除此版本"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))
                  ) : (
                    <div className="px-4 py-3 text-sm" style={{ color: colors.textMuted }}>暂无历史版本</div>
                  )}
                </div>
                <div style={{ borderTop: `1px solid ${colors.border}` }}>
                  <button
                    onClick={handleCreateNew}
                    className="w-full px-4 py-3 text-left text-sm transition-colors flex items-center gap-2 hover:opacity-80"
                    style={{ color: colors.sections[0].iconColor }}
                  >
                    <Plus size={14} />
                    创建新版本
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Theme Selector */}
          <div className="relative">
            <button
              onClick={() => {
                setShowThemeDropdown(!showThemeDropdown);
                setShowVersionDropdown(false);
              }}
              className="p-2.5 rounded-xl transition-all duration-200 border"
              style={{
                backgroundColor: colors.actionBtnBg,
                color: colors.actionBtnText,
                borderColor: colors.actionBtnBorder
              }}
              title="切换主题"
            >
              <Palette size={18} />
            </button>

            {showThemeDropdown && (
              <div
                className="absolute top-full mt-2 left-0 rounded-2xl overflow-hidden z-50 min-w-[140px]"
                style={{
                  backgroundColor: colors.cardBg,
                  boxShadow: '0 10px 40px -10px rgba(0,0,0,0.1)',
                  border: `1px solid ${colors.border}`
                }}
              >
                {Object.values(THEMES).map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      setTheme(t.id);
                      setShowThemeDropdown(false);
                    }}
                    className="w-full px-4 py-3 text-left text-sm transition-colors flex items-center justify-between hover:bg-opacity-50"
                    style={{
                      backgroundColor: currentThemeId === t.id ? colors.actionBtnBg : 'transparent',
                      color: colors.textSub
                    }}
                  >
                    <span>{t.name}</span>
                    {currentThemeId === t.id && <Check size={14} style={{ color: colors.textMain }} />}
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={loadLatestData}
            className="p-2.5 rounded-xl transition-all duration-200"
            style={{ color: colors.textMuted }}
            title="刷新"
          >
            <RefreshCw size={18} />
          </button>
        </div>

        <h2
          className="text-3xl md:text-4xl font-semibold tracking-tight mb-4 transition-colors duration-300"
          style={{ color: colors.textMain }}
        >
          构建你的未来
        </h2>
        <p className="text-lg leading-relaxed transition-colors duration-300" style={{ color: colors.textSub }}>
          定义你正在迈向的身份，以及标记道路的里程碑。
        </p>
      </div>

      <div className="max-w-2xl mx-auto space-y-12">

        {/* Section 1: Future Identity */}
        <section
          className="rounded-[2rem] p-8 md:p-10 relative overflow-hidden transition-all duration-300"
          style={{
            backgroundColor: colors.cardBg,
            boxShadow: `0 4px 30px -8px ${colors.inputRing}`,
            border: `1px solid ${colors.border}`
          }}
        >
          {/* Subtle warm gradient overlay */}
          <div
            className="absolute top-0 right-0 w-64 h-64 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none opacity-25 transition-colors duration-300"
            style={{ backgroundColor: colors.glowColor }}
          />
          <div
            className="absolute bottom-0 left-0 w-48 h-48 rounded-full blur-3xl -ml-10 -mb-10 pointer-events-none opacity-20 transition-colors duration-300"
            style={{ backgroundColor: colors.glowColor }}
          />

          <div className="relative z-10 mb-8 flex items-center gap-4 pb-6 transition-colors duration-300" style={{ borderBottom: `1px solid ${colors.border}` }}>
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center transition-colors duration-300"
              style={{ backgroundColor: identitySectionColors.iconBg, color: identitySectionColors.iconColor }}
            >
              <Sparkles size={22} strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-lg font-semibold transition-colors duration-300" style={{ color: colors.textMain }}>未来的身份</h3>
              <p className="text-sm mt-0.5 transition-colors duration-300" style={{ color: colors.textSub }}>你将成为谁？</p>
            </div>
          </div>

          <div className="space-y-4 relative z-10">
            {data.whoIWantToBeItems.map((item, index) => (
              <div key={item.id} className="group transition-all duration-300">
                <div className="flex items-center gap-4">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium shrink-0 transition-colors duration-300"
                    style={{ backgroundColor: colors.actionBtnBg, color: colors.textMuted }}
                  >
                    {index + 1}
                  </div>
                  <div className="flex-1 relative">
                    <span
                      className="absolute left-4 top-1/2 -translate-y-1/2 text-sm pointer-events-none select-none transition-colors duration-300"
                      style={{ color: colors.textMuted }}
                    >
                      我将成为...
                    </span>
                    <input
                      type="text"
                      value={item.whoIWantToBe}
                      onChange={(e) => handleIdentityChange(item.id, e.target.value)}
                      className="w-full rounded-xl py-4 pl-28 pr-12 text-base font-medium outline-none transition-all duration-200"
                      style={{
                        backgroundColor: colors.inputBg,
                        color: colors.textMain,
                        border: '1px solid transparent'
                      }}
                      onFocus={(e) => {
                        (e.target as HTMLInputElement).style.backgroundColor = colors.inputFocusBg;
                        (e.target as HTMLInputElement).style.border = `1px solid ${colors.border}`;
                        (e.target as HTMLInputElement).style.boxShadow = `0 2px 12px -4px ${colors.inputRing}`;
                      }}
                      onBlur={(e) => {
                        (e.target as HTMLInputElement).style.backgroundColor = colors.inputBg;
                        (e.target as HTMLInputElement).style.border = '1px solid transparent';
                        (e.target as HTMLInputElement).style.boxShadow = 'none';
                      }}
                      onMouseEnter={(e) => {
                        if (document.activeElement !== e.target) {
                          (e.target as HTMLInputElement).style.backgroundColor = colors.inputHoverBg;
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (document.activeElement !== e.target) {
                          (e.target as HTMLInputElement).style.backgroundColor = colors.inputBg;
                        }
                      }}
                      placeholder="有远见的领导者..."
                    />
                    <button
                      onClick={() => removeIdentity(item.id)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-200"
                      style={{ color: colors.textMuted }}
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
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 hover:opacity-80"
                style={{
                  color: colors.textMuted,
                  border: `1px dashed ${colors.border}`
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
              className="w-12 h-12 rounded-2xl flex items-center justify-center transition-colors duration-300"
              style={{ backgroundColor: goalSectionColors.iconBg, color: goalSectionColors.iconColor }}
            >
              <Target size={22} strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-lg font-semibold transition-colors duration-300" style={{ color: colors.textMain }}>具体的里程碑</h3>
              <p className="text-sm mt-0.5 transition-colors duration-300" style={{ color: colors.textSub }}>切实的目标和期限</p>
            </div>
          </div>

          <div className="space-y-5">
            {data.specificGoalsItems.map((item, index) => (
              <div
                key={item.id}
                className="rounded-[2rem] p-6 md:p-8 relative group transition-all duration-300"
                style={{
                  backgroundColor: colors.cardBg,
                  boxShadow: `0 2px 20px -6px ${colors.inputRing}`,
                  border: `1px solid ${colors.border}`
                }}
              >
                <button
                  onClick={() => removeGoal(item.id)}
                  className="absolute top-6 right-6 p-2 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200"
                  style={{ color: colors.textMuted }}
                >
                  <Trash2 size={18} />
                </button>

                {/* Vertical Stack */}
                <div className="space-y-5">
                  {/* Goal Input */}
                  <div className="space-y-3">
                    <label
                      className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider transition-colors duration-300"
                      style={{ color: colors.textSub }}
                    >
                      <Rocket size={14} style={{ color: colors.textMuted }} /> 具体目标
                    </label>
                    <textarea
                      value={item.specificGoals}
                      onChange={(e) => handleGoalChange(item.id, 'specificGoals', e.target.value)}
                      className="w-full rounded-xl p-4 text-base leading-relaxed resize-none outline-none transition-all duration-200 min-h-[90px]"
                      style={{
                        backgroundColor: colors.inputBg,
                        color: colors.textMain,
                        border: '1px solid transparent'
                      }}
                      onFocus={(e) => {
                        (e.target as HTMLTextAreaElement).style.backgroundColor = colors.inputFocusBg;
                        (e.target as HTMLTextAreaElement).style.border = `1px solid ${colors.border}`;
                      }}
                      onBlur={(e) => {
                        (e.target as HTMLTextAreaElement).style.backgroundColor = colors.inputBg;
                        (e.target as HTMLTextAreaElement).style.border = '1px solid transparent';
                      }}
                      onMouseEnter={(e) => {
                        if (document.activeElement !== e.target) {
                          (e.target as HTMLTextAreaElement).style.backgroundColor = colors.inputHoverBg;
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (document.activeElement !== e.target) {
                          (e.target as HTMLTextAreaElement).style.backgroundColor = colors.inputBg;
                        }
                      }}
                      placeholder="你具体想要实现什么？"
                    />
                  </div>

                  {/* Timeline Input */}
                  <div className="space-y-3">
                    <label
                      className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider transition-colors duration-300"
                      style={{ color: colors.textSub }}
                    >
                      <Calendar size={14} style={{ color: colors.textMuted }} /> 期限
                    </label>
                    <input
                      type="text"
                      value={item.whenWillIReachThem}
                      onChange={(e) => handleGoalChange(item.id, 'whenWillIReachThem', e.target.value)}
                      className="w-full md:w-1/2 rounded-xl p-4 text-base outline-none transition-all duration-200"
                      style={{
                        backgroundColor: colors.inputBg,
                        color: colors.textMain,
                        border: '1px solid transparent',
                        fontFamily: "'SF Mono', 'Monaco', monospace"
                      }}
                      onFocus={(e) => {
                        (e.target as HTMLInputElement).style.backgroundColor = colors.inputFocusBg;
                        (e.target as HTMLInputElement).style.border = `1px solid ${colors.border}`;
                      }}
                      onBlur={(e) => {
                        (e.target as HTMLInputElement).style.backgroundColor = colors.inputBg;
                        (e.target as HTMLInputElement).style.border = '1px solid transparent';
                      }}
                      onMouseEnter={(e) => {
                        if (document.activeElement !== e.target) {
                          (e.target as HTMLInputElement).style.backgroundColor = colors.inputHoverBg;
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (document.activeElement !== e.target) {
                          (e.target as HTMLInputElement).style.backgroundColor = colors.inputBg;
                        }
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
              className="w-full py-6 rounded-[2rem] font-medium flex flex-col items-center justify-center gap-2 transition-all duration-300 hover:opacity-80"
              style={{
                border: `2px dashed ${colors.border}`,
                color: colors.textMuted
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
              backgroundColor: saveStatus === 'success' ? colors.success : saveStatus === 'error' ? colors.danger : colors.primaryBtnBg,
              color: colors.primaryBtnText,
              boxShadow: '0 8px 24px -8px rgba(0,0,0, 0.25)',
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
