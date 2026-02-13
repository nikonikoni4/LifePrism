/**
 * DiaryTagBar - 日期下方标签栏
 * 心情 tag + 重要程度 tag + 自定义 tag + 添加按钮
 */
import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, X } from 'lucide-react';
import { MOOD_OPTIONS, IMPORTANCE_OPTIONS, getMoodOption, getImportanceOption } from './diaryConstants';
import type { MoodLevel, ImportanceLevel } from './diaryTypes';
import SliderModal from './SliderModal';

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
  const [showMoodModal, setShowMoodModal] = useState(false);
  const [showImportanceModal, setShowImportanceModal] = useState(false);
  const [isAddingTag, setIsAddingTag] = useState(false);
  const [newTag, setNewTag] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  // 首次选择时连续弹窗
  const [pendingImportance, setPendingImportance] = useState(false);

  useEffect(() => {
    if (isAddingTag && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isAddingTag]);

  const handleMoodClick = () => {
    if (!mood && !importance) {
      setPendingImportance(true);
    }
    setShowMoodModal(true);
  };

  const handleMoodConfirm = (value: MoodLevel) => {
    onMoodChange(value);
    setShowMoodModal(false);
    if (pendingImportance) {
      setTimeout(() => setShowImportanceModal(true), 300);
      setPendingImportance(false);
    }
  };

  const handleImportanceConfirm = (value: ImportanceLevel) => {
    onImportanceChange(value);
    setShowImportanceModal(false);
  };

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

  const moodOpt = mood ? getMoodOption(mood) : null;
  const impOpt = importance ? getImportanceOption(importance) : null;

  return (
    <>
      <div className="flex flex-wrap items-center gap-2.5">
        {/* 心情 tag */}
        <button
          onClick={handleMoodClick}
          className={`px-4 py-1.5 rounded-full text-[11px] tracking-wider transition-all duration-300 ${
            moodOpt
              ? 'border shadow-sm hover:shadow-md hover:scale-105'
              : 'border border-dashed border-gray-300 text-gray-400 hover:border-gray-400 hover:text-gray-500'
          }`}
          style={moodOpt ? {
            backgroundColor: `${moodOpt.color}20`,
            borderColor: `${moodOpt.color}60`,
            color: moodOpt.color,
          } : undefined}
        >
          {moodOpt ? moodOpt.label : '+ 心情'}
        </button>

        {/* 重要程度 tag */}
        <button
          onClick={() => setShowImportanceModal(true)}
          className={`px-4 py-1.5 rounded-full text-[11px] tracking-wider transition-all duration-300 ${
            impOpt
              ? 'border shadow-sm hover:shadow-md hover:scale-105'
              : 'border border-dashed border-gray-300 text-gray-400 hover:border-gray-400 hover:text-gray-500'
          }`}
          style={impOpt ? {
            backgroundColor: `${impOpt.color}20`,
            borderColor: `${impOpt.color}60`,
            color: impOpt.color,
          } : undefined}
        >
          {impOpt ? impOpt.label : '+ 重要程度'}
        </button>

        {/* 自定义 tags */}
        <AnimatePresence>
          {customTags.map(tag => (
            <motion.span
              key={tag}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="group relative px-4 py-1.5 rounded-full text-[11px] tracking-wider bg-gray-100 text-gray-500 border border-gray-200"
            >
              {tag}
              <button
                onClick={() => handleRemoveTag(tag)}
                className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-gray-300 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-gray-400"
              >
                <X size={8} />
              </button>
            </motion.span>
          ))}
        </AnimatePresence>

        {/* 添加自定义 tag */}
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
              className="w-20 px-3 py-1.5 rounded-full text-[11px] bg-gray-50 border border-gray-200 outline-none focus:border-gray-400 transition-colors"
            />
          </motion.div>
        ) : (
          <button
            onClick={() => setIsAddingTag(true)}
            className="px-3 py-1.5 rounded-full text-[11px] border border-dashed border-gray-300 text-gray-400 hover:border-gray-400 hover:text-gray-500 transition-all flex items-center gap-1"
          >
            <Plus size={10} /> 标签
          </button>
        )}
      </div>

      {/* 心情选择弹窗 */}
      <SliderModal
        open={showMoodModal}
        title="此刻的心境"
        options={MOOD_OPTIONS}
        value={mood}
        onConfirm={handleMoodConfirm}
        onClose={() => { setShowMoodModal(false); setPendingImportance(false); }}
      />

      {/* 重要程度选择弹窗 */}
      <SliderModal
        open={showImportanceModal}
        title="这一天的分量"
        options={IMPORTANCE_OPTIONS}
        value={importance}
        onConfirm={handleImportanceConfirm}
        onClose={() => setShowImportanceModal(false)}
      />
    </>
  );
};

export default DiaryTagBar;
