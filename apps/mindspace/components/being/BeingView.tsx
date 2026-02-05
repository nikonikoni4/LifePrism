
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Heart, Compass, X, HelpCircle } from 'lucide-react';
import WhoAmI from './components/WhoAmI';
import WhoWasI from './components/WhoWasI';
import WhoWillIBe from './components/WhoWillIBe';

interface BeingViewProps {
  onBack?: () => void;
  onOpenGuide?: () => void;
}

const BeingView: React.FC<BeingViewProps> = ({ onBack, onOpenGuide }) => {
  const [mounted, setMounted] = useState(false);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [activeModule, setActiveModule] = useState<'menu' | 'who_am_i' | 'who_was_i' | 'who_will_i_be'>('menu');

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleCardClick = (id: string) => {
    if (id === 'am') {
      setActiveModule('who_am_i');
    } else if (id === 'was') {
      setActiveModule('who_was_i');
    } else if (id === 'will') {
      setActiveModule('who_will_i_be');
    }
  };

  // 呼吸感的背景装饰 - Covers full screen
  const Orbs = () => (
    <div className="fixed inset-0 overflow-hidden pointer-events-none -z-10 bg-[#F2EDE9]">
      {/* 浅粉色光晕 */}
      <div className="absolute top-[-5%] left-[-5%] w-[60%] h-[60%] rounded-full bg-[#FDE2E4]/50 blur-[130px] animate-pulse-custom" />
      {/* 浅蓝色光晕 */}
      <div className="absolute bottom-[-5%] right-[-5%] w-[70%] h-[70%] rounded-full bg-[#E0F2FE]/50 blur-[150px] animate-pulse-custom" style={{ animationDelay: '3s' }} />
      {/* 浅紫色光晕 */}
      <div className="absolute top-[35%] right-[5%] w-[45%] h-[45%] rounded-full bg-[#F3E8FF]/40 blur-[120px] animate-pulse-custom" style={{ animationDelay: '1.5s' }} />
    </div>
  );

  const sections = [
    {
      id: 'was',
      title: 'Who was I',
      subtitle: '溯源 · 积淀',
      description: '那些塑造了我的瞬间，如同粉樱飘落，在记忆的土壤里生根发芽，构成了今日之我的根基。',
      icon: <Clock className="w-6 h-6" />,
      theme: 'from-[#FFF0F3] to-[#FCE4E9]',
      accent: 'text-[#D67B96]',
      weight: 'font-extralight'
    },
    {
      id: 'am',
      title: 'Who am I right now',
      subtitle: '当下 · 呼吸',
      description: '心跳的韵律，如此刻清澈的蓝天。在静谧中，感受每一个存在的瞬间，把握属于自己的真实。',
      icon: <Heart className="w-6 h-6" />,
      theme: 'from-[#F0F9FF] to-[#D0EFFF]',
      accent: 'text-[#0284C7]',
      weight: 'font-semibold'
    },
    {
      id: 'will',
      title: 'Who will I be',
      subtitle: '愿景 · 晨晖',
      description: '地平线外的紫色霞光，是尚未书写的诗篇。保持好奇，向光而行，去定义那个更好的自己。',
      icon: <Compass className="w-6 h-6" />,
      theme: 'from-[#F5F3FF] to-[#E9E4FF]',
      accent: 'text-[#7C3AED]',
      weight: 'font-light'
    }
  ];

  return (
    <>
      <AnimatePresence>
        {activeModule === 'who_am_i' && (
          <WhoAmI onExit={() => setActiveModule('menu')} />
        )}
        {activeModule === 'who_was_i' && (
          <WhoWasI onExit={() => setActiveModule('menu')} />
        )}
        {activeModule === 'who_will_i_be' && (
          <WhoWillIBe onExit={() => setActiveModule('menu')} />
        )}
      </AnimatePresence>

      <div className={`relative min-h-screen w-full text-[#1D1D1F] font-sans selection:bg-[#FDE2E4] transition-opacity duration-1000 ${mounted ? 'opacity-100' : 'opacity-0'}`}>
        <Orbs />
        
        {/* Header - Internal Navigation for Being Module */}
        <nav className="w-full py-6 px-8 mb-4 flex justify-between items-center z-10 relative">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-[#FAD2E1] via-[#BAE6FD] to-[#E9D5FF] shadow-inner" />
            <span className="text-sm tracking-[0.4em] uppercase font-medium text-[#6E6E73]">Being</span>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="text-[10px] text-[#86868B] tracking-[0.4em] uppercase font-medium hidden sm:block mr-4">
              The Journey is the Reward
            </div>

            {onOpenGuide && (
              <button 
                onClick={onOpenGuide}
                className="p-3 rounded-full transition-all duration-300 hover:scale-105 active:scale-95 bg-white/50 text-slate-600 hover:bg-white hover:text-indigo-600 hover:shadow-md backdrop-blur-sm border border-transparent hover:border-indigo-100"
                aria-label="User Guide"
              >
                <HelpCircle size={20} strokeWidth={2} />
              </button>
            )}
            
            {/* Back Button */}
            <button 
              onClick={onBack}
              className="group flex items-center gap-2 px-4 py-2 rounded-full bg-white/50 hover:bg-white backdrop-blur-sm border border-transparent hover:border-[#1D1D1F]/10 transition-all duration-300"
            >
              <X className="w-4 h-4 text-[#6E6E73] group-hover:text-[#1D1D1F]" />
            </button>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-6xl mx-auto pb-20 px-4 md:px-8 flex flex-col justify-center min-h-[80vh]">
          <header className="mb-12 lg:mb-20 text-center space-y-6">
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-extralight tracking-tight text-[#1D1D1F]">
              我是怎样的 <span className="italic font-light transition-colors duration-700" style={{ color: activeSection === 'was' ? '#D67B96' : activeSection === 'am' ? '#0284C7' : activeSection === 'will' ? '#7C3AED' : '#1D1D1F' }}>存在</span>
            </h1>
            <div className="flex flex-col items-center space-y-3">
              <p className="text-[#6E6E73] font-light tracking-[0.5em] text-sm">
                没有自我，许多自我
              </p>
              <div className="w-16 h-[1.5px] bg-[#1D1D1F]/10" />
            </div>
          </header>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-10 pb-12">
            {sections.map((section) => (
              <div
                key={section.id}
                onClick={() => handleCardClick(section.id)}
                onMouseEnter={() => setActiveSection(section.id)}
                onMouseLeave={() => setActiveSection(null)}
                className={`group relative cursor-pointer transition-all duration-1000 ease-[cubic-bezier(0.23,1,0.32,1)] 
                  ${activeSection === section.id ? 'scale-[1.03] -translate-y-3' : 'scale-100'}
                  ${activeSection && activeSection !== section.id ? 'opacity-40 blur-[1px]' : 'opacity-100'}
                `}
              >
                <div className={`absolute inset-0 bg-gradient-to-br ${section.theme} rounded-[40px] blur-3xl transition-opacity opacity-0 group-hover:opacity-60 duration-700`} />
                
                <div className="relative min-h-[420px] lg:h-[480px] p-8 lg:p-10 rounded-[40px] border border-white shadow-[0_20px_60px_rgba(0,0,0,0.03)] bg-white/60 backdrop-blur-3xl flex flex-col justify-between overflow-hidden group-hover:bg-white/80 group-hover:border-[#1D1D1F]/5 transition-all duration-700">
                  
                  <div className={`absolute -right-12 -top-12 transition-all duration-1000 ease-out opacity-[0.05] group-hover:opacity-[0.12] group-hover:rotate-6 group-hover:scale-110 ${section.accent}`}>
                    {React.cloneElement(section.icon, { size: 240, strokeWidth: 1.5 })}
                  </div>

                  <div className="space-y-8 z-10">
                    <div className={`p-4 w-fit rounded-[24px] bg-white shadow-md transition-all duration-700 ${activeSection === section.id ? 'scale-110' : ''} ${section.accent}`}>
                      {section.icon}
                    </div>
                    
                    <div className="space-y-2">
                      <h2 className={`text-xl lg:text-2xl ${section.weight} tracking-tight text-[#1D1D1F]`}>
                        {section.title}
                      </h2>
                      <p className={`text-[10px] tracking-[0.4em] uppercase font-bold ${section.accent}`}>
                        {section.subtitle}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-6 z-10">
                    <p className="text-sm lg:text-[15px] leading-relaxed text-[#424245] font-light">
                      {section.description}
                    </p>
                    
                    <div className="pt-4 flex items-center gap-3 text-[10px] tracking-[0.2em] uppercase font-bold text-[#6E6E73] group-hover:text-[#1D1D1F] transition-all">
                      <span>Explore Journey</span>
                      <div className={`h-[1.5px] transition-all duration-700 ${activeSection === section.id ? 'w-12 bg-[#1D1D1F]' : 'w-0 bg-transparent'}`} />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </main>

        <style>
          {`
            @keyframes pulseCustom {
              0%, 100% { opacity: 0.4; transform: scale(1); }
              50% { opacity: 0.7; transform: scale(1.1); }
            }
            .animate-pulse-custom {
              animation: pulseCustom 12s cubic-bezier(0.4, 0, 0.2, 1) infinite;
            }
          `}
        </style>
      </div>
    </>
  );
};

export default BeingView;
