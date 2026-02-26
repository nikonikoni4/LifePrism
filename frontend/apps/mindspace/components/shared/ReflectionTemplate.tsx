import React, { useState, useRef, ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Plus, ChevronRight, Edit3, Save, RotateCcw, Trash2, ChevronLeft } from 'lucide-react';

// --- Shared Types ---
export interface BubbleData {
  id: number;
  text: string;
  x: number;
  y: number;
  rotate: number;
  scale: number;
}

export interface ReflectionStageConfig {
  title: string;
  subtitle: string;
  placeholder: string;
  color: string; // Tailwind gradient classes e.g. "from-blue-100 to-white"
  progressIndex: number; // For the dots at the bottom
  totalStages: number;
  inputValue?: string; // Controlled input (optional)
  isInputDisabled?: boolean;
  isNextDisabled?: boolean;
  nextButtonLabel?: string;
  extraUI?: ReactNode; // Slot for things like list progress indicators
  contextUI?: ReactNode; // Slot for "Reframing" hints
}

interface ReflectionTemplateProps {
  // Navigation
  onExit: () => void;
  onNext: () => void;
  onBack?: () => void; // Added optional back handler
  onJumpToStep?: (index: number) => void; // Added handler for progress bar clicks
  
  // Data Interactions
  onAddAnswer: (text: string) => void;
  onUpdateAnswer: (id: number, newText: string) => void;
  onDeleteAnswer: (id: number) => void;
  
  // State
  answers: BubbleData[];
  currentStage: ReflectionStageConfig;
  isFinished: boolean;
  
  // Render Props
  renderFinishedScreen: () => ReactNode;
  
  // Static Config
  headerTitle?: string;
  footerText?: string;

  // Layout Refs
  centerCardRef?: React.RefObject<HTMLDivElement | null>;
}

