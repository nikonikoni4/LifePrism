/**
 * FieldRoleModal — 字段角色配置弹窗
 * 为每个字段选择展示角色（auto/title/main/chip/hidden）
 */
import React from 'react';
import { X } from 'lucide-react';
import type { FieldDefinition } from '../types';

interface FieldRoleModalProps {
  fields: FieldDefinition[];
  onClose: () => void;
  onFieldRoleChange: (fieldKey: string, displayRole: string) => void;
}

const ROLE_OPTIONS: { value: string; label: string; desc: string }[] = [
  { value: 'auto', label: '自动', desc: '由 L1 引擎自动推断' },
  { value: 'title', label: '标题', desc: '作为卡片标题显示' },
  { value: 'main', label: '正文', desc: '作为主要正文内容显示' },
  { value: 'chip', label: '标签', desc: '作为彩色标签显示' },
  { value: 'hidden', label: '隐藏', desc: '不显示在卡片上' },
];

export const FieldRoleModal: React.FC<FieldRoleModalProps> = ({
  fields,
  onClose,
  onFieldRoleChange,
}) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-900">字段角色配置</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            <X size={18} />
          </button>
        </div>

        {/* 字段列表 */}
        <div className="px-5 py-4 space-y-3 max-h-[60vh] overflow-y-auto">
          {fields.map(field => (
            <div key={field.field_key} className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-700">{field.field_name}</span>
                <span className="text-xs text-slate-400 font-mono">{field.field_key}</span>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap">
                {ROLE_OPTIONS.map(opt => {
                  const isActive = (field.display_role || 'auto') === opt.value;
                  return (
                    <button
                      key={opt.value}
                      onClick={() => onFieldRoleChange(field.field_key, opt.value)}
                      className={`
                        px-2.5 py-1 rounded-lg text-xs font-medium transition-all
                        ${isActive
                          ? 'bg-cyan-500 text-white'
                          : 'bg-slate-50 text-slate-500 hover:bg-slate-100'
                        }
                      `}
                      title={opt.desc}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* 底部 */}
        <div className="px-5 py-3 border-t border-slate-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg text-sm font-medium text-white bg-slate-700 hover:bg-slate-800"
          >
            完成
          </button>
        </div>
      </div>
    </div>
  );
};
