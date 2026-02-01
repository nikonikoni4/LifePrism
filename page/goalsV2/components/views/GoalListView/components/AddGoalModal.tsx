
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Check, ChevronDown, ChevronUp, RefreshCw,
  ArrowUpRight, Quote, HeartHandshake, History, FileText, X, Palette, Target
} from 'lucide-react';
import { Goal, ThemeKey, MilestoneItem, EditableMilestone } from '../../../../types';
import { THEMES, PAST_VALUES, PAST_COMMITMENTS } from '../../../../hooks/useGoalStore';
import MilestoneEditor from './milestone/MilestoneEditor';
import { convertToEditableMilestones } from './milestone/utils';

const SuggestionBox = ({ items, onSelect, onClose, themeColor }: { items: string[], onSelect: (val: string) => void, onClose: () => void, themeColor: string }) => (
  <motion.div
    initial={{ opacity: 0, y: 10, scale: 0.95 }}
    animate={{ opacity: 1, y: 0, scale: 1 }}
    exit={{ opacity: 0, scale: 0.95 }}
    className="absolute top-8 left-0 z-50 w-full bg-white border border-slate-200 shadow-xl rounded-xl overflow-hidden"
  >
    <div className="p-2 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pl-2">快速选择</span>
      <button onClick={onClose} type="button" className="p-1 hover:bg-slate-200 rounded-md transition-colors"><X size={12} className="text-slate-400"/></button>
    </div>
    <div className="max-h-40 overflow-y-auto p-1">
      {items.map((item, index) => (
        <button
          key={index}
          type="button"
          onClick={() => onSelect(item)}
          className="w-full text-left px-3 py-2 text-sm text-slate-600 rounded-lg hover:bg-slate-50 transition-colors truncate"
        >
          {item}
        </button>
      ))}
    </div>
  </motion.div>
);

interface AddGoalModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (goal: Goal) => Promise<void> | void;
  goalToEdit: Goal | null;
}

// Get today's date in YYYY-MM-DD format
const getTodayDate = () => {
  const today = new Date();
  return today.toISOString().split('T')[0]; // Returns YYYY-MM-DD
};

