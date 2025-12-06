
import React, { useState, useEffect, useRef } from 'react';
import { ChevronLeft, ChevronRight, Calendar, Smartphone, Monitor, AlertCircle, Clock, Link, Tag, Loader2, X } from 'lucide-react';
import { MOCK_GOALS, MOCK_CATEGORIES } from '../constants';
import { TimelineEvent, TimelineEventData, TimeOverviewResponse } from '../types';
import { TimelineAPI } from '../services/timelineService';
import { DashboardAPI } from '../services/dashboardService';
import TimeOverviewWidget from './widgets/TimeOverviewWidget';

// 安全的日期解析函数,支持多种格式
const parseLocalDate = (dateStr: string): Date => {
    // 判断输入格式
    const dateRegex = /^(\d{4})-(\d{2})-(\d{2})$/;
    const match = dateStr.match(dateRegex);

    if (match) {
        // 如果是 YYYY-MM-DD 格式，手动解析为本地时间
        const year = parseInt(match[1]);
        const month = parseInt(match[2]) - 1; // 月份从0开始
        const day = parseInt(match[3]);
        return new Date(year, month, day);
    } else {
        // 其他格式，尝试直接解析
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) {
            throw new Error(`Invalid date format: ${dateStr}`);
        }
        return date;
    }
};

// 格式化日期为 YYYY-MM-DD 格式，确保一致性
const formatDateToYYYYMMDD = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

