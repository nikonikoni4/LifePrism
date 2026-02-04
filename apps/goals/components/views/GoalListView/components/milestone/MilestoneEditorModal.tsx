import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Flag } from 'lucide-react';
import { MilestoneItem, EditableMilestone } from '../../../../../types';
import MilestoneEditor from './MilestoneEditor';

interface MilestoneEditorModalProps {
  milestones: MilestoneItem[];
  onSave: (milestones: MilestoneItem[]) => void;
  onClose: () => void;
}

const MilestoneEditorModal: React.FC<MilestoneEditorModalProps> = ({
  milestones,
  onSave,
  onClose,
}) => {
  // Convert MilestoneItem[] to EditableMilestone[] for editing
  const [editableMilestones, setEditableMilestones] = useState<EditableMilestone[]>(
    milestones.map(m => ({
      id: m.id,
      content: m.content,
      orderIndex: m.orderIndex,
    }))
  );

  const handleSave = () => {
    // Convert back to MilestoneItem[], preserving state and finishTime from original
    const updatedMilestones: MilestoneItem[] = editableMilestones.map((em, index) => {
      const original = milestones.find(m => m.id === em.id);
      return {
        id: em.id,
        content: em.content,
        orderIndex: index,
        state: original?.state ?? 0,
        finishTime: original?.finishTime ?? null,
      };
    });
    onSave(updatedMilestones);
    onClose();
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Flag size={18} className="text-orange-500" />
              <h2 className="text-lg font-bold text-slate-800">编辑里程碑</h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl hover:bg-slate-100 transition-colors text-slate-400 hover:text-slate-600"
            >
              <X size={20} />
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            <MilestoneEditor
              milestones={editableMilestones}
              onChange={setEditableMilestones}
              label="里程碑列表"
              addButtonText="添加里程碑"
              maxHeight="16rem"
            />
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-100 bg-slate-50">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200 rounded-xl transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 text-sm font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-xl transition-colors"
            >
              保存
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default MilestoneEditorModal;
