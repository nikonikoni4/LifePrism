/**
 * Timeline Page
 * 
 * 新版 Timeline 页面，使用 /api/v2/timeline 接口
 * 布局和功能沿袭原 TimelinePage.tsx
 */

import React, { useState, useEffect, useRef, useCallback, useLayoutEffect, useMemo } from 'react';
import {
    ChevronLeft, ChevronRight, Calendar, Smartphone, Monitor,
    AlertCircle, Clock, Tag, Loader2, X, Save, Undo2
} from 'lucide-react';

import { TimeOverviewWidget } from '../common';
import { TimelineAPIV2, ActivityLogsAPI, CategoryAPI } from './api';
import {
    TimelineStatsResponse,
    TimelineBlockStats,
    TimelineCategoryStats,
    ThumbnailConfig,
    SelectedTimeRange,
    TimeOverviewData,
    ActivityLogItem,
    CategoryTreeItem,
} from './types';

// 自定义时间块组件
import { CustomBlockLayer, CustomBlockAPI, UserCustomBlock, TodoSelectItem } from './components';

// Todo API
import { todoApi } from '../goals/api';

// ============================================================================
// 工具函数
// ============================================================================

/** 安全的日期解析函数，支持多种格式 */
const parseLocalDate = (dateStr: string): Date => {
    const dateRegex = /^(\d{4})-(\d{2})-(\d{2})$/;
    const match = dateStr.match(dateRegex);

    if (match) {
        const year = parseInt(match[1]);
        const month = parseInt(match[2]) - 1;
        const day = parseInt(match[3]);
        return new Date(year, month, day);
    } else {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) {
            throw new Error(`Invalid date format: ${dateStr}`);
        }
        return date;
    }
};

/** 格式化日期为 YYYY-MM-DD 格式 */
const formatDateToYYYYMMDD = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

/** 格式化时长（秒 → "Xh Ym" 或 "Ym"） */
const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
};

/** 格式化时间（小时浮点数 → "HH:MM"） */
const formatTime = (time: number): string => {
    const h = Math.floor(time);
    const m = Math.round((time - h) * 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
};

/** 将活动日志按小时分组 */
const groupLogsByHour = (logs: ActivityLogItem[]): Map<number, ActivityLogItem[]> => {
    const grouped = new Map<number, ActivityLogItem[]>();
    for (let hour = 0; hour < 24; hour++) {
        grouped.set(hour, []);
    }

    logs.forEach(log => {
        const startDate = new Date(log.start_time);
        const endDate = new Date(log.end_time);
        const startHour = startDate.getHours();
        const endHour = endDate.getHours();

        // 事件可能跨越多个小时，每个小时都添加一份引用
        for (let hour = startHour; hour <= Math.min(endHour, 23); hour++) {
            grouped.get(hour)?.push(log);
        }
    });

    return grouped;
};

/** 计算事件在小时行内的水平位置和宽度 */
const getHourEventStyle = (log: ActivityLogItem, hour: number): { left: string; width: string; startMinute: number; endMinute: number } => {
    const startDate = new Date(log.start_time);
    const endDate = new Date(log.end_time);

    // 计算在当前小时内的开始位置（0-60分钟映射到0-100%）
    let startMinute = 0;
    if (startDate.getHours() === hour) {
        startMinute = startDate.getMinutes() + startDate.getSeconds() / 60;
    }

    // 计算在当前小时内的结束位置
    let endMinute = 60;
    if (endDate.getHours() === hour) {
        endMinute = endDate.getMinutes() + endDate.getSeconds() / 60;
    }

    const left = (startMinute / 60) * 100;
    const width = Math.max(((endMinute - startMinute) / 60) * 100, 0.5); // 最小宽度0.5%

    return { left: `${left}%`, width: `${width}%`, startMinute, endMinute };
};

/** 事件悬停浮窗组件 */
interface EventTooltipProps {
    event: ActivityLogItem;
    position: { x: number; y: number };
}

const EventTooltip: React.FC<EventTooltipProps> = ({ event, position }) => {
    const startDate = new Date(event.start_time);
    const endDate = new Date(event.end_time);

    const formatTimeStr = (date: Date) => {
        return date.toTimeString().slice(0, 8);
    };

    const formatDurationStr = (seconds: number) => {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        }
        return `${minutes}m ${secs}s`;
    };

    return (
        <div
            className="fixed z-[100] bg-amber-50 border border-amber-300 rounded-md shadow-lg p-3 text-xs pointer-events-none"
            style={{
                left: `${position.x + 10}px`,
                top: `${position.y + 10}px`,
                minWidth: '200px',
                maxWidth: '320px',
            }}
        >
            <div className="grid gap-y-1" style={{ gridTemplateColumns: 'auto 1fr' }}>
                <span className="font-bold text-amber-800 pr-3">Start</span>
                <span className="text-amber-900">{formatTimeStr(startDate)}</span>
                <span className="font-bold text-amber-800 pr-3">Stop</span>
                <span className="text-amber-900">{formatTimeStr(endDate)}</span>
                <span className="font-bold text-amber-800 pr-3">Duration</span>
                <span className="text-amber-900">{formatDurationStr(event.duration)}</span>
                <span className="font-bold text-amber-800 pr-3">App</span>
                <span className="text-amber-900 truncate" title={event.app}>{event.app}</span>
                <span className="font-bold text-amber-800 pr-3">Title</span>
                <span className="text-amber-900 truncate" title={event.title}>{event.title}</span>
            </div>
        </div>
    );
};

// ============================================================================
// 缩略图块组件
// ============================================================================

interface ThumbnailBlockProps {
    blockData: TimelineBlockStats;
    height: number;
    maxCategories: number;
    isSelected: boolean;
    onClick: () => void;
}

/** 单个分类色块组件 */
interface CategoryBlockProps {
    id: string;
    name: string;
    color: string;
    percentage: number;
    duration: number;
    isLast?: boolean;
}