const ReflectionTemplate: React.FC<ReflectionTemplateProps> = ({
  onExit,
  onNext,
  onBack,
  onJumpToStep,
  onAddAnswer,
  onUpdateAnswer,
  onDeleteAnswer,
  answers,
  currentStage,
  isFinished,
  renderFinishedScreen,
  headerTitle = "LifePrism • Reflection",
  footerText = "Explore your inner universe",
  centerCardRef
}) => {
  const [internalInput, setInternalInput] = useState('');
  const [selectedAnswer, setSelectedAnswer] = useState<BubbleData | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState('');
  
  // Use controlled input if provided, otherwise internal state
  const inputValue = currentStage.inputValue !== undefined ? currentStage.inputValue : internalInput;
  const setInputValue = (val: string) => {
    setInternalInput(val);
  };

  const handleAdd = () => {
    if (!inputValue.trim()) return;
    onAddAnswer(inputValue);
    setInternalInput(''); // Clear internal state
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAdd();
    }
  };

  const handleSaveEdit = () => {
    if (selectedAnswer && editText.trim()) {
      onUpdateAnswer(selectedAnswer.id, editText);
      setIsEditing(false);
      setSelectedAnswer({ ...selectedAnswer, text: editText }); // Optimistic update for modal
    }
  };

  const handleDelete = () => {
    if (selectedAnswer) {
      onDeleteAnswer(selectedAnswer.id);
      setSelectedAnswer(null);
      setIsEditing(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] w-full h-full flex flex-col items-center justify-center overflow-hidden font-sans text-slate-800 bg-white"
    >
      {/* Exit Button */}
      <button 
        onClick={onExit}
        className="absolute top-6 right-6 z-50 p-2 rounded-full bg-white/40 hover:bg-white/80 transition-colors backdrop-blur-sm"
      >
        <X size={24} className="text-slate-600" />
      </button>

      {/* Dynamic Background */}
      <div className="absolute inset-0 -z-10 transition-colors duration-1000">
        <div className={`absolute inset-0 opacity-60 bg-gradient-to-br ${currentStage.color}`} />
        <div className="absolute inset-0 backdrop-blur-[120px]" />
      </div>

      {/* Header */}
      <header className="absolute top-10 left-0 w-full text-center z-10 pointer-events-none">
        <motion.h1 
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.4 }}
          className="text-[10px] tracking-[0.6em] font-light uppercase text-slate-500"
        >
          {headerTitle}
        </motion.h1>
      </header>

      {/* Bubble Area */}
      <div className="absolute inset-0 z-0 flex items-center justify-center pointer-events-none">
        <AnimatePresence>
          {!isFinished && answers.map((ans, idx) => (
            <motion.div
              key={ans.id}
              initial={{ x: ans.x, y: ans.y, scale: 0, opacity: 0 }}
              animate={{ 
                x: ans.x, 
                y: ans.y,
                scale: 1, 
                opacity: 0.85, 
                rotate: ans.rotate
              }}
              drag
              dragMomentum={true}
              dragElastic={0.1}
              whileDrag={{ scale: 1.1, zIndex: 100, cursor: 'grabbing' }}
              whileHover={{ scale: 1.05, zIndex: 50, cursor: 'grab' }}
              transition={{ duration: 0.5, ease: "backOut" }}
              exit={{ opacity: 0, scale: 0.5, filter: 'blur(10px)' }}
              className="absolute pointer-events-auto touch-none"
            >
              <motion.div
                style={{ scale: ans.scale }}
                className="cursor-grab group active:cursor-grabbing"
              >
                <div 
                  className="
                    relative px-6 py-4 
                    bg-white/60 backdrop-blur-lg border border-white/50 
                    rounded-[2rem] rounded-tr-sm
                    text-sm font-medium text-slate-700 shadow-sm 
                    max-w-[200px] min-w-[80px]
                    transition-all duration-300 hover:bg-white/90 hover:shadow-md
                    flex flex-col items-center justify-center text-center
                  "
                >
                   {/* Optional Index for lists, or just decoration */}
                  <span className="absolute top-2 left-3 text-[9px] font-bold text-slate-400/80 italic select-none">
                     #{idx + 1}
                  </span>
                  <p className="line-clamp-3 leading-relaxed break-words whitespace-normal select-none">
                    {ans.text}
                  </p>
                  
                  {/* Action Buttons Container - Appears on Hover */}
                  <div className="absolute -right-11 top-1/2 -translate-y-1/2 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-all duration-300 z-50">
                    {/* Edit Button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedAnswer(ans);
                        setEditText(ans.text);
                        setIsEditing(true);
                      }}
                      className="
                        bg-white p-2 rounded-full shadow-md border border-slate-100 
                        text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 
                        transform hover:scale-105 transition-all
                      "
                      title="Edit"
                    >
                       <Edit3 size={14} strokeWidth={2} />
                    </button>
                    
                    {/* Delete Button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteAnswer(ans.id);
                      }}
                      className="
                        bg-white p-2 rounded-full shadow-md border border-slate-100 
                        text-slate-400 hover:text-rose-500 hover:bg-rose-50 
                        transform hover:scale-105 transition-all
                      "
                      title="Delete"
                    >
                       <Trash2 size={14} strokeWidth={2} />
                    </button>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Edit Modal */}
      <AnimatePresence>
        {selectedAnswer && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[70] flex items-center justify-center p-6 bg-white/30 backdrop-blur-md"
            onClick={() => setSelectedAnswer(null)}
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="relative w-[90%] md:w-full max-w-md bg-white rounded-3xl shadow-2xl p-6 md:p-8 border border-white/50 flex flex-col max-h-[85vh]"
            >
              <button 
                onClick={() => setSelectedAnswer(null)}
                className="absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-600 transition-colors z-10"
              >
                <X size={20} />
              </button>
              
              <div className="flex flex-col h-full overflow-hidden">
                <span className="text-xs font-bold tracking-widest text-slate-400 uppercase mb-4 flex-shrink-0">
                  {isEditing ? 'Edit Reflection' : 'Reflection'}
                </span>
                
                {isEditing ? (
                  <div className="flex flex-col h-full overflow-hidden">
                    <textarea
                      autoFocus
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      className="w-full h-48 p-4 bg-slate-50 border border-slate-200 rounded-xl resize-none outline-none focus:ring-2 focus:ring-slate-200 text-slate-700 font-light text-lg leading-relaxed mb-4 overflow-y-auto"
                    />
                    <div className="flex justify-end gap-3 pt-2 flex-shrink-0">
                      <button 
                        onClick={() => setIsEditing(false)}
                        className="px-4 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100 rounded-lg transition-colors flex items-center gap-2"
                      >
                         <RotateCcw size={16} /> Cancel
                      </button>
                      <button 
                        onClick={handleSaveEdit}
                        className="px-4 py-2 text-sm font-medium bg-slate-800 text-white hover:bg-slate-700 rounded-lg transition-colors flex items-center gap-2 shadow-md"
                      >
                         <Save size={16} /> Save
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex-grow overflow-y-auto custom-scrollbar pr-2">
                      <p className="text-xl md:text-2xl text-slate-800 font-light leading-relaxed whitespace-pre-wrap break-words">
                        {selectedAnswer.text}
                      </p>
                    </div>
                    
                    <div className="flex gap-4 mt-8 pt-4 border-t border-slate-100 justify-end flex-shrink-0">
                      <button 
                        onClick={handleDelete}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-500 hover:text-rose-500 hover:bg-rose-50 rounded-lg transition-all"
                      >
                        <Trash2 size={16} /> Delete
                      </button>
                      <button 
                        onClick={() => { setIsEditing(true); setEditText(selectedAnswer.text); }} 
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-all"
                      >
                        <Edit3 size={16} /> Edit
                      </button>
                    </div>
                  </>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Interaction Area */}
      <main className="relative z-20 w-full max-w-xl px-6 pointer-events-none">
        <AnimatePresence mode="wait">
          {!isFinished ? (
            <motion.div
              key={currentStage.title} // Re-render animation on title change
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.5 }}
              className="flex flex-col items-center pointer-events-auto"
            >
              {/* Attach Ref Here to measure the central card size */}
              <div 
                ref={centerCardRef} 
                className="w-full flex flex-col items-center space-y-8 py-6 rounded-3xl"
              >
                
                {/* Title Area */}
                <div className="text-center space-y-3">
                  <motion.span 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 0.6 }}
                    className="text-[10px] text-slate-500 tracking-[0.2em] uppercase block font-medium"
                  >
                    {currentStage.subtitle}
                  </motion.span>
                  <h2 className="text-4xl font-extralight text-slate-800 tracking-tight">
                    {currentStage.title}
                  </h2>
                  
                  {/* Context Slot (For Reframing hints) */}
                  {currentStage.contextUI}
                </div>

                {/* Input Area */}
                <div className="w-full max-w-md space-y-4">
                  <div className="relative group">
                    <div className="absolute -inset-1 bg-gradient-to-r from-white/30 to-blue-100/20 rounded-2xl blur opacity-20 group-focus-within:opacity-50 transition duration-500"></div>
                    <div className="relative bg-white/60 backdrop-blur-xl border border-white/50 rounded-2xl p-1.5 flex items-center shadow-sm">
                      <input
                        autoFocus
                        type="text"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={currentStage.placeholder}
                        disabled={currentStage.isInputDisabled}
                        className="w-full bg-transparent px-5 py-4 outline-none text-lg font-light text-slate-700 placeholder:text-slate-400"
                      />
                      <button
                        onClick={handleAdd}
                        disabled={!inputValue.trim() || currentStage.isInputDisabled}
                        className={`p-3 mr-1 rounded-xl transition-all duration-500 ${
                          inputValue.trim() && !currentStage.isInputDisabled
                            ? 'bg-slate-800 text-white shadow-lg' 
                            : 'bg-slate-200/50 text-slate-400 opacity-40'
                        }`}
                      >
                        <Plus size={20} />
                      </button>
                    </div>
                  </div>

                  {/* Extra UI Slot (Examples, List Progress) */}
                  {currentStage.extraUI}

                  {/* Navigation & Progress */}
                  <div className="flex flex-col items-center space-y-6 pt-4">
                    <div className="flex gap-4">
                        {/* Optional Back Button Text (for clarity, although progress bar works) */}
                        {currentStage.progressIndex > 0 && onBack && (
                           <motion.button
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            onClick={onBack}
                            className="flex items-center space-x-2 text-sm font-light tracking-widest text-slate-400 hover:text-slate-600 transition-colors uppercase"
                           >
                              <ChevronLeft size={16} />
                              <span>Back</span>
                           </motion.button>
                        )}
                        
                        <motion.button
                          whileHover={{ x: 3 }}
                          onClick={onNext}
                          className={`flex items-center space-x-2 text-sm font-light tracking-widest transition-all uppercase
                            ${currentStage.isNextDisabled ? 'text-slate-300 cursor-not-allowed' : 'text-slate-600 hover:text-slate-900'}
                          `}
                        >
                          <span>{currentStage.nextButtonLabel || "Next Step"}</span>
                          <ChevronRight size={16} />
                        </motion.button>
                    </div>

                    {/* Progress Bar (Interactive Dashes) */}
                    <div className="flex items-center gap-2">
                      {Array.from({ length: currentStage.totalStages }).map((_, i) => {
                        const isActive = i === currentStage.progressIndex;
                        const isPast = i < currentStage.progressIndex;
                        const isFuture = i > currentStage.progressIndex;
                        
                        return (
                          <button 
                            key={i}
                            onClick={() => {
                                if (onJumpToStep && (isPast || isActive)) {
                                    onJumpToStep(i);
                                }
                            }}
                            disabled={isFuture}
                            className={`
                                h-1.5 rounded-full transition-all duration-500 ease-out
                                ${isActive ? 'w-8 bg-slate-800' : 'w-1.5 bg-slate-300'}
                                ${isPast ? 'hover:bg-slate-400 cursor-pointer' : ''}
                                ${isFuture ? 'opacity-40 cursor-default' : ''}
                            `}
                            aria-label={`Go to step ${i + 1}`}
                          />
                        );
                      })}
                    </div>
                    
                    <div className="text-[10px] text-slate-400 font-light tracking-widest uppercase opacity-60">
                         Step {currentStage.progressIndex + 1} of {currentStage.totalStages}
                    </div>

                  </div>
                </div>
              </div>
            </motion.div>
          ) : (
            // Finished Screen Slot
            <div className="pointer-events-auto">
               {renderFinishedScreen()}
            </div>
          )}
        </AnimatePresence>
      </main>

      <footer className="absolute bottom-10 w-full text-center z-10 pointer-events-none">
        <p className="text-[9px] text-slate-400 tracking-[0.4em] font-light uppercase">
          {footerText}
        </p>
      </footer>
    </motion.div>
  );
};

export default ReflectionTemplate;