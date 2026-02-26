
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

/**
 * Mind Space - ACT Psychology Entry
 * Aesthetic: Light Zen (Rice Paper, Charcoal Ink, Red Seal).
 */

interface MindSpaceHomeProps {
  onNavigate: (view: 'mood' | 'journal' | 'being' | 'commitment') => void;
}

// --- Assets & Icons ---
const LeafIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M12,2C12,2 14,8 20,10C16,12 12,22 12,22C12,22 8,12 4,10C10,8 12,2 12,2Z" />
  </svg>
);

// --- Components ---

const GrainTexture = () => (
  <div className="fixed inset-0 pointer-events-none opacity-[0.4] z-50 mix-blend-multiply">
    <svg className="w-full h-full">
      <filter id="noiseFilter">
        <feTurbulence type="fractalNoise" baseFrequency="0.8" stitchTiles="stitch" />
      </filter>
      <rect width="100%" height="100%" filter="url(#noiseFilter)" />
    </svg>
  </div>
);

const InkBlob = ({ delay, x, y, size, duration }: { delay: number; x: number; y: number; size: number; duration: number }) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.8 }}
    animate={{
      opacity: [0.05, 0.15, 0.05],
      scale: [1, 1.2, 1],
      x: [x, x + 20, x],
      y: [y, y - 20, y]
    }}
    transition={{
      duration: duration,
      repeat: Infinity,
      ease: "easeInOut",
      delay: delay
    }}
    className="absolute rounded-full blur-3xl bg-[#1a1a1a]"
    style={{
      width: size,
      height: size,
      left: `calc(${x}px)`,
      top: `calc(${y}px)`
    }}
  />
);

const FloatingLeaf = ({ delay, duration }: { delay: number; duration: number }) => {
  const randomX = Math.random() * 100;
  return (
    <motion.div
      initial={{ y: -100, x: `${randomX}vw`, opacity: 0, rotate: 0 }}
      animate={{
        y: '110vh',
        x: [`${randomX}vw`, `${randomX + 5}vw`, `${randomX - 5}vw`],
        opacity: [0, 0.6, 0],
        rotate: [0, 45, -45, 90]
      }}
      transition={{
        duration: duration,
        repeat: Infinity,
        delay: delay,
        ease: "linear"
      }}
      className="absolute text-[#2c2c2c] pointer-events-none z-0"
    >
      <LeafIcon className="w-6 h-6 opacity-20" />
    </motion.div>
  );
};

const WaterDistortionFilter = () => (
  <svg className="absolute w-0 h-0">
    <defs>
      <filter id="water-distortion">
        <feTurbulence type="turbulence" baseFrequency="0.01 0.02" numOctaves="2" result="turbulence" seed="5">
          <animate attributeName="baseFrequency" dur="10s" values="0.01 0.02;0.01 0.05;0.01 0.02" repeatCount="indefinite" />
        </feTurbulence>
        <feDisplacementMap in="SourceGraphic" in2="turbulence" scale="4" />
      </filter>
    </defs>
  </svg>
);

const MenuItem = ({ title, sub, index, activeHover, setActiveHover, onClick, metaphor }: any) => {
  const isHovered = activeHover === index;
  const isDimmed = activeHover !== null && !isHovered;

  return (
    <motion.div
      className="relative h-[65vh] min-w-[120px] md:min-w-[160px] md:w-48 flex flex-col items-center justify-center border-r border-[#0000000f] group cursor-pointer z-20 overflow-hidden bg-gradient-to-b from-transparent to-transparent flex-shrink-0"
      style={{
        borderRightWidth: '1px',
      }}
      animate={{
        opacity: isDimmed ? 0.4 : 1,
        backgroundColor: isHovered ? "rgba(0,0,0,0.03)" : "rgba(0,0,0,0)"
      }}
      transition={{ duration: 0.4 }}
      onMouseEnter={() => setActiveHover(index)}
      onMouseLeave={() => setActiveHover(null)}
      onClick={onClick}
    >

      <div className="relative w-full h-full flex flex-col items-center justify-center">

        {/* TOP: Metaphor & Title Group */}
        <motion.div
          className="flex flex-col items-center gap-6 relative z-10"
          animate={{
            y: isHovered ? -70 : 0
          }}
          transition={{ type: "spring", stiffness: 100, damping: 20 }}
        >
          <span className="text-[10px] tracking-[0.3em] uppercase text-[#666666] font-light">
            {metaphor}
          </span>

          <div className="flex flex-col items-center gap-3">
            {title.split('').map((char: string, i: number) => (
              <motion.span
                key={i}
                className="text-3xl md:text-4xl font-serif text-[#222222] opacity-90"
                style={{
                  fontFamily: '"Noto Serif SC", "SimSun", serif',
                  filter: isHovered ? "url(#water-distortion)" : "none",
                  textShadow: isHovered ? "2px 2px 8px rgba(0,0,0,0.1)" : "none"
                }}
                animate={{
                  color: isHovered ? "#000000" : "#222222",
                  scale: isHovered ? 1.05 : 1
                }}
              >
                {char}
              </motion.span>
            ))}
          </div>
        </motion.div>

        {/* BOTTOM: Description & Seal */}
        <div className="absolute top-[55%] w-full flex flex-col items-center justify-start pointer-events-none">
          <AnimatePresence>
            {isHovered && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                className="flex flex-col items-center gap-4 pt-4 px-6 text-center"
              >
                <div className="w-1 h-6 bg-gradient-to-b from-[#00000030] to-transparent opacity-50" />

                <div className="writing-vertical-rl text-[#444444] text-[11px] font-light tracking-widest leading-relaxed h-28 flex items-center select-none text-justify opacity-90 font-serif">
                  {getDesc(sub)}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Seal */}
        <motion.div
          className="absolute bottom-10 w-8 h-8 border border-[#a63737] rounded-sm flex items-center justify-center opacity-70"
          animate={{
            y: isHovered ? 30 : 0,
            borderColor: isHovered ? "#d94e4e" : "#a63737",
            rotate: isHovered ? 0 : 45
          }}
        >
          <div className={`w-4 h-4 bg-[#a63737] rounded-full blur-[1px] transition-colors duration-500 ${isHovered ? 'bg-[#d94e4e]' : ''}`} />
        </motion.div>

      </div>
    </motion.div>
  );
};

