/**
 * GoalsV2 API Service Layer
 *
 * Provides API calls and type conversion between backend GoalItem and frontend Goal types.
 */

import { createApiV2UrlGetter } from '../../services/apiConfig';
import { Goal, ThemeKey, MilestoneItem, JournalEntry } from './types';

// API base URL getter
const getApiBase = createApiV2UrlGetter('/goal');

// ============================================================================
// Backend Types (matching goal_schemas.py)
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
    time_unit: string;
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
    time_invested?: number;
    time_unit?: string;
    track_time_automatically?: boolean;
    milestones?: string;
    status?: string;
}

// ============================================================================
// Color <-> Theme Mapping
// ============================================================================

const COLOR_TO_THEME: Record<string, ThemeKey> = {
    '#5B8FF9': 'indigo',
    '#6366F1': 'indigo',
    '#F43F5E': 'rose',
    '#F59E0B': 'amber',
    '#10B981': 'emerald',
    '#8B5CF6': 'violet',
    '#06B6D4': 'cyan',
};

const THEME_TO_COLOR: Record<ThemeKey, string> = {
    'indigo': '#6366F1',
    'rose': '#F43F5E',
    'amber': '#F59E0B',
    'emerald': '#10B981',
    'violet': '#8B5CF6',
    'cyan': '#06B6D4',
};

function colorToTheme(color: string): ThemeKey {
    return COLOR_TO_THEME[color] || 'indigo';
}

function themeToColor(theme: ThemeKey): string {
    return THEME_TO_COLOR[theme] || '#6366F1';
}

// ============================================================================
// Date Format Conversion
// ============================================================================

/**
 * Convert YYYY-MM-DD to MM.DD display format (for UI display only)
 */
export function formatDateForDisplay(dateStr: string | null): string {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length === 3) {
        return `${parts[1]}.${parts[2]}`;
    }
    return dateStr;
}

/**
 * Ensure date is in YYYY-MM-DD format for API
 * Handles both MM.DD (legacy) and YYYY-MM-DD formats
 */
function formatDateForApi(displayDate: string): string | null {
    if (!displayDate) return null;
    // If already in YYYY-MM-DD format, return as is
    if (displayDate.includes('-') && displayDate.length === 10) {
        return displayDate;
    }
    // Legacy MM.DD format conversion
    const parts = displayDate.split('.');
    if (parts.length === 2) {
        const year = new Date().getFullYear();
        return `${year}-${parts[0].padStart(2, '0')}-${parts[1].padStart(2, '0')}`;
    }
    return null;
}

// ============================================================================
// Type Conversion Functions
// ============================================================================

/**
 * Convert backend GoalItem to frontend Goal
 * Note: Dates are kept in YYYY-MM-DD format for date input compatibility
 */
export function mapBackendGoalToFrontend(backend: BackendGoalItem): Goal {
    const milestones: MilestoneItem[] = (backend.milestones || []).map(m => ({
        id: m.id,
        content: m.content,
        state: m.state,
        finishTime: m.finish_time || null,
        orderIndex: m.order_index,
    }));

    const journal: JournalEntry[] = (backend.journal || []).map(j => ({
        id: j.id,
        date: j.date, // Keep YYYY-MM-DD format
        time: j.time || '',
        content: j.content,
        mood: (j.mood as JournalEntry['mood']) || 'neutral',
        duration: j.duration,
        tags: j.tags || [],
    }));

    return {
        id: backend.id,
        title: backend.name,
        category: backend.link_to_category || '',
        theme: colorToTheme(backend.color),
        timeInvested: backend.time_invested || '0',
        unit: backend.time_unit || 'HRS',
        startDate: backend.start_date || '', // Keep YYYY-MM-DD format
        endDate: backend.expected_finished_at || '', // Keep YYYY-MM-DD format
        value: backend.value || '',
        commitment: backend.commitment || '',
        details: backend.content || '',
        status: (backend.status as Goal['status']) || 'active',
        milestones,
        journal,
        daysStarted: backend.days_started || undefined,
    };
}

/**
 * Convert frontend Goal to backend CreateGoalRequest
 */
export function mapFrontendGoalToCreateRequest(frontend: Partial<Goal>): CreateGoalRequest {
    return {
        name: frontend.title || '',
        content: frontend.details || '',
        color: frontend.theme ? themeToColor(frontend.theme) : '#6366F1',
        start_date: formatDateForApi(frontend.startDate || ''),
        expected_finished_at: formatDateForApi(frontend.endDate || ''),
        value: frontend.value || null,
        commitment: frontend.commitment || null,
        track_time_automatically: true,
    };
}

/**
 * Convert frontend Goal to backend UpdateGoalRequest
 */
