import React, { useState, useRef, useEffect } from 'react';
import { Pencil } from 'lucide-react';

interface InlineEditableTextareaProps {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  icon?: React.ReactNode;
  placeholder?: string;
  className?: string;
  rows?: number;
}

const InlineEditableTextarea: React.FC<InlineEditableTextareaProps> = ({
  value,
  onChange,
  label,
  icon,
  placeholder = '点击编辑...',
  className = '',
  rows = 3,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setEditValue(value);
  }, [value]);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.select();
    }
  }, [isEditing]);

  const handleSave = () => {
    if (editValue !== value) {
      onChange(editValue);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setEditValue(value);
      setIsEditing(false);
    }
    // Allow Enter for newlines, Ctrl+Enter or Cmd+Enter to save
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSave();
    }
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditing(true);
  };

  return (
    <div className={`space-y-2 ${className}`}>
      {label && (
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            {label}
          </span>
        </div>
      )}

      {isEditing ? (
        <div className="relative">
          <textarea
            ref={textareaRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={handleSave}
            onKeyDown={handleKeyDown}
            onClick={(e) => e.stopPropagation()}
            placeholder={placeholder}
            rows={rows}
            className="w-full bg-white border border-indigo-300 rounded-xl p-3 text-sm text-slate-700 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all resize-none leading-relaxed"
          />
          <div className="absolute bottom-2 right-2 text-[10px] text-slate-400">
            Ctrl+Enter 保存
          </div>
        </div>
      ) : (
        <div
          onClick={handleClick}
          className="group/textarea relative bg-slate-50 border border-slate-200 rounded-xl p-3 min-h-[60px] cursor-pointer hover:border-slate-300 hover:bg-slate-100/50 transition-all"
        >
          <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
            {value || <span className="text-slate-300 italic">{placeholder}</span>}
          </p>
          <Pencil
            size={14}
            className="absolute top-3 right-3 text-slate-300 opacity-0 group-hover/textarea:opacity-100 transition-opacity"
          />
        </div>
      )}
    </div>
  );
};

export default InlineEditableTextarea;
