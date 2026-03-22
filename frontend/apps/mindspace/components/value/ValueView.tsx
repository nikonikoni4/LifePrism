import React, { useState, useEffect, useCallback } from 'react';
import { KeywordStampBar, getAllKeywords } from './KeywordStampBar';
import { MirrorLayout } from './MirrorLayout';
import { ValueAPI } from './valueApi';
import { parseValueFromBackend, formatValueForBackend } from './valueDataConverter';
import type { ValueItemFrontend } from './valueTypes';

// 导入 Google Fonts
const FONT_LINK =
  'https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@300;400;600;900&family=Ma+Shan+Zheng&display=swap';
if (typeof document !== 'undefined' && !document.querySelector(`link[href="${FONT_LINK}"]`)) {
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = FONT_LINK;
  document.head.appendChild(link);
}

interface ValueViewProps {
  onBack?: () => void;
  onNavigate?: (view: string) => void;
}

export const ValueView: React.FC<ValueViewProps> = ({ onBack: _onBack, onNavigate: _onNavigate }) => {
  const [values, setValues] = useState<ValueItemFrontend[]>([]);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);
  const [editingValueId, setEditingValueId] = useState<string | null>(null);
  const [editingSide, setEditingSide] = useState<'positive' | 'negative' | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isScrolling, setIsScrolling] = useState(false);

  // 加载价值列表
  useEffect(() => {
    const loadValues = async () => {
      try {
        setIsLoading(true);
        const response = await ValueAPI.getList();
        const parsed = response.items.map(parseValueFromBackend);
        setValues(parsed);
        setError(null);
      } catch (err) {
        console.error('加载价值列表失败:', err);
        setError(err instanceof Error ? err.message : '加载失败');
      } finally {
        setIsLoading(false);
      }
    };
    loadValues();
  }, []);

  // 筛选后的 values
  const filteredValues = selectedKeyword
    ? values.filter(v => v.keywords.includes(selectedKeyword))
    : values;

  // 当前聚焦的 value
  const focusedValue = filteredValues[focusedIndex];

  // 筛选条件变化时重置聚焦索引，防止超出边界
  useEffect(() => {
    setFocusedIndex(0);
  }, [selectedKeyword]);

  // 滚动处理（带防抖）
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      if (isScrolling || filteredValues.length <= 1) return;

      setIsScrolling(true);
      setTimeout(() => setIsScrolling(false), 300);

      if (e.deltaY > 0) {
        setFocusedIndex(prev => (prev + 1) % filteredValues.length);
      } else {
        setFocusedIndex(prev => (prev - 1 + filteredValues.length) % filteredValues.length);
      }
    },
    [isScrolling, filteredValues.length]
  );

  // 编辑处理
  const handleEdit = (valueId: string, side: 'positive' | 'negative') => {
    setEditingValueId(valueId);
    setEditingSide(side);
  };

  // 保存处理
  const handleSave = async (valueId: string, isPositive: boolean, newContent: string) => {
    const value = values.find(v => v.id === valueId);
    if (!value) return;

    const updateData: Partial<ValueItemFrontend> = isPositive
      ? { content_positive: newContent }
      : { content_negative: newContent };

    const backendData = formatValueForBackend(updateData);

    await ValueAPI.update(valueId, backendData);

    // 更新本地状态
    setValues(prev => prev.map(v => (v.id === valueId ? { ...v, ...updateData } : v)));

    // 退出编辑态
    setEditingValueId(null);
    setEditingSide(null);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#FAF8F5]">
        <p className="text-gray-400" style={{ fontFamily: "'Noto Serif SC', serif" }}>
          加载中...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-[#FAF8F5] gap-4">
        <p className="text-red-400">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 border border-[#2C3835] text-[#2C3835] rounded-md hover:bg-[#2C3835] hover:text-white transition-colors"
        >
          重试
        </button>
      </div>
    );
  }

  if (values.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-[#FAF8F5] gap-4">
        <p
          className="text-gray-500 text-lg"
          style={{ fontFamily: "'Ma Shan Zheng', cursive" }}
        >
          尚未定义价值观
        </p>
        <p className="text-gray-400 text-sm">价值观是指引人生的灯塔，让我们一起探索</p>
      </div>
    );
  }

  return (
    <div onWheel={handleWheel} className="relative w-full h-screen">
      <KeywordStampBar
        keywords={getAllKeywords(values)}
        selectedKeyword={selectedKeyword}
        onSelectKeyword={setSelectedKeyword}
      />
      <MirrorLayout
        values={filteredValues}
        focusedIndex={focusedIndex}
        focusedValue={focusedValue}
        editingValueId={editingValueId}
        editingSide={editingSide}
        onEdit={handleEdit}
        onSave={handleSave}
      />
    </div>
  );
};
