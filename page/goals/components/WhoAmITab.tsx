
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
  RefreshCw,
  Palette
} from 'lucide-react';
import { beingApi } from '../api';
import {
  WhoAmIData,
  BeingVersionInfo
} from '../types';

// --- Types & Constants ---
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

// --- Question Block Component ---
interface QuestionBlockProps {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  sectionIndex: number; // 0-3 to pick color from theme
  items: { id: number; value: string }[];
  placeholder: string;
  inputPrefix: string;
  theme: ThemeType;
  onChange: (id: number, val: string) => void;
  onAdd: () => void;
  onDelete: (id: number) => void;
}

const QuestionBlock: React.FC<QuestionBlockProps> = ({
  title,
  subtitle,
  icon,
  sectionIndex,
  items,
  placeholder,
  inputPrefix,
  theme,
  onChange,
  onAdd,
  onDelete
}) => {
  const colors = theme.colors;
  const sectionColors = theme.colors.sections[sectionIndex] || theme.colors.sections[0];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-colors duration-300"
          style={{ backgroundColor: sectionColors.iconBg, color: sectionColors.iconColor }}
        >
          {icon}
        </div>
        <div>
          <h3 className="text-base font-semibold transition-colors duration-300" style={{ color: colors.textMain }}>{title}</h3>
          <p className="text-sm transition-colors duration-300" style={{ color: colors.textSub }}>{subtitle}</p>
        </div>
      </div>

      {/* Items */}
      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={item.id} className="group transition-all duration-300">
            <div className="flex items-center gap-3">
              <span
                className="text-sm font-medium w-5 text-center shrink-0 transition-colors duration-300"
                style={{ color: colors.textMuted }}
              >
                {index + 1}
              </span>
              <div className="flex-1 relative">
                <span
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-sm pointer-events-none select-none transition-colors duration-300"
                  style={{ color: colors.textMuted }}
                >
                  {inputPrefix}
                </span>
                <input
                  type="text"
                  value={item.value}
                  onChange={(e) => onChange(item.id, e.target.value)}
                  className="w-full rounded-xl py-3.5 pl-20 pr-10 text-base outline-none transition-all duration-200"
                  style={{
                    backgroundColor: colors.inputBg,
                    color: colors.textMain,
                    border: '1px solid transparent'
                  }}
                  onFocus={(e) => {
                    e.target.style.backgroundColor = colors.inputFocusBg;
                    e.target.style.border = `1px solid ${colors.border}`;
                    e.target.style.boxShadow = `0 2px 12px -4px ${colors.inputRing}`;
                  }}
                  onBlur={(e) => {
                    e.target.style.backgroundColor = colors.inputBg;
                    e.target.style.border = '1px solid transparent';
                    e.target.style.boxShadow = 'none';
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
                  placeholder={placeholder}
                />
                <button
                  onClick={() => onDelete(item.id)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-200"
                  style={{ color: colors.textMuted }}
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
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all duration-200 hover:opacity-80"
            style={{
              color: colors.textMuted,
              border: `1px dashed ${colors.border}`
            }}
          >
            <Plus size={14} /> 添加
          </button>
        </div>
      </div>
    </div>
  );
};

// --- Main Component ---
const WhoAmITab: React.FC = () => {
  const [data, setData] = useState<WhoAmIData>(INITIAL_DATA);
  const [version, setVersion] = useState<number | null>(null);
  const [versions, setVersions] = useState<BeingVersionInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [showVersionDropdown, setShowVersionDropdown] = useState(false);
  const [showThemeDropdown, setShowThemeDropdown] = useState(false);

  const { theme, currentThemeId, setTheme } = useTheme();
  const colors = theme.colors;

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

  // Delete version
  const handleDeleteVersion = async (verToDelete: number) => {
    if (!window.confirm(`确定要删除版本 ${verToDelete} 吗？此操作无法撤销。`)) return;

    try {
      await beingApi.deleteTest('present', verToDelete);

      // If deleted current version, reload everything (which fetches latest)
      if (version === verToDelete) {
        await loadLatestData();
      } else {
        // Just refresh list
        const versionList = await beingApi.getVersions('present');
        setVersions(versionList.versions);
      }
    } catch (error) {
      console.error('[WhoAmITab] Delete version failed:', error);
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
        <div className="flex items-center justify-center gap-3 mb-6">
          <div
            className="inline-flex items-center justify-center w-12 h-12 rounded-full transition-colors duration-300"
            style={{ backgroundColor: colors.actionBtnBg, color: colors.actionBtnText }}
          >
            <Anchor size={22} strokeWidth={1.5} />
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
          锚定当下
        </h2>
        <p className="text-lg leading-relaxed transition-colors duration-300" style={{ color: colors.textSub }}>
          一次真实的自我检视，扎根于身份、环境与情绪。
        </p>
      </div>

      {/* Single Unified Card */}
      <div
        className="max-w-2xl mx-auto rounded-[2rem] p-8 md:p-10 relative overflow-hidden transition-all duration-300"
        style={{
          backgroundColor: colors.cardBg,
          boxShadow: `0 4px 30px -8px ${colors.inputRing}`,
          border: `1px solid ${colors.border}`
        }}
      >
        {/* Subtle glow overlay */}
        <div
          className="absolute top-0 right-0 w-64 h-64 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none opacity-20 transition-colors duration-300"
          style={{ backgroundColor: colors.glowColor }}
        />

        <div className="relative z-10 space-y-10">

          {/* 1. Who Am I */}
          <QuestionBlock
            title="我现在是谁？"
            subtitle="角色、状态或隐喻"
            icon={<Fingerprint size={20} strokeWidth={1.5} />}
            sectionIndex={0}
            items={data.whoAmIItems.map(i => ({ id: i.id, value: i.whoAmI }))}
            placeholder="一个探索者、一个学习者..."
            inputPrefix="我是..."
            theme={theme}
            onChange={handleWhoAmIChange}
            onAdd={addWhoAmI}
            onDelete={delWhoAmI}
          />

          {/* Divider */}
          <div style={{ height: '1px', backgroundColor: colors.border }} className="transition-colors duration-300" />

          {/* 2. What Time */}
          <QuestionBlock
            title="现在是什么时刻？"
            subtitle="人生阶段、季节或字面时间"
            icon={<Clock size={20} strokeWidth={1.5} />}
            sectionIndex={1}
            items={data.whatTimeItems.map(i => ({ id: i.id, value: i.whatTime }))}
            placeholder="成长的时刻、转变的季节..."
            inputPrefix="是..."
            theme={theme}
            onChange={handleTimeChange}
            onAdd={addTime}
            onDelete={delTime}
          />

          {/* Divider */}
          <div style={{ height: '1px', backgroundColor: colors.border }} className="transition-colors duration-300" />

          {/* 3. Where Am I */}
          <QuestionBlock
            title="我在哪里？"
            subtitle="环境、感官或精神状态"
            icon={<MapPin size={20} strokeWidth={1.5} />}
            sectionIndex={2}
            items={data.whereAmIItems.map(i => ({ id: i.id, value: i.whereAmI }))}
            placeholder="在家中、在思考中、在路上..."
            inputPrefix="在..."
            theme={theme}
            onChange={handleWhereChange}
            onAdd={addWhere}
            onDelete={delWhere}
          />

          {/* Divider */}
          <div style={{ height: '1px', backgroundColor: colors.border }} className="transition-colors duration-300" />

          {/* 4. Feelings */}
          <QuestionBlock
            title="我的感受如何？"
            subtitle="真实的情绪、身体感受"
            icon={<Heart size={20} strokeWidth={1.5} />}
            sectionIndex={3}
            items={data.howAmIFeelingItems.map(i => ({ id: i.id, value: i.howAmIFeeling }))}
            placeholder="平静、期待、有些疲惫..."
            inputPrefix="感到..."
            theme={theme}
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
              <span>保存当下</span>
            </>
          )}
        </button>
      </div>

    </div>
  );
};

export default WhoAmITab;
