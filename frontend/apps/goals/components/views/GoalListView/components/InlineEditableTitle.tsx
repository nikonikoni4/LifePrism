import React, { useState, useRef, useEffect } from 'react';
import { Pencil } from 'lucide-react';

interface InlineEditableTitleProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  placeholder?: string;
  isCompleted?: boolean;
}

const InlineEditableTitle: React.FC<InlineEditableTitleProps> = ({
  value,
  onChange,
  className = '',
  placeholder = '输入标题...',
  isCompleted = false,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setEditValue(value);
  }, [value]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleSave = () => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== value) {
      onChange(trimmed);
    } else {
      setEditValue(value);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      setEditValue(value);
      setIsEditing(false);
    }
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isCompleted) {
      setIsEditing(true);
    }
  };

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        type="text"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        onClick={(e) => e.stopPropagation()}
        placeholder={placeholder}
        className={`w-full bg-transparent border-b-2 border-indigo-500 outline-none ${className}`}
      />
    );
  }

  return (
    <div
      onClick={handleClick}
      className={`group/title flex items-center gap-2 ${!isCompleted ? 'cursor-pointer' : ''}`}
    >
      <span className={`${className} ${isCompleted ? 'line-through text-slate-400' : ''}`}>
        {value || placeholder}
      </span>
      {!isCompleted && (
        <Pencil
          size={14}
          className="text-slate-300 opacity-0 group-hover/title:opacity-100 transition-opacity"
        />
      )}
    </div>
  );
};

export default InlineEditableTitle;
