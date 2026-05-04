/**
 * Add-on 扩展功能类型定义
 */

export interface ExpandDir {
  id: string;
  name: string;
  path: string;
  description: string;
  ai_index: boolean;
  created_at: string;
}

export interface ExpandDirCreate {
  name: string;
  path: string;
  description: string;
  ai_index: boolean;
}

export interface ExpandDirListResponse {
  expand_dirs: ExpandDir[];
}
