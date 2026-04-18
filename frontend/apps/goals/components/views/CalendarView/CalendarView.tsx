import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { GlassCalendar, DateRange } from '@my-ui-kit/core';
import { DateGrid } from './components/DateGrid';
import { viewBackground } from '../../shared/backgroundStyles';
import type { CalendarViewProps } from '../../../types';

export const CalendarView: React.FC<CalendarViewProps> = () => {
    // 默认日期范围：今天-4到今天+3
    const defaultRange: DateRange = useMemo(() => {
        const today = new Date();
        const fourDaysAgo = new Date();
        fourDaysAgo.setDate(today.getDate() - 4);
        const threeDaysLater = new Date();
        threeDaysLater.setDate(today.getDate() + 3);

        return {
            start: fourDaysAgo,
            end: threeDaysLater,
        };
    }, []);

    const [dateRange, setDateRange] = useState<DateRange>(defaultRange);
    const [isCalendarOpen, setIsCalendarOpen] = useState(false);
    const calendarRef = useRef<HTMLDivElement>(null);

    // 点击外部关闭日历
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (calendarRef.current && !calendarRef.current.contains(event.target as Node)) {
                setIsCalendarOpen(false);
            }
        };

        if (isCalendarOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isCalendarOpen]);

    const handleRangeSelect = (range: DateRange) => {
        setDateRange(range);
        // 当选择完成（有开始和结束日期）时自动关闭
        if (range.start && range.end) {
            setIsCalendarOpen(false);
        }
    };

    // 快速导航：向前/向后调整日期范围
    const handleNavigate = (direction: 'prev' | 'next') => {
        if (!dateRange.start || !dateRange.end) return;

        const daysDiff = Math.ceil((dateRange.end.getTime() - dateRange.start.getTime()) / (1000 * 60 * 60 * 24));
        const offset = direction === 'prev' ? -daysDiff : daysDiff;

        const newStart = new Date(dateRange.start);
        const newEnd = new Date(dateRange.end);
        newStart.setDate(newStart.getDate() + offset);
        newEnd.setDate(newEnd.getDate() + offset);

        setDateRange({ start: newStart, end: newEnd });
    };

    // 格式化日期显示
    const formatDateRange = () => {
        if (!dateRange.start) return '选择日期范围';

        const formatDate = (date: Date) => {
            const month = date.getMonth() + 1;
            const day = date.getDate();
            return `${month}月${day}日`;
        };

        if (!dateRange.end) {
            return formatDate(dateRange.start);
        }

        return `${formatDate(dateRange.start)} - ${formatDate(dateRange.end)}`;
    };

    // 计算选中天数
    const selectedDays = useMemo(() => {
        if (!dateRange.start || !dateRange.end) return 0;
        return Math.ceil((dateRange.end.getTime() - dateRange.start.getTime()) / (1000 * 60 * 60 * 24)) + 1;
    }, [dateRange]);

    return (
        <div className={`h-full flex flex-col ${viewBackground.className}`} style={viewBackground.style}>
            {/* 滚动条样式 */}
            <style>{`
                .calendar-scrollbar::-webkit-scrollbar {
                    width: 6px;
                }
                .calendar-scrollbar::-webkit-scrollbar-track {
                    background: transparent;
                }
                .calendar-scrollbar::-webkit-scrollbar-thumb {
                    background-color: rgba(148, 163, 184, 0.3);
                    border-radius: 3px;
                }
                .calendar-scrollbar::-webkit-scrollbar-thumb:hover {
                    background-color: rgba(148, 163, 184, 0.5);
                }
                /* 日期框内任务列表滚动条 */
                .date-cell-scrollbar::-webkit-scrollbar {
                    width: 4px;
                }
                .date-cell-scrollbar::-webkit-scrollbar-track {
                    background: transparent;
                }
                .date-cell-scrollbar::-webkit-scrollbar-thumb {
                    background-color: rgba(148, 163, 184, 0.25);
                    border-radius: 2px;
                }
                .date-cell-scrollbar::-webkit-scrollbar-thumb:hover {
                    background-color: rgba(148, 163, 184, 0.45);
                }
            `}</style>

            {/* 顶部导航栏 - 参考taskCalendar的头部设计 */}
            <div className="flex-shrink-0 px-6 py-5 border-b border-slate-100">
                <div className="flex items-center justify-between max-w-6xl mx-auto">

                    {/* 左侧：导航按钮 + 日期标题 */}
                    <div className="flex items-center gap-4">
                        {/* 导航按钮组 */}
                        <div className="flex gap-2">
                            <button
                                onClick={() => handleNavigate('prev')}
                                className="group/btn flex h-11 w-11 items-center justify-center rounded-full 
                                    border border-slate-200 bg-white text-slate-600 
                                    hover:scale-105 hover:bg-slate-50 hover:border-slate-300 hover:shadow-lg
                                    active:scale-95 transition-all duration-300"
                                aria-label="上一个周期"
                            >
                                <ChevronLeft className="h-5 w-5 opacity-70 group-hover/btn:opacity-100" />
                            </button>
                            <button
                                onClick={() => handleNavigate('next')}
                                className="group/btn flex h-11 w-11 items-center justify-center rounded-full 
                                    border border-slate-200 bg-white text-slate-600 
                                    hover:scale-105 hover:bg-slate-50 hover:border-slate-300 hover:shadow-lg
                                    active:scale-95 transition-all duration-300"
                                aria-label="下一个周期"
                            >
                                <ChevronRight className="h-5 w-5 opacity-70 group-hover/btn:opacity-100" />
                            </button>
                        </div>

                        {/* 日期范围标题 */}
                        <div className="flex flex-col">
                            <h2 className="text-xl font-bold tracking-tight text-slate-800">
                                {formatDateRange()}
                            </h2>
                            <span className="text-sm font-medium tracking-wide text-slate-400">
                                共 {selectedDays} 天
                            </span>
                        </div>
                    </div>

                    {/* 右侧：日期选择器按钮 */}
                    <button
                        onClick={() => setIsCalendarOpen(!isCalendarOpen)}
                        className="group relative flex items-center gap-3 px-4 py-2.5 rounded-2xl 
                            bg-slate-800 text-white
                            shadow-lg shadow-slate-800/20
                            hover:shadow-xl hover:shadow-slate-800/30 hover:scale-[1.02]
                            active:scale-[0.98]
                            transition-all duration-300 ease-out"
                    >
                        <CalendarIcon size={18} className="opacity-80 group-hover:opacity-100" />
                        <span className="text-sm font-semibold">选择日期</span>
                    </button>
                </div>
            </div>

            {/* 居中弹出的日历模态窗口 */}
            <AnimatePresence>
                {isCalendarOpen && (
                    <>
                        {/* 背景模糊遮罩层 */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
                            onClick={() => setIsCalendarOpen(false)}
                        />
                        {/* 居中的日历面板 */}
                        <motion.div
                            ref={calendarRef}
                            initial={{ opacity: 0, scale: 0.95, y: 10 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: 10 }}
                            transition={{ type: "spring", stiffness: 400, damping: 30 }}
                            className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 
                                bg-white rounded-[2rem] p-2 
                                shadow-[0_25px_80px_-15px_rgba(0,0,0,0.2)]
                                border border-slate-200/60"
                            style={{ width: '420px', maxHeight: '85vh' }}
                        >
                            {/* 日历头部装饰 */}
                            <div className="absolute inset-0 -z-10 rounded-[2rem] bg-gradient-to-br from-slate-50 via-white to-slate-50" />

                            <GlassCalendar
                                enableRangeSelection={true}
                                onRangeSelect={handleRangeSelect}
                                monthsToShow={2}
                                className="w-full"
                            />
                        </motion.div>
                    </>
                )}
            </AnimatePresence>

            {/* 日期格子容器 */}
            {dateRange.start && dateRange.end ? (
                <DateGrid startDate={dateRange.start} endDate={dateRange.end} />
            ) : (
                <div className="flex-1 flex items-center justify-center bg-slate-50/50">
                    <div className="text-center p-10 rounded-3xl bg-white border border-slate-200/60 shadow-[0_8px_40px_-12px_rgba(0,0,0,0.08)]">
                        {/* 图标容器 */}
                        <div className="w-20 h-20 mx-auto mb-5 rounded-2xl bg-slate-100 flex items-center justify-center">
                            <CalendarIcon size={32} className="text-slate-400" />
                        </div>
                        <div className="text-lg font-bold text-slate-700 mb-2">请选择日期范围</div>
                        <div className="text-sm text-slate-400">点击右上角按钮选择要查看的日期</div>
                    </div>
                </div>
            )}
        </div>
    );
};
