// ===== 后端原始类型（与 API 响应对齐）=====

export interface MoodTypeItem {
  id: string;
  name: string;
  icon: string;
  color: string;
  score: number;
  is_dark: number;
  sort_order: number;
  created_at: string;
}

export interface MoodEntryItem {
  id: string;
  mood_type_id: string;
  score: number;
  content: string | null;
  factors: string[];
  created_at: string;
  event_time: string;
}

export interface MoodImpactItem {
  id: number;
  name: string;
  sort_order: number;
  created_at: string;
}

// ===== 前端 UI 扩展类型 =====

export interface MoodTypeUI extends MoodTypeItem {
  text: string;
  isDark: boolean;
  glow: string;
}

export interface MoodEntryUI extends MoodEntryItem {
  mood: MoodTypeUI;
  timestamp: Date;
  note: string | null;
  impacts: string[];
}

// ===== 请求类型 =====

export interface CreateMoodTypeRequest {
  name: string;
  icon: string;
  color: string;
  score: number;
  is_dark?: number;
  sort_order?: number;
}

export interface UpdateMoodTypeRequest {
  name?: string;
  icon?: string;
  color?: string;
  score?: number;
  is_dark?: number;
  sort_order?: number;
}

export interface CreateMoodEntryRequest {
  mood_type_id: string;
  content?: string;
  factors?: string[];
  event_time?: string;
}

export interface UpdateMoodEntryRequest {
  mood_type_id?: string;
  content?: string | null;
  factors?: string[];
}

export interface CreateMoodImpactRequest {
  name: string;
  sort_order?: number;
}
