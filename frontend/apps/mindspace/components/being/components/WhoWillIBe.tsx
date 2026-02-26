import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Plus, ChevronRight, Edit3, Trash2, ShieldCheck, Target, ChevronLeft } from 'lucide-react';

// --- 类型定义 ---
export interface BubbleData {
  id: number;
  text: string;
  subtext?: string; 
  x: number;
  y: number;
  rotate: number;
  scale: number;
  type: 'vision' | 'commitment';
}

// --- 气泡组件 ---
const Bubble: React.FC<{ 
  data: BubbleData; 
  isStructured: boolean;
  onEdit?: (data: BubbleData) => void;
}> = ({ data, isStructured, onEdit }) => {
  return (
    <motion.div
      layout
      layoutId={String(data.id)}
      initial={{ scale: 0, opacity: 0 }}
      animate={{ 
        scale: isStructured ? 1 : data.scale, 
        opacity: isStructured ? (data.type === 'vision' ? 0.5 : 1) : 0.9, 
        rotate: isStructured ? 0 : data.rotate,
        x: isStructured ? 0 : data.x,
        y: isStructured ? 0 : data.y
      }}
      exit={{ opacity: 0, scale: 0.5 }}
      transition={{ type: 'spring', stiffness: 200, damping: 25 }}
      
      drag={!isStructured}
      dragMomentum={true}
      dragElastic={0.1}
      whileDrag={{ scale: 1.1, zIndex: 100, cursor: 'grabbing' }}
      whileHover={!isStructured ? { scale: 1.05, zIndex: 50, cursor: 'grab' } : {}}

      className={`${isStructured ? 'relative w-full' : 'absolute pointer-events-auto touch-none'}`}
    >
      <div 
        className={`
          relative px-6 py-4 
          backdrop-blur-lg border transition-all duration-500
          rounded-[2rem] rounded-tr-sm shadow-sm
          flex flex-col items-center justify-center text-center w-full
          max-w-[220px] min-w-[100px]
          ${data.type === 'commitment' 
            ? 'bg-indigo-600/10 border-indigo-500/30 text-indigo-900 font-semibold shadow-indigo-100/50' 
            : 'bg-white/60 border-white/50 text-slate-700 font-medium'}
          ${isStructured ? 'cursor-default' : 'group cursor-grab active:cursor-grabbing hover:bg-white/90 hover:shadow-md'}
        `}
      >
        {/* 对齐 ReflectionTemplate 的 text-sm */}
        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words w-full select-none">{data.text}</p>
        {data.subtext && (
          <p className="text-[10px] mt-1.5 text-indigo-500 font-medium italic select-none">实现于: {data.subtext}</p>
        )}
        
        {!isStructured && onEdit && (
          <button
            onClick={(e) => { e.stopPropagation(); onEdit(data); }}
            className="absolute -right-3 -top-3 opacity-0 group-hover:opacity-100 bg-white p-2 rounded-full shadow-md border border-slate-100 text-slate-400 hover:text-indigo-600 transition-all z-10 hover:scale-110"
          >
            <Edit3 size={12} strokeWidth={2} />
          </button>
        )}
      </div>
    </motion.div>
  );
};

interface WhoWillIBeProps {
  onExit?: () => void;
}

