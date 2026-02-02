/**
 * PlanDoc API
 * /api/v2/plan-docs
 */

import { createApiV2UrlGetter } from '../../../services/apiConfig';
import { PlanDoc } from '../types';
import {
    BackendPlanDocItem,
    BackendPlanDocListResponse,
    CreatePlanDocApiRequest,
    UpdatePlanDocApiRequest
} from '../types/backend';

// API base URL getter
// This points to /api/v2 (Default)
const getApiBase = createApiV2UrlGetter('/goal');

// ============================================================================
// Type Conversion Functions
// ============================================================================

function mapBackendPlanDocToFrontend(backend: BackendPlanDocItem): PlanDoc {
    return {
        id: backend.id,
        goalId: backend.goal_id,
        content: backend.content,
        status: (backend.status as PlanDoc['status']) || 'active',
        createdAt: backend.created_at,
        updatedAt: backend.updated_at || backend.created_at,
    };
}

function mapFrontendPlanDocToCreateRequest(frontend: Partial<PlanDoc>): CreatePlanDocApiRequest {
    return {
        goal_id: frontend.goalId || null,
        id: frontend.id || '',
        content: frontend.content || '',
    };
}

function mapFrontendPlanDocToUpdateRequest(frontend: Partial<PlanDoc>): UpdatePlanDocApiRequest {
    const request: UpdatePlanDocApiRequest = {};

    // if (frontend.title !== undefined) request.title = frontend.title; // Title removed
    if (frontend.content !== undefined) request.content = frontend.content;
    if (frontend.status !== undefined) request.status = frontend.status;

    return request;
}

// ============================================================================
// API Functions
// ============================================================================

export const planDocApi = {
    /**
     * Get plan docs, optionally filtered by goal
     */
    getPlanDocs: async (goalId?: string): Promise<PlanDoc[]> => {
        const queryParams = new URLSearchParams();
        if (goalId) queryParams.append('goal_id', goalId);

        const queryString = queryParams.toString();
        // Correct URL: /api/v2/plan-docs
        const url = queryString ? `${getApiBase()}/plan-docs?${queryString}` : `${getApiBase()}/plan-docs`;

        const res = await fetch(url);
        if (!res.ok) {
            throw new Error(`Failed to fetch plan docs: ${res.status}`);
        }

        const data: BackendPlanDocListResponse = await res.json();
        return data.items.map(mapBackendPlanDocToFrontend);
    },

    /**
     * Get a single plan doc by ID
     */
    getPlanDocDetail: async (docId: string): Promise<PlanDoc> => {
        const res = await fetch(`${getApiBase()}/plan-docs/${docId}`);
        if (!res.ok) {
            throw new Error(`Failed to fetch plan doc: ${res.status}`);
        }

        const data: BackendPlanDocItem = await res.json();
        return mapBackendPlanDocToFrontend(data);
    },

    /**
     * Create a new plan doc
     */
    createPlanDoc: async (planDoc: Partial<PlanDoc>): Promise<PlanDoc> => {
        const request = mapFrontendPlanDocToCreateRequest(planDoc);

        const res = await fetch(`${getApiBase()}/plan-docs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!res.ok) {
            throw new Error(`Failed to create plan doc: ${res.status}`);
        }

        const data: BackendPlanDocItem = await res.json();
        return mapBackendPlanDocToFrontend(data);
    },

    /**
     * Update an existing plan doc
     */
    updatePlanDoc: async (docId: string, planDoc: Partial<PlanDoc>, newId?: string): Promise<PlanDoc> => {
        const request = mapFrontendPlanDocToUpdateRequest(planDoc);

        // Add new_id to request if provided (for renaming)
        if (newId) {
            request.new_id = newId;
        }

        const res = await fetch(`${getApiBase()}/plan-docs/${docId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!res.ok) {
            throw new Error(`Failed to update plan doc: ${res.status}`);
        }

        const data: BackendPlanDocItem = await res.json();
        return mapBackendPlanDocToFrontend(data);
    },

    /**
     * Delete a plan doc
     */
    deletePlanDoc: async (docId: string): Promise<boolean> => {
        const res = await fetch(`${getApiBase()}/plan-docs/${docId}`, {
            method: 'DELETE',
        });
        return res.ok;
    },
};
