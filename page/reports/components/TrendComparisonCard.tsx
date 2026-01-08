/**
 * Trend Comparison Card Component
 * 
 * 环比对比组件 - 展示分类/目标的周期同比数据
 * 布局: 主分类1 | 主分类2 | Goals 三栏水平滚动
 */

import React, { useState } from 'react';
import { TrendingUp, TrendingDown, Minus, ChevronRight, BarChart3 } from 'lucide-react';
import { ComparisonData, CategoryComparisonItem, GoalComparisonItem } from '../types';

interface TrendComparisonCardProps {
    data: ComparisonData;
    title?: string;
    className?: string;
}

// 预定义的彩色色板
const TREND_COLORS = [
    '#FFD60A', // 金黄
    '#FF6B6B', // 珊瑚红
    '#4ECDC4', // 青色
    '#A78BFA', // 紫色
    '#34D399', // 绿色
    '#FB923C', // 橙色
    '#60A5FA', // 蓝色
    '#F472B6', // 粉色
    '#FBBF24', // 琥珀
    '#10B981', // 翡翠绿
];

/**
 * 格式化秒数为可读时间
 */
const formatDuration = (seconds: number): string => {
    if (seconds < 0) seconds = Math.abs(seconds);

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0) {
        return `${hours}h${minutes > 0 ? ` ${minutes}m` : ''}`;
    }
    return `${minutes}m`;
};

/**
 * 格式化每日平均时间
 */
const formatDailyAverage = (seconds: number, days: number = 7): string => {
    const dailySeconds = seconds / days;
    const hours = Math.floor(dailySeconds / 3600);
    const minutes = Math.floor((dailySeconds % 3600) / 60);

    if (hours > 0) {
        return `${hours}小时/天`;
    }
    return `${minutes}分钟/天`;
};

/**
 * 获取趋势图标和颜色
 */
const getTrendIcon = (changeSeconds: number) => {
    if (changeSeconds > 0) {
        return { Icon: TrendingUp, color: '#F59E0B', bgColor: '#FFFBEB' }; // amber-500, amber-50
    } else if (changeSeconds < 0) {
        return { Icon: TrendingDown, color: '#EF4444', bgColor: '#FEF2F2' }; // red-500, red-50
    }
    return { Icon: Minus, color: '#64748B', bgColor: '#F8FAFC' }; // slate-500, slate-50
};

/**
 * 单个趋势指标项
 */
const TrendItem: React.FC<{
    name: string;
    currentDuration: number;
    changeSeconds: number;
    changePercentage?: number | null;
    color: string;
    isChild?: boolean;
}> = ({ name, currentDuration, changeSeconds, changePercentage, color, isChild = false }) => {
    const { Icon, bgColor } = getTrendIcon(changeSeconds);

    return (
        <div
            className={`
                flex items-start gap-3 py-3 px-4 rounded-xl transition-all duration-200
                hover:bg-gray-50 cursor-default
                ${isChild ? 'ml-4' : ''}
            `}
        >
            {/* 趋势图标 */}
            <div
                className="p-2 rounded-lg flex-shrink-0"
                style={{ backgroundColor: bgColor }}
            >
                <Icon size={18} style={{ color }} />
            </div>

            {/* 内容 */}
            <div className="flex-1 min-w-0">
                {/* 名称 */}
                <p className="text-slate-600 text-sm font-medium truncate">
                    {name}
                </p>

                {/* 数值 */}
                <p className="mt-0.5" style={{ color }}>
                    <span className="text-xl font-bold">
                        {formatDuration(currentDuration)}
                    </span>
                    <span className="text-xs text-slate-400 ml-1">
                        /{formatDailyAverage(currentDuration)}
                    </span>
                </p>

                {/* 变化百分比 */}
                {changePercentage !== null && changePercentage !== undefined && (
                    <p className="text-xs text-slate-400 mt-0.5">
                        {changeSeconds >= 0 ? '+' : ''}{formatDuration(changeSeconds)}
                        {' '}
                        ({changePercentage > 0 ? '+' : ''}{changePercentage.toFixed(1)}%)
                    </p>
                )}
            </div>
        </div>
    );
};

/**
 * 分类列（包含主分类和子分类）
 */
