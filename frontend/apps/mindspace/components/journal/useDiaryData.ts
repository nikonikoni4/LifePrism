/**
 * 日记数据管理 Hook
 * 负责：加载日记、保存内容、更新 meta
 */
import { useState, useCallback, useRef } from 'react';
import { DiaryAPI } from './diaryApi';
import type { DiaryItem, MoodLevel, ImportanceLevel } from './diaryTypes';
import { toLocalDateString } from '../../../../core/utils/dateUtils';

interface UseDiaryDataOptions {
  onSaveSuccess?: () => void;
  onSaveError?: (error: string) => void;
}

export function useDiaryData(options: UseDiaryDataOptions = {}) {
  const [diary, setDiary] = useState<DiaryItem | null>(null);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);

  // 防抖保存定时器
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 追踪当前日期，用于防止跨日期保存
  const currentDateRef = useRef<string>('');

  // 加载日记
  const loadDiary = useCallback(async (date: Date) => {
    const dateStr = toLocalDateString(date);
    currentDateRef.current = dateStr;

    try {
      setLoading(true);

      // 取消之前的防抖保存
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }

      const data = await DiaryAPI.getDiary(dateStr);
      setDiary(data);
      setContent(data.content || '');
    } catch (e) {
      console.error('加载日记失败:', e);
      setDiary(null);
      setContent('');
    } finally {
      setLoading(false);
    }
  }, []);

  // 立即保存内容
  const saveContentNow = useCallback(async (dateStr: string, contentToSave: string) => {
    try {
      const updated = await DiaryAPI.saveContent(dateStr, { content: contentToSave });
      setDiary(prev => prev ? { ...prev, word_count: updated.word_count, updated_at: updated.updated_at } : prev);
      options.onSaveSuccess?.();
    } catch (e) {
      console.error('保存日记内容失败:', e);
      options.onSaveError?.('保存失败，请重试');
    }
  }, [options]);

  // 防抖保存内容
  const saveContentDebounced = useCallback((newContent: string, delay: number = 1500) => {
    setContent(newContent);
    const targetDate = currentDateRef.current;

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }

    saveTimerRef.current = setTimeout(() => {
      saveTimerRef.current = null;
      saveContentNow(targetDate, newContent);
    }, delay);
  }, [saveContentNow]);

  // 立即 flush 挂起的保存
  const flushPendingSave = useCallback(async () => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
      await saveContentNow(currentDateRef.current, content);
    }
  }, [content, saveContentNow]);

  // 更新 meta
  const updateMood = useCallback(async (mood: MoodLevel) => {
    if (!diary) return;
    try {
      const updated = await DiaryAPI.updateMeta(diary.date, { mood });
      setDiary(prev => prev ? { ...prev, mood: updated.mood } : prev);
    } catch (e) {
      console.error('更新心情失败:', e);
    }
  }, [diary]);

  const updateImportance = useCallback(async (importance: ImportanceLevel) => {
    if (!diary) return;
    try {
      const updated = await DiaryAPI.updateMeta(diary.date, { importance });
      setDiary(prev => prev ? { ...prev, importance: updated.importance } : prev);
    } catch (e) {
      console.error('更新重要程度失败:', e);
    }
  }, [diary]);

  const updateCustomTags = useCallback(async (tags: string[]) => {
    if (!diary) return;
    try {
      const updated = await DiaryAPI.updateMeta(diary.date, { custom_tags: tags });
      setDiary(prev => prev ? { ...prev, custom_tags: updated.custom_tags } : prev);
    } catch (e) {
      console.error('更新自定义标签失败:', e);
    }
  }, [diary]);

  return {
    diary,
    setDiary,
    content,
    setContent,
    loading,
    loadDiary,
    saveContentDebounced,
    saveContentNow,
    flushPendingSave,
    updateMood,
    updateImportance,
    updateCustomTags,
  };
}
