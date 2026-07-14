/**
 * 新建类型视图 — 动态字段表单
 */
import React, { useState } from 'react';
import { ArrowLeft, Plus, Trash2, X, AlertTriangle } from 'lucide-react';
import { CustomRecordsAPI } from '../api';
import type { FieldDefinition } from '../types';

interface CreateTypeViewProps {
  onBack: () => void;
  onSuccess: () => void;
}

interface FieldRow extends FieldDefinition {
  _id: string;
}

let fieldCounter = 0;
const makeFieldRow = (): FieldRow => ({
  _id: `field_${++fieldCounter}`,
  field_name: '',
  field_key: '',
  field_type: 'text',
});

export const CreateTypeView: React.FC<CreateTypeViewProps> = ({ onBack, onSuccess }) => {
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [fields, setFields] = useState<FieldRow[]>([makeFieldRow()]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const addField = () => setFields([...fields, makeFieldRow()]);
  const removeField = (id: string) => {
    if (fields.length > 1) setFields(fields.filter(f => f._id !== id));
  };
  const updateField = (id: string, key: keyof FieldRow, value: string) => {
    setFields(fields.map(f => f._id === id ? { ...f, [key]: value } : f));
  };

  const validate = (): string | null => {
    if (!name.trim()) return '请输入类型名称';
    if (!slug.trim()) return '请输入标识符 (slug)';
    if (!/^[a-z][a-z0-9_]*$/.test(slug)) return 'slug 必须以小写字母开头，只能包含小写字母、数字和下划线';
    if (fields.length === 0) return '至少需要 1 个字段';
    for (const f of fields) {
      if (!f.field_name.trim()) return '每个字段都需要显示名';
      if (!f.field_key.trim()) return '每个字段都需要标识符';
      if (!/^[a-z][a-z0-9_]*$/.test(f.field_key)) return `字段标识符「${f.field_key}」格式错误，必须以小写字母开头`;
    }
    const keys = fields.map(f => f.field_key);
    if (new Set(keys).size !== keys.length) return '字段标识符不能重复';
    return null;
  };

  const handleSubmit = async () => {
    const err = validate();
    if (err) { setError(err); return; }

    try {
      setSubmitting(true);
      setError('');
      await CustomRecordsAPI.createType({
        name: name.trim(),
        slug: slug.trim(),
        fields: fields.map(({ _id, ...rest }) => rest),
      });
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="animate-[fadeIn_0.3s_ease-out]">
      <button onClick={onBack} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-6">
        <ArrowLeft size={16} />返回
      </button>

      <h1 className="text-2xl font-bold text-slate-900 mb-6">新建记录类型</h1>

      {error && (
        <div className="mb-4 p-4 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm flex items-center gap-2">
          <AlertTriangle size={16} />{error}
        </div>
      )}

      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 space-y-5">
        {/* 名称 + Slug */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">类型名称</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="如：阅读记录"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-400"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">标识符 (slug)</label>
            <input
              type="text"
              value={slug}
              onChange={e => setSlug(e.target.value)}
              placeholder="如：reading"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-400"
            />
            <p className="text-[11px] text-slate-400 mt-1">小写字母开头，仅含小写字母/数字/下划线</p>
          </div>
        </div>

        {/* 字段定义 */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="text-sm font-medium text-slate-700">字段定义</label>
            <button onClick={addField} className="flex items-center gap-1 text-xs font-medium text-cyan-600 hover:text-cyan-700">
              <Plus size={14} />添加字段
            </button>
          </div>
          <div className="space-y-2">
            {fields.map((field) => (
              <div key={field._id} className="flex items-center gap-2 group">
                <input
                  type="text"
                  value={field.field_name}
                  onChange={e => updateField(field._id, 'field_name', e.target.value)}
                  placeholder="显示名（如：书名）"
                  className="flex-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-400"
                />
                <input
                  type="text"
                  value={field.field_key}
                  onChange={e => updateField(field._id, 'field_key', e.target.value)}
                  placeholder="标识符（如：book_title）"
                  className="flex-1 px-3 py-2 rounded-lg border border-slate-200 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-400"
                />
                <select
                  value={field.field_type}
                  onChange={e => updateField(field._id, 'field_type', e.target.value)}
                  className="px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-500 bg-slate-50 focus:outline-none"
                >
                  <option value="text">文本</option>
                  <option value="integer">整数</option>
                  <option value="float">浮点数</option>
                </select>
                <button
                  onClick={() => removeField(field._id)}
                  disabled={fields.length === 1}
                  className="p-2 rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-2 mt-5">
        <button onClick={onBack} className="px-4 py-2.5 rounded-xl text-sm text-slate-600 hover:bg-slate-100">
          取消
        </button>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="px-5 py-2.5 rounded-xl text-sm font-medium text-white bg-gradient-to-r from-cyan-500 to-teal-500 shadow-md shadow-cyan-500/20 hover:shadow-lg transition-shadow disabled:opacity-50"
        >
          {submitting ? '创建中...' : '创建类型'}
        </button>
      </div>
    </div>
  );
};
