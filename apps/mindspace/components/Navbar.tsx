
import React from 'react';
import { HelpCircle } from 'lucide-react';
import { motion } from 'framer-motion';

interface NavbarProps {
  onNavigate?: (view: 'home' | 'being') => void;
  onOpenGuide?: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ onNavigate, onOpenGuide }) => {
  return (
    <nav className="fixed top-0 left-0 w-full z-50 px-6 md:px-12 py-6 flex justify-between items-center pointer-events-none">
      {/* Top Left - Home Anchor / Logo */}
      <motion.div 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="flex items-center gap-3 cursor-pointer pointer-events-auto group"
        onClick={() => onNavigate && onNavigate('home')}
      >
        <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold shadow-md transition-all duration-500 group-hover:scale-105 bg-indigo-600">
          M
        </div>
        <span className="text-xl md:text-2xl font-bold tracking-tight transition-colors duration-500 text-slate-800">
          Mind Space
        </span>
      </motion.div>

      {/* Top Right - Actions (Corner Anchors) */}
      <motion.div 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1, ease: "easeOut" }}
        className="flex items-center gap-3 md:gap-4 pointer-events-auto"
      >
        <button 
          onClick={onOpenGuide}
          className="p-3 rounded-full transition-all duration-300 hover:scale-105 active:scale-95 bg-white/50 text-slate-600 hover:bg-white hover:text-indigo-600 hover:shadow-md backdrop-blur-sm border border-transparent hover:border-indigo-100"
          aria-label="User Guide"
        >
          <HelpCircle size={20} strokeWidth={2} />
        </button>
      </motion.div>
    </nav>
  );
};

export default Navbar;
