import React, { useState, useMemo, useRef, useEffect } from 'react';
import { getMonthGridData, isSameDay, isDayInRange, isToday } from './utils';
import type { GlassCalendarProps, DateRange } from './types';

/**
 * GlassCalendar Component (Dynamic Header Edition)
 * 1. [Layout] 月份标题移至星期表头上方 (Month above Week)
 * 2. [Interaction] 滚动时动态更新顶部月份标题
 * 3. [Visual] 保持宝石蓝玻璃质感
 */

// ------------------- 子组件：单月视图 -------------------
// 注意：移除了内部的 Sticky Header，改为简单的分割标记
interface MonthSectionProps {
    year: number;
    month: number;
    selection: DateRange;
    onDateClick: (date: Date) => void;
    setRef: (el: HTMLDivElement | null) => void;
}

const MonthSection = React.memo(({ year, month, selection, onDateClick, setRef }: MonthSectionProps) => {
    const gridData = useMemo(() => getMonthGridData(year, month), [year, month]);

    // 仅在非首月显示分割线和月份小标签，辅助定位
    const isShowLabel = true;

    return (
        <div
            ref={setRef}
            data-year={year}
            data-month={month}
            className="pb-8 pt-2" // 增加上下间距
        >
            {isShowLabel && (
                <div className="flex items-center gap-4 mb-4 px-2 opacity-40">
                    <div className="h-[1px] flex-1 bg-indigo-900/30"></div>
                    <span className="text-xs font-bold text-indigo-900/60 uppercase tracking-widest">
                        {month + 1}月
                    </span>
                    <div className="h-[1px] flex-1 bg-indigo-900/30"></div>
                </div>
            )}

            <div className="grid grid-cols-7 gap-y-2 gap-x-2">
                {gridData.map((item, index) => {
                    const date = item.date;
                    if (!date) {
                        return <div key={`empty-${index}`} />;
                    }

                    const isStart = isSameDay(date, selection.start);
                    const isEnd = isSameDay(date, selection.end);
                    const isRange = isDayInRange(date, selection.start, selection.end);
                    const isSelected = isStart || isEnd;
                    const isTodayDate = isToday(date);

                    let bgClass = '';
                    let textClass = 'text-slate-600';
                    let roundedClass = 'rounded-xl';

                    if (isSelected) {
                        bgClass = 'bg-indigo-600 shadow-[0_10px_20px_-5px_rgba(79,70,229,0.4)] scale-[1.05] z-10';
                        textClass = 'text-white';
                        if (selection.end) {
                            if (isStart) roundedClass = 'rounded-l-xl rounded-r-md';
                            if (isEnd) roundedClass = 'rounded-r-xl rounded-l-md';
                        }
                    } else if (isRange) {
                        bgClass = 'bg-indigo-600/10 scale-100';
                        textClass = 'text-indigo-900 font-semibold';
                        roundedClass = 'rounded-md';
                    } else {
                        bgClass = 'hover:bg-indigo-900/5 hover:scale-[1.02]';
                    }

                    return (
                        <div
                            key={date.toISOString()}
                            onClick={() => onDateClick(date)}
                            className={`
                group relative flex flex-col items-center justify-center aspect-square transition-all duration-300 cursor-pointer
                ${roundedClass}
                ${bgClass}
                ${textClass}
              `}
                        >
                            {isSelected && (
                                <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-white/20 to-transparent pointer-events-none" />
                            )}

                            {isTodayDate && !isSelected && !isRange && (
                                <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-indigo-500" />
                            )}

                            <span className={`relative z-10 text-sm font-medium ${isSelected ? 'text-base mb-1' : ''}`}>
                                {date.getDate()}
                            </span>

                            {isSelected && (
                                <span className="relative z-10 text-[8px] font-bold leading-none tracking-widest uppercase opacity-90">
                                    {isStart ? '开始' : '结束'}
                                </span>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
});

// ------------------- 主要组件 -------------------

const GlassCalendar: React.FC<GlassCalendarProps> = ({
    className = "",
    enableRangeSelection = true,
    onRangeSelect,
    monthsToShow = 12
}) => {
    const [currentDate] = useState(new Date());
    const [selection, setSelection] = useState<DateRange>({ start: null, end: null });

    // 新增：当前顶部显示的月份状态
    const [visibleMonthTitle, setVisibleMonthTitle] = useState(() => {
        return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long' }).format(new Date());
    });

    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const monthRefs = useRef(new Map<string, HTMLDivElement>());

    // 生成未来N个月的数据列表
    const monthsList = useMemo(() => {
        const list = [];
        for (let i = 0; i < monthsToShow; i++) {
            const d = new Date(currentDate.getFullYear(), currentDate.getMonth() + i, 1);
            list.push({ year: d.getFullYear(), month: d.getMonth() });
        }
        return list;
    }, [currentDate, monthsToShow]);

    // 状态提示文字
    const statusMessage = useMemo(() => {
        if (!enableRangeSelection) return "选择日期";
        if (!selection.start) return "请选择开始日期";
        if (selection.start && !selection.end) return "请选择结束日期";
        return "已选择范围";
    }, [selection, enableRangeSelection]);

    // 滚动监听：动态更新顶部月份标题
    useEffect(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        const handleScroll = () => {
            // 简单的逻辑：找到第一个距离容器顶部较近的月份元素
            const containerTop = container.getBoundingClientRect().top;

            for (const [key, el] of monthRefs.current.entries()) {
                if (!el) continue;
                const rect = el.getBoundingClientRect();
                // 如果元素的底部还在容器顶部下方一段距离内，说明它还是可见的主体
                // 或者元素的顶部接近容器顶部
                if (rect.bottom > containerTop + 100 && rect.top < containerTop + 300) {
                    const year = parseInt(el.getAttribute('data-year') || '0');
                    const month = parseInt(el.getAttribute('data-month') || '0');
                    const title = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long' }).format(new Date(year, month, 1));
                    setVisibleMonthTitle(title);
                    break; // 找到第一个就停止
                }
            }
        };

        container.addEventListener('scroll', handleScroll);
        return () => container.removeEventListener('scroll', handleScroll);
    }, []);

    const handleDateClick = (date: Date) => {
        if (enableRangeSelection) {
            if (!selection.start || (selection.start && selection.end)) {
                const newSelection = { start: date, end: null };
                setSelection(newSelection);
                if (onRangeSelect) onRangeSelect(newSelection);
            } else {
                let newStart = selection.start;
                let newEnd = date;

                if (newEnd < newStart) {
                    [newStart, newEnd] = [newEnd, newStart];
                }

                const newSelection = { start: newStart, end: newEnd };
                setSelection(newSelection);
                if (onRangeSelect) onRangeSelect(newSelection);
            }
        } else {
            const newSelection = { start: date, end: null };
            setSelection(newSelection);
            if (onRangeSelect) onRangeSelect(newSelection);
        }
    };

    return (
        <div
            className={`relative overflow-hidden rounded-[2rem] backdrop-blur-[40px] transition-all duration-300 ${className}`}
            style={{
                background: 'linear-gradient(145deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0.1) 100%)',
                boxShadow: `
          0 25px 50px -12px rgba(30, 58, 138, 0.25), 
          inset 0 0 0 1px rgba(255, 255, 255, 0.5),
          inset 0 1px 0 0 rgba(255, 255, 255, 0.9)
        `
            }}
        >
            <style>{`
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>

            {/* 浅灰色渐变背景层 - 让玻璃效果更明显 */}
            <div
                className="absolute inset-0 -z-20 rounded-[2rem]"
                style={{
                    background: 'linear-gradient(135deg, #e2e8f0 0%, #f1f5f9 25%, #e2e8f0 50%, #f8fafc 75%, #e2e8f0 100%)',
                }}
            />

            {/* 物理光泽层 */}
            <div className="absolute top-0 right-0 w-[80%] h-full bg-gradient-to-l from-indigo-100/10 to-transparent pointer-events-none z-0" />
            <div className="absolute bottom-0 left-0 w-full h-1/3 bg-gradient-to-t from-indigo-100/10 to-transparent pointer-events-none z-0" />

            {/* 噪点纹理 */}
            <div className="absolute inset-0 opacity-[0.04] pointer-events-none z-0 mix-blend-overlay"
                style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }}
            />

            {/* --- 固定顶部区域 (Global Sticky Header) --- */}
            <div className="relative z-20 px-8 pt-8 pb-4 bg-white/5 backdrop-blur-md border-b border-white/10 shadow-sm">
                <div className="flex flex-col items-start justify-center select-none pl-1">
                    {/* 状态提示 */}
                    <div className="flex items-center gap-2 mb-2 ml-0.5">
                        <div className={`h-1.5 w-1.5 rounded-full ${selection.end ? 'bg-emerald-400' : 'bg-indigo-400 animate-pulse'}`}></div>
                        <div className="text-[10px] font-bold tracking-[0.1em] text-indigo-900/60 uppercase">
                            {statusMessage}
                        </div>
                    </div>

                    {/* 1. 动态月份标题 (Month Title) */}
                    <h2 className="text-3xl font-bold tracking-tight text-slate-800 drop-shadow-sm font-sans transition-all duration-300">
                        {visibleMonthTitle}
                    </h2>
                </div>

                {/* 2. 星期表头 (Week Header) - 位于月份标题下方 */}
                <div className="mt-6 grid grid-cols-7 text-center">
                    {['日', '一', '二', '三', '四', '五', '六'].map((day) => (
                        <div key={day} className="text-xs font-bold uppercase tracking-widest text-slate-400/90">
                            {day}
                        </div>
                    ))}
                </div>
            </div>

            {/* --- 滚动区域 (Scroll Content) --- */}
            <div
                ref={scrollContainerRef}
                className="relative z-10 px-8 pb-8 h-[450px] overflow-y-auto no-scrollbar scroll-smooth"
            >
                <div className="pt-4">
                    {monthsList.map((m, idx) => (
                        <MonthSection
                            key={`${m.year}-${m.month}`}
                            year={m.year}
                            month={m.month}
                            selection={selection}
                            onDateClick={handleDateClick}
                            setRef={(el) => {
                                if (el) monthRefs.current.set(`${m.year}-${m.month}`, el);
                                else monthRefs.current.delete(`${m.year}-${m.month}`);
                            }}
                        />
                    ))}

                    <div className="mt-8 flex justify-center opacity-30">
                        <div className="h-1 w-16 rounded-full bg-slate-400"></div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default GlassCalendar;