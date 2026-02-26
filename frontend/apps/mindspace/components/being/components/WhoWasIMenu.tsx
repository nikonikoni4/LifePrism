import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { History, Sparkles, ArrowRight, X } from 'lucide-react';

interface WhoWasIMenuProps {
  onSelectMirror: () => void;
  onSelectPrism: () => void;
  onBack: () => void;
}

const WhoWasIMenu: React.FC<WhoWasIMenuProps> = ({ onSelectMirror, onSelectPrism, onBack }) => {
  const [hovered, setHovered] = useState<'left' | 'right' | null>(null);

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] h-screen w-full bg-[#F5F2EE] overflow-hidden font-sans select-none"
    >
      
      {/* Close Button */}
      <button 
        onClick={onBack}
        className="absolute top-6 right-6 z-50 p-2 rounded-full bg-slate-200/50 hover:bg-slate-300/50 transition-colors backdrop-blur-sm"
      >
        <X size={24} className="text-slate-600" />
      </button>

      {/* Noise Texture Layer */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.04] mix-blend-multiply" 
           style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }}>
      </div>

      {/* Dynamic Ambient Light */}
      <div className="absolute inset-0 transition-all duration-[1200ms] ease-out pointer-events-none">
        <div 
          className={`absolute inset-0 transition-opacity duration-1000 ${hovered === 'left' ? 'opacity-100' : 'opacity-0'}`}
          style={{ background: 'radial-gradient(circle at 25% 50%, #CBD5E1 0%, transparent 65%)' }}
        />
        <div 
          className={`absolute inset-0 transition-opacity duration-1000 ${hovered === 'right' ? 'opacity-100' : 'opacity-0'}`}
          style={{ background: 'radial-gradient(circle at 75% 50%, #FDE68A 0%, transparent 65%)' }}
        />
      </div>

      <div className="relative z-10 h-full flex flex-col md:flex-row">
        
        {/* Left: Mirror of Ages (Navigation Target) */}
        <motion.div 
          onHoverStart={() => setHovered('left')}
          onHoverEnd={() => setHovered(null)}
          onClick={onSelectMirror}
          className="relative flex-1 flex flex-col items-center justify-center cursor-pointer group"
        >
          {/* Background Decoration */}
          <div className="absolute inset-0 flex items-center justify-center overflow-hidden pointer-events-none">
             <motion.div 
               animate={{ 
                 scale: hovered === 'left' ? 1.1 : 1, 
                 opacity: hovered === 'left' ? 0.6 : 0.15 
               }}
               className="w-[380px] h-[380px] rounded-full border-[1px] border-slate-500/40"
               style={{ filter: 'blur(1px)' }}
             />
             <motion.div 
               animate={{ 
                 scale: hovered === 'left' ? 1.3 : 1, 
                 opacity: hovered === 'left' ? 0.3 : 0 
               }}
               transition={{ duration: 1.5, repeat: Infinity, repeatType: "reverse" }}
               className="absolute w-[420px] h-[420px] rounded-full border-[0.5px] border-slate-400/20"
               style={{ filter: 'blur(3px)' }}
             />
          </div>

          <div className="relative flex flex-col items-center space-y-10 px-10 text-center">
            <motion.div 
              animate={{ 
                y: hovered === 'left' ? -10 : 0,
                backgroundColor: hovered === 'left' ? 'rgba(71, 85, 105, 0.1)' : 'rgba(255, 255, 255, 0.4)'
              }}
              className="w-16 h-16 rounded-full backdrop-blur-sm border border-slate-300/60 flex items-center justify-center shadow-sm transition-colors duration-500"
            >
              <History size={28} strokeWidth={1} className={`${hovered === 'left' ? 'text-slate-800' : 'text-slate-500'} transition-colors duration-500`} />
            </motion.div>
            
            <div className="space-y-4">
              <h2 className={`text-4xl md:text-5xl font-extralight tracking-[0.2em] transition-all duration-700 font-serif ${hovered === 'left' ? 'text-slate-900 scale-[1.02]' : 'text-slate-700'}`}>
                岁月的镜像
              </h2>
              <p className={`text-[10px] tracking-[0.5em] uppercase font-light transition-colors duration-700 ${hovered === 'left' ? 'text-slate-600' : 'text-slate-400'}`}>
                Shadows of Yesterday
              </p>
            </div>

            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: hovered === 'left' ? 1 : 0, y: hovered === 'left' ? 0 : 10 }}
              className="flex items-center space-x-2 text-[10px] text-slate-600 tracking-[0.3em] uppercase font-medium"
            >
              <span>静心回顾</span>
              <ArrowRight size={12} className="opacity-80" />
            </motion.div>
          </div>
        </motion.div>

        {/* Divider */}
        <div className="hidden md:block w-[0.5px] h-24 self-center bg-slate-300/30 z-20" />

        {/* Right: Alchemy of Growth (Placeholder for now) */}
        <motion.div 
          onHoverStart={() => setHovered('right')}
          onHoverEnd={() => setHovered(null)}
          onClick={onSelectPrism}
          className="relative flex-1 flex flex-col items-center justify-center cursor-pointer group"
        >
          <div className="absolute inset-0 flex items-center justify-center overflow-hidden pointer-events-none">
             <motion.div 
               animate={{ 
                 scale: hovered === 'right' ? 1.3 : 1, 
                 opacity: hovered === 'right' ? 0.35 : 0.05 
               }}
               className="w-[500px] h-[500px] rounded-full bg-amber-200/40"
               style={{ filter: 'blur(60px)' }}
             />
          </div>

          <div className="relative flex flex-col items-center space-y-10 px-10 text-center">
            <motion.div 
              animate={{ 
                y: hovered === 'right' ? -10 : 0,
                backgroundColor: hovered === 'right' ? 'rgba(251, 191, 36, 0.1)' : 'rgba(255, 255, 255, 0.4)'
              }}
              className="w-16 h-16 rounded-full backdrop-blur-sm border border-amber-200/60 flex items-center justify-center shadow-sm transition-colors duration-500"
            >
              <Sparkles size={28} strokeWidth={1} className={`${hovered === 'right' ? 'text-amber-600' : 'text-amber-500/70'} transition-colors duration-500`} />
            </motion.div>
            
            <div className="space-y-4">
              <h2 className={`text-4xl md:text-5xl font-extralight tracking-[0.2em] transition-all duration-700 font-serif ${hovered === 'right' ? 'text-slate-900 scale-[1.02]' : 'text-slate-700'}`}>
                生命的重塑
              </h2>
              <p className={`text-[10px] tracking-[0.5em] uppercase font-light transition-colors duration-700 ${hovered === 'right' ? 'text-amber-700/60' : 'text-slate-400'}`}>
                Alchemy of Growth
              </p>
            </div>

            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: hovered === 'right' ? 1 : 0, y: hovered === 'right' ? 0 : 10 }}
              className="flex items-center space-x-2 text-[10px] text-amber-700/70 tracking-[0.3em] uppercase font-medium"
            >
              <span>汲取力量</span>
              <ArrowRight size={12} className="opacity-80" />
            </motion.div>
          </div>
        </motion.div>
      </div>

      <footer className="absolute bottom-16 w-full text-center z-20 pointer-events-none px-6">
        <motion.div
          animate={{ opacity: hovered ? 0.4 : 0.7 }}
          className="flex flex-col items-center space-y-3"
        >
          <div className="w-8 h-[1px] bg-slate-300 mb-2 opacity-50" />
          <p className="text-[10px] text-slate-500 tracking-[0.4em] font-light leading-loose">
            过去是时间的馈赠，重构是心灵的觉醒
          </p>
          <p className="text-[8px] text-slate-400 tracking-[0.6em] font-extralight uppercase">
            Deep reflection leads to clear direction
          </p>
        </motion.div>
      </footer>
      
      <style>{`
        .font-serif {
          font-family: 'Noto Serif SC', serif;
        }
      `}</style>
    </motion.div>
  );
};

export default WhoWasIMenu;