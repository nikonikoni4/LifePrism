/**
 * EntryForm — 自定义记录添加/编辑表单 Modal
 *
 * 双模式：
 * - create: 添加新记录（提交时忽略 event_time，沿用 P1 行为：后端使用当前 UTC 时间）
 * - edit:   编辑已存在记录（Slice 2 扩展，支持 event_time 修改和字段 PATCH）
 *
 * Props 类型按完整双模式定义，为 Slice 2 edit 模式扩展预留接口。
 *
 * 三态语义对齐项目标准（参考 backend-api-rules.md）：
 * - 字段未传 → 不修改
 * - 字段传 null → 清空（写入 NULL）
 * - 字段传值 → 更新为新值
 * Slice 1 仅实现 create 模式（buildCreatePayload：留空字段不放入 data dict）。
 */
import React, { useState } from 'react';
import { X, AlertTriangle, Clock } from 'lucide-react';
import { CustomRecordsAPI } from '../api';
import { buildCreatePayload, buildUpdatePayload, isoToDatetimeLocal, isLongTextField } from '../utils/entryFormPayload';
import type { CustomRecordTypeItem, CustomRecordEntryItem } from '../types';

interface EntryFormProps {
  mode: 'create' | 'edit';
  type: CustomRecordTypeItem;
  /** edit 模式必填，create 模式不传 */
  entry?: CustomRecordEntryItem;
  onClose: () => void;
  onSuccess: () => void;
}

export const EntryForm: React.FC<EntryFormProps> = ({
  mode,
  type,
  entry,
  onClose,
  onSuccess,
}) => {
  // 表单初始值
  const buildInitialFormData = (): Record<string, string> => {
    const data: Record<string, string> = {};
    for (const f of type.fields) {
      if (mode === 'edit' && entry) {
        const v = entry[f.field_key];
        data[f.field_key] = v != null ? String(v) : '';
      } else {
        data[f.field_key] = '';
      }
    }
    return data;
  };

  // edit 模式预填 event_time（转 datetime-local 本地格式）；create 模式为空
  const buildInitialEventTime = (): string => {
    if (mode === 'edit' && entry?.event_time) {
      return isoToDatetimeLocal(entry.event_time);
    }
    return '';
  };

  const [formData, setFormData] = useState<Record<string, string>>(buildInitialFormData);
  const [eventTime, setEventTime] = useState<string>(buildInitialEventTime);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // 字段值更新
  const updateField = (fieldKey: string, value: string) => {
    setFormData(prev => ({ ...prev, [fieldKey]: value }));
  };

  // 提交逻辑（create + edit 双模式）
  const handleSubmit = async () => {
    try {
      setSubmitting(true);
      setError('');

      if (mode === 'create') {
        // create 模式：留空字段不放入 data dict；忽略 event_time（沿用 P1 行为）
        const data = buildCreatePayload(formData, type.fields);
        await CustomRecordsAPI.createEntry(type.id, { data });
      } else {
        // edit 模式必填校验：event_time 不允许清空（后端必填字段）
        if (!entry) {
          throw new Error('edit 模式缺少 entry 参数');
        }
        if (!eventTime) {
          throw new Error('事件时间不能为空');
        }
        // edit 模式：diff 后仅传变化字段（未变化=不修改，清空=null，改值=新值）
        const payload = buildUpdatePayload(formData, type.fields, entry, eventTime);
        await CustomRecordsAPI.updateEntry(type.id, entry.id, payload);
      }

      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  const title = mode === 'create' ? `添加记录 · ${type.name}` : `编辑记录 · ${type.name}`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            <X size={18} />
          </button>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="mx-5 mt-4 p-3 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm flex items-center gap-2">
            <AlertTriangle size={14} />
            {error}
          </div>
        )}

        {/* 表单主体 */}
        <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          {/* 事件时间（create 模式不传给后端，仅 UI 统一；edit 模式必填） */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5 flex items-center gap-1.5">
              <Clock size={12} className="text-slate-400" />
              事件时间
              {mode === 'create' ? (
                <span className="text-[10px] text-slate-400">(可选，create 不生效)</span>
              ) : (
                <span className="text-[10px] text-red-400">*</span>
              )}
            </label>
            <input
              type="datetime-local"
              value={eventTime}
              onChange={e => setEventTime(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-400"
            />
          </div>

          {/* 动态字段列表 */}
          {type.fields.map(f => {
            const value = formData[f.field_key] ?? '';
            const labelText = f.field_name;
            return (
              <div key={f.field_key}>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  {labelText}
                </label>
                {f.field_type === 'text' && isLongTextField(f.field_key) ? (
                  <textarea
                    rows={3}
                    value={value}
                    onChange={e => updateField(f.field_key, e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-400 resize-none"
                  />
                ) : (
                  <input
                    type={f.field_type === 'text' ? 'text' : 'number'}
                    step={f.field_type === 'integer' ? '1' : f.field_type === 'float' ? 'any' : undefined}
                    value={value}
                    onChange={e => updateField(f.field_key, e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-400"
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* 底部按钮 */}
        <div className="px-5 py-3 border-t border-slate-100 flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-1.5 rounded-lg text-sm font-medium text-slate-500 hover:bg-slate-100"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="px-4 py-1.5 rounded-lg text-sm font-medium text-white bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50"
          >
            {submitting ? '提交中...' : mode === 'create' ? '添加' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
};
