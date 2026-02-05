
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Plus, ChevronRight, ChevronLeft, SunMedium, Sparkles, Edit3, Save, RotateCcw, Trash2, Moon, Sun, Cloud } from 'lucide-react';

// --- 工具函数：稳健的色彩插值 ---
const lerpColor = (color1, color2, factor) => {
  const parseHex = (hex) => {
    const c = hex.replace('#', '');
    return {
      r: parseInt(c.substring(0, 2), 16),
      g: parseInt(c.substring(2, 4), 16),
      b: parseInt(c.substring(4, 6), 16)
    };
  };

  const c1 = parseHex(color1);
  const c2 = parseHex(color2);

  const r = Math.round(c1.r + (c2.r - c1.r) * factor);
  const g = Math.round(c1.g + (c2.g - c1.g) * factor);
  const b = Math.round(c1.b + (c2.b - c1.b) * factor);

  return `rgb(${r}, ${g}, ${b})`;
};

// --- 核心算法：左上角破晓光影渲染器 ---
const generateGradient = (progress, stageId) => {
  if (stageId === 'input') return '#010409';

  const colors = {
    void: '#000000',
    deepNight: '#020617',
    dawnPurple: '#1e1b4b',
    horizonGold: '#f59e0b',
    skyBlue: '#3b82f6',
    pureLight: '#f8fafc'
  };

  // 扩展半径计算：从左上角扩散
  const lightRadius = -30 + (progress * 170);
  const glowEdge = lightRadius + 60; 

  const coreColor = lerpColor(colors.horizonGold, colors.pureLight, progress);
  const midColor = lerpColor(colors.dawnPurple, colors.skyBlue, progress);
  const outerColor = lerpColor(colors.void, colors.deepNight, progress);

  return `radial-gradient(circle at 0% 0%, 
    ${coreColor} 0%, 
    ${midColor} ${lightRadius}%, 
    ${outerColor} ${glowEdge}%, 
    ${colors.void} 100%
  )`;
};