const CategoryBlock: React.FC<CategoryBlockProps> = ({
    id,
    name,
    color,
    percentage,
    duration,
    isLast = false
}) => {
    const [showTooltip, setShowTooltip] = useState(false);

    // 只有占比足够大才显示文字（>15%）
    const showText = percentage > 15;
    // 中等占比显示简化文字（>10%）
    const showSimpleText = percentage > 10 && percentage <= 15;

    return (
        <div
            className="relative group/block"
            style={{
                width: `calc(${percentage}% - 2px)`,  // 减去间隙
                marginRight: isLast ? '0' : '2px',    // 色块间隙
            }}
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
        >
            {/* 色块本体 */}
            <div
                className="h-full rounded-md overflow-hidden transition-all duration-200 
                           group-hover/block:scale-[1.02] group-hover/block:shadow-lg
                           group-hover/block:z-10 relative"
                style={{
                    background: `linear-gradient(135deg, ${color} 0%, ${adjustBrightness(color, -15)} 100%)`,
                    boxShadow: `inset 0 1px 0 rgba(255,255,255,0.2), inset 0 -1px 0 rgba(0,0,0,0.1)`,
                }}
            >
                {/* 玻璃质感高光层 */}
                <div
                    className="absolute inset-0 opacity-30 pointer-events-none"
                    style={{
                        background: 'linear-gradient(180deg, rgba(255,255,255,0.4) 0%, transparent 50%)',
                    }}
                />

                {/* 文字内容 */}
                <div className="h-full flex items-center justify-center">
                    {showText && (
                        <div className="px-2 text-center leading-tight text-white">
                            <div
                                className="font-bold truncate text-[10px]"
                                style={{
                                    textShadow: '0 1px 3px rgba(0,0,0,0.5), 0 0 8px rgba(0,0,0,0.3)',
                                }}
                            >
                                {name}
                            </div>
                            <div
                                className="text-[9px] opacity-90 font-medium"
                                style={{
                                    textShadow: '0 1px 2px rgba(0,0,0,0.4)',
                                }}
                            >
                                {formatDuration(duration)}
                            </div>
                            <div
                                className="text-[8px] opacity-75"
                                style={{
                                    textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                                }}
                            >
                                {percentage.toFixed(0)}%
                            </div>
                        </div>
                    )}
                    {showSimpleText && (
                        <div
                            className="text-[9px] font-bold text-white truncate px-1"
                            style={{
                                textShadow: '0 1px 3px rgba(0,0,0,0.5)',
                            }}
                        >
                            {name}
                        </div>
                    )}
                </div>
            </div>

            {/* Tooltip */}
            {showTooltip && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 
                                pointer-events-none animate-fade-in">
                    <div className="bg-slate-900/95 backdrop-blur-sm text-white text-xs 
                                    rounded-lg px-3 py-2 shadow-xl whitespace-nowrap
                                    border border-white/10">
                        <div className="font-bold text-sm">{name}</div>
                        <div className="text-slate-300 mt-0.5">
                            {formatDuration(duration)} · {percentage.toFixed(1)}%
                        </div>
                        {/* 小三角 */}
                        <div className="absolute top-full left-1/2 -translate-x-1/2 
                                        border-4 border-transparent border-t-slate-900/95" />
                    </div>
                </div>
            )}
        </div>
    );
};

/** 调整颜色亮度的辅助函数 */
const adjustBrightness = (hex: string, percent: number): string => {
    const color = hex.replace('#', '');
    const r = Math.max(0, Math.min(255, parseInt(color.slice(0, 2), 16) + percent));
    const g = Math.max(0, Math.min(255, parseInt(color.slice(2, 4), 16) + percent));
    const b = Math.max(0, Math.min(255, parseInt(color.slice(4, 6), 16) + percent));
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
};

const ThumbnailBlock: React.FC<ThumbnailBlockProps> = ({
    blockData,
    height,
    maxCategories,
    isSelected,
    onClick
}) => {
    const topCategories = blockData.categories.slice(0, maxCategories);
    const otherCategories = blockData.categories.slice(maxCategories);

    let otherPercentage = 0;
    let otherDuration = 0;
    let otherName = '其他';
    let otherColor = '#9CA3AF';

    if (otherCategories.length > 0) {
        otherDuration = otherCategories.reduce((sum, cat) => sum + cat.duration, 0);
        otherPercentage = otherCategories.reduce((sum, cat) => sum + cat.percentage, 0);
        const firstOther = otherCategories[0];
        otherName = `${firstOther.name}等...`;
        otherColor = firstOther.color;
    }

    return (
        <div
            className={`relative group cursor-pointer transition-all duration-200 z-[1] ${isSelected
                ? 'ring-2 ring-indigo-500 ring-inset bg-indigo-50/50 shadow-inner'
                : 'hover:bg-white/30 hover:shadow-sm'
                }`}
            style={{
                height: `${height}px`,
                // 背景改为透明，让自定义块背景能够透出
                background: isSelected
                    ? 'rgba(238, 242, 255, 0.5)'
                    : 'transparent',
            }}
            onClick={onClick}
        >
            {/* 底部分隔线 */}
            <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-gray-200 to-transparent" />

            {/* 横向堆叠条容器 */}
            <div className="absolute inset-2 flex items-stretch">
                {/* Top N 分类 */}
                {topCategories.map((cat, index) => (
                    <CategoryBlock
                        key={cat.id}
                        id={cat.id}
                        name={cat.name}
                        color={cat.color}
                        percentage={cat.percentage}
                        duration={cat.duration}
                        isLast={index === topCategories.length - 1 && otherPercentage === 0 && blockData.empty_percentage === 0}
                    />
                ))}

                {/* 其他分类 */}
                {otherPercentage > 0 && (
                    <CategoryBlock
                        id="other"
                        name={otherName}
                        color={otherColor}
                        percentage={otherPercentage}
                        duration={otherDuration}
                        isLast={blockData.empty_percentage === 0}
                    />
                )}

                {/* 空白时间 */}
                {blockData.empty_percentage > 0 && (
                    <div
                        className="rounded-md transition-all duration-200"
                        style={{
                            width: `calc(${blockData.empty_percentage}% - 2px)`,
                            marginLeft: topCategories.length > 0 || otherPercentage > 0 ? '0' : '0',
                            background: 'repeating-linear-gradient(45deg, #f3f4f6, #f3f4f6 4px, #e5e7eb 4px, #e5e7eb 8px)',
                            opacity: 0.6,
                        }}
                    />
                )}
            </div>
        </div>
    );
};

