export type CommitmentStatus = 'active' | 'completed' | 'archived';

export interface CommitmentItem {
  id: string;
  content: string;
  value_id: string | null;
  value_keyword: string | null;
  status: CommitmentStatus;
  created_at: string;
  updated_at: string | null;
}

export interface CommitmentListResponse {
  items: CommitmentItem[];
  total: number;
}

export interface CreateCommitmentRequest {
  content: string;
  value_id: string;
}

export interface UpdateCommitmentRequest {
  content?: string;
  value_id?: string;
  status?: CommitmentStatus;
}

export interface ValueOption {
  id: string;
  keyword: string;
}
