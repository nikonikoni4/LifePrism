
import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight } from 'lucide-react';

export interface DropdownItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
  variant?: 'default' | 'danger' | 'warning';
  disabled?: boolean;
  rightLabel?: string; // e.g. "⌘K"
  divider?: boolean; // Show divider above this item
}

interface DropdownMenuProps {
  trigger: React.ReactNode;
  items: DropdownItem[];
  align?: 'left' | 'right';
  width?: string;
  className?: string;
  offset?: number;
}

export const DropdownMenu: React.FC<DropdownMenuProps> = ({
  trigger,
  items,
  align = 'left',
  width = 'w-56',
  className = '',
  offset = 8
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Handle click outside to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleItemClick = (item: DropdownItem) => {
    if (item.disabled) return;
    item.onClick();
    setIsOpen(false);
  };

  return (
    <div className={`relative inline-block text-left ${className}`} ref={containerRef}>
      <div 
        onClick={() => setIsOpen(!isOpen)}
        className="cursor-pointer"
      >
        {trigger}
      </div>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -5 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className={`
              absolute z-50 mt-2 ${width} origin-top-${align === 'left' ? 'left' : 'right'}
              ${align === 'left' ? 'left-0' : 'right-0'}
              bg-white/90 backdrop-blur-xl rounded-2xl
              shadow-[0_20px_40px_-12px_rgba(0,0,0,0.12),0_0_0_1px_rgba(255,255,255,0.5)]
              border border-white/40 ring-1 ring-black/5
              overflow-hidden py-1.5 focus:outline-none
            `}
            style={{ marginTop: offset }}
          >
            {items.map((item, index) => {
              // Variant styles
              let itemStyles = "text-slate-700 hover:bg-slate-100/60 hover:text-slate-900";
              let iconColor = "text-slate-400 group-hover:text-slate-600";
              
              if (item.variant === 'danger') {
                itemStyles = "text-rose-600 hover:bg-rose-50 hover:text-rose-700";
                iconColor = "text-rose-400 group-hover:text-rose-600";
              } else if (item.variant === 'warning') {
                itemStyles = "text-amber-600 hover:bg-amber-50 hover:text-amber-700";
                iconColor = "text-amber-400 group-hover:text-amber-600";
              }

              if (item.disabled) {
                itemStyles = "text-slate-300 cursor-not-allowed hover:bg-transparent";
                iconColor = "text-slate-300";
              }

              return (
                <React.Fragment key={item.id}>
                  {item.divider && index > 0 && (
                    <div className="h-px bg-slate-100 my-1.5 mx-2" />
                  )}
                  <button
                    onClick={() => handleItemClick(item)}
                    disabled={item.disabled}
                    className={`
                      group flex items-center justify-between w-full px-3 py-2 text-sm font-medium transition-colors duration-150
                      ${itemStyles}
                    `}
                  >
                    <div className="flex items-center gap-2.5">
                      {item.icon && (
                        <span className={`transition-colors duration-150 ${iconColor}`}>
                          {item.icon}
                        </span>
                      )}
                      <span>{item.label}</span>
                    </div>
                    
                    {item.rightLabel && (
                      <span className={`text-[10px] font-mono opacity-50 ${item.variant === 'danger' ? 'text-rose-400' : 'text-slate-400'}`}>
                        {item.rightLabel}
                      </span>
                    )}
                  </button>
                </React.Fragment>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
