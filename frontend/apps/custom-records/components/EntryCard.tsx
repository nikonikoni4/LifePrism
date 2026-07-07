/**
 * EntryCard — 自适应卡片组件
 * 根据字段内容自动选择布局（note/compact/tight）
 * 左侧 accent 竖条 + 头部时间戳 + 主体 + chips 标签区
 */
import React from 'react';
import { Trash2, Clock } from 'lucide-react';
import { analyzeCardLayout } from '../utils/cardLayoutEngine';
import { getFieldColor } from '../utils/fieldColors';
import type { FieldDefinition, CustomRecordEntryItem } from '../types';

interface EntryCardProps {
  fields: FieldDefinition[];
  entry: CustomRecordEntryItem;
  accentColor?: string;
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
  accentColor = 'cyan',
  onDelete,
}) => {
  const data: Record<string, string> = {};
  for (const f of fields) {
    const val = entry[f.field_key];
    if (val != null) data[f.field_key] = String(val);
  }

  const { layout, title, main, chips } = analyzeCardLayout(fields, data);
  const layoutLabel = LAYOUT_LABELS[layout] || layout;
  const accentBg = `bg-${accentColor}-500`;
  const accentText = `text-${accentColor}-600`;
  const accentBgLight = `bg-${accentColor}-50`;

  return (
    <div className="group relative bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-all overflow-hidden">
      {/* 左侧 accent 竖条 */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${accentBg}`} />

      <div className="pl-4 pr-4 py-3.5">
        {/* 头部：时间戳 + 布局标签 + 删除按钮 */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Clock size={12} className="text-slate-300" />
            <span className="text-[11px] text-slate-400 font-mono">
              {formatDate(entry.created_at)}
            </span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${accentBgLight} ${accentText} font-medium`}>
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
              <h3 className="text-sm font-semibold text-slate-900 leading-snug">{title}</h3>
            )}
            {main && (
              <p className="text-[13px] text-slate-600 leading-relaxed whitespace-pre-wrap">{main}</p>
            )}
            {chips.length > 0 && (
              <div className="flex gap-1.5 flex-wrap pt-1">
                {chips.map(chip => {
                  const color = getFieldColor(chip.field_key);
                  return (
                    <span
                      key={chip.field_key}
                      className={`text-[10px] px-2 py-0.5 rounded-md ${color.bg} ${color.text} border ${color.border}`}
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
              <h3 className="text-sm font-semibold text-slate-900 leading-snug">{title}</h3>
            )}
            {chips.map(chip => {
              const color = getFieldColor(chip.field_key);
              return (
                <div key={chip.field_key} className="flex items-center gap-2 text-xs">
                  <span className="text-slate-400 min-w-[60px]">{chip.field_name}</span>
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
                  className={`text-xs px-2.5 py-1 rounded-lg ${color.bg} ${color.text} border ${color.border} font-medium`}
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
