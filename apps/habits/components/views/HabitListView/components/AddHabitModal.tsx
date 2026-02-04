import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ChevronDown, Clock, Calendar, Anchor, Target } from 'lucide-react';
import { CreateHabitForm, HabitFrequency, FrequencyType, Habit } from '../../../../types';

interface AddHabitModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: CreateHabitForm) => void;
  habitToEdit?: Habit | null;
}

const FREQUENCY_OPTIONS: { value: FrequencyType; label: string; description: string }[] = [
  { value: 'daily', label: '每天', description: '每天都需要完成' },
  { value: 'weekdays', label: '工作日', description: '周一至周五' },
  { value: 'weekly', label: '每周', description: '每周完成指定次数' },
  { value: 'custom', label: '自定义', description: '选择特定的日期' },
];

const WEEKDAYS = [
  { value: 1, label: '一' },
  { value: 2, label: '二' },
  { value: 3, label: '三' },
  { value: 4, label: '四' },
  { value: 5, label: '五' },
  { value: 6, label: '六' },
  { value: 7, label: '日' },
];

const ANCHOR_TYPES = [
  { value: 'time', label: '时间', icon: Clock, placeholder: '例如：早上7点' },
  { value: 'event', label: '事件', icon: Calendar, placeholder: '例如：吃完早餐后' },
  { value: 'scene', label: '场景', icon: Anchor, placeholder: '例如：在书房' },
];

