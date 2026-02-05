import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2 } from 'lucide-react';
import ReflectionTemplate, { BubbleData, ReflectionStageConfig } from '../../shared/ReflectionTemplate';

interface WhoAmIProps {
  onExit: () => void;
}

const QUESTIONS = [
  { id: 'who', text: 'Who am I right now?', sub: 'Identity & Self', color: 'from-purple-100 to-blue-100' },
  { id: 'when', text: 'What time is it now?', sub: 'Flow of Time', color: 'from-blue-100 to-teal-100' },
  { id: 'where', text: 'Where am I right now?', sub: 'Anchor in Space', color: 'from-teal-100 to-orange-50' },
  { id: 'feel', text: 'How do I feel?', sub: 'Emotional Undertone', color: 'from-orange-50 to-pink-100' },
];

const WhoAmI: React.FC<WhoAmIProps> = ({ onExit }) => {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, BubbleData[]>>({ who: [], when: [], where: [], feel: [] });
  const [isFinished, setIsFinished] = useState(false);
  
  // Reference to the central card to measure its size for bubble exclusion
  const centerCardRef = useRef<HTMLDivElement>(null);

  // Helper to generate a random bubble with dynamic boundaries
  const createBubble = (text: string): BubbleData => {
    // 1. Calculate boundaries based on screen size
    const w = typeof window !== 'undefined' ? window.innerWidth : 1000;
    const h = typeof window !== 'undefined' ? window.innerHeight : 800;
    const shortSide = Math.min(w, h);

    // Max Radius: Outer boundary (Screen Edge - Margin - Bubble Size)
    // 5% margin + ~80px for bubble content
    const margin = shortSide * 0.05;
    const bubbleAllowance = 80; 
    let maxRadius = (shortSide / 2) - margin - bubbleAllowance;

    // 2. Calculate Inner Boundary based on Center Card
    let minRadius = 160; // Default fallback
    
    if (centerCardRef.current) {
      const rect = centerCardRef.current.getBoundingClientRect();
      // Use the diagonal of the half-rect to ensure corners don't overlap
      const halfW = rect.width / 2;
      const halfH = rect.height / 2;
      // Sqrt(a^2 + b^2) + buffer
      minRadius = Math.sqrt(halfW * halfW + halfH * halfH) + 40; 
    }

    // Safety: ensure max > min
    if (maxRadius <= minRadius + 40) {
        maxRadius = minRadius + 60; 
    }

    const angle = Math.random() * Math.PI * 2;
    const distance = minRadius + Math.random() * (maxRadius - minRadius);
    
    return {
      id: Math.random(),
      text,
      x: Math.cos(angle) * distance,
      y: Math.sin(angle) * distance,
      rotate: Math.random() * 10 - 5,
      scale: 0.9 + Math.random() * 0.2,
    };
  };

  // Handlers
  const handleAddAnswer = (text: string) => {
    const currentId = QUESTIONS[step].id;
    setAnswers(prev => ({
      ...prev,
      [currentId]: [...prev[currentId], createBubble(text)]
    }));
  };

  const handleUpdateAnswer = (id: number, text: string) => {
    const currentId = QUESTIONS[step].id;
    setAnswers(prev => ({
      ...prev,
      [currentId]: prev[currentId].map(a => a.id === id ? { ...a, text } : a)
    }));
  };

  const handleDeleteAnswer = (id: number) => {
    const currentId = QUESTIONS[step].id;
    setAnswers(prev => ({
      ...prev,
      [currentId]: prev[currentId].filter(a => a.id !== id)
    }));
  };

  const handleNext = () => {
    if (step < QUESTIONS.length - 1) {
      setStep(step + 1);
    } else {
      setIsFinished(true);
    }
  };

  const handleBack = () => {
    if (step > 0) {
      setStep(step - 1);
    }
  };

  const handleJumpToStep = (index: number) => {
    // Only allow jumping to steps that are less than or equal to current step (or just allow free navigation if desired)
    // Here we allow jumping backwards.
    if (index < step) {
        setStep(index);
    }
  };

  const handleRestart = () => {
    setStep(0);
    setIsFinished(false);
    setAnswers({ who: [], when: [], where: [], feel: [] });
  };

  // Configuration for the Template
  const currentQ = QUESTIONS[step];
  const currentBubbleList = answers[currentQ.id] || [];

  const stageConfig: ReflectionStageConfig = {
    title: currentQ.text,
    subtitle: currentQ.sub,
    placeholder: "Enter your thoughts...",
    color: isFinished ? 'from-slate-100 to-white' : currentQ.color,
    progressIndex: step,
    totalStages: QUESTIONS.length,
    nextButtonLabel: step === QUESTIONS.length - 1 ? "Complete Reflection" : "Next Step",
  };

  const renderFinishedScreen = () => (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className="flex flex-col items-center text-center space-y-8"
    >
      <div className="w-20 h-20 bg-white/60 backdrop-blur-xl rounded-full flex items-center justify-center border border-white/60 shadow-lg">
        <CheckCircle2 size={40} strokeWidth={1.5} className="text-slate-800" />
      </div>
      
      <div className="space-y-4">
        <h2 className="text-3xl font-light text-slate-800 tracking-tight">Thoughts Aligned</h2>
        <p className="text-slate-500 font-light text-sm max-w-xs mx-auto leading-relaxed">
          You have completed the four-fold scan of self.<br/>These moments are now woven into your prism of life.
        </p>
      </div>

      <div className="flex gap-4 mt-6">
        <button
            onClick={handleRestart}
            className="px-8 py-3 bg-white border border-slate-200 text-slate-600 rounded-full text-xs font-bold tracking-widest hover:bg-slate-50 transition-all uppercase"
        >
            Restart
        </button>
        <button
            onClick={onExit}
            className="px-8 py-3 bg-slate-900 text-white rounded-full text-xs font-bold tracking-widest hover:bg-slate-800 transition-all shadow-xl active:scale-95 uppercase"
        >
            Return Home
        </button>
      </div>
    </motion.div>
  );

  return (
    <ReflectionTemplate
      onExit={onExit}
      onNext={handleNext}
      onBack={handleBack}
      onJumpToStep={handleJumpToStep}
      onAddAnswer={handleAddAnswer}
      onUpdateAnswer={handleUpdateAnswer}
      onDeleteAnswer={handleDeleteAnswer}
      answers={currentBubbleList}
      currentStage={stageConfig}
      isFinished={isFinished}
      renderFinishedScreen={renderFinishedScreen}
      headerTitle="LifePrism • Reflections"
      footerText="Safe space for your inner voice"
      centerCardRef={centerCardRef}
    />
  );
};

export default WhoAmI;