const CategoryColumn: React.FC<{
    category: CategoryComparisonItem;
    colorIndex: number;
}> = ({ category, colorIndex }) => {
    const [isExpanded, setIsExpanded] = useState(true);
    const mainColor = category.categoryColor || TREND_COLORS[colorIndex % TREND_COLORS.length];

    return (
        <div className="flex flex-col min-w-[200px] max-w-[280px]">
            {/* 主分类 Header */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors mb-2"
            >
                <div
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{ backgroundColor: mainColor }}
                />
                <span className="text-slate-700 font-semibold text-sm flex-1 text-left truncate">
                    {category.categoryName}
                </span>
                <ChevronRight
                    size={16}
                    className={`text-slate-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                />
            </button>

            {/* 主分类数据 */}
            <TrendItem
                name={category.categoryName}
                currentDuration={category.currentDuration}
                changeSeconds={category.changeSeconds}
                changePercentage={category.changePercentage}
                color={mainColor}
            />

            {/* 子分类列表 */}
            {isExpanded && category.children && category.children.length > 0 && (
                <div className="space-y-1 mt-1">
                    {category.children.map((child, idx) => (
                        <TrendItem
                            key={child.categoryId}
                            name={child.categoryName}
                            currentDuration={child.currentDuration}
                            changeSeconds={child.changeSeconds}
                            changePercentage={child.changePercentage}
                            color={child.categoryColor || TREND_COLORS[(colorIndex + idx + 1) % TREND_COLORS.length]}
                            isChild
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

/**
 * 目标列
 */
const GoalsColumn: React.FC<{
    goals: GoalComparisonItem[];
}> = ({ goals }) => {
    return (
        <div className="flex flex-col min-w-[200px] max-w-[280px]">
            {/* Header */}
            <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-50 mb-2">
                <BarChart3 size={16} className="text-slate-500" />
                <span className="text-slate-700 font-semibold text-sm">
                    Goals 目标
                </span>
            </div>

            {/* 目标列表 */}
            <div className="space-y-1">
                {goals.map((goal, idx) => (
                    <TrendItem
                        key={goal.goalId}
                        name={goal.goalName}
                        currentDuration={goal.currentDuration}
                        changeSeconds={goal.changeSeconds}
                        changePercentage={goal.changePercentage}
                        color={goal.goalColor || TREND_COLORS[(idx + 5) % TREND_COLORS.length]}
                    />
                ))}
            </div>
        </div>
    );
};

/**
 * 分隔线
 */
const Divider: React.FC = () => (
    <div className="w-px bg-gradient-to-b from-transparent via-gray-200 to-transparent mx-2 self-stretch" />
);

/**
 * 主组件
 */
const TrendComparisonCard: React.FC<TrendComparisonCardProps> = ({
    data,
    title = '趋势',
    className = ''
}) => {
    return (
        <div
            className={`
                bg-white
                rounded-2xl shadow-sm border border-gray-100
                overflow-hidden
                ${className}
            `}
        >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-50">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-indigo-50 text-indigo-500 rounded-xl">
                        <TrendingUp size={20} />
                    </div>
                    <div>
                        <h3 className="text-slate-800 font-bold text-lg">{title}</h3>
                        <p className="text-slate-400 text-xs mt-0.5">
                            {data.currentStart} ~ {data.currentEnd} vs {data.previousStart} ~ {data.previousEnd}
                        </p>
                    </div>
                </div>
                <ChevronRight size={22} className="text-slate-300" />
            </div>

            {/* Content - 横向滚动区域 */}
            <div className="px-4 py-4 overflow-x-auto">
                <div className="flex gap-2 min-w-max">
                    {/* 分类列 */}
                    {data.categoryComparison.map((category, idx) => (
                        <React.Fragment key={category.categoryId}>
                            <CategoryColumn category={category} colorIndex={idx} />
                            {idx < data.categoryComparison.length - 1 && <Divider />}
                        </React.Fragment>
                    ))}

                    {/* 分隔线 */}
                    {data.goalComparison.length > 0 && data.categoryComparison.length > 0 && (
                        <Divider />
                    )}

                    {/* 目标列 */}
                    {data.goalComparison.length > 0 && (
                        <GoalsColumn goals={data.goalComparison} />
                    )}
                </div>
            </div>
        </div>
    );
};

export default TrendComparisonCard;