const AddHabitModal: React.FC<AddHabitModalProps> = ({
  isOpen,
  onClose,
  onSave,
  habitToEdit
}) => {
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  const emptyForm: CreateHabitForm = {
    name: '',
    description: '',
    frequency: { type: 'daily' },
    anchorType: undefined,
    anchorDescription: '',
    initialChallenge: {
      targetDays: 7,
      requiredCompletions: 5
    }
  };

  const [form, setForm] = useState<CreateHabitForm>(
    habitToEdit
      ? {
          name: habitToEdit.name,
          description: habitToEdit.description,
          frequency: habitToEdit.frequency,
          anchorType: habitToEdit.anchorType,
          anchorDescription: habitToEdit.anchorDescription,
        }
      : emptyForm
  );

  React.useEffect(() => {
    if (isOpen) {
      if (habitToEdit) {
        setForm({
          name: habitToEdit.name,
          description: habitToEdit.description,
          frequency: habitToEdit.frequency,
          anchorType: habitToEdit.anchorType,
          anchorDescription: habitToEdit.anchorDescription,
        });
        setIsAdvancedOpen(true);
      } else {
        setForm(emptyForm);
        setIsAdvancedOpen(false);
      }
    }
  }, [isOpen, habitToEdit]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    onSave(form);
    onClose();
  };

  const updateFrequency = (updates: Partial<HabitFrequency>) => {
    setForm(prev => ({
      ...prev,
      frequency: { ...prev.frequency, ...updates }
    }));
  };

  const toggleWeekday = (day: number) => {
    const currentDays = form.frequency.specificDays || [];
    const newDays = currentDays.includes(day)
      ? currentDays.filter(d => d !== day)
      : [...currentDays, day].sort();
    updateFrequency({ specificDays: newDays });
  };

  const isEditing = !!habitToEdit;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/20 backdrop-blur-sm"
      />

      <motion.div
        initial={{ scale: 0.95, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.95, opacity: 0, y: 20 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="relative w-full max-w-lg bg-white/95 backdrop-blur-xl border border-white/60 shadow-[0_25px_50px_-12px_rgba(0,0,0,0.15)] rounded-[2rem] overflow-hidden flex flex-col max-h-[85vh]"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 pb-4 border-b border-slate-100">
          <div>
            <h2 className="text-xl font-serif text-slate-800">
              {isEditing ? '编辑习惯' : '培养新习惯'}
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              {isEditing ? '修改习惯设置' : '开始你的习惯养成之旅'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-xl transition-colors"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Name */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">
              习惯名称
            </label>
            <input
              required
              autoFocus
              type="text"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              placeholder="例如：每天阅读30分钟"
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-700 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500 transition-all"
            />
          </div>

          {/* Frequency */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">
              频率设置
            </label>
            <div className="grid grid-cols-2 gap-2">
              {FREQUENCY_OPTIONS.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => updateFrequency({ type: option.value })}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    form.frequency.type === option.value
                      ? 'bg-green-50 border-green-200 ring-2 ring-green-500/20'
                      : 'bg-white border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div className={`text-sm font-medium ${
                    form.frequency.type === option.value ? 'text-green-700' : 'text-slate-700'
                  }`}>
                    {option.label}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    {option.description}
                  </div>
                </button>
              ))}
            </div>

            {/* Weekly times */}
            {form.frequency.type === 'weekly' && (
              <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl">
                <span className="text-sm text-slate-600">每周</span>
                <input
                  type="number"
                  min={1}
                  max={7}
                  value={form.frequency.timesPerWeek || 3}
                  onChange={e => updateFrequency({ timesPerWeek: parseInt(e.target.value) || 3 })}
                  className="w-16 bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-center text-slate-700 focus:outline-none focus:ring-2 focus:ring-green-500/20"
                />
                <span className="text-sm text-slate-600">次</span>
              </div>
            )}

            {/* Custom days */}
            {form.frequency.type === 'custom' && (
              <div className="flex gap-2 p-3 bg-slate-50 rounded-xl">
                {WEEKDAYS.map(day => (
                  <button
                    key={day.value}
                    type="button"
                    onClick={() => toggleWeekday(day.value)}
                    className={`w-9 h-9 rounded-full text-sm font-medium transition-all ${
                      form.frequency.specificDays?.includes(day.value)
                        ? 'bg-green-500 text-white'
                        : 'bg-white border border-slate-200 text-slate-600 hover:border-green-300'
                    }`}
                  >
                    {day.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Advanced Settings */}
          <div className="border border-slate-100 rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
              className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
            >
              <span className="text-sm font-medium text-slate-600">高级设置</span>
              <ChevronDown
                size={16}
                className={`text-slate-400 transition-transform ${isAdvancedOpen ? 'rotate-180' : ''}`}
              />
            </button>

            <AnimatePresence>
              {isAdvancedOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="p-4 pt-0 space-y-4 border-t border-slate-100">
                    {/* Description */}
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                        描述（可选）
                      </label>
                      <textarea
                        value={form.description || ''}
                        onChange={e => setForm({ ...form, description: e.target.value })}
                        placeholder="为什么要养成这个习惯？"
                        rows={2}
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-700 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500 transition-all resize-none"
                      />
                    </div>

                    {/* Anchor */}
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                        锚点习惯（可选）
                      </label>
                      <div className="flex gap-2">
                        {ANCHOR_TYPES.map(anchor => (
                          <button
                            key={anchor.value}
                            type="button"
                            onClick={() => setForm({
                              ...form,
                              anchorType: form.anchorType === anchor.value ? undefined : anchor.value as any
                            })}
                            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                              form.anchorType === anchor.value
                                ? 'bg-green-100 text-green-700 border border-green-200'
                                : 'bg-slate-50 text-slate-600 border border-slate-200 hover:border-slate-300'
                            }`}
                          >
                            <anchor.icon size={12} />
                            {anchor.label}
                          </button>
                        ))}
                      </div>
                      {form.anchorType && (
                        <input
                          type="text"
                          value={form.anchorDescription || ''}
                          onChange={e => setForm({ ...form, anchorDescription: e.target.value })}
                          placeholder={ANCHOR_TYPES.find(a => a.value === form.anchorType)?.placeholder}
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-700 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500 transition-all"
                        />
                      )}
                    </div>

                    {/* Initial Challenge (only for new habits) */}
                    {!isEditing && (
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                          <Target size={12} />
                          初始挑战目标
                        </label>
                        <div className="flex items-center gap-3 p-3 bg-green-50 rounded-xl border border-green-100">
                          <input
                            type="number"
                            min={1}
                            max={90}
                            value={form.initialChallenge?.targetDays || 7}
                            onChange={e => setForm({
                              ...form,
                              initialChallenge: {
                                ...form.initialChallenge!,
                                targetDays: parseInt(e.target.value) || 7
                              }
                            })}
                            className="w-14 bg-white border border-green-200 rounded-lg px-2 py-1.5 text-center text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-green-500/20"
                          />
                          <span className="text-sm text-slate-600">天内完成</span>
                          <input
                            type="number"
                            min={1}
                            max={form.initialChallenge?.targetDays || 7}
                            value={form.initialChallenge?.requiredCompletions || 5}
                            onChange={e => setForm({
                              ...form,
                              initialChallenge: {
                                ...form.initialChallenge!,
                                requiredCompletions: parseInt(e.target.value) || 5
                              }
                            })}
                            className="w-14 bg-white border border-green-200 rounded-lg px-2 py-1.5 text-center text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-green-500/20"
                          />
                          <span className="text-sm text-slate-600">次</span>
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </form>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/50 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-3 rounded-xl text-slate-500 font-medium hover:bg-slate-100 transition-colors text-sm"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            className="flex-[2] py-3 bg-green-500 text-white rounded-xl font-medium shadow-lg shadow-green-500/25 hover:bg-green-600 hover:shadow-xl active:scale-[0.98] transition-all text-sm"
          >
            {isEditing ? '保存修改' : '开始培养'}
          </button>
        </div>
      </motion.div>
    </div>
  );
};

export default AddHabitModal;
