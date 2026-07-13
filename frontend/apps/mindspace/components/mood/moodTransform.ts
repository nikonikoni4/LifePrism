import type { MoodTypeItem, MoodTypeUI, MoodEntryItem, MoodEntryUI } from './types';

export function toMoodTypeUI(item: MoodTypeItem): MoodTypeUI {
  return {
    ...item,
    text: item.name,
    isDark: item.is_dark === 1,
    glow: `${item.color}99`,
  };
}

const FALLBACK_MOOD: MoodTypeUI = {
  id: 'unknown',
  name: '未知',
  icon: 'HelpCircle',
  color: '#94a3b8',
  score: 50,
  is_dark: 0,
  sort_order: 0,
  created_at: '',
  text: '未知',
  isDark: false,
  glow: '#94a3b899',
};

export function toMoodEntryUI(
  entry: MoodEntryItem,
  typesMap: Map<string, MoodTypeUI>,
): MoodEntryUI {
  const mood = typesMap.get(entry.mood_type_id) ?? FALLBACK_MOOD;
  return {
    ...entry,
    mood,
    timestamp: new Date(entry.event_time),
    note: entry.content,
    impacts: entry.factors,
  };
}
