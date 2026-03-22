
import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Navbar from './components/Navbar';
import BlobBackground from './components/BlobBackground';
import BeingView from './components/being/BeingView';
import EmotionView from './components/mood/EmotionView';
import JournalView from './components/journal/journal';
import CommitmentView from './components/commitment/commitment';
import { ValueView } from './components/value/ValueView';
import UniversalGuide from './components/shared/UniversalGuide';
import MindSpaceHome from './components/mindSpace';
import { getDailyQuote } from './services/geminiService';

type ViewState = 'home' | 'being' | 'mood' | 'journal' | 'commitment' | 'value';

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<ViewState>('home');
  const [showGuide, setShowGuide] = useState(false);

  // Still fetch quote for potential future use or if we want to pass it down
  useEffect(() => {
    const fetchQuote = async () => {
        await getDailyQuote();
    };
    fetchQuote();
  }, []);

  const handleNavigate = (view: ViewState) => {
    setCurrentView(view);
  };

  const isHome = currentView === 'home';

  return (
    <div className="min-h-screen w-full relative overflow-hidden bg-white">
      
      {/* Universal Guide Modal */}
      <UniversalGuide isOpen={showGuide} onClose={() => setShowGuide(false)} />

      {/* 
        FULL SCREEN OVERLAY FOR SUB-VIEWS
        This sits on top of the entire layout.
      */}
      <AnimatePresence mode="wait">
        {currentView === 'being' && (
          <motion.div 
            key="being-view"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.05 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="fixed inset-0 z-[100] bg-white overflow-y-auto"
          >
            <BeingView onBack={() => handleNavigate('home')} onOpenGuide={() => setShowGuide(true)} />
          </motion.div>
        )}
        
        {currentView === 'mood' && (
          <motion.div 
            key="mood-view"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="fixed inset-0 z-[100] bg-white overflow-hidden"
          >
            <EmotionView onBack={() => handleNavigate('home')} onNavigate={handleNavigate} onOpenGuide={() => setShowGuide(true)} />
          </motion.div>
        )}

        {currentView === 'journal' && (
          <motion.div 
            key="journal-view"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="fixed inset-0 z-[100] bg-white overflow-hidden"
          >
            <JournalView onBack={() => handleNavigate('home')} onOpenGuide={() => setShowGuide(true)} />
          </motion.div>
        )}

        {currentView === 'commitment' && (
          <motion.div
            key="commitment-view"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="fixed inset-0 z-[100] bg-[#F2F4F1] overflow-y-auto"
          >
            <CommitmentView onBack={() => handleNavigate('home')} />
          </motion.div>
        )}

        {currentView === 'value' && (
          <motion.div
            key="value-view"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
            className="fixed inset-0 z-[100] overflow-hidden"
          >
            <ValueView onBack={() => handleNavigate('home')} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Global Background and Navbar - Hidden on Home for the Zen Aesthetic */}
      {!isHome && <BlobBackground />}
      {!isHome && <Navbar onNavigate={handleNavigate} onOpenGuide={() => setShowGuide(true)} />}

      {/* Main Content Area */}
      <main className="w-full h-full transition-all duration-500">
        <AnimatePresence mode="wait">
          {isHome && (
            <motion.div 
              key="home"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.8 }}
              className="absolute inset-0"
            >
              <MindSpaceHome onNavigate={handleNavigate} />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
      
    </div>
  );
};

export default App;
