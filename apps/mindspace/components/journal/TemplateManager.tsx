/**
 * TemplateManager - 模板管理弹窗
 * 左右分栏：左侧模板列表 + 右侧内容编辑
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Trash2, X, FileText } from 'lucide-react';
import { DiaryAPI } from './diaryApi';

interface TemplateManagerProps {
  open: boolean;
  onClose: () => void;
  /** 选择模板应用到日记 */
  onApplyTemplate?: (content: string) => void;
}

const TemplateManager: React.FC<TemplateManagerProps> = ({ open, onClose, onApplyTemplate }) => {
  const [templates, setTemplates] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const nameInputRef = useRef<HTMLInputElement>(null);

  // 加载模板列表
  const loadTemplates = useCallback(async () => {
    try {
      setLoading(true);
      const list = await DiaryAPI.getTemplates();
      setTemplates(list);
      if (list.length > 0 && !selected) {
        setSelected(list[0]);
      }
    } catch (e) {
      console.error('加载模板列表失败:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  // 加载选中模板内容
  useEffect(() => {
    if (!selected) { setContent(''); return; }
    DiaryAPI.getTemplate(selected)
      .then(t => setContent(t.content))
      .catch(e => console.error('加载模板内容失败:', e));
  }, [selected]);

  useEffect(() => {
    if (open) loadTemplates();
  }, [open, loadTemplates]);

  // 自动保存（防抖）
  const handleContentChange = useCallback((value: string) => {
    setContent(value);
    if (!selected) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(async () => {
      try {
        setSaving(true);
        await DiaryAPI.updateTemplate(selected, value);
      } catch (e) {
        console.error('保存模板失败:', e);
      } finally {
        setSaving(false);
      }
    }, 800);
  }, [selected]);

  // 创建模板
  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    try {
      await DiaryAPI.createTemplate(name);
      setNewName('');
      setIsCreating(false);
      await loadTemplates();
      setSelected(name);
    } catch (e) {
      console.error('创建模板失败:', e);
    }
  };

  // 删除模板
  const handleDelete = async () => {
    if (!selected) return;
    if (!window.confirm(`确定删除模板「${selected}」？`)) return;
    try {
      await DiaryAPI.deleteTemplate(selected);
      setSelected(null);
      setContent('');
      await loadTemplates();
    } catch (e) {
      console.error('删除模板失败:', e);
    }
  };

  useEffect(() => {
    if (isCreating && nameInputRef.current) nameInputRef.current.focus();
  }, [isCreating]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[200] flex items-center justify-center"
          onClick={onClose}
        >
          <div className="absolute inset-0 bg-black/5 backdrop-blur-xl" />

          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
            onClick={e => e.stopPropagation()}
            className="relative w-[720px] h-[500px] bg-white/85 backdrop-blur-2xl rounded-[28px] shadow-[0_20px_60px_-10px_rgba(0,0,0,0.12)] border border-white/60 flex overflow-hidden"
          >
            {/* 左侧：模板列表 */}
            <div className="w-[220px] border-r border-black/[0.04] flex flex-col">
              <div className="px-5 py-4 flex items-center justify-between border-b border-black/[0.04]">
                <span className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.2em]">模板</span>
                <button
                  onClick={() => setIsCreating(true)}
                  className="p-1.5 rounded-lg hover:bg-black/[0.04] text-gray-400 hover:text-gray-600 transition-all"
                >
                  <Plus size={14} />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto py-2">
                {/* 新建输入 */}
                {isCreating && (
                  <div className="px-3 py-1.5">
                    <input
                      ref={nameInputRef}
                      value={newName}
                      onChange={e => setNewName(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') handleCreate();
                        if (e.key === 'Escape') { setIsCreating(false); setNewName(''); }
                      }}
                      onBlur={() => { if (!newName.trim()) setIsCreating(false); }}
                      placeholder="模板名称"
                      maxLength={20}
                      className="w-full px-3 py-2 text-[12px] rounded-lg bg-black/[0.03] border border-black/[0.06] outline-none focus:border-black/[0.12] transition-colors"
                    />
                  </div>
                )}

                {templates.map(name => (
                  <button
                    key={name}
                    onClick={() => setSelected(name)}
                    className={`w-full text-left px-5 py-2.5 text-[12px] transition-all flex items-center gap-2.5 ${
                      selected === name
                        ? 'bg-black/[0.05] text-gray-800 font-medium'
                        : 'text-gray-500 hover:bg-black/[0.02] hover:text-gray-700'
                    }`}
                  >
                    <FileText size={13} className="opacity-30 shrink-0" />
                    <span className="truncate">{name}</span>
                  </button>
                ))}

                {!loading && templates.length === 0 && !isCreating && (
                  <p className="px-5 py-8 text-[11px] text-gray-300 text-center italic">暂无模板</p>
                )}
              </div>
            </div>

            {/* 右侧：内容编辑 */}
            <div className="flex-1 flex flex-col">
              <div className="px-5 py-4 flex items-center justify-between border-b border-black/[0.04]">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] text-gray-700 font-serif italic">
                    {selected || '选择模板'}
                  </span>
                  {saving && (
                    <span className="text-[9px] text-gray-300 tracking-wider">保存中...</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {selected && onApplyTemplate && (
                    <button
                      onClick={() => { onApplyTemplate(content); onClose(); }}
                      className="px-3 py-1.5 text-[10px] rounded-lg bg-black/[0.04] text-gray-500 hover:bg-black/[0.08] hover:text-gray-700 transition-all tracking-wider"
                    >
                      应用到日记
                    </button>
                  )}
                  {selected && (
                    <button
                      onClick={handleDelete}
                      className="p-1.5 rounded-lg text-gray-300 hover:text-red-400 hover:bg-red-50 transition-all"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                  <button
                    onClick={onClose}
                    className="p-1.5 rounded-lg text-gray-300 hover:text-gray-500 hover:bg-black/[0.04] transition-all"
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>

              <div className="flex-1 p-5 overflow-hidden">
                {selected ? (
                  <textarea
                    value={content}
                    onChange={e => handleContentChange(e.target.value)}
                    placeholder="在此编辑模板内容..."
                    className="w-full h-full text-[14px] leading-[1.8] text-gray-700 bg-transparent border-none outline-none resize-none font-serif placeholder-gray-300"
                  />
                ) : (
                  <div className="h-full flex items-center justify-center">
                    <p className="text-[12px] text-gray-300 italic">选择或创建一个模板</p>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default TemplateManager;
