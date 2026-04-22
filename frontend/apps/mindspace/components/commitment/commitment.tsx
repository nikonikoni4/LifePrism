import React, { useState, useEffect, useCallback } from 'react';
import { X, ArrowRight, Trash2, Edit2, Compass, Wind, Droplets, Mountain, PenTool, Archive, RotateCcw } from 'lucide-react';
import { CommitmentAPI, ValueAPI } from './commitmentApi';
import type { CommitmentItem, CommitmentStatus, UpdateCommitmentRequest, ValueOption } from './commitmentTypes';

interface CommitmentViewProps {
  onBack?: () => void;
  onNavigate?: (view: string) => void;
}

const CommitmentView: React.FC<CommitmentViewProps> = ({ onBack, onNavigate }) => {
  // ---------------- State ----------------
  const [commitments, setCommitments] = useState<CommitmentItem[]>([]);
  const [values, setValues] = useState<ValueOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [isAdding, setIsAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formValueId, setFormValueId] = useState<string>('');
  const [formAction, setFormAction] = useState('');

  // ---------------- Data Loading ----------------
  const fetchData = useCallback(async () => {
    try {
      const [cmtRes, valOpts] = await Promise.all([
        CommitmentAPI.getList(),
        ValueAPI.getOptions(),
      ]);
      setCommitments(cmtRes.items);
      setValues(valOpts);
    } catch (e: any) {
      setError(e.message || '数据加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Auto-dismiss error toast
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 3000);
    return () => clearTimeout(t);
  }, [error]);

  // ---------------- Handlers ----------------

  const handleAdd = async () => {
    if (!formValueId || !formAction.trim() || submitting) return;
    setSubmitting(true);
    try {
      await CommitmentAPI.create({ content: formAction.trim(), value_id: formValueId });
      resetForm();
      await fetchData();
    } catch (e: any) {
      setError(e.message || '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdate = async () => {
    if (!editingId || submitting) return;
    const original = commitments.find(c => c.id === editingId);
    if (!original) return;

    const patch: UpdateCommitmentRequest = {};
    if (formAction.trim() !== original.content) patch.content = formAction.trim();
    if (formValueId !== (original.value_id ?? '')) patch.value_id = formValueId;
    if (Object.keys(patch).length === 0) { resetForm(); return; }

    setSubmitting(true);
    try {
      await CommitmentAPI.update(editingId, patch);
      resetForm();
      await fetchData();
    } catch (e: any) {
      setError(e.message || '更新失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (submitting) return;
    if (!(await window.electronAPI.showConfirm({ message: '确定要放下这条承诺吗？' }))) return;
    setSubmitting(true);
    try {
      await CommitmentAPI.delete(id);
      await fetchData();
    } catch (e: any) {
      setError(e.message || '删除失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleComplete = async (id: string) => {
    if (submitting) return;
    const item = commitments.find(c => c.id === id);
    if (!item || item.status === 'archived') return;
    const newStatus: CommitmentStatus = item.status === 'completed' ? 'active' : 'completed';
    setSubmitting(true);
    try {
      await CommitmentAPI.update(id, { status: newStatus });
      await fetchData();
    } catch (e: any) {
      setError(e.message || '状态切换失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleArchive = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (submitting) return;
    const item = commitments.find(c => c.id === id);
    if (!item || item.status === 'completed') return;
    const newStatus: CommitmentStatus = item.status === 'archived' ? 'active' : 'archived';
    setSubmitting(true);
    try {
      await CommitmentAPI.update(id, { status: newStatus });
      await fetchData();
    } catch (e: any) {
      setError(e.message || '搁置切换失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleJumpToTarget = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (onNavigate) onNavigate('being');
  };

  const startEdit = (c: CommitmentItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(c.id);
    setFormValueId(c.value_id ?? '');
    setFormAction(c.content);
    setIsAdding(true);
  };

  const resetForm = () => {
    setIsAdding(false);
    setEditingId(null);
    setFormValueId('');
    setFormAction('');
  };

  // ---------------- Helpers ----------------

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  };

  const splitValue = (val: string) => {
    const limit = 2;
    return { core: val.slice(0, limit), extended: val.length > limit ? val.slice(limit) : null };
  };

  // ---------------- Render ----------------

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F2F4F1] flex items-center justify-center">
        <p className="font-ink text-lg text-[#6B7875] tracking-widest animate-pulse">观想中…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F2F4F1] text-[#2C3835] relative overflow-x-hidden font-sans selection:bg-[#A64B4B] selection:text-white">

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@300;400;600;900&family=Ma+Shan+Zheng&display=swap');
        .font-ink { font-family: 'Noto Serif SC', serif; }
        .font-brush { font-family: 'Ma Shan Zheng', cursive; }
        .vertical-text { writing-mode: vertical-rl; text-orientation: upright; letter-spacing: 0.3em; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: #BCC5C1; border-radius: 4px; }
      `}</style>

      {/* Error Toast */}
      {error && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-[200] px-6 py-3 bg-[#A64B4B] text-white rounded shadow-lg font-ink text-sm tracking-wide animate-in fade-in slide-in-from-top-2 duration-300">
          {error}
        </div>
      )}

      {/* Exit Button */}
      {onBack && (
        <button onClick={onBack} className="fixed top-6 right-6 z-40 p-2 rounded-full bg-[#2C3835]/5 hover:bg-[#2C3835]/10 text-[#2C3835] transition-colors" title="返回">
          <X size={24} />
        </button>
      )}

      <div className="fixed inset-0 pointer-events-none z-0 bg-gradient-to-br from-[#F8FAF9] to-[#E6E8E5]" />

      {/* Main Layout */}
      <div className="relative z-10 flex min-h-screen">
        {/* Left Pillar */}
        <aside className="hidden md:flex w-32 lg:w-40 flex-col items-center py-12 border-r border-[#2C3835]/10 fixed h-full bg-[#F2F4F1]/40">
          <div className="flex-1 flex flex-col items-center justify-center space-y-12">
            <div className="vertical-text font-ink font-black text-3xl tracking-[0.5em] text-[#2C3835] opacity-90">接纳承诺</div>
            <div className="w-[1px] h-24 bg-[#2C3835]/20"></div>
            <div className="vertical-text font-ink text-sm text-[#6B7875]">观想 · 觉察 · 行动</div>
          </div>
          <div className="mt-auto pb-8">
            <div className="w-8 h-8 rounded-full border border-[#2C3835] flex items-center justify-center opacity-40">
              <span className="font-serif text-xs">{commitments.length}</span>
            </div>
          </div>
        </aside>

        {/* Content */}
        <main className="flex-1 md:ml-32 lg:ml-40 min-h-screen">
          <div className="max-w-5xl mx-auto px-6 py-12 md:py-24 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <header className="md:hidden mb-16 text-center">
              <h1 className="font-brush text-5xl text-[#2C3835] mb-4">接纳承诺</h1>
              <p className="font-ink text-xs tracking-widest text-[#6B7875]">叶随流水意，心随承诺行</p>
            </header>

            <section className="mb-20 md:pl-12 opacity-80">
              <div className="flex gap-4 text-[#3A4A45] mb-6">
                <Wind size={20} strokeWidth={1} /><Droplets size={20} strokeWidth={1} /><Mountain size={20} strokeWidth={1} />
              </div>
              <p className="font-ink text-lg md:text-xl leading-loose max-w-2xl text-[#3A4A45]">
                想象你的思绪如同溪流落叶。与其试图阻挡水流，不如观察它们缓缓飘过。<br/>在这静谧之处，种下你的承诺。
              </p>
            </section>

            {/* Card List */}
            <div className="space-y-12 md:pl-8 pb-32">
              {commitments.map((item) => {
                const valueLabel = item.value_keywords ?? '未关联';
                const { core, extended } = splitValue(valueLabel);
                const isCompleted = item.status === 'completed';
                const isArchived = item.status === 'archived';

                return (
                  <div
                    key={item.id}
                    onClick={() => handleToggleComplete(item.id)}
                    className={`group relative pl-8 md:pl-12 py-2 transition-all duration-500 ease-out ${
                      isArchived ? 'opacity-40 cursor-default' : 'cursor-pointer'
                    } ${isCompleted ? 'opacity-60 grayscale-[0.8]' : ''}`}
                  >
                    <div className="absolute left-0 top-0 bottom-0 w-[1px] bg-[#2C3835]/10 group-hover:bg-[#2C3835]/30 transition-colors duration-500"></div>
                    <div className={`absolute left-[-5px] top-8 w-[11px] h-[11px] rounded-full border border-[#F2F4F1] shadow-sm transition-all duration-500 z-10 ${
                      isCompleted ? 'bg-[#A64B4B] scale-75' : isArchived ? 'bg-[#BCC5C1] scale-75' : 'bg-[#4A635D] group-hover:scale-125'
                    }`}></div>

                    {/* Card Body */}
                    <div className={`relative p-8 md:p-10 rounded-sm transition-all duration-500 ${
                      isArchived ? 'bg-transparent border border-dashed border-[#2C3835]/20' :
                      isCompleted ? 'bg-transparent translate-x-4' :
                      'bg-[#3A4A45] text-[#F2F4F1] hover:-translate-y-1 shadow-sm hover:shadow-lg'
                    }`}>
                      <div className="flex flex-col md:flex-row gap-6 md:gap-10 items-start">
                        {/* Left: Core Value */}
                        <div className="md:w-12 flex-shrink-0 pt-1">
                          <div className={`font-ink font-bold text-xl md:text-2xl tracking-widest md:vertical-text ${
                            isArchived ? 'text-[#2C3835]/40 italic' : isCompleted ? 'text-[#2C3835]' : 'text-[#A3B0AC]'
                          }`}>{core}</div>
                          {extended && <div className="mt-2 w-1 h-1 rounded-full bg-[#A64B4B] mx-auto opacity-60 md:block hidden"></div>}
                        </div>

                        {/* Right: Content */}
                        <div className="flex-1 space-y-4">
                          {extended && (
                            <div className={`inline-block mb-2 px-3 py-1 rounded-full text-xs font-ink tracking-widest ${
                              isCompleted ? 'bg-[#2C3835]/5 text-[#2C3835]/40' : isArchived ? 'bg-[#2C3835]/5 text-[#2C3835]/30' : 'bg-[#F2F4F1]/10 text-[#A3B0AC]'
                            }`}>延续 · {extended}</div>
                          )}
                          <p className={`font-ink text-lg md:text-xl leading-relaxed tracking-wide transition-all duration-500 ${
                            isArchived ? 'text-[#6B7875]/60 italic' :
                            isCompleted ? 'text-[#6B7875] line-through decoration-[#A64B4B]/30' :
                            'text-[#F0F2EF] font-light'
                          }`}>{item.content}</p>

                          <div className={`flex justify-between items-center pt-4 border-t ${
                            isCompleted || isArchived ? 'border-[#2C3835]/10' : 'border-[#F2F4F1]/10'
                          }`}>
                            <span className={`text-xs tracking-widest font-ink ${isCompleted ? 'text-[#A64B4B]' : 'text-[#8F9E99]'}`}>{formatDate(item.created_at)}</span>

                            <div className={`flex gap-4 ${isCompleted ? 'opacity-0' : 'opacity-0 group-hover:opacity-100'} transition-opacity duration-300`}>
                              {!isCompleted && !isArchived && (
                                <button onClick={(e) => startEdit(item, e)} className="text-[#8F9E99] hover:text-white transition-colors" title="修习"><Edit2 size={14} /></button>
                              )}
                              {!isCompleted && (
                                <button onClick={(e) => handleToggleArchive(item.id, e)} className="text-[#8F9E99] hover:text-[#BCC5C1] transition-colors" title={isArchived ? '恢复' : '搁置'}>
                                  {isArchived ? <RotateCcw size={14} /> : <Archive size={14} />}
                                </button>
                              )}
                              <button onClick={(e) => handleJumpToTarget(item.id, e)} className="text-[#8F9E99] hover:text-[#2C3835] transition-colors" title="定向"><Compass size={14} /></button>
                              <button onClick={(e) => handleDelete(item.id, e)} className="text-[#8F9E99] hover:text-[#FF9999] transition-colors" title="放下"><Trash2 size={14} /></button>
                            </div>
                          </div>
                        </div>

                        {/* Stamp */}
                        {isCompleted && (
                          <div className="absolute top-6 right-8 md:top-8 md:right-10 w-20 h-20 border-2 border-[#A64B4B] flex flex-col items-center justify-center pointer-events-none opacity-80 rotate-[-15deg] animate-in zoom-in duration-300">
                            <span className="font-brush text-[#A64B4B] text-2xl leading-none">行</span>
                            <span className="font-brush text-[#A64B4B] text-2xl leading-none">动</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Add Box */}
              <div onClick={() => setIsAdding(true)} className="group relative pl-8 md:pl-12 py-2 cursor-pointer">
                <div className="absolute left-0 top-0 bottom-0 w-[1px] bg-[#2C3835]/10"></div>
                <div className="absolute left-[-5px] top-8 w-[11px] h-[11px] rounded-full border border-[#2C3835]/20 bg-[#F2F4F1] group-hover:bg-[#4A635D] transition-all duration-300"></div>
                <div className="relative p-10 md:p-14 border border-dashed border-[#2C3835]/20 rounded-sm bg-[#2C3835]/[0.02] hover:bg-[#2C3835]/[0.05] transition-all duration-300 flex flex-col items-center justify-center space-y-4">
                  <PenTool size={28} strokeWidth={1} className="text-[#2C3835]/30 group-hover:text-[#2C3835]/60 transition-all mb-2" />
                  <div className="font-brush text-3xl text-[#2C3835]/40 group-hover:text-[#2C3835]/80 transition-colors">起愿 · 落笔</div>
                  <p className="font-ink text-sm tracking-[0.3em] text-[#6B7875]/40 group-hover:text-[#6B7875]/80">在此刻，种下新的承诺</p>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Slide-in Form */}
      <div className={`fixed inset-0 z-50 flex justify-end transition-opacity duration-300 ${isAdding ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none delay-100'}`}>
        <div className="absolute inset-0 bg-[#2C3835]/40" onClick={resetForm}></div>
        <div className={`relative w-full md:w-[600px] h-full bg-[#F2F4F1] shadow-[-20px_0_60px_rgba(0,0,0,0.2)] flex flex-col transform transition-transform duration-500 ${isAdding ? 'translate-x-0' : 'translate-x-full'}`}>
          <div className="relative z-10 p-12 h-full flex flex-col">
            <div className="flex justify-between items-center mb-16">
              <h2 className="font-brush text-4xl text-[#2C3835]">{editingId ? '修习' : '起愿'}</h2>
              <button onClick={resetForm} className="p-2 hover:bg-[#2C3835]/5 rounded-full transition-colors"><X size={24} className="text-[#6B7875]" /></button>
            </div>
            <div className="space-y-16 flex-1">
              <div className="group">
                <label className="block font-ink text-[#A64B4B] text-sm tracking-widest mb-4 opacity-70">价值 · VALUE</label>
                {values.length > 0 ? (
                  <select
                    value={formValueId}
                    onChange={(e) => setFormValueId(e.target.value)}
                    className="w-full bg-transparent border-b border-[#2C3835]/20 py-4 font-ink font-bold text-3xl text-[#2C3835] focus:outline-none focus:border-[#2C3835] appearance-none cursor-pointer"
                    autoFocus
                  >
                    <option value="">选择价值…</option>
                    {values.map(v => <option key={v.id} value={v.id}>{v.keywords}</option>)}
                  </select>
                ) : (
                  <p className="font-ink text-lg text-[#6B7875]/60 py-4 border-b border-[#2C3835]/10">暂无价值，请先创建</p>
                )}
              </div>
              <div className="group">
                <label className="block font-ink text-[#A64B4B] text-sm tracking-widest mb-4 opacity-70">行动 · ACTION</label>
                <textarea value={formAction} onChange={(e) => setFormAction(e.target.value)} rows={4} className="w-full bg-transparent border-b border-[#2C3835]/20 py-4 font-ink text-xl text-[#3A4A45] placeholder-[#BCC5C1] focus:outline-none focus:border-[#2C3835] resize-none leading-loose" placeholder="此刻，我承诺…" />
              </div>
            </div>
            <div className="mt-auto flex justify-end">
              <button
                onClick={editingId ? handleUpdate : handleAdd}
                disabled={!formValueId || !formAction.trim() || submitting}
                className="group relative px-10 py-4 bg-[#2C3835] text-[#F2F4F1] overflow-hidden disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <div className="absolute inset-0 w-0 bg-[#4A635D] transition-all duration-[250ms] group-hover:w-full"></div>
                <span className="relative font-ink tracking-[0.2em] flex items-center gap-4">
                  {submitting ? '落笔中…' : editingId ? '更正' : '落笔'} <ArrowRight size={16} />
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CommitmentView;
