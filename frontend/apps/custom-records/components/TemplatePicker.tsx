/**
 * TemplatePicker — 模板选择器
 * 5 套模板并排展示，点击切换，带 debounce 自动保存
 */
import React, { useState, useEffect } from 'react';
import { Check } from 'lucide-react';
import { TEMPLATE_PRESETS } from '../utils/templatePresets';

interface TemplatePickerProps {
  currentTemplate: string;
  onTemplateChange: (templateId: string) => void;
}

export const TemplatePicker: React.FC<TemplatePickerProps> = ({
  currentTemplate,
  onTemplateChange,
}) => {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {TEMPLATE_PRESETS.map(tpl => {
        const isActive = currentTemplate === tpl.id;
        return (
          <button
            key={tpl.id}
            onClick={() => onTemplateChange(tpl.id)}
            className={`
              relative px-3 py-2 rounded-xl text-sm font-medium transition-all
              ${isActive
                ? 'ring-2 ring-cyan-500 ring-offset-1'
                : 'ring-1 ring-slate-200 hover:ring-slate-300'
              }
              ${tpl.cardClass}
            `}
            title={tpl.description}
          >
            <span className={tpl.titleClass}>{tpl.name}</span>
            {isActive && (
              <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-cyan-500 flex items-center justify-center">
                <Check size={10} className="text-white" />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
