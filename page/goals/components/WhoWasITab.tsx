import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Plus,
  Loader2,
  Check,
  ChevronDown,
  AlertCircle,
  Trash2,
  RefreshCw,
  BookOpen,
  Palette,
  History,
  Gift,
  Sparkles,
  FileQuestion,
  RotateCcw,
  Quote,
  Eye
} from 'lucide-react';
import { beingApi } from '../api';
import {
  WhoWasIData,
  WhoWasIItem,
  PositivePastReframingItem,
  BeingVersionInfo
} from '../types';

// --- Default Initial Data ---
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

// --- Theme Definition (Matched with WhoAmITab) ---
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
      bg: '#F7F6F5',
      cardBg: '#FFFFFF',
      textMain: '#292524',
      textSub: '#44403C',
      textMuted: '#78716C',
      border: '#E7E5E4',
      inputBg: '#F5F5F4',
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
        { iconBg: '#FFF7ED', iconColor: '#C2410C' },
        { iconBg: '#F0FDF4', iconColor: '#15803D' },
        { iconBg: '#ECFEFF', iconColor: '#0E7490' },
        { iconBg: '#FFF1F2', iconColor: '#BE123C' }
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





// --- Theme Context Hook ---
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
  sectionIndex: number;
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

// --- Reframing Block Component ---
interface ReframingBlockProps {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  sectionIndex: number;
  items: PositivePastReframingItem[];
  theme: ThemeType;
  onChange: (id: number, field: keyof PositivePastReframingItem, val: string) => void;
  onAdd: () => void;
  onDelete: (id: number) => void;
}

const ReframingBlock: React.FC<ReframingBlockProps> = ({
  title,
  subtitle,
  icon,
  sectionIndex,
  items,
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
      <div className="space-y-6">
        {items.map((item, index) => (
          <div
            key={item.id}
            className="p-5 rounded-2xl space-y-4 group transition-all duration-300 relative"
            style={{ backgroundColor: colors.inputBg }}
          >
            {/* Index Label */}
            <div className="absolute left-0 top-6 -translate-x-full pr-3 hidden md:block">
              <span className="text-sm font-medium" style={{ color: colors.textMuted }}>{index + 1}</span>
            </div>

            {/* Delete Button */}
            <button
              onClick={() => onDelete(item.id)}
              className="absolute right-4 top-4 p-1 rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-200"
              style={{ color: colors.textMuted }}
            >
              <Trash2 size={16} />
            </button>

            {/* Fields */}
            <div className="space-y-4">
              {/* Negative Past */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <FileQuestion size={14} style={{ color: colors.textSub }} />
                  <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: colors.textMuted }}>过去的事件</span>
                </div>
                <textarea
                  value={item.negativePast}
                  onChange={(e) => onChange(item.id, 'negativePast', e.target.value)}
                  className="w-full rounded-xl p-3 text-sm outline-none transition-all duration-200 resize-none"
                  rows={2}
                  style={{
                    backgroundColor: colors.cardBg,
                    color: colors.textMain,
                    border: `1px solid ${colors.border}`
                  }}
                  placeholder="描述一段困难经历..."
                  onFocus={(e) => e.target.style.borderColor = colors.textMuted}
                  onBlur={(e) => e.target.style.borderColor = colors.border}
                />
              </div>

              {/* Positive Takeaways */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Gift size={14} style={{ color: theme.colors.success }} />
                  <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: colors.textMuted }}>隐藏的礼物</span>
                </div>
                <textarea
                  value={item.positiveTakeaways}
                  onChange={(e) => onChange(item.id, 'positiveTakeaways', e.target.value)}
                  className="w-full rounded-xl p-3 text-sm outline-none transition-all duration-200 resize-none"
                  rows={2}
                  style={{
                    backgroundColor: colors.cardBg,
                    color: colors.textMain,
                    border: `1px solid ${colors.border}`
                  }}
                  placeholder="收获了什么力量或教训？"
                  onFocus={(e) => e.target.style.borderColor = colors.textMuted}
                  onBlur={(e) => e.target.style.borderColor = colors.border}
                />
              </div>

              {/* How it helps */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Sparkles size={14} style={{ color: theme.colors.sections[0].iconColor }} />
                  <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: colors.textMuted }}>今日的智慧</span>
                </div>
                <textarea
                  value={item.howPositiveTakeawaysHelpMe}
                  onChange={(e) => onChange(item.id, 'howPositiveTakeawaysHelpMe', e.target.value)}
                  className="w-full rounded-xl p-3 text-sm outline-none transition-all duration-200 resize-none"
                  rows={2}
                  style={{
                    backgroundColor: colors.cardBg,
                    color: colors.textMain,
                    border: `1px solid ${colors.border}`
                  }}
                  placeholder="如何帮助你继续前行？"
                  onFocus={(e) => e.target.style.borderColor = colors.textMuted}
                  onBlur={(e) => e.target.style.borderColor = colors.border}
                />
              </div>
            </div>
          </div>
        ))}

        <div className="pt-2">
          <button
            onClick={onAdd}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all duration-200 hover:opacity-80"
            style={{
              color: colors.textMuted,
              border: `1px dashed ${colors.border}`
            }}
          >
            <Plus size={14} /> 添加新故事
          </button>
        </div>
      </div>
    </div>
  );
};

