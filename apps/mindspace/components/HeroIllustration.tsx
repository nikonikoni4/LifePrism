
import React from 'react';
import { Sparkles, Leaf, CloudSun } from 'lucide-react';
import { motion } from 'framer-motion';

const HeroIllustration: React.FC = () => {
  return (
    <div className="relative w-full h-[500px] flex items-center justify-center">
      
      {/* Abstract Background Shapes for Illustration */}
      <motion.div 
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 1 }}
        className="absolute w-[90%] h-[90%] rounded-[3rem] rotate-3 transform z-0 top-4 right-4 bg-orange-100"
      />
      <motion.div 
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 1, delay: 0.2 }}
        className="absolute w-[90%] h-[90%] bg-white border-4 border-slate-900 rounded-[3rem] -rotate-2 transform z-10 overflow-hidden flex flex-col relative"
      >
        
        {/* Top Decorative Circle */}
        <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full z-0 bg-rose-200 opacity-50"></div>
        
        {/* Main Image Content */}
        <div className="w-full h-full flex flex-col items-center justify-center p-8 z-20 relative">
          
          <motion.div 
            animate={{ y: [0, -10, 0] }} 
            transition={{ repeat: Infinity, duration: 4 }}
            className="mb-6 relative"
          >
             {/* Central Figure Representation (Abstract Person/Soul) */}
             <div className="w-48 h-48 rounded-full flex items-center justify-center relative overflow-hidden bg-slate-900">
                <img 
                  src="https://picsum.photos/400/400?grayscale&blur=2" 
                  alt="Mind Space Texture" 
                  className="absolute inset-0 w-full h-full object-cover opacity-40"
                />
                <Leaf className="w-24 h-24 text-white relative z-10" />
             </div>
             
             {/* Floating Elements */}
             <div className="absolute -right-8 top-0 bg-white p-3 rounded-2xl shadow-xl border-2 border-slate-100">
               <CloudSun className="w-8 h-8 text-orange-400" />
             </div>
             <div className="absolute -left-6 bottom-4 bg-white p-3 rounded-2xl shadow-xl border-2 border-slate-100">
               <Sparkles className="w-8 h-8 text-purple-400" />
             </div>
          </motion.div>

          <div className="text-center space-y-2 max-w-xs">
            <h3 className="font-bold text-2xl text-slate-900">Inner Peace</h3>
            <p className="text-slate-500 text-sm">Find balance in the chaos of daily life through reflection.</p>
          </div>
          
          {/* Decorative Plant-like elements */}
          <div className="absolute bottom-0 right-8 flex flex-col items-center">
             <div className="w-1 h-12 rounded-full bg-green-800"></div>
             <div className="w-8 h-8 border-2 border-slate-900 rounded-b-full bg-white relative -mt-1"></div>
          </div>

        </div>

        {/* Kanji or Decorative Text */}
        <div className="absolute top-8 left-8">
           <span className="writing-vertical text-4xl font-serif text-slate-300 opacity-60 select-none">
             平静
           </span>
        </div>

      </motion.div>
    </div>
  );
};

export default HeroIllustration;
