/**
 * Timeline Types
 * 
 * TypeScript 类型定义，对应后端 timeline_schemas.py
 */

// ============================================================================
// 缩略图 Timeline 相关类型 (来自 timeline_schemas.py)
// ============================================================================

/** 单个分类在时间块内的统计数据 */
export interface TimelineCategoryStats {
    id: string;           // 分类ID（主分类或子分类）
    name: string;         // 分类名称
    color: string;        // 分类颜色（十六进制格式）
    duration: number;     // 该分类在此时间块内的持续时长（秒）
    percentage: number;   // 占该时间块的百分比（0-100）
}

/** 单个时间块的统计数据（对应前端的 HourlyData） */
export interface TimelineBlockStats {
    start_hour: number;                    // 时间块开始小时（0-23）
    end_hour: number;                      // 时间块结束小时（1-24）
    categories: TimelineCategoryStats[];   // 该时间块内的分类统计（按时长降序排列）
    total_duration: number;                // 该时间块内的总活动时长（秒）
    empty_duration: number;                // 该时间块内的空闲时长（秒）
    empty_percentage: number;              // 空闲时间占比（0-100）
}

/** 缩略图 Timeline 完整响应 */
export interface TimelineStatsResponse {
    date: string;                          // 查询日期（YYYY-MM-DD）
    hour_granularity: number;              // 时间粒度（小时数：1/2/3/4/6）
    category_level: 'main' | 'sub';        // 分类级别（主分类/子分类）
    blocks: TimelineBlockStats[];          // 时间块列表（按小时顺序排列）
    total_tracked_duration: number;        // 当日总追踪时长（秒）
}

// ============================================================================
// 缩略图配置状态类型
// ============================================================================

/** 缩略图配置 */
export interface ThumbnailConfig {
    enabled: boolean;                      // 是否启用缩略图模式
    hourGranularity: 1 | 2 | 3 | 4 | 6;    // 时间粒度
    categoryLevel: 'main' | 'sub';         // 分类级别
    maxCategories: number;                 // 显示的最大分类数
}

// ============================================================================
// Timeline Overview 相关类型
// ============================================================================

import { TimeOverviewData } from '../../../../core/types/common-components';

/** 点击缩略图时间块后的详细概览响应 */
export interface TimelineTimeOverviewResponse {
    data: TimeOverviewData;
}

// ============================================================================
// 选中的时间范围类型
// ============================================================================

/** 选中的时间范围 */
export interface SelectedTimeRange {
    startHour: number;
    endHour: number;
}

// ============================================================================
// 重导出 common 类型
// ============================================================================

export type {
    TimeOverviewData,
    ChartSegment,
    BarConfig,
    ActivityLogItem,
    ActivityLogsResponse,
    ActivityLogsParams,
    CategoryTreeItem,
    SubCategoryTreeItem,
} from '../../../../core/types/common-components';

// ============================================================================
// Behavior Summary 相关类型
// ============================================================================

/** 单个行为分析项 */
export interface BehaviorAnalysisItem {
  title: string;           // 标题
  start_time: string;       // 开始时间，格式：YYYY-MM-DD HH:MM:SS
  end_time: string;         // 结束时间，格式：YYYY-MM-DD HH:MM:SS
  screen_count: number;     // 截图数量
  behavior_summary: string; // 总结性描述
  behaviors: string;        // 分点行为（带序号的文本）
  created_at: string;       // 创建时间
}

/** 行为分析响应 */
export interface BehaviorAnalysisResponse {
  behavior_list: BehaviorAnalysisItem[];
}
