import React from 'react';
import { motion } from 'framer-motion';

interface CentralKeywordDisplayProps {
  keywords: string[];
}

export const CentralKeywordDisplay: React.FC<CentralKeywordDisplayProps> = ({ keywords }) => {
  if (!keywords || keywords.length === 0) return null;

  return (
    <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-30 pointer-events-none">
      <div
        className="flex flex-col items-center gap-4 text-3xl text-[#2C3835] opacity-80"
        style={{ fontFamily: "'Ma Shan Zheng', cursive" }}
      >
        {keywords.map((keyword, index) => (
          <motion.div
            key={keyword}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            style={{ writingMode: 'vertical-rl' }}
          >
            【{keyword}】
          </motion.div>
        ))}
      </div>
    </div>
  );
};
