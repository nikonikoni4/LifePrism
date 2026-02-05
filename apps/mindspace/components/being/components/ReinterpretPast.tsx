import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence, Variants } from 'framer-motion';
import { X, HelpCircle, ArrowRight } from 'lucide-react';

interface ReinterpretPastProps {
  onExit: () => void;
}

interface AnswerData {
  event1: string;
  event2: string;
  event3: string;
  gain1: string;
  gain2: string;
  gain3: string;
  future1: string;
  future2: string;
  future3: string;
}

const ReinterpretPast: React.FC<ReinterpretPastProps> = ({ onExit }) => {
  const [step, setStep] = useState(1);
  const [showHelp, setShowHelp] = useState(false);
  const [answers, setAnswers] = useState<AnswerData>({
    event1: '', event2: '', event3: '',
    gain1: '', gain2: '', gain3: '',
    future1: '', future2: '', future3: ''
  });

  // Auto-show help on mount
  useEffect(() => {
    const timer = setTimeout(() => setShowHelp(true), 600);
    return () => clearTimeout(timer);
  }, []);

  const handleInput = (key: keyof AnswerData, value: string) => {
    setAnswers(prev => ({ ...prev, [key]: value }));
  };

  const autoGrow = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    e.target.style.height = 'auto';
    e.target.style.height = `${e.target.scrollHeight}px`;
    handleInput(e.target.name as keyof AnswerData, e.target.value);
  };

  const handleNext = (nextStep: number) => {
    if (nextStep === 3 && !answers.event1.trim()) {
      alert("请至少记录第一件事。");
      return;
    }
    setStep(nextStep);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // --- Animation Variants ---
  const fadeUp: Variants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.4, 0, 0.2, 1] } },
    exit: { opacity: 0, y: -20, transition: { duration: 0.4 } }
  };

  const modalVariants: Variants = {
    hidden: { scale: 0, opacity: 0, x: -100, y: -100 },
    visible: { scale: 1, opacity: 1, x: 0, y: 0, transition: { type: "spring", damping: 25, stiffness: 300 } },
    exit: { scale: 0, opacity: 0, x: -100, y: -100, transition: { duration: 0.4 } }
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5 }}
      className="fixed inset-0 z-[70] bg-[#fcfcf9] overflow-y-auto text-[#2c3e50] font-sans selection:bg-[#c9a063]/20 selection:text-[#2c3e50] no-scrollbar"
    >
      <style>{`
        .no-scrollbar::-webkit-scrollbar {
          display: none !important;
        }
        .no-scrollbar {
          -ms-overflow-style: none !important;
          scrollbar-width: none !important;
        }
        /* 针对 textarea 的额外处理 */
        textarea.no-scrollbar {
          overflow: hidden !important;
        }
      `}</style>
      
      {/* Background Breathing Glow */}
      <div className="fixed inset-0 pointer-events-none flex items-center justify-center -z-10">
          <motion.div 
            animate={{ opacity: [0.3, 0.6, 0.3] }}
            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
            className="w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,rgba(201,160,99,0.08)_0%,rgba(255,255,255,0)_70%)]"
          />
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 w-full px-6 md:px-10 py-6 flex justify-between items-center z-50 bg-[#fcfcf9]/80 backdrop-blur-sm">
        <div className="flex items-center space-x-4">
            <div className="text-xs uppercase tracking-widest font-bold text-slate-800">LifePrism</div>
            <div className="h-4 w-px bg-slate-200 mx-2 hidden sm:block"></div>
            <div className="text-xs font-mono opacity-50 tracking-tighter">
                {step === 5 ? 'DONE' : `0${step} / 04`}
            </div>
        </div>
        
        <div className="flex items-center space-x-4">
            <button 
                onClick={() => setShowHelp(true)} 
                className="text-xs font-semibold text-[#c9a063] hover:text-[#a07c45] flex items-center transition-colors uppercase tracking-wider px-3 py-1.5 rounded-full hover:bg-[#c9a063]/10"
            >
                <HelpCircle size={14} className="mr-1.5" />
                指南
            </button>
            <button onClick={onExit} className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-400 hover:text-slate-800">
                 <X size={20} />
            </button>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="max-w-3xl w-full mx-auto py-32 px-6 min-h-screen flex flex-col justify-center">
        <AnimatePresence mode="wait">
            
            {/* Step 1: Intro */}
            {step === 1 && (
                <motion.section key="step1" variants={fadeUp} initial="hidden" animate="visible" exit="exit" className="text-center">
                    <h1 className="font-serif text-4xl md:text-5xl mb-8 leading-tight text-slate-900">
                        放下过去，并不意味着遗忘。<br />
                        这只意味着，<span className="text-[#c9a063]">和过去和解</span>。
                    </h1>
                    <p className="text-[#7f8c8d] text-lg mb-12 max-w-xl mx-auto leading-relaxed font-light">
                        每一个曾让你感到寒冷的时刻，都藏着一颗通往未来的种子。
                    </p>
                    <button onClick={() => handleNext(2)} className="bg-[#2c3e50] text-white px-10 py-3 rounded-full font-medium tracking-widest hover:bg-black hover:scale-105 transition-all shadow-lg hover:shadow-xl">
                        开始重构
                    </button>
                </motion.section>
            )}

            {/* Step 2: Negative Events */}
            {step === 2 && (
                <motion.section key="step2" variants={fadeUp} initial="hidden" animate="visible" exit="exit">
                    <div className="mb-12 text-center md:text-left">
                        <h2 className="font-serif text-3xl mb-2 text-slate-900">第一步：列出三件重要的负面事件</h2>
        
                    </div>
                    <div className="space-y-12">
                        {[1, 2, 3].map((num) => (
                            <div key={`event${num}`} className="group">
                                <label className="text-[10px] uppercase tracking-widest text-[#c9a063] mb-2 block opacity-70 group-focus-within:opacity-100 transition-opacity">
                                    事件 0{num}
                                </label>
                                <textarea
                                    name={`event${num}`}
                                    className="w-full bg-transparent border-b border-slate-200 py-4 text-xl outline-none resize-none transition-colors focus:border-[#c9a063] font-serif placeholder:text-slate-300 placeholder:italic placeholder:font-sans no-scrollbar overflow-hidden"
                                    placeholder={num === 1 ? "在那段艰难的日子里，发生了什么？" : num === 2 ? "还有什么令你感到受挫的事？" : "第三件事。"}
                                    value={answers[`event${num}` as keyof AnswerData]}
                                    onChange={autoGrow}
                                    rows={1}
                                />
                            </div>
                        ))}
                    </div>
                    <div className="mt-16 flex justify-center">
                        <button onClick={() => handleNext(3)} className="bg-[#2c3e50] text-white px-10 py-3 rounded-full font-medium tracking-widest hover:bg-black hover:scale-105 transition-all shadow-lg hover:shadow-xl">
                            寻找收获
                        </button>
                    </div>
                </motion.section>
            )}

            {/* Step 3: Gains */}
            {step === 3 && (
                <motion.section key="step3" variants={fadeUp} initial="hidden" animate="visible" exit="exit">
                    <div className="mb-12">
                        <h2 className="font-serif text-3xl mb-4 text-slate-900">第二步：从中得到的正面收获</h2>
                        <p className="text-[#7f8c8d]">“痛苦是成长的外壳”。在这三件事中，你分别能得到什么？</p>
                    </div>
                    
                    <div className="space-y-10">
                        {[1, 2, 3].map((num) => {
                             const eventKey = `event${num}` as keyof AnswerData;
                             const gainKey = `gain${num}` as keyof AnswerData;
                             if (!answers[eventKey]) return null;

                             return (
                                <div key={gainKey} className="p-8 bg-white rounded-[20px] shadow-[0_4px_30px_rgba(0,0,0,0.03)] border border-white/50">
                                    <p className="text-xs italic text-[#7f8c8d]/60 mb-4 font-serif">
                                        针对：{answers[eventKey]}
                                    </p>
                                    <textarea
                                        name={gainKey}
                                        className="w-full bg-transparent border-b border-transparent focus:border-[#c9a063] py-2 text-lg outline-none resize-none transition-colors font-medium text-slate-700 placeholder:text-slate-300 placeholder:font-light no-scrollbar overflow-hidden"
                                        placeholder={num === 1 ? "这件事让你学会了什么？" : "例如：我知道了即使再难我也能战胜它。"}
                                        value={answers[gainKey]}
                                        onChange={autoGrow}
                                        rows={1}
                                    />
                                </div>
                             )
                        })}
                    </div>
                    <div className="mt-16 flex justify-center">
                        <button onClick={() => handleNext(4)} className="bg-[#2c3e50] text-white px-10 py-3 rounded-full font-medium tracking-widest hover:bg-black hover:scale-105 transition-all shadow-lg hover:shadow-xl">
                            投射未来
                        </button>
                    </div>
                </motion.section>
            )}

             {/* Step 4: Future */}
             {step === 4 && (
                <motion.section key="step4" variants={fadeUp} initial="hidden" animate="visible" exit="exit">
                    <div className="mb-12">
                        <h2 className="font-serif text-3xl mb-4 text-slate-900">第三步：这些收获如何帮助未来</h2>
                        <p className="text-[#7f8c8d]">将这些智慧转化为你的护甲。</p>
                    </div>
                    
                    <div className="space-y-10">
                        {[1, 2, 3].map((num) => {
                             const gainKey = `gain${num}` as keyof AnswerData;
                             const futureKey = `future${num}` as keyof AnswerData;
                             if (!answers[`event${num}` as keyof AnswerData]) return null;

                             return (
                                <div key={futureKey} className="p-8 bg-white rounded-[20px] shadow-[0_4px_30px_rgba(0,0,0,0.03)] border border-white/50">
                                    <p className="text-xs font-bold uppercase tracking-widest text-[#c9a063] mb-4">
                                        收获：{answers[gainKey] || "..."}
                                    </p>
                                    <textarea
                                        name={futureKey}
                                        className="w-full bg-transparent border-b border-transparent focus:border-[#c9a063] py-2 text-lg outline-none resize-none transition-colors font-light text-slate-700 placeholder:text-slate-300 no-scrollbar overflow-hidden"
                                        placeholder={num === 1 ? "如何在未来更有效地处理？" : "写下你的未来宣言。"}
                                        value={answers[futureKey]}
                                        onChange={autoGrow}
                                        rows={1}
                                    />
                                </div>
                             )
                        })}
                    </div>
                    <div className="mt-16 flex justify-center">
                        <button onClick={() => handleNext(5)} className="bg-[#2c3e50] text-white px-10 py-3 rounded-full font-medium tracking-widest hover:bg-black hover:scale-105 transition-all shadow-lg hover:shadow-xl">
                            完成重构
                        </button>
                    </div>
                </motion.section>
            )}

            {/* Step 5: Final Summary */}
            {step === 5 && (
                 <motion.section key="step5" variants={fadeUp} initial="hidden" animate="visible" exit="exit" className="pb-20">
                    <div className="text-center mb-16">
                        <h2 className="font-serif text-4xl mb-4 text-slate-900">重构完成</h2>
                        <p className="text-[#7f8c8d]">这是你用勇气和智慧改写的个人史。</p>
                    </div>
                    
                    <div className="space-y-6">
                        {[1, 2, 3].map(num => {
                            const event = answers[`event${num}` as keyof AnswerData];
                            const gain = answers[`gain${num}` as keyof AnswerData];
                            const future = answers[`future${num}` as keyof AnswerData];

                            if(!event) return null;

                            return (
                                <div key={num} className="bg-white rounded-[20px] p-8 md:p-10 shadow-sm border border-slate-100/50 hover:shadow-md transition-shadow">
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">
                                        <div className="space-y-2">
                                            <span className="text-[10px] uppercase tracking-widest text-slate-400 block">过去的阴影</span>
                                            <p className="font-serif text-lg leading-relaxed text-slate-700 whitespace-pre-wrap decoration-slate-200 underline underline-offset-4 decoration-1">{event}</p>
                                        </div>
                                        <div className="space-y-2 relative">
                                            <div className="hidden md:block absolute -left-6 top-2 bottom-2 w-[1px] bg-slate-100"></div>
                                            <span className="text-[10px] uppercase tracking-widest text-[#c9a063] block font-bold">现在的炼金</span>
                                            <p className="text-sm font-semibold leading-relaxed text-slate-800 whitespace-pre-wrap">{gain || "未填写"}</p>
                                        </div>
                                        <div className="space-y-2 relative">
                                             <div className="hidden md:block absolute -left-6 top-2 bottom-2 w-[1px] bg-slate-100"></div>
                                            <span className="text-[10px] uppercase tracking-widest text-slate-400 block">未来的指引</span>
                                            <p className="text-sm text-[#7f8c8d] leading-relaxed whitespace-pre-wrap">{future || "未填写"}</p>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    <div className="mt-24 text-center space-y-8">
                        <p className="font-serif text-2xl italic text-[#c9a063] opacity-80">“Stay Hungry, Stay Foolish.”</p>
                        <div className="flex justify-center gap-6">
                            <button onClick={() => { setStep(1); setAnswers({ event1: '', event2: '', event3: '', gain1: '', gain2: '', gain3: '', future1: '', future2: '', future3: '' }) }} className="text-xs uppercase tracking-widest text-slate-400 hover:text-slate-800 transition-colors">
                                重新开启旅程
                            </button>
                            <button onClick={onExit} className="text-xs uppercase tracking-widest text-[#c9a063] hover:text-[#a07c45] font-bold transition-colors">
                                返回主页
                            </button>
                        </div>
                    </div>
                 </motion.section>
            )}

        </AnimatePresence>
      </main>

      {/* Help Modal Overlay */}
      <AnimatePresence>
        {showHelp && (
            <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setShowHelp(false)}
                className="fixed inset-0 z-[100] bg-white/40 backdrop-blur-md flex items-center justify-center p-6"
            >
                <motion.div 
                    variants={modalVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                    onClick={(e) => e.stopPropagation()}
                    className="bg-white w-full max-w-[500px] max-h-[85vh] overflow-y-auto p-10 rounded-[30px] shadow-2xl relative border border-white no-scrollbar"
                >
                    <h3 className="font-serif text-2xl mb-6 text-[#c9a063]">如何进行“积极重构”？</h3>
                    <div className="space-y-8 text-sm leading-relaxed text-[#7f8c8d]">
                        <section>
                            <h4 className="font-bold text-[#2c3e50] mb-2 text-base">1. 阴影</h4>
                            <p>选择那些依然能让你联想起消极情绪（内疚、羞耻、伤心或恐惧）的事件。请记住，这些事情都已经过去了，它们不能决定你的今天。重新解构过去，是让你控制过去，而不是让过去控制你。</p>
                        </section>
                        <section>
                            <h4 className="font-bold text-[#2c3e50] mb-2 text-base">2. 收获</h4>
                            <p>事物都具有两面性。问问自己：如果这件事没有发生，我会失去哪部分的韧性？例如：一次挫败可能教会了你“边界感”或“真正的兴趣”。若暂时想不出，不妨多给自己一些时间去觉察。</p>
                        </section>
                        <section>
                            <h4 className="font-bold text-[#2c3e50] mb-2 text-base">3. 未来</h4>
                            <p>将收获转化为具体的行动准则。你学会了如何在未来避免类似情形出现，或者学会了当事情再发生时如何更有效地处理。</p>
                        </section>
                    </div>
                    <button onClick={() => setShowHelp(false)} className="mt-10 w-full py-4 rounded-full border border-slate-100 bg-slate-50 hover:bg-slate-100 hover:border-slate-200 transition-all text-xs font-bold tracking-[0.2em] uppercase text-slate-800">
                        开启旅程
                    </button>
                </motion.div>
            </motion.div>
        )}
      </AnimatePresence>

    </motion.div>
  );
};

export default ReinterpretPast;