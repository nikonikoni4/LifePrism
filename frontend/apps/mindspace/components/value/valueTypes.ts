// 后端 API 返回格式
export interface ValueItem {
  id: string;
  keywords: string;              // "健康;活力;自律" (分号分隔)
  content_positive: string;
  content_negative: string;
  sort_order: number;
  created_at: string;
  updated_at: string | null;
}

// 前端内部使用格式
export interface ValueItemFrontend {
  id: string;
  keywords: string[];            // 解析为数组
  content_positive: string;
  content_negative: string;
  sort_order: number;
  created_at: string;
  updated_at: string | null;
}

// API 响应格式
export interface ValueListResponse {
  items: ValueItem[];
  total: number;
}

// 创建请求
export interface CreateValueRequest {
  keywords: string;
  content_positive: string;
  content_negative: string;
}

// 更新请求
export interface UpdateValueRequest {
  keywords?: string;
  content_positive?: string;
  content_negative?: string;
  sort_order?: number;
}

// 关键词聚合结果
export interface KeywordWithOrder {
  keyword: string;
  sortOrder: number;
}
