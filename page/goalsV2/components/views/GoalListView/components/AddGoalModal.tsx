
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Check, ChevronDown, ChevronUp, RefreshCw, 
  ArrowUpRight, Quote, HeartHandshake, History, FileText, X, Palette
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
    className="absolute top-8 left-0 z-50 w-full bg-white/95 backdrop-blur-xl border border-slate-200 shadow-xl rounded-xl overflow-hidden"
  >
    <div className="p-2 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pl-2">Quick Select</span>
      <button onClick={onClose} type="button" className="p-1 hover:bg-slate-200 rounded-md transition-colors"><X size={12} className="text-slate-400"/></button>
    </div>
    <div className="max-h-40 overflow-y-auto p-1">
      {items.map((item, index) => (
        <button
          key={index}
          type="button"
          onClick={() => onSelect(item)}
          className={`w-full text-left px-3 py-2 text-sm text-slate-600 rounded-lg hover:bg-${themeColor}-50 hover:text-${themeColor}-600 transition-colors truncate`}
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
  onSave: (goal: Goal) => void;
  goalToEdit: Goal | null;
}

const AddGoalModal: React.FC<AddGoalModalProps> = ({ isOpen, onClose, onSave, goalToEdit }) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [showValueHistory, setShowValueHistory] = useState(false);
  const [showCommitmentHistory, setShowCommitmentHistory] = useState(false);

  const emptyForm: Goal = { 
    id: '',
    title: '', 
    category: '', 
    theme: 'indigo',
    timeInvested: '0', 
    unit: 'HRS', 
    startDate: '', 
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const goalData = goalToEdit 
      ? { ...form } 
      : { ...form, id: Date.now().toString(), status: 'active' as const };
    
    onSave(goalData);
    onClose();
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
        className="absolute inset-0 bg-[#F1F5F9]/80 backdrop-blur-md transition-all"
      />
      <motion.div 
        initial={{ scale: 0.95, opacity: 0, y: 40 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.95, opacity: 0, y: 40 }}
        transition={{ type: "spring", damping: 25, stiffness: 300 }}
        className="relative w-full max-w-2xl bg-white/90 backdrop-blur-2xl border border-white/60 shadow-[0_40px_80px_-20px_rgba(0,0,0,0.15)] rounded-[2.5rem] overflow-hidden flex flex-col max-h-[90vh]"
      >
        <div className="flex-1 overflow-y-auto p-8 md:p-10 scrollbar-hide">
          <form onSubmit={handleSubmit} className="space-y-8">
            {/* Title */}
            <div className="space-y-2 text-center">
              <label className="text-xs font-bold text-slate-400 uppercase tracking-[0.2em]">Goal Name</label>
              <input 
                required
                autoFocus
                type="text" 
                className="w-full bg-transparent border-b-2 border-slate-100 px-2 py-4 text-xl md:text-2xl text-center text-slate-800 placeholder:text-slate-200 focus:outline-none focus:border-slate-300 transition-colors font-serif"
                placeholder="Name your ambition..."
                value={form.title}
                onChange={e => setForm({...form, title: e.target.value})}
              />
            </div>

            {/* Settings */}
            <div className="border border-slate-100 rounded-2xl bg-slate-50/50 overflow-hidden">
              <button 
                type="button"
                onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                className="w-full flex items-center justify-between p-4 px-6 hover:bg-slate-100/50 transition-colors group"
              >
                <div className="flex items-center gap-2 text-slate-500 font-medium text-sm">
                  <Palette size={16} className="text-slate-400 group-hover:text-indigo-500 transition-colors" />
                  <span>Configuration & Aesthetics</span>
                </div>
                {isSettingsOpen ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
              </button>

              <AnimatePresence initial={false}>
                {isSettingsOpen && (
                  <motion.div 
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3, ease: "easeInOut" }}
                    className="overflow-hidden"
                  >
                    <div className="p-6 pt-0 space-y-6">
                      <div className="h-px w-full bg-slate-100 mb-6"></div>
                      {/* Theme */}
                      <div className="space-y-3">
                         <label className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">Card Theme</label>
                         <div className="flex gap-4">
                           {Object.entries(THEMES).map(([key, rawConfig]) => {
                             const config = rawConfig as typeof THEMES['indigo'];
                             return (
                               <button
                                 key={key}
                                 type="button"
                                 onClick={() => setForm({...form, theme: key as ThemeKey})}
                                 className={`group relative w-10 h-10 rounded-full ${config.progressBg} shadow-sm transition-all hover:scale-110 flex items-center justify-center`}
                               >
                                 {form.theme === key && <Check size={16} className="text-white" />}
                                 <span className="absolute -bottom-6 text-[9px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity uppercase font-bold tracking-wider">{config.label}</span>
                               </button>
                             );
                           })}
                         </div>
                      </div>

                      {/* Category & Time */}
                      <div className="grid grid-cols-2 gap-6">
                         <div className="space-y-2">
                          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">Category</label>
                          <div className="relative">
                            <select 
                              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 appearance-none transition-all"
                              value={form.category}
                              onChange={e => setForm({...form, category: e.target.value})}
                            >
                                <option value="" disabled>Select...</option>
                                <option value="Work">WORK</option>
                                <option value="Learn">LEARN</option>
                                <option value="Health">HEALTH</option>
                                <option value="Life">LIFE</option>
                            </select>
                            <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">Initial Invested</label>
                          <div className="flex gap-2">
                            <input 
                              type="text" 
                              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all tabular-nums"
                              placeholder="0"
                              value={form.timeInvested}
                              onChange={e => setForm({...form, timeInvested: e.target.value})}
                            />
                             <span className="flex items-center justify-center bg-slate-100 rounded-xl px-3 text-[10px] font-bold text-slate-400">HRS</span>
                          </div>
                        </div>
                      </div>

                      {/* Dates */}
                      <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">Start Date</label>
                          <input 
                            type="text" 
                            placeholder="MM.DD"
                            className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all font-mono"
                            value={form.startDate}
                            onChange={e => setForm({...form, startDate: e.target.value})}
                          />
                        </div>
                        <div className="space-y-2">
                          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">Target Date</label>
                          <input 
                            type="text" 
                            placeholder="MM.DD"
                            className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all font-mono"
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
               {/* Value */}
               <div className="space-y-3 relative group">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-400 group-focus-within:bg-indigo-500 group-focus-within:text-white transition-colors duration-500">
                        <Quote size={14} />
                      </div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest group-focus-within:text-indigo-500 transition-colors">The Value</label>
                    </div>
                    <button 
                      type="button"
                      onClick={() => setShowValueHistory(!showValueHistory)}
                      className="text-slate-300 hover:text-indigo-500 transition-colors p-1"
                      title="History"
                    >
                      <History size={14} />
                    </button>
                  </div>
                  
                  <div className="relative">
                    <textarea 
                      className="w-full h-32 bg-slate-50/50 border border-slate-200 rounded-2xl p-4 text-sm text-slate-600 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all resize-none leading-relaxed"
                      placeholder="Why does this goal matter to you deeply?"
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
               <div className="space-y-3 relative group">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-rose-50 flex items-center justify-center text-rose-400 group-focus-within:bg-rose-500 group-focus-within:text-white transition-colors duration-500">
                        <HeartHandshake size={14} />
                      </div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest group-focus-within:text-rose-500 transition-colors">The Vow</label>
                    </div>
                    <button 
                      type="button"
                      onClick={() => setShowCommitmentHistory(!showCommitmentHistory)}
                      className="text-slate-300 hover:text-rose-500 transition-colors p-1"
                      title="History"
                    >
                      <History size={14} />
                    </button>
                  </div>

                  <div className="relative">
                    <textarea 
                      className="w-full h-32 bg-slate-50/50 border border-slate-200 rounded-2xl p-4 text-sm text-slate-600 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-rose-500/10 focus:border-rose-500 transition-all resize-none leading-relaxed"
                      placeholder="What small daily promise will you keep?"
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
            <div className="space-y-3 pt-2">
                <MilestoneEditor 
                    milestones={convertToEditableMilestones(form.milestones || [])}
                    onChange={handleMilestonesChange}
                    label="The Roadmap"
                    addButtonText="Add Key Milestone"
                />
            </div>

            {/* Blueprint */}
            <div className="space-y-3 relative group">
               <div className="flex items-center gap-2">
                 <div className="w-8 h-8 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 group-focus-within:bg-slate-800 group-focus-within:text-white transition-colors duration-500">
                   <FileText size={14} />
                 </div>
                 <label className="text-xs font-bold text-slate-400 uppercase tracking-widest group-focus-within:text-slate-800 transition-colors">The Blueprint</label>
               </div>
               <textarea 
                 className="w-full h-40 bg-white border border-slate-200 rounded-2xl p-5 text-sm text-slate-700 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-500/10 focus:border-slate-400 transition-all resize-none leading-relaxed shadow-sm font-sans"
                 placeholder="Draft your preliminary vision, specific steps, or detailed notes here..."
                 value={form.details}
                 onChange={e => setForm({...form, details: e.target.value})}
               />
            </div>

          </form>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-100 bg-white/50 backdrop-blur-sm flex gap-4">
            <button 
              type="button" 
              onClick={onClose}
              className="flex-1 py-4 rounded-2xl text-slate-500 font-medium hover:bg-slate-50 transition-colors text-sm"
            >
              Discard
            </button>
            <button 
              onClick={handleSubmit}
              type="submit" 
              className="flex-[2] py-4 bg-slate-900 text-white rounded-2xl font-medium shadow-xl shadow-slate-900/20 hover:scale-[1.02] hover:shadow-2xl active:scale-[0.98] transition-all text-sm flex items-center justify-center gap-2"
            >
              {isEditing ? (
                <>Refine Goal <RefreshCw size={16} /></>
              ) : (
                <>Forge Goal <ArrowUpRight size={16} /></>
              )}
            </button>
        </div>

      </motion.div>
    </div>
  );
};

export default AddGoalModal;
