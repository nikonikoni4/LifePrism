/**
 * EntryCard — 自适应卡片组件
 * 根据字段内容自动选择布局（note/compact/tight）
 * 支持模板预设（clean/paper/minimal/bold/metric）切换 CSS 类名
 * 左侧 accent 竖条 + 头部时间戳 + 主体 + chips 标签区
 */
import React from 'react';
import { Trash2, Clock } from 'lucide-react';
import { analyzeCardLayout } from '../utils/cardLayoutEngine';
import type { Overrides } from '../utils/cardLayoutEngine';
import { getFieldColor } from '../utils/fieldColors';
import { getTemplatePreset } from '../utils/templatePresets';
import type { FieldDefinition, CustomRecordEntryItem } from '../types';

interface EntryCardProps {
  fields: FieldDefinition[];
  entry: CustomRecordEntryItem;
  templateId?: string;
  onDelete?: (entryId: string) => void;
}

const LAYOUT_LABELS: Record<string, string> = {
  note: '笔记',
  compact: '条目',
  tight: '速记',
};

const formatDate = (dateStr: string): string => {
  if (!dateStr) return '';
  const dt = dateStr.replace('T', ' ');
  return dt.slice(0, 16);
};

export const EntryCard: React.FC<EntryCardProps> = ({
  fields,
  entry,
  templateId = 'clean',
  onDelete,
}) => {
  const data: Record<string, string> = {};
  for (const f of fields) {
    const val = entry[f.field_key];
    if (val != null) data[f.field_key] = String(val);
  }

  // 构建 overrides：字段的 display_role 覆盖
  const overrides: Overrides = {};
  for (const f of fields) {
    if (f.display_role && f.display_role !== 'auto') {
      overrides[f.field_key] = f.display_role as Overrides[string];
    }
  }

  const { layout, title, main, chips } = analyzeCardLayout(fields, data, overrides);
  const tpl = getTemplatePreset(templateId);
  const layoutLabel = LAYOUT_LABELS[layout] || layout;

  return (
    <div className={`group relative ${tpl.cardClass} hover:shadow-md transition-all overflow-hidden`}>
      {/* 左侧 accent 竖条 */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${tpl.accentBarClass}`} />

      <div className="pl-4 pr-4 py-3.5">
        {/* 头部：时间戳 + 布局标签 + 删除按钮 */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Clock size={12} className="opacity-30" />
            <span className={`text-[11px] opacity-50 font-mono`}>
              {formatDate(entry.created_at)}
            </span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${tpl.chipClass}`}>
              {layoutLabel}
            </span>
          </div>
          {onDelete && (
            <button
              onClick={() => onDelete(entry.id)}
              className="p-1 rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>

        {/* 主体区域 — 根据 layout 模式渲染 */}
        {layout === 'note' && (
          <div className="space-y-2">
            {title && (
              <h3 className={`${tpl.titleClass} leading-snug`}>{title}</h3>
            )}
            {main && (
              <p className={`${tpl.mainClass} whitespace-pre-wrap`}>{main}</p>
            )}
            {chips.length > 0 && (
              <div className="flex gap-1.5 flex-wrap pt-1">
                {chips.map(chip => {
                  const color = getFieldColor(chip.field_key);
                  return (
                    <span
                      key={chip.field_key}
                      className={`${tpl.chipClass} ${color.bg} ${color.text} border ${color.border}`}
                    >
                      {chip.value}
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {layout === 'compact' && (
          <div className="space-y-1.5">
            {title && (
              <h3 className={`${tpl.titleClass} leading-snug`}>{title}</h3>
            )}
            {chips.map(chip => {
              const color = getFieldColor(chip.field_key);
              return (
                <div key={chip.field_key} className="flex items-center gap-2 text-xs">
                  <span className="opacity-40 min-w-[60px]">{chip.field_name}</span>
                  <span className={`font-medium ${color.text}`}>{chip.value || '—'}</span>
                </div>
              );
            })}
          </div>
        )}

        {layout === 'tight' && (
          <div className="flex gap-1.5 flex-wrap">
            {chips.map(chip => {
              const color = getFieldColor(chip.field_key);
              return (
                <span
                  key={chip.field_key}
                  className={`text-xs px-2.5 py-1 rounded-lg ${tpl.chipClass} ${color.bg} ${color.text} border ${color.border} font-medium`}
                >
                  {chip.value || '—'}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
