import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface ValueCardProps {
  valueId: string;
  content: string;
  isLeft: boolean;
  isPositive: boolean;
  isFocused: boolean;
  isEditing: boolean;
  onEdit: () => void;
  onSave: (valueId: string, isPositive: boolean, newContent: string) => Promise<void>;
}

export const ValueCard: React.FC<ValueCardProps> = ({
  valueId,
  content,
  isLeft,
  isPositive,
  isFocused,
  isEditing,
  onEdit,
  onSave,
}) => {
  const [editContent, setEditContent] = useState(content);
  const [isSaving, setIsSaving] = useState(false);

  // 当 content prop 变化时同步 editContent（切换卡片时）
  useEffect(() => {
    if (!isEditing) {
      setEditContent(content);
    }
  }, [content, isEditing]);

  const handleSave = async () => {
    if (editContent === content) return;
    setIsSaving(true);
    try {
      await onSave(valueId, isPositive, editContent);
    } catch (error) {
      console.error('保存失败:', error);
      setEditContent(content); // 回滚
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <motion.div
      className={[
        'relative p-8 rounded-[2rem] border shadow-sm',
        'bg-white/60 backdrop-blur-xl border-white/50',
        'transition-colors duration-500 cursor-pointer',
        isFocused ? 'opacity-100' : 'opacity-40',
        isEditing ? 'border-indigo-400 shadow-lg' : '',
        isSaving ? 'opacity-60 pointer-events-none' : '',
      ].join(' ')}
      animate={{ scale: isFocused ? 1 : 0.85 }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
      onClick={isFocused && !isEditing ? onEdit : undefined}
      style={{
        writingMode: 'vertical-rl',
        direction: isLeft ? 'ltr' : 'rtl',
        minHeight: '400px',
        width: '180px',
      }}
    >
      {isEditing ? (
        <textarea
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          onBlur={handleSave}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setEditContent(content);
              onEdit(); // 退出编辑态
            }
          }}
          className="w-full h-full bg-transparent outline-none text-lg leading-loose resize-none"
          style={{
            writingMode: 'vertical-rl',
            direction: isLeft ? 'ltr' : 'rtl',
            fontFamily: "'Noto Serif SC', serif",
          }}
          autoFocus
        />
      ) : (
        <p
          className="text-lg leading-loose tracking-wide text-[#2C3835]"
          style={{ fontFamily: "'Noto Serif SC', serif" }}
        >
          {content || '（空）'}
        </p>
      )}
      {isSaving && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/50 rounded-[2rem]">
          <span className="text-sm text-gray-600">保存中...</span>
        </div>
      )}
    </motion.div>
  );
};
