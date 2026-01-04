
import React, { useState } from 'react';
import {
  User,
  Plus,
  History,
  Sparkles,
  Target,
  ArrowRight,
  Fingerprint,
  Shield,
  Gem
} from 'lucide-react';
import WhoWasITab from './WhoWasITab';
import WhoAmITab from './WhoAmITab';
import WhoIWantToBeTab from './WhoIWantToBeTab';

// --- Types ---
interface PrismCardData {
  id: string;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  color: string; // Tailwind bg class basis
  accentColor: string; // Text color
  content: React.ReactNode;
}

const BeingTabView: React.FC = () => {
  const [activeTab, setActiveTab] = useState('life-prism');
  // Default active index 2 corresponds to "Who I want to be" in the prism
  const [carouselIndex, setCarouselIndex] = useState(2);

  const sidebarItems = [
    { id: 'life-prism', label: 'Life Prism', icon: <Gem size={18} /> },
    { id: 'who-was-i', label: 'Who Was I', icon: <History size={18} /> },
    { id: 'who-am-i', label: 'Who Am I', icon: <Fingerprint size={18} /> },
    { id: 'who-i-want-to-be', label: 'Who I Want To Be', icon: <Sparkles size={18} /> },
    { id: 'shadow', label: 'Shadow Work', icon: <User size={18} /> },
    { id: 'principles', label: 'Non-negotiables', icon: <Shield size={18} /> },
  ];

  // --- Card Content Generators ---

  // 1. Past
  const renderPastContent = () => (
    <div className="p-4 h-full overflow-hidden relative">
      <div className="space-y-3 opacity-60 pointer-events-none">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-stone-100"></div>
          <div className="h-2 w-32 bg-stone-100 rounded"></div>
        </div>
        <div className="h-2 w-full bg-stone-50 rounded"></div>
        <div className="h-2 w-2/3 bg-stone-50 rounded"></div>
      </div>
      <div className="absolute inset-0 flex items-center justify-center">
        <button
          onClick={() => setActiveTab('who-was-i')}
          className="px-4 py-2 bg-stone-100 text-stone-600 rounded-xl text-xs font-bold hover:bg-stone-200 transition-colors pointer-events-auto"
        >
          Open Full Tab
        </button>
      </div>
    </div>
  );

  // 2. Present
  const renderPresentContent = () => (
    <div className="p-4 h-full overflow-hidden relative">
      <div className="space-y-3 opacity-60 pointer-events-none">
        <div className="flex items-center gap-2 mb-2">
          <div className="h-3 w-3 bg-orange-100 rounded-full"></div>
          <div className="h-2 w-24 bg-orange-50 rounded"></div>
        </div>
        <div className="p-4 bg-orange-50/20 rounded-xl border border-orange-100/50">
          <div className="h-2 w-full bg-orange-100/50 rounded mb-2"></div>
          <div className="h-2 w-2/3 bg-orange-100/50 rounded"></div>
        </div>
        <div className="p-4 bg-orange-50/20 rounded-xl border border-orange-100/50">
          <div className="h-2 w-full bg-orange-100/50 rounded mb-2"></div>
        </div>
      </div>
      <div className="absolute inset-0 flex items-center justify-center">
        <button
          onClick={() => setActiveTab('who-am-i')}
          className="px-4 py-2 bg-orange-50 text-orange-600 rounded-xl text-xs font-bold hover:bg-orange-100 transition-colors pointer-events-auto border border-orange-100"
        >
          Open Full Tab
        </button>
      </div>
    </div>
  );

  // 3. Future
  const renderFutureContent = () => (
    <div className="h-full relative overflow-hidden p-1">
      <div className="space-y-6 opacity-60 pointer-events-none">
        <div className="relative p-6 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-[2rem] text-white shadow-xl shadow-blue-500/20 overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white opacity-10 rounded-full blur-2xl -mr-10 -mt-10 pointer-events-none"></div>
          <div className="relative z-10">
            <h4 className="text-blue-100 font-medium text-sm mb-1">North Star</h4>
            <p className="text-2xl font-black tracking-tight leading-tight">
              "Build software that empowers 10,000 creators to earn a living."
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-blue-50 rounded-2xl border border-blue-100">
            <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center text-blue-500 mb-3 shadow-sm">
              <Target size={16} />
            </div>
            <p className="text-xs font-bold text-blue-400 uppercase mb-1">By 2026</p>
            <p className="text-slate-700 font-bold text-sm">CTO of own Venture</p>
          </div>
          <div className="p-4 bg-indigo-50 rounded-2xl border border-indigo-100">
            <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center text-indigo-500 mb-3 shadow-sm">
              <Sparkles size={16} />
            </div>
            <p className="text-xs font-bold text-indigo-400 uppercase mb-1">Lifestyle</p>
            <p className="text-slate-700 font-bold text-sm">Digital Nomad</p>
          </div>
        </div>
      </div>
      <div className="absolute inset-0 flex items-center justify-center z-20">
        <button
          onClick={() => setActiveTab('who-i-want-to-be')}
          className="px-4 py-2 bg-blue-50 text-blue-600 rounded-xl text-xs font-bold hover:bg-blue-100 transition-colors pointer-events-auto border border-blue-100 shadow-sm"
        >
          Open Full Tab
        </button>
      </div>
    </div>
  );

  const CARDS: PrismCardData[] = [
    {
      id: 'past',
      title: 'Who was I',
      subtitle: 'Roots & Lessons',
      icon: <History size={24} />,
      color: 'bg-stone-50',
      accentColor: 'text-stone-600',
      content: renderPastContent()
    },
    {
      id: 'present',
      title: 'Who am I',
      subtitle: 'Execution & Habits',
      icon: <Fingerprint size={24} />,
      color: 'bg-[#FFF7ED]', // Light Orange/Cream
      accentColor: 'text-orange-600',
      content: renderPresentContent()
    },
    {
      id: 'future',
      title: 'Who I want to be',
      subtitle: 'Vision & Aspiration',
      icon: <Sparkles size={24} />,
      color: 'bg-[#EFF6FF]', // Light Blue
      accentColor: 'text-blue-600',
      content: renderFutureContent()
    }
  ];

  // Helper to get circular index
  const getCardIndex = (offset: number) => {
    const len = CARDS.length;
    return (carouselIndex + offset + len) % len;
  };

  const activeCard = CARDS[carouselIndex];
  const prevCard = CARDS[getCardIndex(-1)];
  const nextCard = CARDS[getCardIndex(1)];

  // --- Main Render Content Switcher ---
  const renderMainContent = () => {
    if (activeTab === 'who-was-i') {
      return <WhoWasITab />;
    }

    if (activeTab === 'who-am-i') {
      return <WhoAmITab />;
    }

    if (activeTab === 'who-i-want-to-be') {
      return <WhoIWantToBeTab />;
    }

    if (activeTab === 'life-prism') {
      return (
        <div className="relative w-full max-w-6xl h-[600px] flex items-center justify-center">
          {/* --- PREV CARD (Left) --- */}
          <div
            onClick={() => setCarouselIndex(getCardIndex(-1))}
            className="absolute left-4 lg:left-12 top-1/2 -translate-y-1/2 w-[300px] lg:w-[380px] h-[450px] bg-white rounded-[2.5rem] shadow-xl border border-slate-200/60 p-8 flex flex-col opacity-60 scale-90 blur-[2px] hover:blur-0 hover:opacity-80 hover:scale-95 transition-all duration-500 cursor-pointer z-10 origin-right hover:z-20 group select-none"
          >
            <div className="mb-4 opacity-50 group-hover:opacity-100 transition-opacity">
              <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-wider ${prevCard.color} ${prevCard.accentColor}`}>
                {prevCard.title}
              </span>
            </div>
            <div className="flex-1 opacity-50 grayscale group-hover:grayscale-0 transition-all overflow-hidden relative">
              <div className="absolute inset-0 z-50"></div>
              {prevCard.content}
            </div>
          </div>

          {/* --- NEXT CARD (Right) --- */}
          <div
            onClick={() => setCarouselIndex(getCardIndex(1))}
            className="absolute right-4 lg:right-12 top-1/2 -translate-y-1/2 w-[300px] lg:w-[380px] h-[450px] bg-white rounded-[2.5rem] shadow-xl border border-slate-200/60 p-8 flex flex-col opacity-60 scale-90 blur-[2px] hover:blur-0 hover:opacity-80 hover:scale-95 transition-all duration-500 cursor-pointer z-10 origin-left hover:z-20 group select-none"
          >
            <div className="mb-4 opacity-50 group-hover:opacity-100 transition-opacity">
              <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-wider ${nextCard.color} ${nextCard.accentColor}`}>
                {nextCard.title}
              </span>
            </div>
            <div className="flex-1 opacity-50 grayscale group-hover:grayscale-0 transition-all overflow-hidden relative">
              <div className="absolute inset-0 z-50"></div>
              {nextCard.content}
            </div>
          </div>

          {/* --- ACTIVE CARD (Center) --- */}
          <div
            className="relative w-[340px] lg:w-[440px] h-[520px] bg-white rounded-[3rem] shadow-[0_20px_50px_-12px_rgba(0,0,0,0.1)] border border-white p-8 flex flex-col z-30 scale-100 transition-all duration-500 ease-out"
          >
            <div className="flex items-start justify-between mb-8">
              <div>
                <h2 className={`text-3xl font-black tracking-tight mb-1 ${activeCard.accentColor}`}>
                  {activeCard.title}
                </h2>
                <p className="text-slate-400 font-medium text-sm">{activeCard.subtitle}</p>
              </div>
              <div className={`p-4 rounded-2xl ${activeCard.color} ${activeCard.accentColor}`}>
                {activeCard.icon}
              </div>
            </div>

            <div className="flex-1 overflow-hidden relative">
              {activeCard.content}
            </div>

            <div className="mt-6 pt-6 border-t border-slate-50 flex justify-between items-center">
              <span className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">
                {carouselIndex + 1} / {CARDS.length}
              </span>
              <button className={`flex items-center gap-2 text-sm font-bold ${activeCard.accentColor} hover:opacity-70 transition-opacity`}>
                Refine <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="flex flex-col items-center justify-center text-center opacity-40 h-full">
        <div className="w-24 h-24 bg-slate-100 rounded-full flex items-center justify-center mb-6">
          <Fingerprint size={40} className="text-slate-300" />
        </div>
        <h3 className="text-2xl font-bold text-slate-800">Section Under Construction</h3>
        <p className="text-slate-500 max-w-xs mt-2">The "{activeTab.replace('-', ' ')}" module is currently being architected.</p>
      </div>
    );
  };

  return (
    <div className="flex h-full w-full bg-[#F8FAFC] overflow-hidden">

      {/* 1. Left Sidebar - Option Card */}
      <aside className="w-64 bg-white border-r border-slate-100 flex flex-col pt-10 pr-6 z-20">
        <h3 className="text-[10px] font-black text-slate-300 uppercase tracking-[0.25em] mb-8 pl-6">Identity Design</h3>

        <div className="space-y-2 flex-1">
          {sidebarItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 pl-6 pr-4 py-3.5 rounded-2xl text-sm font-bold transition-all duration-300 group ${isActive
                  ? 'bg-slate-900 text-white shadow-lg shadow-slate-200 scale-[1.02]'
                  : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'
                  }`}
              >
                <div className={`transition-transform duration-300 ${isActive ? 'scale-110' : 'group-hover:scale-110'}`}>
                  {item.icon}
                </div>
                <span>{item.label}</span>
                {isActive && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-white/30 animate-pulse"></div>}
              </button>
            );
          })}
        </div>

        <div className="pl-6 pr-4 py-4 mb-8 bg-gradient-to-br from-slate-50 to-slate-100 rounded-2xl border border-slate-200">
          <p className="text-xs font-medium text-slate-500 leading-relaxed italic">
            "Your identity is not a fixed object, but a fluid process of becoming."
          </p>
        </div>
      </aside>

      {/* 2. Main Content */}
      <main className="flex-1 relative flex flex-col items-center justify-center p-4 overflow-hidden perspective-1000">

        {/* Background Decor */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-100/50 rounded-full blur-3xl mix-blend-multiply opacity-50 animate-blob"></div>
          <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-purple-100/50 rounded-full blur-3xl mix-blend-multiply opacity-50 animate-blob animation-delay-2000"></div>
          <div className="absolute -bottom-32 left-1/2 w-96 h-96 bg-orange-100/50 rounded-full blur-3xl mix-blend-multiply opacity-50 animate-blob animation-delay-4000"></div>
        </div>

        {renderMainContent()}

      </main>
    </div>
  );
};

export default BeingTabView;
