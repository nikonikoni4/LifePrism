import React from 'react';
import { StampButton } from './StampButton';
import type { KeywordWithOrder } from './valueTypes';

interface KeywordStampBarProps {
  keywords: KeywordWithOrder[];
  selectedKeyword: string | null;
  onSelectKeyword: (keyword: string | null) => void;
}

export const KeywordStampBar: React.FC<KeywordStampBarProps> = ({
  keywords,
  selectedKeyword,
  onSelectKeyword,
}) => {
  // 按 sortOrder 降序排列
  const sortedKeywords = [...keywords].sort((a, b) => b.sortOrder - a.sortOrder);

  // 中心对称布局：左右分组
  const midIndex = Math.ceil(sortedKeywords.length / 2);
  const leftKeywords = sortedKeywords.slice(0, midIndex).reverse();
  const rightKeywords = sortedKeywords.slice(midIndex);

  return (
    <div className="fixed top-6 left-0 right-0 z-40 flex justify-center items-center gap-8">
      {/* 左侧组 */}
      <div className="flex gap-4">
        {leftKeywords.map((k) => (
          <StampButton
            key={k.keyword}
            keyword={k.keyword}
            isSelected={selectedKeyword === k.keyword}
            onClick={() => onSelectKeyword(selectedKeyword === k.keyword ? null : k.keyword)}
          />
        ))}
      </div>

      {/* 右侧组 */}
      <div className="flex gap-4">
        {rightKeywords.map((k) => (
          <StampButton
            key={k.keyword}
            keyword={k.keyword}
            isSelected={selectedKeyword === k.keyword}
            onClick={() => onSelectKeyword(selectedKeyword === k.keyword ? null : k.keyword)}
          />
        ))}
      </div>
    </div>
  );
};

/**
 * 辅助函数：从所有 values 中聚合 keywords
 */
export function getAllKeywords(
  values: Array<{ keywords: string[]; sort_order: number }>
): KeywordWithOrder[] {
  const keywordMap = new Map<string, number>();

  values.forEach(value => {
    value.keywords.forEach(keyword => {
      const currentMax = keywordMap.get(keyword) ?? 0;
      keywordMap.set(keyword, Math.max(currentMax, value.sort_order));
    });
  });

  return Array.from(keywordMap.entries()).map(([keyword, sortOrder]) => ({
    keyword,
    sortOrder,
  }));
}
