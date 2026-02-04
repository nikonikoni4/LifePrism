
import React from 'react';
import { motion } from 'framer-motion';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  hoverEffect?: boolean;
}

export const Card: React.FC<CardProps> = ({ children, className = '', onClick, hoverEffect = false }) => {
  const Component = onClick ? motion.div : 'div';
  const interactionProps = onClick && hoverEffect ? {
    whileHover: { y: -2, boxShadow: '0 10px 30px -10px rgba(0,0,0,0.1)' },
    whileTap: { scale: 0.98 }
  } : {};

  return (
    // @ts-ignore
    <Component
      onClick={onClick}
      className={`bg-white rounded-[20px] border border-slate-100 shadow-soft-sm ${className}`}
      {...interactionProps}
    >
      {children}
    </Component>
  );
};
