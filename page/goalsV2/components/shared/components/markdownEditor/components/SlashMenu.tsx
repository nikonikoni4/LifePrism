import React, { useState, useEffect, useCallback, useRef } from 'react';
import { SlashCommandItem } from '../types';

interface SlashMenuProps {
  items: SlashCommandItem[];
  command: (item: SlashCommandItem) => void;
  clientRect: (() => DOMRect | null) | null;
}

export const SlashMenu: React.FC<SlashMenuProps> = ({
  items,
  command,
  clientRect,
}) => {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const menuRef = useRef<HTMLDivElement>(null);

  const selectItem = useCallback(
    (index: number) => {
      const item = items[index];
      if (item) {
        command(item);
      }
    },
    [items, command]
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [items]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + items.length) % items.length);
        return true;
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % items.length);
        return true;
      }

      if (event.key === 'Enter') {
        event.preventDefault();
        selectItem(selectedIndex);
        return true;
      }

      return false;
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [items.length, selectedIndex, selectItem]);

  // Scroll selected item into view
  useEffect(() => {
    const selectedElement = menuRef.current?.querySelector(
      `[data-index="${selectedIndex}"]`
    );
    selectedElement?.scrollIntoView({ block: 'nearest' });
  }, [selectedIndex]);

  if (items.length === 0) {
    return null;
  }

  const rect = clientRect?.();
  const style: React.CSSProperties = rect
    ? {
        position: 'fixed',
        top: rect.bottom + 8,
        left: rect.left,
        zIndex: 50,
      }
    : {};

  return (
    <div
      ref={menuRef}
      style={style}
      className="bg-white rounded-lg shadow-lg border border-gray-200 py-2 min-w-[220px] max-h-[300px] overflow-y-auto"
    >
      {items.map((item, index) => (
        <button
          key={item.title}
          data-index={index}
          onClick={() => selectItem(index)}
          className={`
            w-full flex items-center gap-3 px-3 py-2 text-left transition-colors duration-100
            ${index === selectedIndex
              ? 'bg-indigo-50 text-indigo-700'
              : 'text-gray-700 hover:bg-gray-50'
            }
          `}
        >
          <span className="flex-shrink-0 text-gray-500">{item.icon}</span>
          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm">{item.title}</div>
            <div className="text-xs text-gray-500 truncate">
              {item.description}
            </div>
          </div>
        </button>
      ))}
    </div>
  );
};

export default SlashMenu;
