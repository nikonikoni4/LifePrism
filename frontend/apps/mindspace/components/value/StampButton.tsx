import React from 'react';
import { motion } from 'framer-motion';

interface StampButtonProps {
  keyword: string;
  isSelected: boolean;
  onClick: () => void;
}

export const StampButton: React.FC<StampButtonProps> = ({
  keyword,
  isSelected,
  onClick,
}) => {
  return (
    <motion.button
      whileTap={{ scale: 0.95 }}
      whileHover={{ scale: 1.05 }}
      transition={{ type: 'spring', stiffness: 400, damping: 17 }}
      onClick={onClick}
      className={`
        relative px-4 py-2 rounded-md border-2 font-serif font-bold text-sm tracking-widest
        transition-all duration-300
        ${
          isSelected
            ? 'border-[#A64B4B] text-[#A64B4B] bg-white/40 shadow-lg scale-110'
            : 'border-[#2C3835] text-[#2C3835] bg-white/20 opacity-100 hover:opacity-80'
        }
      `}
      aria-label={`筛选价值：${keyword}`}
    >
      {keyword}
    </motion.button>
  );
};