// --- Review Block Component ---
interface ReviewBlockProps {
  items: WhoWasIItem[];
  theme: ThemeType;
  onJudge: (id: number, judge: '+' | '0' | '-') => void;
}

const ReviewBlock: React.FC<ReviewBlockProps> = ({ items, theme, onJudge }) => {
  const colors = theme.colors;
  const sectionColors = theme.colors.sections[2];

  // Calculate statistics
  const stats = items.reduce(
    (acc, item) => {
      const latestJudge = item.judgeItems && item.judgeItems.length > 0
        ? item.judgeItems[item.judgeItems.length - 1].judge
        : null;
      if (latestJudge === '+') acc.positive++;
      else if (latestJudge === '-') acc.negative++;
      else if (latestJudge === '0') acc.neutral++;
      return acc;
    },
    { positive: 0, negative: 0, neutral: 0 }
  );

  const score = stats.positive - stats.negative;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-colors duration-300"
          style={{ backgroundColor: sectionColors.iconBg, color: sectionColors.iconColor }}
        >
          <Eye size={20} strokeWidth={1.5} />
        </div>
        <div>
          <h3 className="text-base font-semibold transition-colors duration-300" style={{ color: colors.textMain }}>审视过去</h3>
          <p className="text-sm transition-colors duration-300" style={{ color: colors.textSub }}>对过去的态度进行评价</p>
        </div>
      </div>

      {/* Statistics Card */}
      <div
        className="p-6 rounded-2xl transition-all duration-300"
        style={{ backgroundColor: colors.inputBg, border: `1px solid ${colors.border}` }}
      >
        <h4 className="text-sm font-semibold mb-4 transition-colors duration-300" style={{ color: colors.textSub }}>评价统计</h4>
        <div className="grid grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold transition-colors duration-300" style={{ color: colors.success }}>+{stats.positive}</div>
            <div className="text-xs mt-1 transition-colors duration-300" style={{ color: colors.textMuted }}>积极</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold transition-colors duration-300" style={{ color: colors.textMuted }}>0 {stats.neutral}</div>
            <div className="text-xs mt-1 transition-colors duration-300" style={{ color: colors.textMuted }}>中性</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold transition-colors duration-300" style={{ color: colors.danger }}>-{stats.negative}</div>
            <div className="text-xs mt-1 transition-colors duration-300" style={{ color: colors.textMuted }}>消极</div>
          </div>
          <div className="text-center">
            <div
              className="text-2xl font-bold transition-colors duration-300"
              style={{ color: score >= 0 ? colors.success : colors.danger }}
            >
              {score >= 0 ? '+' : ''}{score}
            </div>
            <div className="text-xs mt-1 transition-colors duration-300" style={{ color: colors.textMuted }}>总分</div>
          </div>
        </div>
      </div>

      {/* Items List */}
      <div className="space-y-3">
        {items.map((item, index) => {
          const latestJudge = item.judgeItems && item.judgeItems.length > 0
            ? item.judgeItems[item.judgeItems.length - 1].judge
            : null;

          return (
            <div key={item.id} className="group transition-all duration-300">
              <div className="flex items-center gap-3">
                <span
                  className="text-sm font-medium w-5 text-center shrink-0 transition-colors duration-300"
                  style={{ color: colors.textMuted }}
                >
                  {index + 1}
                </span>
                <div
                  className="flex-1 rounded-xl py-3.5 px-4 transition-all duration-200"
                  style={{
                    backgroundColor: colors.inputBg,
                    color: colors.textMain,
                    border: `1px solid ${colors.border}`
                  }}
                >
                  <span className="text-sm font-medium transition-colors duration-300" style={{ color: colors.textMuted }}>我曾经...</span>
                  <span className="ml-2">{item.content || '(未填写)'}</span>
                </div>
                <select
                  value={latestJudge || ''}
                  onChange={(e) => onJudge(item.id, e.target.value as '+' | '0' | '-')}
                  className="px-4 py-2 rounded-xl text-sm font-medium outline-none transition-all duration-200"
                  style={{
                    backgroundColor: colors.cardBg,
                    color: colors.textMain,
                    border: `1px solid ${colors.border}`
                  }}
                >
                  <option value="">未评价</option>
                  <option value="+">+ 积极</option>
                  <option value="0">0 中性</option>
                  <option value="-">- 消极</option>
                </select>
              </div>
            </div>
          );
        })}
      </div>

      {/* Note */}
      <div
        className="p-4 rounded-xl text-sm leading-relaxed transition-all duration-300"
        style={{ backgroundColor: colors.sections[0].iconBg, color: colors.textSub }}
      >
        <strong>提示：</strong>请根据每个答案是否体现积极态度进行评价。建议在完成测试两周后再进行评价，以观察态度变化。
      </div>
    </div>
  );
};

