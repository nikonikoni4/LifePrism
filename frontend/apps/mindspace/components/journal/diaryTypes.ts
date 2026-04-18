/**
 * 日记模块类型定义
 * 与后端 diary_schemas.py 对应
 */

export type MoodLevel = 'very_happy' | 'happy' | 'calm' | 'bad' | 'very_bad';
export type ImportanceLevel = 'important' | 'normal' | 'unimportant';
export type ExistingSummaryMode = 'regenerate_all' | 'regenerate_changed' | 'skip_existing';

export interface DiaryItem {
  date: string;
  mood: MoodLevel | null;
  importance: ImportanceLevel | null;
  custom_tags: string[];
  word_count: number;
  ai_summary: string | null;
  content: string;
  created_at: string;
  updated_at: string | null;
}

export interface DiaryMetaItem {
  date: string;
  mood: MoodLevel | null;
  importance: ImportanceLevel | null;
  custom_tags: string[];
  word_count: number;
  ai_summary: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface UpdateDiaryMetaRequest {
  mood?: MoodLevel | null;
  importance?: ImportanceLevel | null;
  custom_tags?: string[];
}

export interface SaveDiaryContentRequest {
  content: string;
}

export interface DiaryAISummaryResponse {
  content: string;
}

export interface TemplateItem {
  name: string;
  content: string;
}

export interface GenerateDiaryAISummaryRangeRequest {
  start_date: string;
  end_date: string;
  mode: ExistingSummaryMode;
}

export interface GenerateDiaryAISummaryRangeResponse {
  created_dates: string[];
  updated_dates: string[];
}

export interface SliderOption<T extends string> {
  value: T;
  label: string;
  color: string;
}
