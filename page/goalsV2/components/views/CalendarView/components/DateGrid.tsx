import React, { useMemo } from 'react';
import { Plus, GripVertical } from 'lucide-react';
import { DroppableDateCell, DraggableItem } from '@my-ui-kit/core';
import { TodoItem } from '../../../../types/todo';
import { useTaskPoolStore } from '../../../../hooks/useTaskPoolStore';
import { useGoalPageContext } from '../../../../context/GoalPageContext';

interface DateGridProps {
    startDate: Date;
    endDate: Date;
}

/**
 * 生成日期范围数组
 */
const generateDateRange = (start: Date, end: Date): string[] => {
    const dates: string[] = [];
    const current = new Date(start);

    while (current <= end) {
        dates.push(current.toISOString().split('T')[0]);
        current.setDate(current.getDate() + 1);
    }

    return dates;
};

/**
 * 弹性布局日期格子容器 - 参考taskCalendar设计风格
 */
export const DateGrid: React.FC<DateGridProps> = ({ startDate, endDate }) => {
    const { tasks } = useTaskPoolStore();
    const { selectedDate, setSelectedDate } = useGoalPageContext();

    const dates = useMemo(() => generateDateRange(startDate, endDate), [startDate, endDate]);

    // 按日期分组任务（只显示被直接拖动的任务，不显示因父任务拖动而跟随的子任务）
    const tasksByDate = useMemo(() => {
        const map = new Map<string, TodoItem[]>();

        tasks.forEach(task => {
            if (task.scheduledDate) {
                // 检查父任务是否也是 scheduled 状态
                const parentTask = task.parentId
                    ? tasks.find(t => t.id === Number(task.parentId))
                    : null;
                const parentIsScheduled = parentTask && parentTask.state === 'scheduled';

                // 只显示：没有父任务 或 父任务不是scheduled状态的任务
                // 这样可以区分"被直接拖动的任务"和"因父任务拖动而跟随的子任务"
                if (!task.parentId || !parentIsScheduled) {
                    if (!map.has(task.scheduledDate)) {
                        map.set(task.scheduledDate, []);
                    }
                    map.get(task.scheduledDate)!.push(task);
                }
            }
        });

        return map;
    }, [tasks]);

    // 判断是否是今天
    const isToday = (dateStr: string) => {
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        return dateStr === todayStr;
    };

    // 判断是否是周末
    const isWeekend = (dateObj: Date) => {
        const day = dateObj.getDay();
        return day === 0 || day === 6;
    };

    return (
        <div className="flex-1 overflow-y-auto calendar-scrollbar">
            {/* 内容区域 */}
            <div className="px-6 py-4 max-w-6xl mx-auto">
                {/* 日期格子网格 */}
                <div className="flex flex-wrap gap-4 justify-start">
                    {dates.map(date => {
                        const dateTasks = tasksByDate.get(date) || [];
                        const dateObj = new Date(date);
                        const dayName = ['日', '一', '二', '三', '四', '五', '六'][dateObj.getDay()];
                        const monthDay = `${dateObj.getMonth() + 1}/${dateObj.getDate()}`;
                        const today = isToday(date);
                        const weekend = isWeekend(dateObj);
                        const isSelected = selectedDate.toISOString().split('T')[0] === date;

                        const handleDateClick = () => {
                            setSelectedDate(dateObj);
                        };

                        return (
                            <DroppableDateCell
                                key={date}
                                id={`date-${date}`}
                                date={date}
                                className="w-[200px] h-[360px] flex-shrink-0 rounded-2xl"
                            >
                                {/* 日期卡片 - 参考taskCalendar的磨砂玻璃设计 */}
                                <div
                                    onClick={handleDateClick}
                                    className={`
                                    group/cell relative flex-1 rounded-2xl p-3.5 flex flex-col cursor-pointer
                                    transition-all duration-300 ease-out
                                    bg-white border border-slate-200/60
                                    shadow-[0_4px_20px_-4px_rgba(0,0,0,0.06)]
                                    hover:shadow-[0_12px_40px_-8px_rgba(0,0,0,0.12)]
                                    hover:border-slate-300/80
                                    hover:translate-y-[-2px]
                                    ${today ? 'ring-2 ring-blue-400/60 shadow-[0_8px_30px_-6px_rgba(59,130,246,0.25)]' : ''}
                                    ${isSelected && !today ? 'ring-2 ring-emerald-400/60 shadow-[0_8px_30px_-6px_rgba(16,185,129,0.25)]' : ''}
                                    ${weekend ? 'bg-slate-50/80' : ''}
                                `}>
                                    {/* 顶部反光效果 - 参考taskCalendar */}
                                    <div className="absolute inset-0 -z-10 bg-gradient-to-br from-white via-transparent to-transparent opacity-90 pointer-events-none rounded-2xl" />

                                    {/* 日期标题区域 */}
                                    <div className="flex-shrink-0 mb-2.5">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-baseline gap-2">
                                                {/* 日期数字 */}
                                                <span className={`
                                                    text-xl font-bold tracking-tight
                                                    ${today ? 'text-blue-600' : 'text-slate-800'}
                                                    ${weekend && !today ? 'text-slate-500' : ''}
                                                `}>
                                                    {monthDay}
                                                </span>
                                                {/* 星期 */}
                                                <span className={`
                                                    text-xs font-semibold uppercase tracking-widest
                                                    ${weekend ? 'text-amber-500' : 'text-slate-400'}
                                                `}>
                                                    周{dayName}
                                                </span>
                                            </div>

                                            {/* 今日标记 - 参考taskCalendar的今天标签 */}
                                            {today && (
                                                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500 shadow-lg shadow-blue-500/30">
                                                    <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                                                    <span className="text-[10px] font-bold text-white uppercase tracking-wider">今天</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* 分隔线 */}
                                    <div className="h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent mb-2.5 flex-shrink-0" />

                                    {/* 任务列表区域 */}
                                    <div className="flex-1 overflow-y-auto space-y-1.5 scrollbar-hide">
                                        {dateTasks.length === 0 ? (
                                            /* 空状态 - 参考taskCalendar的添加提示 */
                                            <div
                                                className="flex flex-col items-center justify-center h-full
                                                    opacity-0 group-hover/cell:opacity-100
                                                    transition-opacity duration-300 cursor-pointer"
                                            >
                                                <div className="w-10 h-10 rounded-xl bg-slate-100 border-2 border-dashed border-slate-200
                                                    flex items-center justify-center mb-2
                                                    group-hover/cell:border-slate-300 group-hover/cell:bg-slate-50
                                                    transition-all duration-300">
                                                    <Plus size={16} className="text-slate-300 group-hover/cell:text-slate-400" />
                                                </div>
                                                <span className="text-xs font-medium text-slate-300 group-hover/cell:text-slate-400">
                                                    拖放任务到这里
                                                </span>
                                            </div>
                                        ) : (
                                            /* 任务卡片列表 - 支持拖拽 */
                                            dateTasks.map(task => (
                                                <DraggableItem
                                                    key={task.id}
                                                    id={`calendar-${task.id}`}
                                                    type="task"
                                                    source="calendar"
                                                    data={task}
                                                    draggingClassName="opacity-50 shadow-xl scale-105"
                                                >
                                                    <div
                                                        className="
                                                            group/task relative px-2.5 py-2 rounded-xl text-xs font-medium cursor-grab
                                                            transition-all duration-200
                                                            bg-slate-50 text-slate-700
                                                            border border-slate-100
                                                            hover:bg-slate-100 hover:border-slate-200
                                                            hover:shadow-sm hover:scale-[1.01]
                                                            active:cursor-grabbing active:scale-[0.99]
                                                        "
                                                        title={task.content}
                                                    >
                                                        <div className="flex items-center gap-2">
                                                            {/* 拖拽手柄 */}
                                                            <GripVertical
                                                                size={12}
                                                                className="text-slate-300 opacity-0 group-hover/task:opacity-100 transition-opacity flex-shrink-0"
                                                            />
                                                            {/* 状态指示器 */}
                                                            <div className={`
                                                                w-2 h-2 rounded-full flex-shrink-0
                                                                ${task.state == "completed" ? 'bg-emerald-400' : 'bg-violet-400'}
                                                                shadow-sm
                                                            `} />
                                                            <span className="truncate">{task.content}</span>
                                                        </div>
                                                    </div>
                                                </DraggableItem>
                                            ))
                                        )}
                                    </div>

                                    {/* 底部任务计数 */}
                                    {dateTasks.length > 0 && (
                                        <div className="flex-shrink-0 mt-2.5 pt-1.5 border-t border-slate-100">
                                            <div className="flex items-center justify-between">
                                                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                                                    {dateTasks.length} 个任务
                                                </span>
                                                {/* 完成进度指示 */}
                                                <div className="flex items-center gap-1">
                                                    <div className="w-12 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                                                        <div
                                                            className="h-full rounded-full bg-emerald-400 transition-all duration-300"
                                                            style={{
                                                                width: `${(dateTasks.filter(t => t.state === "completed").length / dateTasks.length) * 100}%`
                                                            }}
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </DroppableDateCell>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