// ============================================================================
// 主组件
// ============================================================================

const Timeline: React.FC = () => {
    // === 日期状态 ===
    const [currentDate, setCurrentDate] = useState(() => formatDateToYYYYMMDD(new Date()));
    const dateInputRef = useRef<HTMLInputElement>(null);

    // === 缩略图配置 ===
    const [thumbnailConfig, setThumbnailConfig] = useState<ThumbnailConfig>({
        enabled: true,
        hourGranularity: 1,
        categoryLevel: 'main',
        maxCategories: 3,
    });

    // === 缩略图数据状态 ===
    const [thumbnailData, setThumbnailData] = useState<TimelineStatsResponse | null>(null);
    const [thumbnailLoading, setThumbnailLoading] = useState(false);
    const [thumbnailError, setThumbnailError] = useState<string | null>(null);

    // === 非缩略图模式：活动日志 ===
    const [activityLogs, setActivityLogs] = useState<ActivityLogItem[]>([]);
    const [logsLoading, setLogsLoading] = useState(false);
    const [logsError, setLogsError] = useState<string | null>(null);
    const [minDurationFilter, setMinDurationFilter] = useState<number>(3);

    // === 选中状态 ===
    const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
    const [selectedTimeRange, setSelectedTimeRange] = useState<SelectedTimeRange | null>(null);
    const [hoveredEventId, setHoveredEventId] = useState<string | null>(null);
    const [mousePosition, setMousePosition] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

    // === Overview 面板状态 ===
    const [overviewData, setOverviewData] = useState<TimeOverviewData | null>(null);
    const [overviewLoading, setOverviewLoading] = useState(false);
    const overviewCache = useRef<Map<string, TimeOverviewData>>(new Map());

    // === 分类编辑状态 ===
    const [categories, setCategories] = useState<CategoryTreeItem[]>([]);
    const [editedCategory, setEditedCategory] = useState<string | null>(null);
    const [editedSubCategory, setEditedSubCategory] = useState<string | null>(null);
    const [isSaving, setIsSaving] = useState(false);

    // === 自定义时间块状态 ===
    const [customBlocks, setCustomBlocks] = useState<UserCustomBlock[]>([]);
    const [customBlocksLoading, setCustomBlocksLoading] = useState(false);

    // === 当天待办事项状态（用于自定义时间块绑定） ===
    const [todos, setTodos] = useState<TodoSelectItem[]>([]);

    // === 缩放配置 ===
    const MIN_HOUR_HEIGHT = 30;
    const MAX_HOUR_HEIGHT = 1200;
    const DEFAULT_HOUR_HEIGHT = 80;
    const ZOOM_STEP = 1.15;
    const [hourHeight, setHourHeight] = useState<number>(DEFAULT_HOUR_HEIGHT);
    const timelineContainerRef = useRef<HTMLDivElement>(null);
    const pendingZoomRef = useRef<{ height: number; scrollTop: number } | null>(null);

    const HOUR_HEIGHT = hourHeight;
    const zoomPercentage = Math.round((hourHeight / DEFAULT_HOUR_HEIGHT) * 100);

    // =========================================================================
    // 数据获取
    // =========================================================================

    // 获取分类列表
    useEffect(() => {
        const fetchCategories = async () => {
            try {
                const data = await CategoryAPI.getTree(2);
                setCategories(data);
            } catch (err) {
                console.error('Failed to load categories:', err);
            }
        };
        fetchCategories();
    }, []);

    // 获取缩略图数据
    useEffect(() => {
        if (!thumbnailConfig.enabled) return;

        const fetchThumbnailData = async () => {
            setThumbnailLoading(true);
            setThumbnailError(null);
            try {
                const data = await TimelineAPIV2.getStats(
                    currentDate,
                    thumbnailConfig.hourGranularity,
                    thumbnailConfig.categoryLevel
                );
                setThumbnailData(data);
            } catch (err) {
                console.error('Failed to fetch thumbnail data:', err);
                setThumbnailError('无法加载缩略图数据，请稍后重试');
            } finally {
                setThumbnailLoading(false);
            }
        };

        fetchThumbnailData();
        // 清除缓存
        overviewCache.current.clear();
    }, [currentDate, thumbnailConfig.enabled, thumbnailConfig.hourGranularity, thumbnailConfig.categoryLevel]);

    // 获取自定义时间块数据
    const fetchCustomBlocks = useCallback(async () => {
        if (!thumbnailConfig.enabled) return;
        setCustomBlocksLoading(true);
        try {
            const blocks = await CustomBlockAPI.getByDate(currentDate);
            setCustomBlocks(blocks);
        } catch (err) {
            console.error('Failed to fetch custom blocks:', err);
            setCustomBlocks([]);
        } finally {
            setCustomBlocksLoading(false);
        }
    }, [currentDate, thumbnailConfig.enabled]);

    useEffect(() => {
        fetchCustomBlocks();
    }, [fetchCustomBlocks]);

    // 获取当天待办事项（用于自定义时间块绑定下拉）
    useEffect(() => {
        const fetchTodos = async () => {
            if (!thumbnailConfig.enabled) return;
            try {
                const response = await todoApi.getTodos(currentDate, true);
                // 转换为 TodoSelectItem 格式
                setTodos(response.items.map(todo => ({
                    id: todo.id,
                    content: todo.content,
                })));
            } catch (err) {
                console.error('Failed to fetch todos for custom block:', err);
                setTodos([]);
            }
        };
        fetchTodos();
    }, [currentDate, thumbnailConfig.enabled]);

    // 获取非缩略图模式的活动日志
    useEffect(() => {
        if (thumbnailConfig.enabled) return;

        const fetchActivityLogs = async () => {
            setLogsLoading(true);
            setLogsError(null);
            try {
                const startTime = `${currentDate} 00:00:00`;
                const endTime = `${currentDate} 23:59:59`;
                const response = await ActivityLogsAPI.getLogs({
                    start_time: startTime,
                    end_time: endTime,
                    sort_by: 'start_time',
                    sort_order: 'asc',
                    page_size: 3000,
                });
                setActivityLogs(response.data);
            } catch (err) {
                console.error('Failed to fetch activity logs:', err);
                setLogsError('无法加载活动日志，请稍后重试');
            } finally {
                setLogsLoading(false);
            }
        };

        fetchActivityLogs();
    }, [currentDate, thumbnailConfig.enabled]);

    // =========================================================================
    // 缩略图点击处理
    // =========================================================================

    const handleThumbnailClick = useCallback(async (block: TimelineBlockStats) => {
        const { start_hour, end_hour } = block;
        const cacheKey = `${currentDate}-${start_hour}-${end_hour}`;

        setSelectedEventId(null);
        setSelectedTimeRange({ startHour: start_hour, endHour: end_hour });

        // 检查缓存
        if (overviewCache.current.has(cacheKey)) {
            setOverviewData(overviewCache.current.get(cacheKey)!);
            return;
        }

        // 加载数据
        setOverviewLoading(true);
        try {
            const response = await TimelineAPIV2.getOverview(currentDate, start_hour, end_hour);
            overviewCache.current.set(cacheKey, response.data);
            setOverviewData(response.data);
        } catch (error) {
            console.error('Failed to fetch timeline overview:', error);
            setOverviewData(null);
        } finally {
            setOverviewLoading(false);
        }
    }, [currentDate]);

    const handleCloseOverview = useCallback(() => {
        setSelectedTimeRange(null);
        setOverviewData(null);
    }, []);

    // =========================================================================
    // 日期导航
    // =========================================================================

    const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setCurrentDate(e.target.value);
    };

    const handleCalendarClick = () => {
        if (dateInputRef.current) {
            if ('showPicker' in dateInputRef.current) {
                (dateInputRef.current as any).showPicker();
            } else {
                dateInputRef.current.click();
            }
        }
    };

    const handlePrevDay = () => {
        const date = parseLocalDate(currentDate);
        date.setDate(date.getDate() - 1);
        setCurrentDate(formatDateToYYYYMMDD(date));
    };

    const handleNextDay = () => {
        const date = parseLocalDate(currentDate);
        date.setDate(date.getDate() + 1);
        setCurrentDate(formatDateToYYYYMMDD(date));
    };

    // =========================================================================
    // 分类编辑
    // =========================================================================

    const selectedEvent = activityLogs.find(e => e.id === selectedEventId);

    useEffect(() => {
        if (selectedEvent) {
            setEditedCategory(selectedEvent.category_id || null);
            setEditedSubCategory(selectedEvent.sub_category_id || null);
        } else {
            setEditedCategory(null);
            setEditedSubCategory(null);
        }
    }, [selectedEventId, selectedEvent?.category_id, selectedEvent?.sub_category_id]);

    const hasChanges = selectedEvent && (
        editedCategory !== (selectedEvent.category_id || null) ||
        editedSubCategory !== (selectedEvent.sub_category_id || null)
    );

    const handleCategoryChange = (categoryId: string) => {
        setEditedCategory(categoryId);
        setEditedSubCategory(null);
    };

    const handleSaveCategory = async () => {
        if (!selectedEvent || !editedCategory || !hasChanges) return;

        setIsSaving(true);
        try {
            await ActivityLogsAPI.updateCategory(
                selectedEvent.id,
                editedCategory,
                editedSubCategory || undefined
            );
            // 更新本地数据
            setActivityLogs(prev => prev.map(e =>
                e.id === selectedEvent.id
                    ? { ...e, category_id: editedCategory, sub_category_id: editedSubCategory || undefined }
                    : e
            ));
        } catch (err) {
            console.error('Failed to save category:', err);
            alert('保存失败，请重试');
        } finally {
            setIsSaving(false);
        }
    };

    const activeCategoryDef = editedCategory
        ? categories.find(c => c.id === editedCategory)
        : null;

    // =========================================================================
    // 缩放处理
    // =========================================================================

    const handleWheel = useCallback((e: WheelEvent) => {
        if (!e.ctrlKey) return;
        e.preventDefault();

        const container = timelineContainerRef.current;
        if (!container) return;

        const rect = container.getBoundingClientRect();
        const mouseY = e.clientY - rect.top + container.scrollTop;
        const mouseTimePosition = mouseY / hourHeight;

        const zoomIn = e.deltaY < 0;
        const newHeight = zoomIn
            ? Math.min(hourHeight * ZOOM_STEP, MAX_HOUR_HEIGHT)
            : Math.max(hourHeight / ZOOM_STEP, MIN_HOUR_HEIGHT);

        if (Math.abs(newHeight - hourHeight) < 0.1) return;

        const newMouseY = mouseTimePosition * newHeight;
        const newScrollTop = Math.max(0, newMouseY - (e.clientY - rect.top));

        pendingZoomRef.current = { height: newHeight, scrollTop: newScrollTop };
        setHourHeight(newHeight);
    }, [hourHeight]);

    useLayoutEffect(() => {
        if (pendingZoomRef.current && timelineContainerRef.current) {
            timelineContainerRef.current.scrollTop = pendingZoomRef.current.scrollTop;
            pendingZoomRef.current = null;
        }
    }, [hourHeight]);

    useEffect(() => {
        const container = timelineContainerRef.current;
        if (!container) return;

        container.addEventListener('wheel', handleWheel, { passive: false });
        return () => container.removeEventListener('wheel', handleWheel);
    }, [handleWheel]);

    // =========================================================================
    // 刻度计算
    // =========================================================================

    const MIN_TICK_HEIGHT = 15;

    const getScaleIntervals = (height: number): { majorInterval: number; minorInterval: number } => {
        if (height >= 400) {
            return { majorInterval: 5 / 60, minorInterval: 1 / 60 };
        } else if (height >= 180) {
            return { majorInterval: 0.25, minorInterval: 5 / 60 };
        } else if (height >= 100) {
            return { majorInterval: 0.5, minorInterval: 0.25 };
        } else if (height >= 60) {
            return { majorInterval: 1, minorInterval: 0.5 };
        } else {
            return { majorInterval: 2, minorInterval: 1 };
        }
    };

    const { majorInterval, minorInterval } = getScaleIntervals(hourHeight);

    const majorTicks = useMemo(() => {
        const ticks: number[] = [];
        for (let i = 0; i <= 24; i += majorInterval) {
            ticks.push(Math.round(i * 1000) / 1000);
        }
        return ticks;
    }, [majorInterval]);

    const minorTicks = useMemo(() => {
        const ticks: number[] = [];
        const minorTickHeight = HOUR_HEIGHT * minorInterval;
        if (minorTickHeight >= MIN_TICK_HEIGHT) {
            for (let i = 0; i < 24; i += minorInterval) {
                const rounded = Math.round(i * 1000) / 1000;
                if (!majorTicks.some(t => Math.abs(t - rounded) < 0.001)) {
                    ticks.push(rounded);
                }
            }
        }
        return ticks;
    }, [HOUR_HEIGHT, minorInterval, majorTicks]);

    // =========================================================================
    // 非缩略图模式：事件样式计算
    // =========================================================================

    const getEventStyle = (log: ActivityLogItem) => {
        // 解析时间
        const startDate = new Date(log.start_time);
        const endDate = new Date(log.end_time);
        const startTime = startDate.getHours() + startDate.getMinutes() / 60;
        const endTime = endDate.getHours() + endDate.getMinutes() / 60 + (endDate.getSeconds() > 0 ? endDate.getSeconds() / 3600 : 0);

        const top = startTime * HOUR_HEIGHT;
        const height = Math.max((endTime - startTime) * HOUR_HEIGHT, 2);

        const isSelected = selectedEventId === log.id;

        return {
            top: `${top}px`,
            height: `${height}px`,
            className: `absolute left-36 right-4 rounded-xl border ${isSelected
                ? 'bg-white ring-2 ring-indigo-500 shadow-lg z-10 border-indigo-200 text-slate-800'
                : 'bg-gray-200 border-gray-300 text-slate-700 hover:bg-gray-100 hover:shadow-md'
                } p-3 text-xs cursor-pointer transition-shadow duration-200 flex flex-col justify-center overflow-hidden`,
            startTime,
            endTime,
        };
    };

    // =========================================================================
    // 渲染
    // =========================================================================

    const formattedDateLabel = new Date(currentDate).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric'
    });

    return (
        <div className="flex flex-col h-screen -m-6 lg:-m-10">
            {/* Top Filter Bar */}
            <div className="flex-shrink-0 bg-white border-b border-gray-200 px-6 py-4 flex flex-col md:flex-row justify-between items-center gap-4 z-20 sticky top-0">
                <div className="flex items-center gap-4">
                    {/* 日期导航 */}
                    <div className="flex items-center gap-2 bg-gray-50 p-1 rounded-lg border border-gray-200 relative">
                        <button
                            onClick={handlePrevDay}
                            className="p-1.5 hover:bg-white rounded-md shadow-sm transition-all z-10"
                        >
                            <ChevronLeft size={16} className="text-gray-500" />
                        </button>
                        <div
                            className="flex items-center gap-2 px-2 relative cursor-pointer"
                            onClick={handleCalendarClick}
                        >
                            <input
                                ref={dateInputRef}
                                type="date"
                                value={currentDate}
                                onChange={handleDateChange}
                                className="absolute inset-0 opacity-0 cursor-pointer z-20 w-full h-full pointer-events-none"
                            />
                            <Calendar size={16} className="text-gray-400 pointer-events-none" />
                            <span className="text-sm font-bold text-gray-700 pointer-events-none whitespace-nowrap">
                                {formattedDateLabel}
                            </span>
                        </div>
                        <button
                            onClick={handleNextDay}
                            className="p-1.5 hover:bg-white rounded-md shadow-sm transition-all z-10"
                        >
                            <ChevronRight size={16} className="text-gray-500" />
                        </button>
                    </div>

                    {/* 设备过滤（占位） */}
                    <div className="hidden md:flex gap-2">
                        <span className="px-3 py-1.5 bg-indigo-50 text-indigo-600 text-xs font-bold rounded-full">All Sources</span>
                        <span className="px-3 py-1.5 hover:bg-gray-50 text-gray-500 text-xs font-bold rounded-full cursor-pointer transition-colors">PC Only</span>
                        <span className="px-3 py-1.5 hover:bg-gray-50 text-gray-500 text-xs font-bold rounded-full cursor-pointer transition-colors">Mobile Only</span>
                    </div>
                </div>

                {/* 缩放控制 */}
                <div className="flex items-center gap-2 bg-gray-100 px-3 py-1.5 rounded-lg">
                    <span className="text-xs font-medium text-gray-600">缩放</span>
                    <span className="text-xs font-bold text-gray-800 min-w-[3rem] text-center">{zoomPercentage}%</span>
                    <button
                        onClick={() => setHourHeight(DEFAULT_HOUR_HEIGHT)}
                        className="text-xs text-indigo-600 hover:text-indigo-800 font-medium px-2 py-0.5 hover:bg-indigo-50 rounded transition-colors"
                        title="重置缩放"
                    >
                        重置
                    </button>
                    <span className="text-[10px] text-gray-400 hidden md:inline">Ctrl+滚轮缩放</span>
                </div>

                {/* 时间过滤器 - 仅在非缩略图模式下显示 */}
                {!thumbnailConfig.enabled && (
                    <div className="flex items-center gap-2 bg-gray-50 px-3 py-1.5 rounded-lg border border-gray-200">
                        <span className="text-xs font-medium text-gray-600">过滤</span>
                        <input
                            type="number"
                            min={0}
                            value={minDurationFilter}
                            onChange={(e) => setMinDurationFilter(Math.max(0, Number(e.target.value)))}
                            className="w-16 text-xs border rounded px-2 py-1 text-center"
                            placeholder="0"
                        />
                        <span className="text-xs text-gray-500">分钟以下</span>
                    </div>
                )}

                {/* Thumbnail Controls */}
                <div className="flex items-center gap-3 ml-auto">
                    {thumbnailConfig.enabled && (
                        <>
                            {/* 时间粒度 */}
                            <select
                                value={thumbnailConfig.hourGranularity}
                                onChange={(e) => setThumbnailConfig(prev => ({
                                    ...prev,
                                    hourGranularity: Number(e.target.value) as any
                                }))}
                                className="text-xs border rounded px-2 py-1 bg-white"
                            >
                                <option value={1}>1小时</option>
                                <option value={2}>2小时</option>
                                <option value={3}>3小时</option>
                                <option value={4}>4小时</option>
                                <option value={6}>6小时</option>
                            </select>

                            {/* 分类级别 */}
                            <select
                                value={thumbnailConfig.categoryLevel}
                                onChange={(e) => setThumbnailConfig(prev => ({
                                    ...prev,
                                    categoryLevel: e.target.value as any
                                }))}
                                className="text-xs border rounded px-2 py-1 bg-white"
                            >
                                <option value="main">主分类</option>
                                <option value="sub">子分类</option>
                            </select>

                            {/* 显示数量 */}
                            <div className="flex items-center gap-1">
                                <span className="text-[10px] text-gray-500">Top</span>
                                <input
                                    type="number"
                                    min={1}
                                    max={5}
                                    value={thumbnailConfig.maxCategories}
                                    onChange={(e) => setThumbnailConfig(prev => ({
                                        ...prev,
                                        maxCategories: Number(e.target.value)
                                    }))}
                                    className="w-12 text-xs border rounded px-1 py-1 text-center"
                                />
                            </div>
                        </>
                    )}

                    {/* Toggle Switch */}
                    <label className="flex items-center gap-2 cursor-pointer">
                        <span className="text-xs font-medium text-gray-700">缩略图</span>
                        <div className="relative">
                            <input
                                type="checkbox"
                                checked={thumbnailConfig.enabled}
                                onChange={(e) => {
                                    // 切换模式时清除所有选中状态
                                    setSelectedEventId(null);
                                    setSelectedTimeRange(null);
                                    setOverviewData(null);
                                    setThumbnailConfig(prev => ({
                                        ...prev,
                                        enabled: e.target.checked
                                    }));
                                }}
                                className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-500"></div>
                        </div>
                    </label>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex flex-1 overflow-hidden">
                {/* Left Column: Vertical Timeline Feed */}
                <div
                    ref={timelineContainerRef}
                    className="w-full lg:w-[65%] h-full overflow-y-auto relative bg-[#FAFAFA]"
                >
                    {/* 
                        布局结构：
                        - 时间刻度区域：w-16 (64px)
                        - 标签区域：w-20 (80px) - 用于显示自定义块标签
                        - 内容区域：剩余空间
                        总偏移量：64 + 80 = 144px (left-36 in rem, 或者用 left-[144px])
                    */}
                    <div className="relative min-h-[2000px] py-4" style={{ height: `${24 * HOUR_HEIGHT}px` }}>
                        {/* Time Ruler - 时间刻度区域 */}
                        <div className="absolute left-0 top-0 bottom-0 w-16 border-r border-dashed border-gray-200 bg-white z-10">
                            {majorTicks.map((t) => (
                                <div
                                    key={t}
                                    className="absolute w-full flex justify-end pr-2 text-[10px] font-mono font-medium text-gray-400"
                                    style={{ top: `${t * HOUR_HEIGHT - 6}px` }}
                                >
                                    {formatTime(t)}
                                </div>
                            ))}
                        </div>

                        {/* Label Area - 标签区域背景（用于显示自定义块标签） */}
                        <div className="absolute left-16 top-0 bottom-0 w-20 bg-white/50 z-0" />

                        {/* 自定义时间块层 - 在标签区域和内容区域之下，作为底层背景 */}
                        {thumbnailConfig.enabled && (
                            <CustomBlockLayer
                                currentDate={currentDate}
                                blocks={customBlocks}
                                hourHeight={HOUR_HEIGHT}
                                categories={categories}
                                todos={todos}
                                onUpdate={fetchCustomBlocks}
                                isLoading={customBlocksLoading}
                            />
                        )}

                        {/* Major Grid Lines */}
                        {majorTicks.map((t) => (
                            <div
                                key={`major-${t}`}
                                className="absolute left-36 right-0 border-t border-gray-200"
                                style={{ top: `${t * HOUR_HEIGHT}px` }}
                            />
                        ))}

                        {/* Minor Grid Lines */}
                        {minorTicks.map((t) => (
                            <div
                                key={`minor-${t}`}
                                className="absolute left-36 right-0 border-t border-gray-100"
                                style={{ top: `${t * HOUR_HEIGHT}px` }}
                            />
                        ))}

                        {/* === 条件渲染：缩略图 OR 事件详情 === */}
                        {thumbnailConfig.enabled ? (
                            /* 缩略图视图 */
                            <div className="absolute left-36 right-0 top-0 bottom-0 z-[1]">

                                {thumbnailLoading && (
                                    <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-30">
                                        <div className="flex flex-col items-center gap-3">
                                            <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                                            <p className="text-sm text-gray-600 font-medium">加载缩略图数据...</p>
                                        </div>
                                    </div>
                                )}

                                {thumbnailError && !thumbnailLoading && (
                                    <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-30">
                                        <div className="flex flex-col items-center gap-3 max-w-md p-6">
                                            <AlertCircle className="w-12 h-12 text-red-500" />
                                            <p className="text-sm text-gray-700 font-medium text-center">{thumbnailError}</p>
                                            <button
                                                onClick={() => setCurrentDate(currentDate)}
                                                className="px-4 py-2 bg-indigo-500 text-white rounded-lg text-sm font-medium hover:bg-indigo-600 transition-colors"
                                            >
                                                重试
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {!thumbnailLoading && !thumbnailError && thumbnailData && (
                                    thumbnailData.blocks.map((block) => (
                                        <ThumbnailBlock
                                            key={block.start_hour}
                                            blockData={block}
                                            height={HOUR_HEIGHT * thumbnailConfig.hourGranularity}
                                            maxCategories={thumbnailConfig.maxCategories}
                                            isSelected={selectedTimeRange?.startHour === block.start_hour}
                                            onClick={() => handleThumbnailClick(block)}
                                        />
                                    ))
                                )}
                            </div>
                        ) : (
                            /* 事件详情视图 */
                            <>
                                {logsLoading && (
                                    <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-30">
                                        <div className="flex flex-col items-center gap-3">
                                            <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                                            <p className="text-sm text-gray-600 font-medium">加载时间线数据...</p>
                                        </div>
                                    </div>
                                )}

                                {logsError && !logsLoading && (
                                    <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-30">
                                        <div className="flex flex-col items-center gap-3 max-w-md p-6">
                                            <AlertCircle className="w-12 h-12 text-red-500" />
                                            <p className="text-sm text-gray-700 font-medium text-center">{logsError}</p>
                                        </div>
                                    </div>
                                )}

                                {!logsLoading && !logsError && activityLogs.length === 0 && (
                                    <div className="absolute inset-0 flex items-center justify-center z-30">
                                        <div className="flex flex-col items-center gap-3 max-w-md p-6 text-center">
                                            <Monitor className="w-16 h-16 text-gray-300" />
                                            <h3 className="text-lg font-bold text-gray-700">暂无活动数据</h3>
                                            <p className="text-sm text-gray-500">
                                                该日期没有记录到任何活动。请选择其他日期，或确保 ActivityWatch 正在运行。
                                            </p>
                                        </div>
                                    </div>
                                )}

                                {/* 水平小时行布局 */}
                                {(() => {
                                    const filteredLogs = activityLogs.filter((log) => {
                                        const durationMinutes = log.duration / 60;
                                        return durationMinutes >= minDurationFilter;
                                    });
                                    const groupedLogs = groupLogsByHour(filteredLogs);
                                    const hoveredEvent = hoveredEventId ? activityLogs.find(e => e.id === hoveredEventId) : null;

                                    return (
                                        <>
                                            {/* 24小时行 */}
                                            {Array.from({ length: 24 }, (_, hour) => {
                                                const hourLogs = groupedLogs.get(hour) || [];
                                                return (
                                                    <div
                                                        key={hour}
                                                        className="absolute left-36 right-4"
                                                        style={{
                                                            top: `${hour * HOUR_HEIGHT}px`,
                                                            height: `${HOUR_HEIGHT}px`,
                                                        }}
                                                    >
                                                        {/* 小时行内的事件 */}
                                                        <div className="relative h-full">
                                                            {hourLogs.map((log) => {
                                                                const style = getHourEventStyle(log, hour);
                                                                const isSelected = selectedEventId === log.id;
                                                                const isHovered = hoveredEventId === log.id;

                                                                return (
                                                                    <div
                                                                        key={`${log.id}-${hour}`}
                                                                        className={`absolute top-1 bottom-1 rounded border cursor-pointer transition-all overflow-hidden ${isSelected
                                                                            ? 'bg-indigo-100 border-indigo-400 ring-2 ring-indigo-300 z-20'
                                                                            : isHovered
                                                                                ? 'bg-gray-100 border-gray-400 z-10'
                                                                                : 'bg-gray-200 border-gray-300 hover:bg-gray-100'
                                                                            }`}
                                                                        style={{
                                                                            left: style.left,
                                                                            width: style.width,
                                                                        }}
                                                                        onClick={() => {
                                                                            setSelectedTimeRange(null);
                                                                            setOverviewData(null);
                                                                            setSelectedEventId(log.id);
                                                                        }}
                                                                        onMouseEnter={(e) => {
                                                                            setHoveredEventId(log.id);
                                                                            setMousePosition({ x: e.clientX, y: e.clientY });
                                                                        }}
                                                                        onMouseMove={(e) => {
                                                                            setMousePosition({ x: e.clientX, y: e.clientY });
                                                                        }}
                                                                        onMouseLeave={() => {
                                                                            setHoveredEventId(null);
                                                                        }}
                                                                    >
                                                                        {/* 尽可能显示文字，CSS truncate 会自动处理溢出 */}
                                                                        <div className="px-0.5 text-[14px] font-medium text-gray-700 truncate h-full flex items-center whitespace-nowrap overflow-hidden">
                                                                            {log.app?.split('.')[0] || log.title?.slice(0, 10)}
                                                                        </div>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                );
                                            })}

                                            {/* 浮窗 */}
                                            {hoveredEvent && (
                                                <EventTooltip event={hoveredEvent} position={mousePosition} />
                                            )}
                                        </>
                                    );
                                })()}
                            </>
                        )}
                    </div>
                </div>

                {/* Right Column: Inspector Panel */}
                <div className="hidden lg:flex w-[35%] h-full bg-white border-l border-gray-200 flex-col overflow-y-auto">
                    {/* Timeline Overview Panel */}
                    {selectedTimeRange ? (
                        <div className="p-4 h-full flex flex-col animate-fade-in">
                            {/* Header */}
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2 text-xs font-bold text-gray-400 uppercase tracking-widest">
                                    <Clock size={14} />
                                    {formatTime(selectedTimeRange.startHour)} - {formatTime(selectedTimeRange.endHour)}
                                </div>
                                <button
                                    onClick={handleCloseOverview}
                                    className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                                    title="关闭"
                                >
                                    <X size={16} className="text-gray-400" />
                                </button>
                            </div>

                            {/* Loading State */}
                            {overviewLoading && (
                                <div className="flex-1 flex items-center justify-center">
                                    <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                                </div>
                            )}

                            {/* Overview Widget */}
                            {!overviewLoading && overviewData && (
                                <div className="flex-1 min-h-0">
                                    <TimeOverviewWidget data={overviewData} />
                                </div>
                            )}

                            {/* Error State */}
                            {!overviewLoading && !overviewData && (
                                <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-400">
                                    <AlertCircle className="w-12 h-12 text-gray-300 mb-4" />
                                    <p className="text-sm">无法加载该时间段的数据</p>
                                </div>
                            )}
                        </div>
                    ) : selectedEvent ? (
                        <div className="p-8 animate-fade-in">
                            <div className="flex items-center gap-2 mb-6 text-xs font-bold text-gray-400 uppercase tracking-widest">
                                <Clock size={14} />
                                Event Details
                            </div>

                            <h2 className="text-2xl font-bold text-slate-900 mb-2">{selectedEvent.title}</h2>
                            <div className="flex items-center gap-2 text-slate-500 font-mono text-sm mb-8">
                                <span>{selectedEvent.start_time.split(' ')[1]?.slice(0, 5)}</span>
                                <span>→</span>
                                <span>{selectedEvent.end_time.split(' ')[1]?.slice(0, 5)}</span>
                                <span className="text-slate-300">|</span>
                                <span>{Math.round(selectedEvent.duration / 60)}m</span>
                            </div>

                            {/* Category Editor */}
                            <div className="space-y-6">
                                {/* Level 1: Category */}
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-2">Category</label>
                                    <div className="grid grid-cols-3 gap-2">
                                        {categories.map(cat => (
                                            <button
                                                key={cat.id}
                                                onClick={() => handleCategoryChange(cat.id)}
                                                className={`px-3 py-2 rounded-lg text-sm font-medium capitalize border transition-all ${editedCategory === cat.id
                                                    ? 'bg-slate-800 text-white border-slate-800'
                                                    : 'bg-white border-gray-200 text-slate-600 hover:bg-gray-50'
                                                    }`}
                                            >
                                                {cat.name}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* Level 2: Sub-category */}
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-2">Sub-category</label>
                                    <div className="relative">
                                        <select
                                            className="w-full appearance-none bg-white border border-gray-200 text-slate-700 rounded-xl px-4 py-3 pr-8 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300 transition-shadow cursor-pointer hover:bg-gray-50"
                                            value={editedSubCategory || ''}
                                            onChange={(e) => setEditedSubCategory(e.target.value || null)}
                                        >
                                            <option value="">Select a sub-category...</option>
                                            {activeCategoryDef?.subcategories?.map((sub) => (
                                                <option key={sub.id} value={sub.id}>{sub.name}</option>
                                            ))}
                                        </select>
                                        <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                                            <Tag size={16} />
                                        </div>
                                    </div>
                                    <p className="text-[10px] text-slate-400 mt-2 font-medium">
                                        Showing sub-categories for <span className="text-slate-600 font-bold">{activeCategoryDef?.name || 'None'}</span>
                                    </p>
                                </div>

                                {/* Action Buttons */}
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => {
                                            if (selectedEvent) {
                                                setEditedCategory(selectedEvent.category_id || null);
                                                setEditedSubCategory(selectedEvent.sub_category_id || null);
                                            }
                                        }}
                                        disabled={!hasChanges || isSaving}
                                        className={`flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium transition-all ${hasChanges
                                            ? 'bg-gray-200 text-gray-700 hover:bg-gray-300 cursor-pointer'
                                            : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                            }`}
                                        title="撤销修改"
                                    >
                                        <Undo2 size={16} />
                                    </button>
                                    <button
                                        onClick={handleSaveCategory}
                                        disabled={!hasChanges || isSaving}
                                        className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium transition-all ${hasChanges
                                            ? 'bg-blue-600 text-white hover:bg-blue-700 cursor-pointer'
                                            : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                            }`}
                                    >
                                        {isSaving ? (
                                            <>
                                                <Loader2 size={16} className="animate-spin" />
                                                保存中...
                                            </>
                                        ) : (
                                            <>
                                                <Save size={16} />
                                                {hasChanges ? '保存修改' : '无修改'}
                                            </>
                                        )}
                                    </button>
                                </div>

                                {/* Description */}
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-2">Description</label>
                                    <div className="p-4 bg-gray-50 rounded-xl border border-gray-100 space-y-2 text-sm">
                                        <div className="flex">
                                            <span className="text-slate-500 font-mono">"app:{selectedEvent.app}"：</span>
                                            <span className="text-slate-700 ml-1">{selectedEvent.app_description || '无'}</span>
                                        </div>
                                        <div className="flex">
                                            <span className="text-slate-500 font-mono">"title:{selectedEvent.title}"：</span>
                                            <span className="text-slate-700 ml-1">{selectedEvent.title_analysis || '无'}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="p-8 h-full flex flex-col items-center justify-center text-center text-slate-400">
                            <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mb-4">
                                <Smartphone size={24} className="text-gray-300" />
                            </div>
                            <h3 className="text-slate-900 font-bold mb-1">No Selection</h3>
                            <p className="text-sm max-w-[200px]">
                                {thumbnailConfig.enabled
                                    ? "点击左侧缩略图查看时间段概览，或切换到详情视图编辑事件。"
                                    : "Click on any time block in the feed to view details or edit categorization."
                                }
                            </p>

                            <div className="mt-12 w-full p-4 bg-yellow-50 rounded-2xl border border-yellow-100 text-left">
                                <div className="flex items-center gap-2 text-yellow-700 font-bold text-xs uppercase mb-2">
                                    <AlertCircle size={14} />
                                    Daily Insight
                                </div>
                                <p className="text-yellow-800 text-sm font-medium leading-relaxed">
                                    You have 2.5 hours of untracked time today. Most of it occurred between 2 PM and 4 PM.
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Timeline;
