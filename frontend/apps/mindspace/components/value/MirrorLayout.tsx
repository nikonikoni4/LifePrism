import React from 'react';
import { AnimatePresence } from 'framer-motion';
import { ValueCard } from './ValueCard';
import { CentralKeywordDisplay } from './CentralKeywordDisplay';
import type { ValueItemFrontend } from './valueTypes';

interface MirrorLayoutProps {
  values: ValueItemFrontend[];
  focusedIndex: number;
  focusedValue: ValueItemFrontend | undefined;
  editingValueId: string | null;
  editingSide: 'positive' | 'negative' | null;
  onEdit: (valueId: string, side: 'positive' | 'negative') => void;
  onSave: (valueId: string, isPositive: boolean, newContent: string) => Promise<void>;
}

export const MirrorLayout: React.FC<MirrorLayoutProps> = ({
  values,
  focusedIndex,
  focusedValue,
  editingValueId,
  editingSide,
  onEdit,
  onSave,
}) => {
  // 计算左右两侧显示的卡片索引（聚焦卡片 + 前后各一个）
  const getCardIndices = (): number[] => {
    const total = values.length;
    if (total === 0) return [];
    if (total === 1) return [0];
    if (total === 2) return [0, 1];

    const prev = (focusedIndex - 1 + total) % total;
    const next = (focusedIndex + 1) % total;
    return [prev, focusedIndex, next];
  };

  const cardIndices = getCardIndices();

  if (!focusedValue) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-500">暂无价值数据</p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-screen overflow-hidden">
      {/* 渐变背景（替代分割线） */}
      <div
        className="absolute inset-0 -z-10"
        style={{
          background:
            'linear-gradient(to right, #FFF8F0 0%, #FFE8E0 35%, #FFFFFF 50%, #F0F4F8 65%, #E0E8F0 100%)',
        }}
      />

      {/* 纸质纹理 */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.4] z-50 mix-blend-multiply">
        <svg className="w-full h-full">
          <filter id="valueNoiseFilter">
            <feTurbulence type="fractalNoise" baseFrequency="0.8" stitchTiles="stitch" />
          </filter>
          <rect width="100%" height="100%" filter="url(#valueNoiseFilter)" />
        </svg>
      </div>

      {/* 左侧卡片区（正面内容） */}
      <div className="absolute left-[8%] top-1/2 -translate-y-1/2 flex gap-6 items-center">
        <AnimatePresence mode="popLayout">
          {cardIndices.map((idx, position) => {
            const value = values[idx];
            // 只有一个卡片时聚焦；多个卡片时中间位置聚焦
            const isFocused =
              cardIndices.length === 1 ? true : position === Math.floor(cardIndices.length / 2);
            return (
              <ValueCard
                key={`left-${value.id}`}
                valueId={value.id}
                content={value.content_positive}
                isLeft={true}
                isPositive={true}
                isFocused={isFocused}
                isEditing={editingValueId === value.id && editingSide === 'positive'}
                onEdit={() => onEdit(value.id, 'positive')}
                onSave={onSave}
              />
            );
          })}
        </AnimatePresence>
      </div>

      {/* 中央关键词显示区（位于分隔线上，垂直居中） */}
      <CentralKeywordDisplay keywords={focusedValue.keywords} />

      {/* 右侧卡片区（反面内容） */}
      <div className="absolute right-[8%] top-1/2 -translate-y-1/2 flex gap-6 items-center">
        <AnimatePresence mode="popLayout">
          {cardIndices.map((idx, position) => {
            const value = values[idx];
            const isFocused =
              cardIndices.length === 1 ? true : position === Math.floor(cardIndices.length / 2);
            return (
              <ValueCard
                key={`right-${value.id}`}
                valueId={value.id}
                content={value.content_negative}
                isLeft={false}
                isPositive={false}
                isFocused={isFocused}
                isEditing={editingValueId === value.id && editingSide === 'negative'}
                onEdit={() => onEdit(value.id, 'negative')}
                onSave={onSave}
              />
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
};
