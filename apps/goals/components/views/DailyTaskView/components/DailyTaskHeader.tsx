import React from 'react';
import { Target, AlertTriangle } from 'lucide-react';

interface DailyTaskHeaderProps {
    selectedDate: Date;
    completedCount: number;
    totalCount: number;
    overdueCount: number;
}

/**
 * 每日任务头部状态栏
 * 显示标题、完成进度、逾期警示
 */
export const DailyTaskHeader: React.FC<DailyTaskHeaderProps> = ({
    selectedDate,
    completedCount,
    totalCount,
    overdueCount
}) => {
    const isToday = () => {
        const today = new Date();
        return selectedDate.toDateString() === today.toDateString();
    };

    const formatDate = () => {
        const month = selectedDate.getMonth() + 1;
        const day = selectedDate.getDate();
        const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
        const weekDay = weekDays[selectedDate.getDay()];
        return `${month}月${day}日 ${weekDay}`;
    };

    return (
        <div className="bg-white/50 backdrop-blur-sm border-b border-slate-200/60 px-6 py-4">
            <div className="flex items-center justify-between">
                {/* 左侧：标题和日期 */}
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-emerald-50 rounded-xl flex items-center justify-center text-emerald-500">
                        <Target size={20} strokeWidth={1.5} />
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-slate-800">
                            {isToday() ? '今日聚焦' : '每日聚焦'}
                        </h2>
                        <p className="text-sm text-slate-500">{formatDate()}</p>
                    </div>
                </div>

                {/* 右侧：统计标签 */}
                <div className="flex items-center gap-3">
                    {/* 完成进度 */}
                    <div className="bg-emerald-50 text-emerald-600 rounded-full px-3 py-1 text-sm font-medium">
                        {completedCount}/{totalCount} 完成
                    </div>

                    {/* 逾期警示 */}
                    {overdueCount > 0 && (
                        <div className="bg-red-50 text-red-600 rounded-full px-3 py-1 text-sm font-medium flex items-center gap-1.5">
                            <AlertTriangle size={14} />
                            {overdueCount} 项逾期
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