// --- 主应用组件 ---
export default function WhoWillIBe({ onExit }: WhoWillIBeProps) {
  const [step, setStep] = useState(0); 
  const [visions, setVisions] = useState<BubbleData[]>([]);
  const [commitments, setCommitments] = useState<BubbleData[]>([]);
  const [isFinished, setIsFinished] = useState(false);
  
  const [inputA, setInputA] = useState(''); 
  const [inputB, setInputB] = useState(''); 
  const [editingItem, setEditingItem] = useState<BubbleData | null>(null);

  const centerRef = useRef<HTMLDivElement>(null);

  // Adjusted generation to ensure outer ring placement and safety zone
  const createBubble = (text: string, subtext: string = '', type: 'vision' | 'commitment'): BubbleData => {
    const w = typeof window !== 'undefined' ? window.innerWidth : 1000;
    const h = typeof window !== 'undefined' ? window.innerHeight : 800;
    const shortSide = Math.min(w, h);

    // Max Radius (Outer)
    const margin = shortSide * 0.05;
    const bubbleHalfSize = 80;
    let maxRadius = (shortSide / 2) - margin - bubbleHalfSize;

    // Min Radius (Inner - Center Card)
    let minRadius = 140;
    if (centerRef.current) {
        const rect = centerRef.current.getBoundingClientRect();
        const halfW = rect.width / 2;
        const halfH = rect.height / 2;
        minRadius = Math.sqrt(halfW * halfW + halfH * halfH) + 40; 
    }

    if (maxRadius <= minRadius + 40) {
        maxRadius = minRadius + 60;
    }

    const angle = Math.random() * Math.PI * 2;
    const distance = minRadius + Math.random() * (maxRadius - minRadius);
    
    return {
      id: Math.random(),
      text,
      subtext,
      type,
      x: Math.cos(angle) * distance,
      y: Math.sin(angle) * distance,
      rotate: Math.random() * 8 - 4,
      scale: 0.9 + Math.random() * 0.15,
    };
  };

  const handleAdd = () => {
    if (!inputA.trim()) return;
    if (step === 0) {
      setVisions([...visions, createBubble(inputA, '', 'vision')]);
      setInputA('');
    } else {
      if (!inputB.trim()) return; 
      setCommitments([...commitments, createBubble(inputA, inputB, 'commitment')]);
      setInputA('');
      setInputB('');
    }
  };

  const handleUpdate = () => {
    if (!editingItem) return;
    const updater = (list: BubbleData[]) => list.map(item => item.id === editingItem.id ? editingItem : item);
    if (editingItem.type === 'vision') setVisions(updater(visions));
    else setCommitments(updater(commitments));
    setEditingItem(null);
  };

  const handleDelete = (id: number, type: 'vision' | 'commitment') => {
    if (type === 'vision') setVisions(visions.filter(v => v.id !== id));
    else setCommitments(commitments.filter(c => c.id !== id));
    setEditingItem(null);
  };

  const handleBack = () => {
    if (step > 0) {
      setStep(step - 1);
    }
  };

  const jumpToStep = (targetStep: number) => {
    if (targetStep < step) {
        setStep(targetStep);
    }
  }

  if (isFinished) {
    return (
      <div className="fixed inset-0 z-[200] bg-gradient-to-br from-indigo-50 to-white flex items-center justify-center p-6 font-sans">
        <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="max-w-sm w-full text-center space-y-10">
          <div className="w-20 h-20 bg-indigo-600/10 rounded-full flex items-center justify-center mx-auto border border-indigo-100 shadow-xl">
            <ShieldCheck size={40} className="text-indigo-600" strokeWidth={1.5} />
          </div>
          <div className="space-y-4">
            <h2 className="text-4xl font-light text-slate-800 tracking-tight">星辰已定 / The Seal</h2>
            <p className="text-slate-500 font-light text-sm leading-relaxed">愿每一份坚持，都能照亮你前行的路。</p>
          </div>
          <div className="flex flex-col gap-4 pt-4">
            <button onClick={() => { setStep(0); setIsFinished(false); setVisions([]); setCommitments([]); }} className="w-full py-4 bg-slate-900 text-white rounded-full text-xs font-bold tracking-[0.2em] uppercase shadow-2xl hover:bg-slate-800 transition-all hover:scale-105 active:scale-95">重新开启旅程</button>
            <button onClick={onExit} className="w-full py-4 bg-transparent text-slate-400 hover:text-slate-600 rounded-full text-xs font-bold tracking-[0.2em] uppercase transition-all">退出</button>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[200] w-full h-full flex items-center justify-center overflow-hidden font-sans bg-white">
      <div className={`absolute inset-0 -z-10 bg-gradient-to-br transition-all duration-1000 ${step === 0 ? 'from-violet-50 to-fuchsia-50' : 'from-indigo-50 to-emerald-50'}`} />
      
      {/* 退出按钮 - 对齐 ReflectionTemplate */}
      <button 
        onClick={onExit}
        className="absolute top-6 right-6 z-50 p-2 rounded-full bg-white/40 hover:bg-white/80 transition-colors backdrop-blur-sm"
      >
        <X size={24} className="text-slate-600" />
      </button>

      {/* 结构化视图 (Step 1) - 容器加宽以适应更大的气泡 */}
      <AnimatePresence>
        {step === 1 && (
          <div className="absolute inset-0 flex justify-between px-6 md:px-20 py-28 pointer-events-none z-10">
            {/* 左侧：愿景栏 (Blueprint) */}
            <motion.div 
              initial={{ x: -100, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              className="w-48 md:w-72 flex flex-col gap-5 overflow-y-auto no-scrollbar pointer-events-auto pr-4"
            >
              <span className="text-[10px] font-bold tracking-widest text-slate-400 uppercase mb-2 sticky top-0 bg-transparent backdrop-blur-sm pb-2 z-10">愿景 / Visions</span>
              {visions.map((v) => (
                <Bubble key={v.id} data={v} isStructured={true} />
              ))}
            </motion.div>

            {/* 右侧：承诺栏 (Covenants) */}
            <motion.div 
              initial={{ x: 100, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              className="w-48 md:w-72 flex flex-col gap-5 overflow-y-auto no-scrollbar pointer-events-auto pl-4 items-end"
            >
              <span className="text-[10px] font-bold tracking-widest text-indigo-400 uppercase mb-2 sticky top-0 bg-transparent backdrop-blur-sm pb-2 z-10 w-full text-right">承诺 / Commitments</span>
              {commitments.map((c) => (
                <Bubble key={c.id} data={c} isStructured={true} />
              ))}
              {commitments.length === 0 && (
                <div className="w-full border-2 border-dashed border-indigo-100 rounded-[2rem] h-32 flex items-center justify-center text-indigo-300 text-xs italic p-6 text-center">
                  等待你的第一个承诺...
                </div>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* 自由气泡区域 (Step 0) */}
      {step === 0 && (
        <div className="absolute inset-0 z-0 flex items-center justify-center pointer-events-none">
          <AnimatePresence>
            {visions.map((data) => (
              <Bubble key={data.id} data={data} isStructured={false} onEdit={setEditingItem} />
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* 核心交互区域 */}
      <main className="relative z-20 w-full max-w-xl px-6 flex flex-col items-center">
        <motion.div 
            layout 
            ref={centerRef} 
            className="w-full flex flex-col items-center space-y-8 rounded-3xl p-4"
        >
          
          {/* 标题区域 - 对齐 ReflectionTemplate 的 4xl */}
          <div className="text-center space-y-3">
            <span className="text-[10px] tracking-[0.2em] text-slate-500 uppercase block font-medium">
              {step === 0 ? 'The Vision of Potential' : 'The Soul Covenant'}
            </span>
            <h2 className="text-4xl font-extralight text-slate-800 tracking-tight">
              {step === 0 ? 'Who will I be?' : 'The Commitment'}
            </h2>
          </div>

          <div className="w-full max-w-md space-y-4">
            <div className="flex flex-col space-y-4">
              {/* 输入框 A - 增大尺寸和字号 */}
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 rounded-2xl blur opacity-0 group-focus-within:opacity-100 transition duration-500"></div>
                <div className="relative bg-white/60 backdrop-blur-xl border border-white/50 rounded-2xl p-1.5 flex items-center shadow-sm">
                  <input
                    value={inputA}
                    onChange={(e) => setInputA(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && step === 0 && handleAdd()}
                    placeholder={step === 0 ? "我将成为..." : "我承诺会..."}
                    className="w-full bg-transparent px-5 py-4 outline-none text-lg font-light text-slate-700 placeholder:text-slate-400"
                  />
                  {step === 0 && (
                    <button 
                      onClick={handleAdd} 
                      className={`p-3 mr-1 rounded-xl transition-all duration-500 ${inputA.trim() ? 'bg-slate-800 text-white shadow-lg' : 'bg-slate-200/50 text-slate-400 opacity-50'}`}
                    >
                      <Plus size={20} />
                    </button>
                  )}
                </div>
              </div>

              {/* 输入框 B (Step 1 Only) */}
              {step === 1 && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="relative group">
                  <div className="relative bg-white/60 backdrop-blur-xl border border-white/50 rounded-2xl p-1.5 flex items-center shadow-sm">
                    <input
                      value={inputB}
                      onChange={(e) => setInputB(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
                      placeholder="实现时间？(如：2025、明年深秋...)"
                      className="w-full bg-transparent px-5 py-4 outline-none text-lg font-light text-slate-700 placeholder:text-slate-400"
                    />
                    <button 
                      onClick={handleAdd} 
                      className={`p-3 mr-1 rounded-xl transition-all duration-500 ${inputB.trim() ? 'bg-indigo-600 text-white shadow-lg' : 'bg-slate-200/50 text-slate-400 opacity-50'}`}
                    >
                      <Target size={20} />
                    </button>
                  </div>
                </motion.div>
              )}
            </div>

            <div className="flex flex-col items-center space-y-6 pt-4">
              
              <div className="flex gap-4">
                {step > 0 && (
                   <button
                    onClick={handleBack}
                    className="flex items-center space-x-2 text-sm font-light tracking-widest text-slate-400 hover:text-slate-600 transition-colors uppercase"
                   >
                      <ChevronLeft size={16} />
                      <span>Back</span>
                   </button>
                )}

                <button
                    onClick={() => step === 0 ? setStep(1) : setIsFinished(true)}
                    disabled={step === 0 && visions.length === 0}
                    className={`flex items-center space-x-2 text-sm font-light tracking-widest uppercase transition-all
                    ${(step === 0 && visions.length === 0) 
                        ? 'text-slate-300 cursor-not-allowed' 
                        : 'text-slate-600 hover:text-indigo-600'}
                    `}
                >
                    <span>{step === 0 ? 'Next Step' : (commitments.length === 0 ? 'Skip & Seal' : 'Seal Vision')}</span>
                    <ChevronRight size={16} />
                </button>
              </div>
              
              {/* New Progress Bar Style */}
              <div className="flex items-center gap-2">
                {[0, 1].map(i => {
                    const isActive = i === step;
                    const isPast = i < step;
                    const isFuture = i > step;
                    
                    return (
                        <button 
                            key={i}
                            onClick={() => {
                                if (isPast) jumpToStep(i);
                            }}
                            disabled={isFuture}
                            className={`
                                h-1.5 rounded-full transition-all duration-500 ease-out
                                ${isActive ? 'w-8 bg-slate-800' : 'w-1.5 bg-slate-300'}
                                ${isPast ? 'hover:bg-slate-400 cursor-pointer' : ''}
                                ${isFuture ? 'opacity-40 cursor-default' : ''}
                            `}
                        />
                    );
                })}
              </div>

            </div>
          </div>
        </motion.div>
      </main>

      <footer className="absolute bottom-8 w-full text-center pointer-events-none opacity-50">
        <p className="text-[9px] tracking-[0.4em] font-light uppercase text-slate-500">LifePrism • Design Your Soul</p>
      </footer>

      {/* 编辑弹窗 - 保持一致的圆角和阴影 */}
      <AnimatePresence>
        {editingItem && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[300] flex items-center justify-center p-6 bg-white/30 backdrop-blur-md">
            <div className="bg-white rounded-[2rem] p-8 w-full max-w-sm shadow-2xl border border-slate-100 flex flex-col space-y-6">
              <div className="flex justify-between items-center">
                <span className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">编辑条目</span>
                <button onClick={() => setEditingItem(null)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
              </div>
              <div>
                <textarea
                  autoFocus
                  value={editingItem.text}
                  onChange={(e) => setEditingItem({...editingItem, text: e.target.value})}
                  className="w-full h-32 p-4 bg-slate-50 border border-slate-200 rounded-xl resize-none text-lg text-slate-700 font-light focus:ring-1 focus:ring-indigo-200 outline-none"
                />
              </div>
              <div className="flex gap-4 pt-2 border-t border-slate-50">
                <button onClick={() => handleDelete(editingItem.id, editingItem.type)} className="flex items-center gap-2 px-4 py-2 text-xs font-bold text-rose-500 hover:bg-rose-50 rounded-lg transition-all uppercase tracking-wider">
                  <Trash2 size={14} /> 删除
                </button>
                <div className="flex-grow" />
                <button onClick={handleUpdate} className="px-6 py-2 bg-slate-800 text-white text-xs font-bold rounded-lg shadow-md hover:bg-slate-700 transition-all uppercase tracking-wider">保存</button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}