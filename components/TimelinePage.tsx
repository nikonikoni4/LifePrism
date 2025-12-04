
import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Calendar, Smartphone, Monitor, AlertCircle, Clock, Link, Tag } from 'lucide-react';
import { TIMELINE_EVENTS, COLORS, MOCK_GOALS, MOCK_CATEGORIES } from '../constants';
import { TimelineEvent } from '../types';

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
    const [currentDate, setCurrentDate] = useState('2023-10-25');
    const dateInputRef = React.useRef<HTMLInputElement>(null);
    const selectedEvent = TIMELINE_EVENTS.find(e => e.id === selectedEventId);

    // Time ruler generation (0 to 24)
    const hours = Array.from({ length: 25 }, (_, i) => i);
    const HOUR_HEIGHT = 80; // pixels per hour

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
                    <button className="px-3 py-1 bg-white shadow-sm rounded-md text-xs font-bold text-gray-800">1h</button>
                    <button className="px-3 py-1 text-xs font-medium text-gray-500 hover:text-gray-700">30m</button>
                    <button className="px-3 py-1 text-xs font-medium text-gray-500 hover:text-gray-700">15m</button>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex flex-1 overflow-hidden">
                {/* Left Column: Vertical Timeline Feed */}
                <div className="w-full lg:w-[65%] h-full overflow-y-auto relative bg-[#FAFAFA] no-scrollbar">
                    <div className="relative min-h-[2000px] py-4" style={{ height: `${24 * HOUR_HEIGHT}px` }}>
                        {/* Time Ruler */}
                        <div className="absolute left-0 top-0 bottom-0 w-16 border-r border-dashed border-gray-200 bg-white z-0">
                            {hours.map((h) => (
                                <div key={h} className="absolute w-full flex justify-end pr-2 text-[10px] font-mono font-medium text-gray-400" style={{ top: `${h * HOUR_HEIGHT - 6}px` }}>
                                    {h}:00
                                </div>
                            ))}
                        </div>

                        {/* Grid Lines */}
                        {hours.map((h) => (
                            <div key={`line-${h}`} className="absolute left-16 right-0 border-t border-gray-100" style={{ top: `${h * HOUR_HEIGHT}px` }}></div>
                        ))}

                        {/* Events */}
                        {TIMELINE_EVENTS.map((event) => {
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

                        {/* Current Time Indicator (Mock) */}
                        <div className="absolute left-0 right-0 border-t-2 border-red-400 z-20 pointer-events-none flex items-center" style={{ top: `${14.05 * HOUR_HEIGHT}px` }}>
                            <div className="bg-red-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-r-md -mt-[9px]">14:03</div>
                            <div className="w-2 h-2 rounded-full bg-red-500 -ml-1 -mt-[1px]"></div>
                        </div>
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
