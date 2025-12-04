
import React, { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Calendar, Smartphone, Monitor, AlertCircle, Clock, Link, Tag, Loader2 } from 'lucide-react';
import { MOCK_GOALS, MOCK_CATEGORIES } from '../constants';
import { TimelineEvent, TimelineEventData } from '../types';
import { TimelineAPI } from '../services/timelineService';

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

    type TimeScale = '2h' | '1h' | '30m' | '15m' | '1m';
    const [timeScale, setTimeScale] = useState<TimeScale>('1h');

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

    const SCALE_CONFIG: Record<TimeScale, { hourHeight: number; labelInterval: number }> = {
        '2h': { hourHeight: 60, labelInterval: 2 },
        '1h': { hourHeight: 80, labelInterval: 1 },
        '30m': { hourHeight: 120, labelInterval: 0.5 },
        '15m': { hourHeight: 200, labelInterval: 0.25 },
        '1m': { hourHeight: 1200, labelInterval: 1 / 60 },
    };

    const { hourHeight: HOUR_HEIGHT, labelInterval } = SCALE_CONFIG[timeScale];

    // Time ruler generation
    const ticks: number[] = [];
    for (let i = 0; i <= 24; i += labelInterval) {
        ticks.push(i);
    }

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
            className: `absolute left-16 right-4 rounded-xl border ${borderColor} ${bgColor} ${textColor} p-3 text-xs cursor-pointer hover:shadow-md transition-all duration-200 flex flex-col justify-center overflow-hidden`
        };
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

    const formattedDateLabel = new Date(currentDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    // Helper to get active category definition for dropdowns
    const activeCategoryDef = selectedEvent ? MOCK_CATEGORIES.find(c => c.id === selectedEvent.category) : null;

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

                <div className="flex items-center gap-2 bg-gray-100 p-1 rounded-lg">
                    <button
                        onClick={() => setTimeScale('2h')}
                        className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${timeScale === '2h' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        2h
                    </button>
                    <button
                        onClick={() => setTimeScale('1h')}
                        className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${timeScale === '1h' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        1h
                    </button>
                    <button
                        onClick={() => setTimeScale('30m')}
                        className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${timeScale === '30m' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        30m
                    </button>
                    <button
                        onClick={() => setTimeScale('15m')}
                        className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${timeScale === '15m' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        15m
                    </button>
                    <button
                        onClick={() => setTimeScale('1m')}
                        className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${timeScale === '1m' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        1m
                    </button>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex flex-1 overflow-hidden">
                {/* Left Column: Vertical Timeline Feed */}
                <div className="w-full lg:w-[65%] h-full overflow-y-auto relative bg-[#FAFAFA]">
                    <div className="relative min-h-[2000px] py-4" style={{ height: `${24 * HOUR_HEIGHT}px` }}>
                        {/* Time Ruler */}
                        <div className="absolute left-0 top-0 bottom-0 w-16 border-r border-dashed border-gray-200 bg-white z-0">
                            {ticks.map((t) => (
                                <div key={t} className="absolute w-full flex justify-end pr-2 text-[10px] font-mono font-medium text-gray-400" style={{ top: `${t * HOUR_HEIGHT - 6}px` }}>
                                    {formatTickLabel(t)}
                                </div>
                            ))}
                        </div>

                        {/* Grid Lines */}
                        {ticks.map((t) => (
                            <div key={`line-${t}`} className="absolute left-16 right-0 border-t border-gray-100" style={{ top: `${t * HOUR_HEIGHT}px` }}></div>
                        ))}

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

                        {/* Events */}
                        {events.map((event) => {
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
                                            {event.linkedGoal && (
                                                <div className="w-2 h-2 rounded-full bg-current opacity-50"></div>
                                            )}
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
                    </div>
                </div>

                {/* Right Column: Inspector Panel */}
                <div className="hidden lg:flex w-[35%] h-full bg-white border-l border-gray-200 flex-col overflow-y-auto">
                    {selectedEvent ? (
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

                                {/* Level 2: Sub-category (New) */}
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

                                {/* Linked Goal */}
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-2">Linked Goal</label>
                                    <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-center justify-between group cursor-pointer hover:border-blue-200 hover:bg-blue-50/30 transition-all">
                                        <div className="flex items-center gap-3">
                                            <div className="p-2 bg-white rounded-lg text-blue-500 shadow-sm">
                                                <Link size={16} />
                                            </div>
                                            <div>
                                                {selectedEvent.linkedGoal ? (
                                                    <p className="text-sm font-semibold text-slate-800">
                                                        {MOCK_GOALS.find(g => g.id === selectedEvent.linkedGoal)?.text || 'Unknown Goal'}
                                                    </p>
                                                ) : (
                                                    <p className="text-sm font-medium text-slate-400 italic">No goal linked</p>
                                                )}
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
                            <h3 className="text-slate-900 font-bold mb-1">No Event Selected</h3>
                            <p className="text-sm max-w-[200px]">Click on any time block in the feed to view details or edit categorization.</p>

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
