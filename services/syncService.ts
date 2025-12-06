/**
 * 数据同步服务
 * 负责与后端同步 ActivityWatch 数据
 */

const API_BASE_URL = 'http://localhost:8000/api/v1';

export interface SyncRequest {
    hours?: number;
    auto_classify?: boolean;
    use_incremental_sync?: boolean;
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
 * 同步 ActivityWatch 数据
 * @param request 同步请求参数
 * @returns 同步结果
 */
export async function syncActivityWatchData(
    request: SyncRequest = {}
): Promise<SyncResponse> {
    const defaultRequest: SyncRequest = {
        hours: 24,
        auto_classify: true,
        use_incremental_sync: true, // 默认使用增量同步
        ...request,
    };

    try {
        const response = await fetch(`${API_BASE_URL}/sync/activitywatch`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(defaultRequest),
        });

        if (!response.ok) {
            throw new Error(`同步失败: ${response.statusText}`);
        }

        const data: SyncResponse = await response.json();
        return data;
    } catch (error) {
        console.error('数据同步错误:', error);
        throw error;
    }
}

/**
 * 执行增量同步（从上次同步时间开始）
 */
export async function incrementalSync(): Promise<SyncResponse> {
    return syncActivityWatchData({
        hours: null,
        use_incremental_sync: true,
        auto_classify: true,
    });
}

/**
 * 执行全量同步（获取最近N小时的数据）
 * @param hours 小时数，默认24小时
 */
export async function fullSync(hours: number = 24): Promise<SyncResponse> {
    return syncActivityWatchData({
        hours,
        auto_classify: true,
        use_incremental_sync: false,
    });
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