const AddGoalModal: React.FC<AddGoalModalProps> = ({ isOpen, onClose, onSave, goalToEdit }) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [showValueHistory, setShowValueHistory] = useState(false);
  const [showCommitmentHistory, setShowCommitmentHistory] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const emptyForm: Goal = {
    id: '',
    title: '',
    category: '',
    theme: 'indigo',
    timeInvested: '0',
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

  useEffect(() => {
    if (isOpen) {
      if (goalToEdit) {
        setForm(goalToEdit);
        setIsSettingsOpen(true);
      } else {
        setForm(emptyForm);
        setIsSettingsOpen(false);
      }
    }
  }, [isOpen, goalToEdit]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaving) return;

    setIsSaving(true);
    try {
      const goalData = goalToEdit
        ? { ...form }
        : { ...form, id: Date.now().toString(), status: 'active' as const };

      await onSave(goalData);
      onClose();
    } catch (err) {
      console.error('Failed to save goal:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleMilestonesChange = (newMilestones: EditableMilestone[]) => {
      const updated: MilestoneItem[] = newMilestones.map(nm => {
        const existing = form.milestones?.find(m => m.id === nm.id);
        return {
          id: nm.id,
          content: nm.content,
          orderIndex: nm.orderIndex,
          state: existing?.state || 0,
          finishTime: existing?.finishTime || null
        };
      });
      setForm({...form, milestones: updated});
  };

  const isEditing = !!goalToEdit;

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
        className="relative w-full max-w-2xl bg-white border border-slate-200 shadow-2xl rounded-[1.5rem] overflow-hidden flex flex-col max-h-[90vh]"
      >
        {/* Header */}
        <div className="px-8 pt-6 pb-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 rounded-xl text-indigo-600">
              <Target size={20} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">{isEditing ? '编辑目标' : '创建新目标'}</h2>
              <p className="text-xs text-slate-400 font-medium">设定你的长期目标</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-8 scrollbar-hide">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Title */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">目标名称</label>
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

            {/* Settings */}
            <div className="border border-slate-200 rounded-xl bg-slate-50/50 overflow-hidden">
              <button
                type="button"
                onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                className="w-full flex items-center justify-between p-4 px-5 hover:bg-slate-100/50 transition-colors group"
              >
                <div className="flex items-center gap-2 text-slate-600 font-medium text-sm">
                  <Palette size={16} className="text-slate-400 group-hover:text-indigo-500 transition-colors" />
                  <span>配置与主题</span>
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

                      {/* Category & Time */}
                      <div className="grid grid-cols-2 gap-4">
                         <div className="space-y-2">
                          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">分类</label>
                          <div className="relative">
                            <select
                              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 appearance-none transition-all font-medium"
                              value={form.category}
                              onChange={e => setForm({...form, category: e.target.value})}
                            >
                                <option value="" disabled>选择分类...</option>
                                <option value="Work">工作</option>
                                <option value="Learn">学习</option>
                                <option value="Health">健康</option>
                                <option value="Life">生活</option>
                            </select>
                            <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">已投入时间</label>
                          <div className="flex gap-2">
                            <input
                              type="text"
                              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all tabular-nums font-medium"
                              placeholder="0"
                              value={form.timeInvested}
                              onChange={e => setForm({...form, timeInvested: e.target.value})}
                            />
                             <span className="flex items-center justify-center bg-slate-100 rounded-xl px-3 text-xs font-bold text-slate-400">小时</span>
                          </div>
                        </div>
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

            {/* Core Drive */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
               {/* Value */}
               <div className="space-y-2 relative group">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-500">
                        <Quote size={12} />
                      </div>
                      <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">价值意义</label>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowValueHistory(!showValueHistory)}
                      className="text-slate-300 hover:text-indigo-500 transition-colors p-1"
                      title="历史记录"
                    >
                      <History size={14} />
                    </button>
                  </div>

                  <div className="relative">
                    <textarea
                      className="w-full h-28 bg-slate-50 border border-slate-200 rounded-xl p-4 text-sm text-slate-600 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all resize-none leading-relaxed"
                      placeholder="这个目标对你有什么意义？"
                      value={form.value}
                      onChange={e => setForm({...form, value: e.target.value})}
                    />
                    <AnimatePresence>
                      {showValueHistory && (
                        <SuggestionBox
                          items={PAST_VALUES}
                          onSelect={(val) => {
                            setForm({...form, value: val});
                            setShowValueHistory(false);
                          }}
                          onClose={() => setShowValueHistory(false)}
                          themeColor="indigo"
                        />
                      )}
                    </AnimatePresence>
                  </div>
               </div>

               {/* Commitment */}
               <div className="space-y-2 relative group">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-rose-50 flex items-center justify-center text-rose-500">
                        <HeartHandshake size={12} />
                      </div>
                      <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">每日承诺</label>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowCommitmentHistory(!showCommitmentHistory)}
                      className="text-slate-300 hover:text-rose-500 transition-colors p-1"
                      title="历史记录"
                    >
                      <History size={14} />
                    </button>
                  </div>

                  <div className="relative">
                    <textarea
                      className="w-full h-28 bg-slate-50 border border-slate-200 rounded-xl p-4 text-sm text-slate-600 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 transition-all resize-none leading-relaxed"
                      placeholder="你每天会做什么来推进这个目标？"
                      value={form.commitment}
                      onChange={e => setForm({...form, commitment: e.target.value})}
                    />
                    <AnimatePresence>
                      {showCommitmentHistory && (
                        <SuggestionBox
                          items={PAST_COMMITMENTS}
                          onSelect={(val) => {
                            setForm({...form, commitment: val});
                            setShowCommitmentHistory(false);
                          }}
                          onClose={() => setShowCommitmentHistory(false)}
                          themeColor="rose"
                        />
                      )}
                    </AnimatePresence>
                  </div>
               </div>
            </div>

            {/* Milestones */}
            <div className="space-y-2">
                <MilestoneEditor
                    milestones={convertToEditableMilestones(form.milestones || [])}
                    onChange={handleMilestonesChange}
                    label="里程碑"
                    addButtonText="添加里程碑"
                />
            </div>

            {/* Blueprint */}
            <div className="space-y-2 relative group">
               <div className="flex items-center gap-2">
                 <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500">
                   <FileText size={12} />
                 </div>
                 <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">详细计划</label>
               </div>
               <textarea
                 className="w-full h-32 bg-white border border-slate-200 rounded-xl p-4 text-sm text-slate-700 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all resize-none leading-relaxed"
                 placeholder="写下你的初步计划、具体步骤或详细笔记..."
                 value={form.details}
                 onChange={e => setForm({...form, details: e.target.value})}
               />
            </div>

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
              disabled={isSaving}
              className="flex-[2] py-3 bg-slate-900 text-white rounded-xl font-medium shadow-lg shadow-slate-900/20 hover:bg-slate-800 active:scale-[0.98] transition-all text-sm flex items-center justify-center gap-2 disabled:opacity-70"
            >
              {isSaving ? (
                <>保存中... <RefreshCw size={16} className="animate-spin" /></>
              ) : isEditing ? (
                <>更新目标 <RefreshCw size={16} /></>
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
