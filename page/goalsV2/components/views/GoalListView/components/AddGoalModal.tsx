import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Check, ChevronDown, ChevronUp, RefreshCw,
  ArrowUpRight, Palette, Target
} from 'lucide-react';
import { Goal, ThemeKey } from '../../../../types';
import { THEMES } from '../../../../hooks/useGoalStore';
import CategoryFilter, { CategoryFilterValue } from '../../../../../common/CategoryFilter';

interface AddGoalModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (goal: Goal) => Promise<void> | void;
  goalToEdit?: Goal | null; // Kept for backwards compatibility but not used
}

// Get today's date in YYYY-MM-DD format
const getTodayDate = () => {
  const today = new Date();
  return today.toISOString().split('T')[0];
};

const AddGoalModal: React.FC<AddGoalModalProps> = ({ isOpen, onClose, onSave }) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const emptyForm: Goal = {
    id: '',
    title: '',
    category: '',
    theme: 'indigo',
    timeInvested: '0',
    trackTimeAutomatically: true,
    unit: 'HRS',
    startDate: getTodayDate(),
    endDate: '',
    value: '',
    commitment: '',
    details: '',
    status: 'active',
    milestones: [],
    journal: []
  };

  const [form, setForm] = useState<Goal>(emptyForm);

  // Reset form when modal opens
  React.useEffect(() => {
    if (isOpen) {
      setForm(emptyForm);
      setIsSettingsOpen(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaving || !form.title.trim()) return;

    setIsSaving(true);
    try {
      const goalData: Goal = {
        ...form,
        id: `goal-${Date.now()}`,
        status: 'active'
      };

      await onSave(goalData);
      onClose();
    } catch (err) {
      console.error('Failed to save goal:', err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/20 backdrop-blur-sm transition-all"
      />
      <motion.div
        initial={{ scale: 0.95, opacity: 0, y: 40 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.95, opacity: 0, y: 40 }}
        transition={{ type: "spring", damping: 25, stiffness: 300 }}
        className="relative w-full max-w-lg bg-white border border-slate-200 shadow-2xl rounded-[1.5rem] overflow-hidden flex flex-col max-h-[80vh]"
      >
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 rounded-xl text-indigo-600">
              <Target size={20} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">创建新目标</h2>
              <p className="text-xs text-slate-400 font-medium">设定你的长期目标，稍后可以添加更多详情</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 scrollbar-hide">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Title */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">目标名称 *</label>
              <input
                required
                autoFocus
                type="text"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-base text-slate-800 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all font-medium"
                placeholder="输入你的目标..."
                value={form.title}
                onChange={e => setForm({...form, title: e.target.value})}
              />
            </div>

            {/* Quick Settings (Collapsible) */}
            <div className="border border-slate-200 rounded-xl bg-slate-50/50 overflow-hidden">
              <button
                type="button"
                onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                className="w-full flex items-center justify-between p-4 px-5 hover:bg-slate-100/50 transition-colors group"
              >
                <div className="flex items-center gap-2 text-slate-600 font-medium text-sm">
                  <Palette size={16} className="text-slate-400 group-hover:text-indigo-500 transition-colors" />
                  <span>配置与主题</span>
                  <span className="text-xs text-slate-400">(可选)</span>
                </div>
                {isSettingsOpen ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
              </button>

              <AnimatePresence initial={false}>
                {isSettingsOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="p-5 pt-0 space-y-5">
                      <div className="h-px w-full bg-slate-200 mb-5"></div>

                      {/* Theme */}
                      <div className="space-y-3">
                         <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">卡片主题</label>
                         <div className="flex gap-3">
                           {Object.entries(THEMES).map(([key, rawConfig]) => {
                             const config = rawConfig as typeof THEMES['indigo'];
                             return (
                               <button
                                 key={key}
                                 type="button"
                                 onClick={() => setForm({...form, theme: key as ThemeKey})}
                                 className={`group relative w-9 h-9 rounded-full shadow-sm transition-all hover:scale-110 flex items-center justify-center ${form.theme === key ? 'ring-2 ring-offset-2 ring-slate-400' : ''}`}
                                 style={{ backgroundColor: config.accentColor }}
                               >
                                 {form.theme === key && <Check size={14} className="text-white" />}
                               </button>
                             );
                           })}
                         </div>
                      </div>

                      {/* Category */}
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">分类</label>
                        <CategoryFilter
                          value={{
                            categoryId: form.category || null,
                            subCategoryId: null,
                            color: null,
                          }}
                          onChange={(val: CategoryFilterValue) => setForm({...form, category: val.categoryId || ''})}
                          buttonClassName="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all font-medium flex items-center gap-2"
                          showLabel={true}
                        />
                      </div>

                      {/* Dates */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">开始日期</label>
                          <input
                            type="date"
                            className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all font-medium"
                            value={form.startDate}
                            onChange={e => setForm({...form, startDate: e.target.value})}
                          />
                        </div>
                        <div className="space-y-2">
                          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">目标日期</label>
                          <input
                            type="date"
                            className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all font-medium"
                            value={form.endDate}
                            onChange={e => setForm({...form, endDate: e.target.value})}
                          />
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Hint */}
            <p className="text-xs text-slate-400 text-center">
              创建后可以展开卡片添加里程碑、价值意义等详细信息
            </p>
          </form>
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-slate-100 bg-slate-50/50 flex gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="flex-1 py-3 rounded-xl text-slate-500 font-medium hover:bg-slate-100 transition-colors text-sm disabled:opacity-50"
            >
              取消
            </button>
            <button
              onClick={handleSubmit}
              type="submit"
              disabled={isSaving || !form.title.trim()}
              className="flex-[2] py-3 bg-slate-900 text-white rounded-xl font-medium shadow-lg shadow-slate-900/20 hover:bg-slate-800 active:scale-[0.98] transition-all text-sm flex items-center justify-center gap-2 disabled:opacity-70"
            >
              {isSaving ? (
                <>保存中... <RefreshCw size={16} className="animate-spin" /></>
              ) : (
                <>创建目标 <ArrowUpRight size={16} /></>
              )}
            </button>
        </div>

      </motion.div>
    </div>
  );
};

export default AddGoalModal;