const getDesc = (type: string) => {
  switch (type) {
    case 'MOOD': return "如云漂浮，接纳情绪，不加评判。";
    case 'DIARY': return "叶随流水，记录当下，自然流淌。";
    case 'BARRIER': return "识别思维迷雾，解开自我束缚。";
    case 'VALUE': return "追寻内心指南针，确定生命航向。";
    case 'COMMITMENT': return "言出必行，脚踏实地，坚定践行。";
    case 'EXPLORE': return "打破认知边界，发现无限可能。";
    default: return "";
  }
}

const MindSpaceHome: React.FC<MindSpaceHomeProps> = ({ onNavigate }) => {
  const [activeHover, setActiveHover] = useState<number | null>(null);

  const handleMenuClick = (sub: string) => {
    switch (sub) {
      case 'MOOD':
        onNavigate('mood');
        break;
      case 'DIARY':
        onNavigate('journal');
        break;
      case 'COMMITMENT':
        onNavigate('commitment');
        break;
      // "Being" content is not connected yet as per instructions
      case 'BARRIER':
      case 'VALUE':
      case 'EXPLORE':
        console.log("Being content - coming soon");
        break;
    }
  };

  const menuItems = [
    { title: "心情", sub: "MOOD", metaphor: "CLOUDS" },
    { title: "日记", sub: "DIARY", metaphor: "STREAM" },
    { title: "迷障", sub: "BARRIER", metaphor: "FOG" },
    { title: "价值", sub: "VALUE", metaphor: "COMPASS" },
    { title: "承诺", sub: "COMMITMENT", metaphor: "PATH" },
    { title: "探索", sub: "EXPLORE", metaphor: "HORIZON" },
  ];

  return (
    <div className="relative w-full h-screen overflow-hidden bg-[#f0f0eb] text-[#2c2c2c] font-sans selection:bg-[#a63737] selection:text-white">
      {/* 1. Global Effects */}
      <GrainTexture />
      <WaterDistortionFilter />

      {/* 2. Background */}
      <div className="absolute inset-0 z-0 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-[#f5f5f2] via-[#f0f0eb] to-[#e6e6e3]" />

        {/* Ink Blobs */}
        <InkBlob x={200} y={100} size={500} duration={25} delay={0} />
        <InkBlob x={800} y={500} size={600} duration={30} delay={2} />
        <InkBlob x={-100} y={600} size={400} duration={28} delay={4} />

        {/* Floating Leaves */}
        {[...Array(6)].map((_, i) => (
          <FloatingLeaf key={i} delay={i * 3} duration={18 + Math.random() * 10} />
        ))}
      </div>

      {/* 3. Main Layout */}
      <div className="relative z-10 w-full h-full flex flex-col justify-center items-center">

        {/* Branding */}
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 0.8 }} transition={{ duration: 2 }}
          className="absolute top-8 left-8 md:top-12 md:left-12 flex flex-col items-start gap-2 pointer-events-none select-none"
        >
          <div className="w-12 h-12 border border-[#444444] rounded-full flex items-center justify-center">
            <span className="font-serif text-lg italic text-[#222222]">M</span>
          </div>
          <span className="text-xs tracking-[0.3em] text-[#444444] uppercase">Mind Space(开发中，部分界面完成)</span>
        </motion.div>

        {/* Footer Poem (New Addition) */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 2, delay: 1 }}
          className="absolute bottom-6 md:bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-3 z-30"
        >
          <span className="font-serif text-[#444444] text-[10px] md:text-xs tracking-[0.4em] opacity-80 whitespace-nowrap pointer-events-none select-none">
            行到水穷处，坐看云起时
          </span>
        </motion.div>

        {/* Navigation Pillars - Horizontal Scroll on Mobile */}
        <div className="flex flex-row items-center md:justify-center overflow-x-auto md:overflow-hidden h-full w-full max-w-6xl px-4 no-scrollbar snap-x snap-mandatory">
          <div className="flex flex-row md:justify-center min-w-full md:min-w-0 px-4 md:px-0 gap-0">
            {menuItems.map((item, index) => (
              <div key={index} className="snap-center">
                <MenuItem
                  index={index}
                  title={item.title}
                  sub={item.sub}
                  metaphor={item.metaphor}
                  activeHover={activeHover}
                  setActiveHover={setActiveHover}
                  onClick={() => handleMenuClick(item.sub)}
                />
              </div>
            ))}
          </div>
        </div>

      </div>

      <div className="absolute inset-0 pointer-events-none bg-radial-gradient from-transparent to-[#0000000a] z-30" />

      <style>{`
        .writing-vertical-rl {
          writing-mode: vertical-rl;
          text-orientation: mixed;
        }
        .no-scrollbar::-webkit-scrollbar {
          display: none;
        }
        .no-scrollbar {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@300;400;700&display=swap');
      `}</style>
    </div>
  );
};

export default MindSpaceHome;
