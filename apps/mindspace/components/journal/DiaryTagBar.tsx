/**
 * DiaryTagBar - 日期下方标签栏
 * 心情 pill 标签组 + 重要程度 pill 标签组 + 自定义 tag + 添加按钮
 */
import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, X } from 'lucide-react';
import { MOOD_OPTIONS, IMPORTANCE_OPTIONS } from './diaryConstants';
import type { MoodLevel, ImportanceLevel } from './diaryTypes';

interface DiaryTagBarProps {
  mood: MoodLevel | null;
  importance: ImportanceLevel | null;
  customTags: string[];
  onMoodChange: (mood: MoodLevel) => void;
  onImportanceChange: (importance: ImportanceLevel) => void;
  onCustomTagsChange: (tags: string[]) => void;
}

const DiaryTagBar: React.FC<DiaryTagBarProps> = ({
  mood, importance, customTags,
  onMoodChange, onImportanceChange, onCustomTagsChange,
}) => {
  const [isAddingTag, setIsAddingTag] = useState(false);
  const [newTag, setNewTag] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isAddingTag && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isAddingTag]);

  const handleAddTag = () => {
    const tag = newTag.trim();
    if (tag && !customTags.includes(tag)) {
      onCustomTagsChange([...customTags, tag]);
    }
    setNewTag('');
    setIsAddingTag(false);
  };

  const handleRemoveTag = (tag: string) => {
    onCustomTagsChange(customTags.filter(t => t !== tag));
  };

  /* 渲染单个 pill 按钮 */
  const renderPill = (
    o: { value: string; label: string; color: string },
    selected: boolean,
    onClick: () => void,
  ) => (
    <button
      key={o.value}
      onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-[11px] tracking-widest transition-all duration-300 focus:outline-none ${
        selected ? 'scale-[1.03]' : 'diary-pill'
      }`}
      style={selected ? {
        background: `${o.color}1A`,
        border: `1px solid ${o.color}35`,
        color: '#1f2937',
        boxShadow: `0 1px 6px ${o.color}15, inset 0 1px 0 rgba(255,255,255,0.4)`,
      } : {
        background: 'transparent',
        border: `1px solid ${o.color}25`,
        color: 'rgba(31,41,55,0.6)',
        boxShadow: 'none',
        '--pill-hover-bg': `${o.color}0A`,
        '--pill-hover-border': `${o.color}40`,
        '--pill-hover-color': '#1f2937',
      } as React.CSSProperties}
    >
      {o.label}
    </button>
  );

  return (
    <div className="flex flex-col gap-3">
      {/* 心情标签组 */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] tracking-[0.2em] text-gray-400 shrink-0">心情</span>
        <div className="flex flex-wrap gap-1.5">
          {MOOD_OPTIONS.map(o =>
            renderPill(o, mood === o.value, () => onMoodChange(o.value))
          )}
        </div>
      </div>

      {/* 重要程度标签组 */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] tracking-[0.2em] text-gray-400 shrink-0">重要</span>
        <div className="flex flex-wrap gap-1.5">
          {IMPORTANCE_OPTIONS.map(o =>
            renderPill(o, importance === o.value, () => onImportanceChange(o.value))
          )}
        </div>
      </div>

      {/* 自定义标签行 */}
      <div className="flex flex-wrap items-center gap-1.5">
        <AnimatePresence>
          {customTags.map(tag => (
            <motion.span
              key={tag}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="group relative px-4 py-1.5 rounded-full text-[11px] tracking-wider"
              style={{
                background: 'transparent',
                border: '1px solid rgba(154,142,130,0.25)',
                color: 'rgba(154,142,130,0.7)',
                boxShadow: 'none',
              }}
            >
              {tag}
              <button
                onClick={() => handleRemoveTag(tag)}
                className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-[#c4b5a4] text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[#a89888]"
              >
                <X size={8} />
              </button>
            </motion.span>
          ))}
        </AnimatePresence>

        {isAddingTag ? (
          <motion.div
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: 'auto' }}
            className="flex items-center"
          >
            <input
              ref={inputRef}
              value={newTag}
              onChange={e => setNewTag(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') handleAddTag();
                if (e.key === 'Escape') { setIsAddingTag(false); setNewTag(''); }
              }}
              onBlur={handleAddTag}
              placeholder="标签名"
              maxLength={10}
              className="w-20 px-3 py-1.5 rounded-full text-[11px] outline-none transition-colors"
              style={{
                background: 'transparent',
                border: '1px solid rgba(154,142,130,0.25)',
                color: '#7a6e62',
                boxShadow: 'none',
              }}
            />
          </motion.div>
        ) : (
          <button
            onClick={() => setIsAddingTag(true)}
            className="px-3 py-1.5 rounded-full text-[11px] transition-all flex items-center gap-1 hover:brightness-95"
            style={{
              background: 'transparent',
              border: '1px solid rgba(181,169,157,0.25)',
              color: 'rgba(181,169,157,0.7)',
            }}
          >
            <Plus size={10} /> 标签
          </button>
        )}
      </div>
    </div>
  );
};

export default DiaryTagBar;