export function mapFrontendGoalToUpdateRequest(frontend: Partial<Goal>): UpdateGoalRequest {
    const request: UpdateGoalRequest = {};

    if (frontend.title !== undefined) request.name = frontend.title;
    if (frontend.details !== undefined) request.content = frontend.details;
    if (frontend.theme !== undefined) request.color = themeToColor(frontend.theme);
    if (frontend.startDate !== undefined) request.start_date = formatDateForApi(frontend.startDate);
    if (frontend.endDate !== undefined) request.expected_finished_at = formatDateForApi(frontend.endDate);
    if (frontend.value !== undefined) request.value = frontend.value || null;
    if (frontend.commitment !== undefined) request.commitment = frontend.commitment || null;
    if (frontend.unit !== undefined) request.time_unit = frontend.unit;
    if (frontend.status !== undefined) request.status = frontend.status;

    if (frontend.milestones !== undefined) {
        const backendMilestones = frontend.milestones.map(m => ({
            id: m.id,
            content: m.content,
            state: m.state,
            finish_time: m.finishTime ? formatDateForApi(m.finishTime) : null,
            order_index: m.orderIndex,
        }));
        request.milestones = JSON.stringify(backendMilestones);
    }

    return request;
}

// ============================================================================
// API Functions
// ============================================================================

export const goalsV2Api = {
    /**
     * Get all goals
     */
    getGoals: async (params?: {
        status?: string;
        page?: number;
        pageSize?: number;
    }): Promise<Goal[]> => {
        const queryParams = new URLSearchParams();
        if (params?.status) queryParams.append('status', params.status);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.pageSize) queryParams.append('page_size', params.pageSize.toString());

        const queryString = queryParams.toString();
        const url = queryString ? `${getApiBase()}/goals?${queryString}` : `${getApiBase()}/goals`;

        const res = await fetch(url);
        if (!res.ok) {
            throw new Error(`Failed to fetch goals: ${res.status}`);
        }

        const data: BackendGoalListResponse = await res.json();
        return data.items.map(mapBackendGoalToFrontend);
    },

    /**
     * Get a single goal by ID
     */
    getGoal: async (id: string): Promise<Goal> => {
        const res = await fetch(`${getApiBase()}/goals/${id}`);
        if (!res.ok) {
            throw new Error(`Failed to fetch goal: ${res.status}`);
        }

        const data: BackendGoalItem = await res.json();
        return mapBackendGoalToFrontend(data);
    },

    /**
     * Create a new goal
     */
    createGoal: async (goal: Partial<Goal>): Promise<Goal> => {
        const request = mapFrontendGoalToCreateRequest(goal);

        const res = await fetch(`${getApiBase()}/goals`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!res.ok) {
            throw new Error(`Failed to create goal: ${res.status}`);
        }

        const data: BackendGoalItem = await res.json();
        return mapBackendGoalToFrontend(data);
    },

    /**
     * Update an existing goal
     */
    updateGoal: async (id: string, goal: Partial<Goal>): Promise<Goal> => {
        const request = mapFrontendGoalToUpdateRequest(goal);

        const res = await fetch(`${getApiBase()}/goals/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!res.ok) {
            throw new Error(`Failed to update goal: ${res.status}`);
        }

        const data: BackendGoalItem = await res.json();
        return mapBackendGoalToFrontend(data);
    },

    /**
     * Delete a goal
     */
    deleteGoal: async (id: string): Promise<boolean> => {
        const res = await fetch(`${getApiBase()}/goals/${id}`, {
            method: 'DELETE',
        });
        return res.ok;
    },

    /**
     * Reorder goals
     */
    reorderGoals: async (goalIds: string[]): Promise<boolean> => {
        const res = await fetch(`${getApiBase()}/goals/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal_ids: goalIds }),
        });
        return res.ok;
    },

    /**
     * Update milestone state
     */
    updateMilestoneState: async (goalId: string, milestoneId: string, state: number): Promise<Goal> => {
        const res = await fetch(`${getApiBase()}/goals/${goalId}/milestones/${milestoneId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state }),
        });

        if (!res.ok) {
            throw new Error(`Failed to update milestone: ${res.status}`);
        }

        const data: BackendGoalItem = await res.json();
        return mapBackendGoalToFrontend(data);
    },

    /**
     * Create a journal entry for a goal
     */
    createJournal: async (goalId: string, journal: Omit<JournalEntry, 'id'>): Promise<JournalEntry> => {
        const request = {
            goal_id: goalId,
            date: journal.date,
            time: journal.time || null,
            content: journal.content,
            mood: journal.mood,
            duration: journal.duration,
            tags: journal.tags.length > 0 ? JSON.stringify(journal.tags) : null,
        };

        const res = await fetch(`${getApiBase()}/journals`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!res.ok) {
            throw new Error(`Failed to create journal: ${res.status}`);
        }

        const data: BackendJournalEntry = await res.json();
        return {
            id: data.id,
            date: data.date,
            time: data.time || '',
            content: data.content,
            mood: (data.mood as JournalEntry['mood']) || 'neutral',
            duration: data.duration,
            tags: data.tags || [],
        };
    },
};

export default goalsV2Api;
