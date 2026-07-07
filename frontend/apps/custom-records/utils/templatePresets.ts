/**
 * L3 模板预设系统
 * 5 套视觉模板：clean / paper / minimal / bold / metric
 * 每套模板定义卡片各部位的 CSS 类名
 */

export interface TemplatePreset {
  id: string;
  name: string;
  description: string;
  cardClass: string;
  titleClass: string;
  mainClass: string;
  chipClass: string;
  accentBarClass: string;
}

export const TEMPLATE_PRESETS: TemplatePreset[] = [
  {
    id: 'clean',
    name: '简洁',
    description: '干净的白底卡片，适合大多数场景',
    cardClass: 'bg-white rounded-2xl border border-slate-100 shadow-sm',
    titleClass: 'text-sm font-semibold text-slate-900',
    mainClass: 'text-[13px] text-slate-600 leading-relaxed',
    chipClass: 'text-[10px] px-2 py-0.5 rounded-md',
    accentBarClass: 'bg-cyan-500',
  },
  {
    id: 'paper',
    name: '纸张',
    description: '暖色调纸张质感，适合笔记和日记',
    cardClass: 'bg-amber-50/50 rounded-2xl border border-amber-100 shadow-sm',
    titleClass: 'text-sm font-semibold text-amber-900',
    mainClass: 'text-[13px] text-amber-800 leading-relaxed',
    chipClass: 'text-[10px] px-2 py-0.5 rounded-md bg-amber-100 text-amber-700',
    accentBarClass: 'bg-amber-500',
  },
  {
    id: 'minimal',
    name: '极简',
    description: '无边框纯文字，极致克制',
    cardClass: 'bg-transparent',
    titleClass: 'text-sm font-medium text-slate-800',
    mainClass: 'text-[13px] text-slate-500 leading-relaxed',
    chipClass: 'text-[10px] px-1.5 py-0.5 text-slate-400',
    accentBarClass: 'bg-slate-300',
  },
  {
    id: 'bold',
    name: '粗体',
    description: '强对比大字标题，适合展示型数据',
    cardClass: 'bg-white rounded-2xl border-2 border-slate-800 shadow-md',
    titleClass: 'text-base font-bold text-slate-900',
    mainClass: 'text-sm text-slate-700 leading-relaxed',
    chipClass: 'text-xs px-2.5 py-1 rounded-lg font-bold',
    accentBarClass: 'bg-slate-800',
  },
  {
    id: 'metric',
    name: '数据',
    description: '等宽字体，适合数值和指标',
    cardClass: 'bg-slate-900 rounded-2xl border border-slate-700 shadow-lg',
    titleClass: 'text-sm font-mono font-semibold text-cyan-400',
    mainClass: 'text-[13px] font-mono text-slate-300 leading-relaxed',
    chipClass: 'text-[10px] font-mono px-2 py-0.5 rounded-md bg-slate-800 text-cyan-400',
    accentBarClass: 'bg-cyan-400',
  },
];

export const TEMPLATE_IDS: string[] = TEMPLATE_PRESETS.map(t => t.id);

const DEFAULT_PRESET = TEMPLATE_PRESETS[0];

/**
 * 根据 templateId 获取模板预设
 * 未知 id 或 undefined 时 fallback 到 clean
 */
export const getTemplatePreset = (templateId: string | undefined): TemplatePreset => {
  if (!templateId) return DEFAULT_PRESET;
  return TEMPLATE_PRESETS.find(t => t.id === templateId) ?? DEFAULT_PRESET;
};
