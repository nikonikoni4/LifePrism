
import React from 'react';
import { motion } from 'framer-motion';
import { FeatureItem } from '../types';

interface FeatureCardProps {
  item: FeatureItem;
  onClick?: () => void;
}

const FeatureCard: React.FC<FeatureCardProps> = ({ item, onClick }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.6, delay: item.delay }}
      onClick={onClick}
      className="flex flex-col items-center text-center p-6 group cursor-pointer"
    >
      <div 
        className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-6 transition-all duration-500 group-hover:scale-110 group-hover:rotate-3 shadow-sm border-2 border-transparent group-hover:border-slate-100 ${item.color}`}
      >
        <item.icon 
          className="w-8 h-8 text-slate-800 transition-colors duration-500" 
          strokeWidth={1.5} 
        />
      </div>
      
      <h3 className="text-xl font-bold mb-3 transition-colors duration-500 text-slate-900">{item.title}</h3>
      <p className="text-slate-500 leading-relaxed max-w-xs">
        {item.description}
      </p>
    </motion.div>
  );
};

export default FeatureCard;
