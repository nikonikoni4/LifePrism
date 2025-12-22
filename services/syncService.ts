/**
 * 数据同步服务
 * 负责与后端同步 ActivityWatch 数据
 */

const API_BASE_URL = 'http://localhost:8000/api/v2';

export interface SyncRequest {
    auto_classify?: boolean;
}

export interface SyncTimeRangeRequest {
    start_time: string; // Format: YYYY-MM-DD HH:MM:SS
    end_time: string;   // Format: YYYY-MM-DD HH:MM:SS
    auto_classify?: boolean;
}

export interface SyncResponse {
    status: string;
    synced_events: number;
    new_apps_classified: number;
    duration: number;
    message: string;
    details?: {
        sync_mode: string;
        time_range: string;
        total_events: number;
        filtered_events: number;
        apps_to_classify: number;
        unclassified_events: number;
    };
}

/**
 * 执行增量同步（从数据库最新时间开始同步到现在）
 * @param autoClassify 是否自动分类新应用，默认开启
 */
export async function incrementalSync(autoClassify: boolean = true): Promise<SyncResponse> {
    try {
        const response = await fetch(`${API_BASE_URL}/sync/activitywatch`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                auto_classify: autoClassify,
            }),
        });

        if (!response.ok) {
            throw new Error(`同步失败: ${response.statusText}`);
        }

        const data: SyncResponse = await response.json();
        return data;
    } catch (error) {
        console.error('增量同步错误:', error);
        throw error;
    }
}

/**
 * 按时间范围同步数据
 * @param request 时间范围同步请求参数
 * @returns 同步结果
 */
export async function syncActivityWatchDataByTimeRange(
    request: SyncTimeRangeRequest
): Promise<SyncResponse> {
    try {
        const response = await fetch(`${API_BASE_URL}/sync/activitywatch/timerange`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                start_time: request.start_time,
                end_time: request.end_time,
                auto_classify: request.auto_classify ?? true,
            }),
        });

        if (!response.ok) {
            throw new Error(`同步失败: ${response.statusText}`);
        }

        const data: SyncResponse = await response.json();
        return data;
    } catch (error) {
        console.error('时间范围数据同步错误:', error);
        throw error;
    }
}

