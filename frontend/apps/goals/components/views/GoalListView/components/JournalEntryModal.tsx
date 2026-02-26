import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { X, Sun, Moon, Coffee, Zap, Tag, FileText } from 'lucide-react';
import { JournalEntry } from '../../../../types';

interface JournalEntryModalProps {
  goalId: string;
  onClose: () => void;
  onSave: (journal: Omit<JournalEntry, 'id'>) => Promise<void>;
}

type MoodType = JournalEntry['mood'];

const MOOD_OPTIONS: { value: MoodType; label: string; icon: React.ReactNode; bgColor: string; textColor: string }[] = [
  { value: 'joy', label: '开心', icon: <Sun size={16} />, bgColor: 'bg-amber-100', textColor: 'text-amber-500' },
  { value: 'calm', label: '平静', icon: <Coffee size={16} />, bgColor: 'bg-emerald-100', textColor: 'text-emerald-500' },
  { value: 'frustrated', label: '沮丧', icon: <Zap size={16} />, bgColor: 'bg-rose-100', textColor: 'text-rose-500' },
  { value: 'neutral', label: '一般', icon: <Moon size={16} />, bgColor: 'bg-slate-100', textColor: 'text-slate-400' },
];

const getTodayDate = () => {
  return new Date().toISOString().split('T')[0];
};

const getCurrentTime = () => {
  const now = new Date();
  return now.toTimeString().slice(0, 5); // HH:MM format
};

const JournalEntryModal: React.FC<JournalEntryModalProps> = ({ goalId, onClose, onSave }) => {
  const [form, setForm] = useState({
    date: getTodayDate(),
    time: getCurrentTime(),
    content: '',
    mood: 'neutral' as MoodType,
    tags: '',
  });
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaving || !form.content.trim()) return;

    setIsSaving(true);
    try {
      const journalData: Omit<JournalEntry, 'id'> = {
        date: form.date,
        time: form.time,
        content: form.content.trim(),
        mood: form.mood,
        duration: 0,
        tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
      };
      await onSave(journalData);
    } catch (err) {
      console.error('Failed to save journal:', err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/30 backdrop-blur-sm"
      />
      <motion.div
        initial={{ scale: 0.95, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.95, opacity: 0, y: 20 }}
        transition={{ type: "spring", damping: 25, stiffness: 300 }}
        className="relative w-full max-w-lg bg-white border border-slate-200 shadow-2xl rounded-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-slate-100 rounded-xl text-slate-600">
              <FileText size={18} />
            </div>
            <h2 className="text-lg font-bold text-slate-900">记录日志</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-xl transition-colors text-slate-400 hover:text-slate-600"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Date & Time */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">日期</label>
              <input
                type="date"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all font-medium"
                value={form.date}
                onChange={e => setForm({ ...form, date: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">时间</label>
              <input
                type="time"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all font-medium"
                value={form.time}
                onChange={e => setForm({ ...form, time: e.target.value })}
              />
            </div>
          </div>

          {/* Content */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">内容</label>
            <textarea
              required
              autoFocus
              className="w-full h-32 bg-slate-50 border border-slate-200 rounded-xl p-4 text-sm text-slate-700 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all resize-none leading-relaxed"
              placeholder="记录你的进展、想法或反思..."
              value={form.content}
              onChange={e => setForm({ ...form, content: e.target.value })}
            />
          </div>

          {/* Mood Selection */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">心情</label>
            <div className="flex gap-2">
              {MOOD_OPTIONS.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setForm({ ...form, mood: option.value })}
                  className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl border-2 transition-all ${
                    form.mood === option.value
                      ? `${option.bgColor} ${option.textColor} border-current`
                      : 'bg-white border-slate-200 text-slate-400 hover:border-slate-300'
                  }`}
                >
                  {option.icon}
                  <span className="text-xs font-medium">{option.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Tags */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
              <Tag size={12} /> 标签
            </label>
            <input
              type="text"
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-600 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all font-medium"
              placeholder="用逗号分隔"
              value={form.tags}
              onChange={e => setForm({ ...form, tags: e.target.value })}
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="flex-1 py-3 rounded-xl text-slate-500 font-medium hover:bg-slate-100 transition-colors text-sm disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isSaving || !form.content.trim()}
              className="flex-[2] py-3 bg-slate-900 text-white rounded-xl font-medium shadow-lg shadow-slate-900/20 hover:bg-slate-800 active:scale-[0.98] transition-all text-sm disabled:opacity-70"
            >
              {isSaving ? '保存中...' : '保存日志'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
};

export default JournalEntryModal;