// --- Main Component ---
const WhoWasITab: React.FC = () => {
  const [data, setData] = useState<WhoWasIData>(INITIAL_DATA);
  const [version, setVersion] = useState<number | null>(null);
  const [versions, setVersions] = useState<BeingVersionInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [showVersionDropdown, setShowVersionDropdown] = useState(false);
  const [showThemeDropdown, setShowThemeDropdown] = useState(false);

  // Tab State
  const [activeTab, setActiveTab] = useState<'who' | 'reframe' | 'review'>('who');

  const { theme, currentThemeId, setTheme } = useTheme();
  const colors = theme.colors;

  // Prevent StrictMode double fetch
  const hasFetched = useRef(false);

  // Load latest data
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

  // Load specific version
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

  // Save data
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

  // Create new version
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

  // Delete version
  const handleDeleteVersion = async (verToDelete: number) => {
    if (!window.confirm(`确定要删除版本 ${verToDelete} 吗？此操作无法撤销。`)) return;

    try {
      await beingApi.deleteTest('past', verToDelete);

      // If deleted current version, reload everything (which fetches latest)
      if (version === verToDelete) {
        await loadLatestData();
      } else {
        // Just refresh list
        const versionList = await beingApi.getVersions('past');
        setVersions(versionList.versions);
      }
    } catch (error) {
      console.error('[WhoWasITab] Delete version failed:', error);
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

  // Tab Switching Handler
  const handleTabChange = (tab: 'who' | 'reframe' | 'review') => {
    setActiveTab(tab);
  };

  // Judge Handler
  const handleJudge = (id: number, judge: '+' | '0' | '-') => {
    setData(prev => ({
      ...prev,
      whoWasIItems: prev.whoWasIItems.map(item =>
        item.id === id
          ? {
            ...item,
            judgeItems: [
              ...(item.judgeItems || []),
              {
                judge,
                reason: '',
                time: new Date().toISOString()
              }
            ]
          }
          : item
      )
    }));
  };

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
            <History size={22} strokeWidth={1.5} />
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
          回溯过往
        </h2>
        <p className="text-lg leading-relaxed transition-colors duration-300" style={{ color: colors.textSub }}>
          改变你对过去的态度
        </p>
      </div>

      {/* Single Column Layout Container */}
      <div className="max-w-2xl mx-auto mb-12">
        <div className="flex flex-col gap-8">
          {/* Top: Psychological Hint Block */}
          <div className="w-full">
            <div
              className="p-8 rounded-3xl relative overflow-hidden transition-all duration-300"
              style={{
                backgroundColor: colors.sections[0].iconBg,
                border: `1px solid ${colors.sections[0].iconColor}20`
              }}
            >
              <div className="absolute top-0 right-0 p-6 opacity-10 pointer-events-none transition-colors duration-300">
                <Quote size={100} style={{ color: colors.sections[0].iconColor }} />
              </div>

              <div className="relative z-10">
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2 transition-colors duration-300" style={{ color: colors.sections[0].iconColor }}>
                  <Sparkles size={20} />
                  心理提示
                </h3>
                {activeTab === 'who' ? (
                  <p className="text-base leading-relaxed text-justify transition-colors duration-300" style={{ color: colors.textMain }}>
                    <span className="font-semibold block mb-3 text-lg">
                      你不能改变你的过去，但你可以改变你对过去的态度。
                    </span>
                    在开始主动重构你的过去之前，请先完成这份 "我曾经是谁" 的测试。这份测试包括了同一个问题：我曾经是谁？但这个问题会被连续问 20 次。即使你不能回答所有的提问，也不用担心，但请务必花时间尝试这一练习。请列出 20 项最重要的可以描述你之前行事方式的答案。除了你自己之外，其他人不会看到你的答案，所以你也没有必要把自己描述得比真实情况更差或者更好。但请记得把答案留下来，因为在几周之后你需要重新回顾答案。
                  </p>
                ) : activeTab === 'reframe' ? (
                  <p className="text-base leading-relaxed text-justify transition-colors duration-300" style={{ color: colors.textMain }}>
                    在你完成 "我曾经是谁" 测试之后，请接着完成下一页的积极重构过去清单。你可以选择任何你想要的三件事，但你应该选择那些依然能让你联想起消极情绪，比如内疚、羞耻、被侮辱、伤心或者恐惧的事件。请记住，这些事情都已经过去了。它们并不能决定你的今天。而你有能力改变你的态度。请相信，重新解构你的过去，并不是对回忆中可能出现的其他人的不尊重。相反，这才是真正的尊重。重新建构你的过去，只不过是让你可以控制过去，而不是让过去控制你。
                  </p>
                ) : (
                  <p className="text-base leading-relaxed text-justify transition-colors duration-300" style={{ color: colors.textMain }}>
                    在你完成两周之后，请再把之前的答案拿出来。在两张 20 题的答案上，如果答案体现了对待过去的积极态度，请你在旁边写上 "+"，如果体现的态度是中性的，请写上 "0"，如果体现的是对待过去的消极态度，请标上 "-"。请分别数出两张列表上 "+" 号和 "-" 号的数目。在每一次答案的计算中，用 "+" 的出现次数减去 "-" 的出现次数。在两周之内，你的分数应该出现上升，变得更加积极。如果没有，也不用绝望。你的过去不是一夜之间发生的，所以改变通常也需要时间。当你结束一天的时候，请确信改变会发生，而且当你改变之后，你将会把自己的心态往积极的方向调整，进入更快乐的时间段。请记住，我们正在改变你生活中的大河的流向，而每一次微小的尝试如果假以时日都能带来显著的变化。而且无论你的得分如何，每天完成一份感恩清单都可能让你的心情变得更好，改善你的健康。
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Tab Switcher */}
          <div className="flex justify-center">
            <div
              className="p-1 rounded-2xl flex items-center relative"
              style={{ backgroundColor: colors.inputBg }}
            >
              <button
                onClick={() => handleTabChange('who')}
                className={`relative z-10 px-6 py-2.5 rounded-xl text-sm font-medium transition-all duration-300 flex items-center gap-2 ${activeTab === 'who' ? 'shadow-sm' : ''}`}
                style={{
                  color: activeTab === 'who' ? colors.textMain : colors.textMuted,
                  backgroundColor: activeTab === 'who' ? colors.cardBg : 'transparent'
                }}
              >
                <FileQuestion size={16} />
                我曾经是谁
              </button>
              <button
                onClick={() => handleTabChange('reframe')}
                className={`relative z-10 px-6 py-2.5 rounded-xl text-sm font-medium transition-all duration-300 flex items-center gap-2 ${activeTab === 'reframe' ? 'shadow-sm' : ''}`}
                style={{
                  color: activeTab === 'reframe' ? colors.textMain : colors.textMuted,
                  backgroundColor: activeTab === 'reframe' ? colors.cardBg : 'transparent'
                }}
              >
                <RotateCcw size={16} />
                积极重构
              </button>
              <button
                onClick={() => handleTabChange('review')}
                className={`relative z-10 px-6 py-2.5 rounded-xl text-sm font-medium transition-all duration-300 flex items-center gap-2 ${activeTab === 'review' ? 'shadow-sm' : ''}`}
                style={{
                  color: activeTab === 'review' ? colors.textMain : colors.textMuted,
                  backgroundColor: activeTab === 'review' ? colors.cardBg : 'transparent'
                }}
              >
                <Eye size={16} />
                审视过去
              </button>
            </div>
          </div>

          {/* Bottom: Tab Content */}
          <div className="w-full relative">
            {activeTab === 'who' ? (
              <div
                className="rounded-[2rem] p-8 md:p-10 relative overflow-hidden transition-all duration-300"
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

                <div className="relative z-10">
                  <QuestionBlock
                    title="我曾经是谁？"
                    subtitle="回忆过去的角色、状态"
                    icon={<FileQuestion size={20} strokeWidth={1.5} />}
                    sectionIndex={1}
                    items={data.whoWasIItems.map(item => ({ id: item.id, value: item.content }))}
                    placeholder="胆小、被成绩定义、害怕冲突..."
                    inputPrefix="我曾经..."
                    theme={theme}
                    onChange={handleWhoWasIChange}
                    onAdd={handleAddStatement}
                    onDelete={handleDeleteStatement}
                  />
                </div>
              </div>
            ) : activeTab === 'reframe' ? (
              <div
                className="rounded-[2rem] p-8 md:p-10 relative overflow-hidden transition-all duration-300"
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

                <div className="relative z-10">
                  <ReframingBlock
                    title="积极重构过去"
                    subtitle="寻找困难经历背后的礼物"
                    icon={<RotateCcw size={20} strokeWidth={1.5} />}
                    sectionIndex={0}
                    items={data.positivePastReframingItems}
                    theme={theme}
                    onChange={handleReframeChange}
                    onAdd={handleAddReframe}
                    onDelete={handleDeleteReframe}
                  />
                </div>
              </div>
            ) : (
              <div
                className="rounded-[2rem] p-8 md:p-10 relative overflow-hidden transition-all duration-300"
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

                <div className="relative z-10">
                  <ReviewBlock
                    items={data.whoWasIItems}
                    theme={theme}
                    onJudge={handleJudge}
                  />
                </div>
              </div>
            )}
          </div>
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
              <span>保存回忆</span>
            </>
          )}
        </button>
      </div>

    </div>
  );
};

export default WhoWasITab;
