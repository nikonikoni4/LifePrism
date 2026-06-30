/**
 * 背景色管理 Hook
 */
import { useState, useEffect } from 'react';

const STORAGE_KEY_HSL = 'diary-bg-hsl';

interface HSL {
  h: number;
  s: number;
  l: number;
}

export function useBackgroundColor() {
  const [hsl, setHsl] = useState<HSL>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_HSL);
      return saved ? JSON.parse(saved) : { h: 200, s: 15, l: 92 };
    } catch {
      return { h: 200, s: 15, l: 92 };
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_HSL, JSON.stringify(hsl));
  }, [hsl]);

  const handleHslChange = (key: keyof HSL, value: string) => {
    setHsl(prev => ({ ...prev, [key]: parseInt(value) }));
  };

  const bgColor = `hsl(${hsl.h}, ${hsl.s}%, ${hsl.l}%)`;

  return { hsl, setHsl, handleHslChange, bgColor };
}