// --- 基础模版组件 ---
const ReflectionTemplate = ({
  onExit,
  onRestart,
  onBack,
  onNext,
  onAddAnswer,
  onUpdateAnswer,
  onDeleteAnswer,
  onUpdateSentiment,
  answers,
  currentStage,
  isFinished,
  renderFinishedScreen,
  headerTitle = "LifePrism • Reflection",
  footerText = "Explore your inner universe",
  centerRef
}) => {
  const [internalInput, setInternalInput] = useState('');
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [isEditingModal, setIsEditingModal] = useState(false);
  const [editText, setEditText] = useState('');
  const [activeMenuId, setActiveMenuId] = useState(null); 
  
  const isLightMode = currentStage.isLightMode;
  const isAlchemyStage = currentStage.id === 'alchemy';

  // 这里的 gradientString 作为背景层的 Key
  const gradientString = generateGradient(currentStage.progress || 0, currentStage.id);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAdd();
    }
  };

  const handleAdd = () => {
    if (!internalInput.trim()) return;
    onAddAnswer(internalInput);
    setInternalInput('');
  };

  const handleSaveEdit = () => {
    if (selectedAnswer && editText.trim()) {
      onUpdateAnswer(selectedAnswer.id, editText);
      setIsEditingModal(false);
      setSelectedAnswer(null);
    }
  };

  return (
    <div 
      className="fixed inset-0 w-full h-full flex flex-col items-center justify-center overflow-hidden font-sans select-none bg-black"
      onClick={() => setActiveMenuId(null)} 
    >
      {/* 核心：动态背景交叉淡化层 */}
      <div className="absolute inset-0 z-0">
        <AnimatePresence>
          <motion.div
            key={gradientString}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1, ease: "easeInOut" }}
            style={{ background: gradientString }}
            className="absolute inset-0"
          />
        </AnimatePresence>
        {/* 微弱噪点纹理增加质感 */}
        <div className="absolute inset-0 opacity-[0.03] pointer-events-none bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />
      </div>

      {/* 顶部退出按钮 (Changed from Restart to Close) */}
      <button 
        onClick={onExit}
        className={`absolute top-6 right-6 z-[100] p-2.5 rounded-full transition-all backdrop-blur-md active:scale-90 ${isLightMode ? 'bg-slate-800/5 hover:bg-slate-800/10 text-slate-600' : 'bg-white/10 hover:bg-white/20 text-white/70'}`}
      >
        <X size={18} />
      </button>

      <header className="absolute top-12 w-full text-center z-10 pointer-events-none">
        <h1 className={`text-[9px] tracking-[0.8em] font-light uppercase transition-all duration-1000 ${isLightMode ? 'text-slate-800 opacity-40' : 'text-white opacity-30'}`}>
          {headerTitle}
        </h1>
      </header>

      {/* 气泡渲染层 */}
      <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
        <AnimatePresence mode="popLayout">
          {!isFinished && answers.map((ans, idx) => {
            const isActive = activeMenuId === ans.id;
            return (
              <motion.div
                key={ans.id}
                layout
                initial={{ x: ans.x, y: ans.y, scale: 0, opacity: 0 }}
                animate={{ 
                  x: ans.x, 
                  y: ans.y, 
                  scale: 1, 
                  opacity: 0.9, 
                  zIndex: isActive ? 100 : 10 
                }}
                exit={{ opacity: 0, scale: 0, filter: 'blur(20px)' }}
                drag={!isAlchemyStage}
                dragMomentum={true}
                dragElastic={0.1}
                className="absolute pointer-events-auto touch-none"
              >
                <div className="relative group">
                  <motion.div 
                    onClick={(e) => {
                      e.stopPropagation();
                      if (isAlchemyStage) setActiveMenuId(isActive ? null : ans.id);
                    }}
                    whileHover={isAlchemyStage ? { scale: 1.05 } : {}}
                    className={`
                      relative px-6 py-4 backdrop-blur-3xl border rounded-[2rem] rounded-tr-sm text-sm font-light shadow-2xl transition-all duration-700
                      max-w-[200px] min-w-[90px] text-center
                      ${!isAlchemyStage ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer'}
                      ${ans.sentiment === 'good' ? 'bg-white/95 text-blue-900 border-blue-100' : 
                        ans.sentiment === 'neutral' ? 'bg-sky-100/70 text-sky-900 border-sky-200' : 
                        'bg-slate-900/50 text-slate-100 border-white/10'}
                    `}
                  >
                    <span className="absolute top-2.5 left-4 text-[8px] font-bold opacity-20 italic">
                       #{idx + 1}
                    </span>
                    <p className="line-clamp-4 leading-relaxed break-words pointer-events-none">
                      {ans.text}
                    </p>
                    
                    {!isAlchemyStage && (
                      <div className="absolute -right-12 top-1/2 -translate-y-1/2 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-all duration-300 z-50">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedAnswer(ans);
                            setEditText(ans.text);
                            setIsEditingModal(true);
                          }}
                          className={`p-2 rounded-full shadow-xl border transition-all hover:scale-105 ${isLightMode ? 'bg-white text-slate-500 border-slate-100 hover:text-indigo-600' : 'bg-slate-800 text-white/70 border-white/10 hover:text-white'}`}
                          title="Edit"
                        >
                           <Edit3 size={12} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteAnswer(ans.id);
                          }}
                          className={`p-2 rounded-full shadow-xl border transition-all hover:scale-105 ${isLightMode ? 'bg-white text-slate-500 border-slate-100 hover:text-rose-500' : 'bg-slate-800 text-white/70 border-white/10 hover:text-rose-400'}`}
                          title="Delete"
                        >
                           <Trash2 size={12} />
                        </button>
                      </div>
                    )}
                  </motion.div>

                  {/* 炼金转换菜单 */}
                  <AnimatePresence>
                    {isAlchemyStage && isActive && (
                      <motion.div 
                        initial={{ opacity: 0, scale: 0.8, y: 15 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.8, y: 15 }}
                        className="absolute -top-16 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-white/10 backdrop-blur-3xl border border-white/20 rounded-full p-1 shadow-2xl z-[110]"
                      >
                        {[
                          { id: 'bad', icon: Moon, color: 'hover:text-purple-400' },
                          { id: 'neutral', icon: Cloud, color: 'hover:text-sky-400' },
                          { id: 'good', icon: Sun, color: 'hover:text-yellow-400' }
                        ].map((opt) => (
                          <button
                            key={opt.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              onUpdateSentiment(ans.id, opt.id);
                              setActiveMenuId(null);
                            }}
                            className={`p-2.5 rounded-full transition-all ${ans.sentiment === opt.id ? 'bg-white text-slate-900 scale-110 shadow-lg' : 'text-white/60 ' + opt.color}`}
                          >
                            <opt.icon size={16} />
                          </button>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* 编辑弹窗 */}
      <AnimatePresence>
        {isEditingModal && selectedAnswer && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[120] flex items-center justify-center p-6 bg-black/40 backdrop-blur-xl"
            onClick={() => setIsEditingModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, y: 30 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 30 }}
              onClick={(e) => e.stopPropagation()}
              className={`relative w-full max-w-md rounded-[2.5rem] shadow-3xl p-10 border flex flex-col ${isLightMode ? 'bg-white/95 border-white' : 'bg-slate-900/90 border-white/10'}`}
            >
              <span className={`text-[10px] font-bold tracking-[0.4em] uppercase mb-8 opacity-40 text-center ${isLightMode ? 'text-black' : 'text-white'}`}>Edit Fragment</span>
              <textarea
                autoFocus
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                className={`w-full h-48 p-5 rounded-2xl resize-none outline-none text-lg font-light leading-relaxed mb-8 transition-colors ${isLightMode ? 'bg-slate-50 text-slate-800' : 'bg-white/5 text-white'}`}
              />
              <div className="flex justify-between items-center">
                <button 
                  onClick={() => { onDeleteAnswer(selectedAnswer.id); setIsEditingModal(false); }} 
                  className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-rose-500/60 hover:text-rose-500 transition-colors"
                >
                  <Trash2 size={14} className="inline mr-2" /> Delete
                </button>
                <div className="flex gap-4">
                  <button onClick={() => setIsEditingModal(false)} className={`px-5 py-2 text-[10px] font-bold uppercase tracking-widest ${isLightMode ? 'text-slate-400' : 'text-white/40'}`}>Cancel</button>
                  <button onClick={handleSaveEdit} className={`px-8 py-3 rounded-xl text-[10px] font-bold uppercase tracking-widest shadow-xl active:scale-95 transition-all ${isLightMode ? 'bg-slate-900 text-white' : 'bg-white text-slate-900'}`}>Save</button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 主操作区域 */}
      <main className="relative z-20 w-full max-w-xl px-6 pointer-events-auto flex flex-col items-center">
        <AnimatePresence mode="wait">
          {!isFinished ? (
            <motion.div
              key={currentStage.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="flex flex-col items-center w-full"
            >
              <div 
                ref={centerRef} 
                className="w-full flex flex-col items-center rounded-3xl"
              >
                <div className="text-center space-y-4 mb-12 pointer-events-none">
                  <span className={`text-[9px] tracking-[0.4em] uppercase block opacity-60 font-medium ${isLightMode ? 'text-slate-500' : 'text-white'}`}>
                    {currentStage.sub}
                  </span>
                  <h2 className={`text-5xl font-extralight tracking-tighter transition-all duration-1000 ${isLightMode ? 'text-slate-900' : 'text-white'}`}>
                    {currentStage.title}
                  </h2>
                </div>

                {!currentStage.isInputDisabled && (
                  <div className="w-full max-w-[300px] bg-white/5 border border-white/10 backdrop-blur-2xl rounded-2xl p-1.5 flex items-center mb-12 shadow-2xl transition-all focus-within:ring-1 focus-within:ring-white/20">
                    <input
                      type="text"
                      value={internalInput}
                      onChange={(e) => setInternalInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder={currentStage.placeholder}
                      className="w-full bg-transparent px-4 py-3 outline-none text-white text-sm font-light placeholder:text-white/20"
                    />
                    <button 
                      onClick={handleAdd} 
                      disabled={!internalInput.trim()}
                      className={`p-2.5 rounded-xl transition-all active:scale-90 ${internalInput.trim() ? 'bg-white text-black shadow-lg shadow-white/10' : 'bg-white/5 text-white/20'}`}
                    >
                      <Plus size={16} />
                    </button>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-12 mt-8">
                {onBack && currentStage.id !== 'input' && (
                  <button 
                    onClick={onBack}
                    className={`group flex items-center space-x-3 text-[10px] tracking-[0.4em] uppercase transition-all ${isLightMode ? 'text-slate-400 hover:text-black' : 'text-white/40 hover:text-white'}`}
                  >
                    <ChevronLeft size={12} className="group-hover:-translate-x-1 transition-transform" />
                    <span>Back</span>
                  </button>
                )}

                <button 
                  onClick={onNext} 
                  disabled={currentStage.isNextDisabled}
                  className={`group flex items-center space-x-3 text-[10px] tracking-[0.4em] uppercase transition-all ${currentStage.isNextDisabled ? 'opacity-20 cursor-not-allowed' : (isLightMode ? 'text-slate-400 hover:text-black' : 'text-white/40 hover:text-white')}`}
                >
                  <span>{currentStage.nextButtonLabel}</span>
                  <ChevronRight size={12} className="group-hover:translate-x-1 transition-transform" />
                </button>
              </div>

            </motion.div>
          ) : (
            <div>{renderFinishedScreen()}</div>
          )}
        </AnimatePresence>
      </main>

      <footer className="absolute bottom-12 w-full text-center z-10 opacity-30 pointer-events-none">
        <p className={`text-[9px] tracking-[0.6em] font-light uppercase ${isLightMode ? 'text-slate-900' : 'text-white'}`}>{footerText}</p>
      </footer>
    </div>
  );
};

// --- 容器组件 ---
const WhoWasIReflection = ({ onExit }) => {
  const [stageIndex, setStageIndex] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [isFinished, setIsFinished] = useState(false);
  const centerRef = useRef(null);

  const progress = useMemo(() => {
    if (answers.length === 0) return 0;
    const score = answers.reduce((acc, a) => {
      if (a.sentiment === 'good') return acc + 1;
      if (a.sentiment === 'neutral') return acc + 0.45;
      return acc;
    }, 0);
    return score / answers.length;
  }, [answers]);

  const currentStageId = stageIndex === 0 ? 'input' : 'alchemy';

  const handleAddAnswer = useCallback((text) => {
    const w = typeof window !== 'undefined' ? window.innerWidth : 1000;
    const h = typeof window !== 'undefined' ? window.innerHeight : 800;
    const shortSide = Math.min(w, h);

    // Max Radius
    const margin = shortSide * 0.05;
    const bubbleHalfSize = 80;
    let maxRadius = (shortSide / 2) - margin - bubbleHalfSize;

    // Min Radius from center card
    let minRadius = 160;
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
    const dist = minRadius + Math.random() * (maxRadius - minRadius);
    
    const newBubble = {
      id: Date.now(),
      text,
      x: Math.cos(angle) * dist,
      y: Math.sin(angle) * dist - 30, // Slight y offset for visual balance
      sentiment: 'bad'
    };
    setAnswers(prev => [...prev, newBubble]);
  }, []);

  const handleUpdateSentiment = (id, sentiment) => {
    setAnswers(prev => prev.map(a => a.id === id ? { ...a, sentiment } : a));
  };

  const handleUpdateAnswer = (id, text) => {
    setAnswers(prev => prev.map(a => a.id === id ? { ...a, text } : a));
  };

  const handleDeleteAnswer = (id) => {
    setAnswers(prev => prev.filter(a => a.id !== id));
  };

  const handleRestart = () => {
    setStageIndex(0);
    setAnswers([]);
    setIsFinished(false);
  };

  const handleBack = () => {
    if (stageIndex === 1) {
      setStageIndex(0);
    }
  };

  return (
    <ReflectionTemplate
      onExit={onExit} // Passed exit handler
      onRestart={handleRestart}
      onBack={handleBack}
      onNext={() => stageIndex === 0 ? (answers.length > 0 && setStageIndex(1)) : setIsFinished(true)}
      onAddAnswer={handleAddAnswer}
      onUpdateAnswer={handleUpdateAnswer}
      onDeleteAnswer={handleDeleteAnswer}
      onUpdateSentiment={handleUpdateSentiment}
      answers={answers}
      currentStage={{
        id: currentStageId,
        title: stageIndex === 0 ? 'Who was I?' : 'Alchemy of Dawn',
        sub: stageIndex === 0 ? 'PAST IDENTITY • 过去的碎片' : 'RECONSTRUCTION • 破晓的炼金术',
        placeholder: '想起过去的自己是...',
        progress: progress,
        isInputDisabled: stageIndex === 1,
        isNextDisabled: stageIndex === 0 && answers.length === 0,
        isLightMode: progress > 0.6,
        nextButtonLabel: stageIndex === 0 ? 'Begin Alchemy' : 'Finish Transformation'
      }}
      isFinished={isFinished}
      renderFinishedScreen={() => (
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="text-center space-y-12 flex flex-col items-center">
          <div className="relative">
            <motion.div animate={{ scale: [1, 1.3, 1], rotate: 360 }} transition={{ duration: 15, repeat: Infinity, ease: "linear" }} className="absolute -inset-16 bg-blue-500/20 blur-[80px] rounded-full" />
            <div className={`w-32 h-32 rounded-full flex items-center justify-center backdrop-blur-3xl border shadow-3xl transition-all duration-1000 ${progress > 0.6 ? 'bg-white/60 border-white' : 'bg-white/10 border-white/20'}`}>
              <SunMedium size={60} className={progress > 0.6 ? "text-blue-500" : "text-yellow-200"} />
            </div>
          </div>
          <div className="space-y-4">
            <h2 className={`text-4xl font-extralight italic transition-colors ${progress > 0.6 ? 'text-black' : 'text-white'}`}>The Sun Rises Within</h2>
            <button onClick={handleRestart} className={`px-12 py-5 rounded-full font-bold uppercase text-[10px] tracking-[0.4em] shadow-2xl hover:scale-105 active:scale-95 transition-all ${progress > 0.6 ? 'bg-slate-900 text-white' : 'bg-white text-slate-900'}`}>Restart Journey</button>
          </div>
        </motion.div>
      )}
      centerRef={centerRef}
    />
  );
};

interface WhoWasIProps {
  onExit: () => void;
}

// --- 入口 App ---
export default function WhoWasI({ onExit }: WhoWasIProps) {
  return (
    <div className="min-h-screen bg-black text-white selection:bg-blue-500/30">
      <WhoWasIReflection onExit={onExit} />
    </div>
  );
}
