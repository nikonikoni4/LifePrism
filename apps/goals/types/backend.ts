/**
 * Backend Data Transfer Objects (DTOs)
 * Defined to match backend Pydantic models in goal_schemas.py
 */

// ============================================================================
// Goal Backend Types
// ============================================================================

export interface BackendMilestoneItem {
    id: string;
    content: string;
    state: number;
    finish_time: string | null;
    order_index: number;
}

export interface BackendJournalEntry {
    id: string;
    date: string;
    time: string | null;
    content: string;
    mood: string;
    duration: number;
    tags: string[];
}

export interface BackendGoalItem {
    id: string;
    name: string;
    content: string;
    color: string;
    created_at: string;
    link_to_category: string | null;
    link_to_sub_category: string | null;
    start_date: string | null;
    expected_finished_at: string | null;
    value: string | null;
    commitment: string | null;
    time_invested: string;
    track_time_automatically: boolean;
    milestones: BackendMilestoneItem[];
    journal: BackendJournalEntry[];
    status: string;
    order_index: number;
    days_started: number | null;
}

export interface BackendGoalListResponse {
    items: BackendGoalItem[];
    total: number;
}

export interface CreateGoalRequest {
    name: string;
    content?: string;
    color?: string;
    link_to_category_id?: string | null;
    link_to_sub_category_id?: string | null;
    start_date?: string | null;
    expected_finished_at?: string | null;
    value?: string | null;
    commitment?: string | null;
    track_time_automatically?: boolean;
}

export interface UpdateGoalRequest {
    name?: string;
    content?: string;
    color?: string;
    link_to_category_id?: string | null;
    link_to_sub_category_id?: string | null;
    start_date?: string | null;
    expected_finished_at?: string | null;
    value?: string | null;
    commitment?: string | null;
    time_invested?: number;  // 秒，仅手动模式有效
    track_time_automatically?: boolean;
    milestones?: string;
    status?: string;
}

// ============================================================================
// PlanDoc Backend Types
// ============================================================================

export interface BackendPlanDocItem {
    id: string;
    goal_id: string;
    content: string;
    status: string;
    order_index: number;
    created_at: string;
    updated_at: string | null;
}

export interface BackendPlanDocListResponse {
    items: BackendPlanDocItem[];
}

export interface CreatePlanDocApiRequest {
    goal_id: string | null;
    id: string;
    content?: string;
}

export interface UpdatePlanDocApiRequest {
    new_id?: string;
    content?: string;
    status?: string;
}

// ============================================================================
// Todo Backend Types
// ============================================================================

export interface BackendTodoItem {
    id: number;
    content: string;
    parent_id: number | null;
    link_to_goal_id: string | null;
    plan_doc_id: string | null;
    source_anchor_id: string | null;
    state: string;
    date: string | null;
    expected_finished_at: string | null;
    actual_finished_at: string | null;
    delay_days: number | null;
    delay_reason: string | null;
    color: string;
    order_index: number;
    pool_order_index: number | null;
    waid_order: number | null;
    created_at: string | null;
}

export interface BackendTodoListResponse {
    items: BackendTodoItem[];
}

// 待删除任务预览
export interface TodoDeletePreview {
    id: number;
    content: string;
    state: string;
    source_anchor_id: string | null;
}

export interface BackendSyncResponse {
    created: number;
    updated: number;
    deleted: number;
    cleaned: number;
    total: number;
    to_delete: TodoDeletePreview[] | null;  // dry_run 模式返回
}

export interface BackendUpdateTodoResponse {
    item: BackendTodoItem;
    md_synced: boolean;
}

export interface BackendCreateTodoResponse {
    item: BackendTodoItem;
}