const TimelinePage: React.FC = () => {
    const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
    const [currentDate, setCurrentDate] = useState(() => formatDateToYYYYMMDD(new Date()));
    const [events, setEvents] = useState<TimelineEventData[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [currentTime, setCurrentTime] = useState<number | null>(null);
    // 时间过滤器状态（分钟），用于非缩略图视图
    const [minDurationFilter, setMinDurationFilter] = useState<number>(3);

    // === 缩放相关配置 ===
    const MIN_HOUR_HEIGHT = 30;   // 最小每小时高度（像素）
    const MAX_HOUR_HEIGHT = 1200; // 最大每小时高度（像素）
    const DEFAULT_HOUR_HEIGHT = 80;
    const ZOOM_STEP = 1.15;       // 每次滚轮的缩放倍率

    const [hourHeight, setHourHeight] = useState<number>(DEFAULT_HOUR_HEIGHT);
    const timelineContainerRef = useRef<HTMLDivElement>(null);

    // === Thumbnail 缩略图配置 ===
    interface ThumbnailConfig {
        enabled: boolean;
        hourGranularity: 1 | 2 | 3 | 4 | 6;
        categoryLevel: 'main' | 'sub';
        maxCategories: number;
        width: number;
    }

    const [thumbnailConfig, setThumbnailConfig] = useState<ThumbnailConfig>({
        enabled: true,
        hourGranularity: 1,
        categoryLevel: 'main',
        maxCategories: 3,
        width: 80
    });

    // === Timeline Overview 状态 ===
    const [selectedTimeRange, setSelectedTimeRange] = useState<{
        startHour: number;
        endHour: number;
    } | null>(null);
    const [overviewData, setOverviewData] = useState<TimeOverviewResponse | null>(null);
    const [overviewLoading, setOverviewLoading] = useState(false);
    const overviewCache = useRef<Map<string, TimeOverviewResponse>>(new Map());

    const dateInputRef = React.useRef<HTMLInputElement>(null);
    const selectedEvent = events.find(e => e.id === selectedEventId);

    // 获取时间线数据
    useEffect(() => {
        const fetchTimelineData = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await TimelineAPI.getTimelineData(currentDate, 'all');
                setEvents(data.events);
                setCurrentTime(data.currentTime || null);
            } catch (err) {
                console.error('Failed to fetch timeline data:', err);
                setError('无法加载时间线数据，请稍后重试');
                setEvents([]);
            } finally {
                setLoading(false);
            }
        };

        fetchTimelineData();
    }, [currentDate]);

    // === Ctrl+滚轮缩放处理 ===
    const pendingZoomRef = useRef<{ height: number; scrollTop: number } | null>(null);

    const handleWheel = React.useCallback((e: WheelEvent) => {
        // 只在按住 Ctrl 键时处理缩放
        if (!e.ctrlKey) return;

        e.preventDefault();

        const container = timelineContainerRef.current;
        if (!container) return;

        // 获取鼠标在容器中的相对位置
        const rect = container.getBoundingClientRect();
        const mouseY = e.clientY - rect.top + container.scrollTop;
        const mouseTimePosition = mouseY / hourHeight; // 鼠标所在的时间位置（小时）

        // 计算新的高度
        const zoomIn = e.deltaY < 0;
        const newHeight = zoomIn
            ? Math.min(hourHeight * ZOOM_STEP, MAX_HOUR_HEIGHT)
            : Math.max(hourHeight / ZOOM_STEP, MIN_HOUR_HEIGHT);

        // 如果高度没有变化，直接返回
        if (Math.abs(newHeight - hourHeight) < 0.1) return;

        // 计算新的滚动位置
        const newMouseY = mouseTimePosition * newHeight;
        const newScrollTop = Math.max(0, newMouseY - (e.clientY - rect.top));

        // 保存待处理的缩放信息
        pendingZoomRef.current = { height: newHeight, scrollTop: newScrollTop };

        // 更新高度（这会触发 useLayoutEffect）
        setHourHeight(newHeight);
    }, [hourHeight]);

    // 使用 useLayoutEffect 同步更新滚动位置
    React.useLayoutEffect(() => {
        if (pendingZoomRef.current && timelineContainerRef.current) {
            timelineContainerRef.current.scrollTop = pendingZoomRef.current.scrollTop;
            pendingZoomRef.current = null;
        }
    }, [hourHeight]);

    // 绑定滚轮事件
    useEffect(() => {
        const container = timelineContainerRef.current;
        if (!container) return;

        container.addEventListener('wheel', handleWheel, { passive: false });
        return () => container.removeEventListener('wheel', handleWheel);
    }, [handleWheel]);

    // 最小刻度高度限制（像素）
    const MIN_TICK_HEIGHT = 15;

    // 使用当前 hourHeight 作为 HOUR_HEIGHT
    const HOUR_HEIGHT = hourHeight;

    // 根据 hourHeight 动态计算刻度间隔
    const getScaleIntervals = (height: number): { majorInterval: number; minorInterval: number } => {
        if (height >= 400) {
            return { majorInterval: 5 / 60, minorInterval: 1 / 60 };  // 5分钟/1分钟
        } else if (height >= 180) {
            return { majorInterval: 0.25, minorInterval: 5 / 60 };   // 15分钟/5分钟
        } else if (height >= 100) {
            return { majorInterval: 0.5, minorInterval: 0.25 };      // 30分钟/15分钟
        } else if (height >= 60) {
            return { majorInterval: 1, minorInterval: 0.5 };         // 1小时/30分钟
        } else {
            return { majorInterval: 2, minorInterval: 1 };           // 2小时/1小时
        }
    };

    const { majorInterval, minorInterval } = getScaleIntervals(hourHeight);

    // 生成主刻度（显示标签）
    const majorTicks: number[] = React.useMemo(() => {
        const ticks: number[] = [];
        for (let i = 0; i <= 24; i += majorInterval) {
            ticks.push(Math.round(i * 1000) / 1000); // 避免浮点精度问题
        }
        return ticks;
    }, [majorInterval]);

    // 生成次刻度（只显示网格线）
    const minorTicks: number[] = React.useMemo(() => {
        const ticks: number[] = [];
        const minorTickHeight = HOUR_HEIGHT * minorInterval;
        // 只有当次刻度高度满足最小要求时才生成
        if (minorTickHeight >= MIN_TICK_HEIGHT) {
            for (let i = 0; i < 24; i += minorInterval) {
                const rounded = Math.round(i * 1000) / 1000;
                // 排除与主刻度重合的位置
                if (!majorTicks.some(t => Math.abs(t - rounded) < 0.001)) {
                    ticks.push(rounded);
                }
            }
        }
        return ticks;
    }, [HOUR_HEIGHT, minorInterval, majorTicks]);

    // 计算缩放百分比用于显示
    const zoomPercentage = Math.round((hourHeight / DEFAULT_HOUR_HEIGHT) * 100);

    // Helper to calculate style for event blocks
    const getEventStyle = (event: TimelineEvent) => {
        const top = event.startTime * HOUR_HEIGHT;
        const height = (event.endTime - event.startTime) * HOUR_HEIGHT;

        let bgColor = 'bg-gray-200';
        let borderColor = 'border-gray-300';
        let textColor = 'text-gray-700';

        switch (event.category) {
            case 'work':
                bgColor = 'bg-blue-50';
                borderColor = 'border-blue-200';
                textColor = 'text-blue-700';
                break;
            case 'entertainment':
                bgColor = 'bg-orange-50';
                borderColor = 'border-orange-200';
                textColor = 'text-orange-700';
                break;
            case 'other':
                bgColor = 'bg-gray-100';
                borderColor = 'border-gray-200';
                textColor = 'text-gray-600';
                break;
        }

        if (selectedEventId === event.id) {
            bgColor = 'bg-white ring-2 ring-indigo-500 shadow-lg z-10';
        }

        return {
            top: `${top}px`,
            height: `${height}px`,
            className: `absolute left-16 right-4 rounded-xl border ${borderColor} ${bgColor} ${textColor} p-3 text-xs cursor-pointer hover:shadow-md transition-shadow duration-200 flex flex-col justify-center overflow-hidden`
        };
    };

    // === Thumbnail 数据聚合逻辑 ===
    interface CategoryData {
        id: string;
        name: string;
        color: string;
        duration: number;  // 秒
        percentage: number;
    }

    interface HourlyData {
        hour: number;
        categories: CategoryData[];
        emptyPercentage: number;
    }

    // 获取分类颜色（直接使用后端返回的颜色）
    const getCategoryColor = (event: TimelineEventData): string => {
        if (thumbnailConfig.categoryLevel === 'main') {
            return event.categoryColor;
        } else {
            return event.subCategoryColor || event.categoryColor;
        }
    };

    // 聚合按小时数据
    const aggregateByHour = React.useMemo(() => {
        const hourlyMap = new Map<number, Map<string, CategoryData>>();
        const hourDuration = 3600 * thumbnailConfig.hourGranularity;

        // 初始化所有时间块
        for (let h = 0; h < 24; h += thumbnailConfig.hourGranularity) {
            hourlyMap.set(h, new Map());
        }

        // 聚合事件数据
        events.forEach(event => {
            const startHour = Math.floor(event.startTime / thumbnailConfig.hourGranularity) * thumbnailConfig.hourGranularity;
            const endHour = Math.floor(event.endTime / thumbnailConfig.hourGranularity) * thumbnailConfig.hourGranularity;

            for (let h = startHour; h <= endHour && h < 24; h += thumbnailConfig.hourGranularity) {
                const categoryMap = hourlyMap.get(h);
                if (!categoryMap) continue;

                // 计算重叠时长
                const blockStart = h;
                const blockEnd = h + thumbnailConfig.hourGranularity;
                const overlapStart = Math.max(event.startTime, blockStart);
                const overlapEnd = Math.min(event.endTime, blockEnd);
                const overlapDuration = Math.max(0, (overlapEnd - overlapStart) * 3600);

                // 确定分类Key
                const categoryKey = thumbnailConfig.categoryLevel === 'main'
                    ? event.category
                    : event.subCategoryId || event.category;

                const categoryName = thumbnailConfig.categoryLevel === 'main'
                    ? event.categoryName
                    : event.subCategoryName || event.categoryName;

                let categoryData = categoryMap.get(categoryKey);
                if (!categoryData) {
                    categoryData = {
                        id: categoryKey,
                        name: categoryName,
                        color: getCategoryColor(event),
                        duration: 0,
                        percentage: 0
                    };
                    categoryMap.set(categoryKey, categoryData);
                }

                categoryData.duration += overlapDuration;
            }
        });

        // 转换为数组并计算百分比
        const hourlyData: HourlyData[] = [];
        for (let h = 0; h < 24; h += thumbnailConfig.hourGranularity) {
            const categoryMap = hourlyMap.get(h)!;
            const categories = Array.from(categoryMap.values());

            const totalDuration = categories.reduce((sum, cat) => sum + cat.duration, 0);
            const emptyDuration = hourDuration - totalDuration;
            const emptyPercentage = (emptyDuration / hourDuration) * 100;

            categories.forEach(cat => {
                cat.percentage = (cat.duration / hourDuration) * 100;
            });

            // 按时长排序并选择 Top N
            categories.sort((a, b) => b.duration - a.duration);

            hourlyData.push({
                hour: h,
                categories,
                emptyPercentage: Math.max(0, emptyPercentage)
            });
        }

        return hourlyData;
    }, [events, thumbnailConfig.hourGranularity, thumbnailConfig.categoryLevel]);

    // 格式化时长
    const formatDuration = (seconds: number): string => {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        }
        return `${minutes}m`;
    };

    // Format float hour to HH:MM
    const formatTime = (time: number) => {
        const h = Math.floor(time);
        const m = Math.round((time - h) * 60);
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
    };

    // Format tick label (e.g. 1.5 -> 01:30)
    const formatTickLabel = (time: number) => {
        const h = Math.floor(time);
        const m = Math.round((time - h) * 60);
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
    };

    const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setCurrentDate(e.target.value);
    };

    const handleCalendarClick = () => {
        console.log('handleCalendarClick called');
        if (dateInputRef.current) {
            if ('showPicker' in dateInputRef.current) {
                (dateInputRef.current as any).showPicker();
            } else {
                dateInputRef.current.click();
            }
        }
    };

    const handlePrevDay = () => {
        console.log('handlePrevDay called');
        const date = parseLocalDate(currentDate);
        date.setDate(date.getDate() - 1);
        setCurrentDate(formatDateToYYYYMMDD(date));
    };

    const handleNextDay = () => {
        console.log('handleNextDay called');
        const date = parseLocalDate(currentDate);
        date.setDate(date.getDate() + 1);
        setCurrentDate(formatDateToYYYYMMDD(date));
    };

    const handleCategoryChange = (categoryId: string) => {
        if (!selectedEventId) return;
        setEvents(prev => prev.map(e =>
            e.id === selectedEventId ? { ...e, category: categoryId } : e
        ));
    };

    // === Thumbnail Click Handler ===
    const handleThumbnailClick = async (startHour: number) => {
        const endHour = startHour + thumbnailConfig.hourGranularity;
        const cacheKey = `${currentDate}-${startHour}-${endHour}`;

        // 清除事件选中状态，显示 overview
        setSelectedEventId(null);
        setSelectedTimeRange({ startHour, endHour });

        // 检查缓存
        if (overviewCache.current.has(cacheKey)) {
            setOverviewData(overviewCache.current.get(cacheKey)!);
            return;
        }

        // 加载数据
        setOverviewLoading(true);
        try {
            const data = await DashboardAPI.getTimelineOverview(
                currentDate, startHour, endHour
            );
            overviewCache.current.set(cacheKey, data);
            setOverviewData(data);
        } catch (error) {
            console.error('Failed to fetch timeline overview:', error);
            setOverviewData(null);
        } finally {
            setOverviewLoading(false);
        }
    };

    // === 关闭 Overview Panel ===
    const handleCloseOverview = () => {
        setSelectedTimeRange(null);
        setOverviewData(null);
    };

    const formattedDateLabel = new Date(currentDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    // Helper to get active category definition for dropdowns
    const activeCategoryDef = selectedEvent ? MOCK_CATEGORIES.find(c => c.id === selectedEvent.category) : null;

    // === Thumbnail Components ===
    const ThumbnailBlock: React.FC<{
        hourData: HourlyData;
        height: number;
    }> = ({ hourData, height }) => {
        const topCategories = hourData.categories.slice(0, thumbnailConfig.maxCategories);
        const otherCategories = hourData.categories.slice(thumbnailConfig.maxCategories);

        let otherPercentage = 0;
        let otherDuration = 0;
        let otherName = '其他';
        let otherColor = '#9CA3AF';

        if (otherCategories.length > 0) {
            otherDuration = otherCategories.reduce((sum, cat) => sum + cat.duration, 0);
            otherPercentage = otherCategories.reduce((sum, cat) => sum + cat.percentage, 0);

            // 使用第一个剩余分类的名称和颜色，格式为"A等..."
            const firstOther = otherCategories[0];
            otherName = `${firstOther.name}等...`;
            otherColor = firstOther.color;
        }

        const isSelected = selectedTimeRange?.startHour === hourData.hour;

        return (
            <div
                className={`relative border-b border-gray-100 group cursor-pointer transition-all ${isSelected
                    ? 'ring-2 ring-indigo-500 ring-inset bg-indigo-50/30'
                    : 'hover:bg-gray-50/50'
                    }`}
                style={{ height: `${height}px` }}
                onClick={() => handleThumbnailClick(hourData.hour)}
            >
                {/* 横向堆叠条 */}
                <div className="absolute inset-0 flex">
                    {/* Top N 分类 */}
                    {topCategories.map((cat, idx) => (
                        <div
                            key={cat.id}
                            style={{
                                width: `${cat.percentage}%`,
                                backgroundColor: cat.color
                            }}
                            className="relative flex items-center justify-center overflow-hidden text-[9px] font-medium text-white transition-all"
                            title={`${cat.name}: ${formatDuration(cat.duration)} (${cat.percentage.toFixed(1)}%)`}
                        >
                            {/* 显示分类信息（如果宽度足够） */}
                            {cat.percentage > 8 && (
                                <div className="px-1 text-center leading-tight" style={{
                                    textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                                    fontSize: '8px'
                                }}>
                                    <div className="font-bold truncate">{cat.name}</div>
                                    <div className="opacity-90">{formatDuration(cat.duration)}</div>
                                    <div className="opacity-75">{cat.percentage.toFixed(0)}%</div>
                                </div>
                            )}
                        </div>
                    ))}

                    {/* 其他分类（动态命名） */}
                    {otherPercentage > 0 && (
                        <div
                            style={{
                                width: `${otherPercentage}%`,
                                backgroundColor: otherColor
                            }}
                            className="relative flex items-center justify-center text-[9px] font-medium text-white"
                            title={`${otherName}: ${formatDuration(otherDuration)} (${otherPercentage.toFixed(1)}%)`}
                        >
                            {otherPercentage > 5 && (
                                <div style={{ textShadow: '0 1px 2px rgba(0,0,0,0.3)', fontSize: '8px' }}>
                                    {otherName}
                                </div>
                            )}
                        </div>
                    )}

                    {/* 空白时间 */}
                    {hourData.emptyPercentage > 0 && (
                        <div
                            style={{ width: `${hourData.emptyPercentage}%` }}
                            className="bg-gray-50 border-l border-gray-100"
                        />
                    )}
                </div>
            </div>
        );
    };

    return (
        <div className="flex flex-col h-screen -m-6 lg:-m-10">
            {/* Top Filter Bar */}
            <div className="flex-shrink-0 bg-white border-b border-gray-200 px-6 py-4 flex flex-col md:flex-row justify-between items-center gap-4 z-20 sticky top-0">
                <div className="flex items-center gap-4">
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
                            <span className="text-sm font-bold text-gray-700 pointer-events-none whitespace-nowrap">{formattedDateLabel}</span>
                        </div>
                        <button
                            onClick={handleNextDay}
                            className="p-1.5 hover:bg-white rounded-md shadow-sm transition-all z-10"
                        >
                            <ChevronRight size={16} className="text-gray-500" />
                        </button>
                    </div>
                    <div className="hidden md:flex gap-2">
                        <span className="px-3 py-1.5 bg-indigo-50 text-indigo-600 text-xs font-bold rounded-full">All Sources</span>
                        <span className="px-3 py-1.5 hover:bg-gray-50 text-gray-500 text-xs font-bold rounded-full cursor-pointer transition-colors">PC Only</span>
                        <span className="px-3 py-1.5 hover:bg-gray-50 text-gray-500 text-xs font-bold rounded-full cursor-pointer transition-colors">Mobile Only</span>
                    </div>
                </div>

                {/* 缩放控制 - 显示当前缩放级别和提示 */}
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

                {/* Thumbnail Controls - 移到最右侧 */}
                <div className="flex items-center gap-3 ml-auto">
                    {thumbnailConfig.enabled && (
                        <>
                            {/* 时间粒度 */}
                            <select
                                value={thumbnailConfig.hourGranularity}
                                onChange={(e) => setThumbnailConfig(prev => ({ ...prev, hourGranularity: Number(e.target.value) as any }))}
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
                                onChange={(e) => setThumbnailConfig(prev => ({ ...prev, categoryLevel: e.target.value as any }))}
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
                                    onChange={(e) => setThumbnailConfig(prev => ({ ...prev, maxCategories: Number(e.target.value) }))}
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
                                onChange={(e) => setThumbnailConfig(prev => ({ ...prev, enabled: e.target.checked }))}
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
                    <div className="relative min-h-[2000px] py-4" style={{ height: `${24 * HOUR_HEIGHT}px` }}>
                        {/* Time Ruler - Major Ticks with Labels */}
                        <div className="absolute left-0 top-0 bottom-0 w-16 border-r border-dashed border-gray-200 bg-white z-0">
                            {majorTicks.map((t) => (
                                <div key={t} className="absolute w-full flex justify-end pr-2 text-[10px] font-mono font-medium text-gray-400" style={{ top: `${t * HOUR_HEIGHT - 6}px` }}>
                                    {formatTickLabel(t)}
                                </div>
                            ))}
                        </div>

                        {/* Grid Lines - Major Ticks */}
                        {majorTicks.map((t) => (
                            <div key={`major-${t}`} className="absolute left-16 right-0 border-t border-gray-200" style={{ top: `${t * HOUR_HEIGHT}px` }}></div>
                        ))}

                        {/* Grid Lines - Minor Ticks (lighter) */}
                        {minorTicks.map((t) => (
                            <div key={`minor-${t}`} className="absolute left-16 right-0 border-t border-gray-100" style={{ top: `${t * HOUR_HEIGHT}px` }}></div>
                        ))}

                        {/* === 条件渲染：缩略图 OR 事件详情 === */}
                        {thumbnailConfig.enabled ? (
                            /* 缩略图视图 */
                            <div className="absolute left-16 right-0 top-0 bottom-0">
                                {aggregateByHour.map(hourData => (
                                    <ThumbnailBlock
                                        key={hourData.hour}
                                        hourData={hourData}
                                        height={HOUR_HEIGHT * thumbnailConfig.hourGranularity}
                                    />
                                ))}
                            </div>
                        ) : (
                            /* 事件详情视图 */
                            <>

                                {/* Loading State */}
                                {loading && (
                                    <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-30">
                                        <div className="flex flex-col items-center gap-3">
                                            <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                                            <p className="text-sm text-gray-600 font-medium">加载时间线数据...</p>
                                        </div>
                                    </div>
                                )}

                                {/* Error State */}
                                {error && !loading && (
                                    <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-30">
                                        <div className="flex flex-col items-center gap-3 max-w-md p-6">
                                            <AlertCircle className="w-12 h-12 text-red-500" />
                                            <p className="text-sm text-gray-700 font-medium text-center">{error}</p>
                                            <button
                                                onClick={() => setCurrentDate(currentDate)}
                                                className="px-4 py-2 bg-indigo-500 text-white rounded-lg text-sm font-medium hover:bg-indigo-600 transition-colors"
                                            >
                                                重试
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {/* Empty State */}
                                {!loading && !error && events.length === 0 && (
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

                                {/* Events - 根据 minDurationFilter 过滤 */}
                                {events
                                    .filter((event) => {
                                        // 计算事件时长（分钟）
                                        const durationMinutes = (event.endTime - event.startTime) * 60;
                                        return durationMinutes >= minDurationFilter;
                                    })
                                    .map((event) => {
                                        const style = getEventStyle(event);
                                        const catDef = MOCK_CATEGORIES.find(c => c.id === event.category);
                                        const subCatDef = catDef?.subCategories.find(s => s.id === event.subCategoryId);

                                        return (
                                            <div
                                                key={event.id}
                                                style={{ top: style.top, height: style.height }}
                                                className={style.className}
                                                onClick={() => setSelectedEventId(event.id)}
                                            >
                                                <div className="font-bold truncate">{event.title}</div>
                                                {style.height !== '0px' && parseInt(style.height) > 30 && (
                                                    <div className="flex items-center justify-between mt-1">
                                                        <div className="flex items-center gap-1 opacity-80">
                                                            <span className="text-[10px]">{formatTime(event.startTime)} - {formatTime(event.endTime)}</span>
                                                            {subCatDef && (
                                                                <>
                                                                    <span className="mx-0.5">•</span>
                                                                    <span className="text-[10px] font-medium opacity-100 bg-black/5 px-1.5 rounded-sm">{subCatDef.name}</span>
                                                                </>
                                                            )}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}

                                {/* Current Time Indicator */}
                                {currentTime !== null && (
                                    <div className="absolute left-0 right-0 border-t-2 border-red-400 z-20 pointer-events-none flex items-center" style={{ top: `${currentTime * HOUR_HEIGHT}px` }}>
                                        <div className="bg-red-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-r-md -mt-[9px]">{formatTime(currentTime)}</div>
                                        <div className="w-2 h-2 rounded-full bg-red-500 -ml-1 -mt-[1px]"></div>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </div>

                {/* Right Column: Inspector Panel */}
                <div className="hidden lg:flex w-[35%] h-full bg-white border-l border-gray-200 flex-col overflow-y-auto">
                    {/* Timeline Overview Panel */}
                    {selectedTimeRange ? (
                        <div className="p-4 h-full flex flex-col animate-fade-in">
                            {/* Header with close button */}
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
                                    <TimeOverviewWidget
                                        selectedDate={currentDate}
                                        initialData={overviewData}
                                    />
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
                                <span>{formatTime(selectedEvent.startTime)}</span>
                                <span>→</span>
                                <span>{formatTime(selectedEvent.endTime)}</span>
                                <span className="text-slate-300">|</span>
                                <span>{Math.round((selectedEvent.endTime - selectedEvent.startTime) * 60)}m</span>
                            </div>

                            {/* Quick Actions Form */}
                            <div className="space-y-6">
                                {/* Level 1: Category */}
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-2">Category</label>
                                    <div className="grid grid-cols-3 gap-2">
                                        {MOCK_CATEGORIES.map(cat => (
                                            <button
                                                key={cat.id}
                                                onClick={() => handleCategoryChange(cat.id)}
                                                className={`px-3 py-2 rounded-lg text-sm font-medium capitalize border transition-all ${selectedEvent.category === cat.id
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
                                            defaultValue={selectedEvent.subCategoryId || ''}
                                        >
                                            <option value="" disabled>Select a sub-category...</option>
                                            {activeCategoryDef?.subCategories.map((sub) => (
                                                <option key={sub.id} value={sub.id}>{sub.name}</option>
                                            ))}
                                        </select>
                                        <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                                            <Tag size={16} />
                                        </div>
                                    </div>
                                    <p className="text-[10px] text-slate-400 mt-2 font-medium">
                                        Showing sub-categories for <span className="text-slate-600 font-bold">{activeCategoryDef?.name}</span>
                                    </p>
                                </div>

                                {/* Linked Goal - 暂时隐藏 */}

                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-2">Linked Goal</label>
                                    <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-center justify-between group cursor-pointer hover:border-blue-200 hover:bg-blue-50/30 transition-all">
                                        <div className="flex items-center gap-3">
                                            <div className="p-2 bg-white rounded-lg text-blue-500 shadow-sm">
                                                <Link size={16} />
                                            </div>
                                            <div>
                                                <p className="text-sm font-medium text-slate-400 italic">No goal linked</p>
                                            </div>
                                        </div>
                                        <ChevronRight size={16} className="text-gray-400" />
                                    </div>
                                </div>


                                {/* Description */}
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-2">Description</label>
                                    <textarea
                                        className="w-full h-32 p-3 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 resize-none"
                                        defaultValue={selectedEvent.description || ''}
                                        placeholder="Add notes about this session..."
                                    />
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

export default TimelinePage;
