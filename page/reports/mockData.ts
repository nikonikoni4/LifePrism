/**
 * Report Mock Data
 * 
 * 报告页面模拟数据
 */

import { TimeOverviewData } from '../common/types';
import {
    DailyReportData,
    WeeklyReportData,
    MonthlyReportData,
    CategoryConfig,
    TimeDistributionPoint,
    GoalProgressData,
    HeatmapDay
} from './types';

// ============================================================================
// Common Mock Data
// ============================================================================

/** 通用分类配置 */
export const MOCK_CATEGORIES: CategoryConfig[] = [
    { key: 'work', name: '工作', color: '#5B8FF9' },
    { key: 'study', name: '学习', color: '#61DDAA' },
    { key: 'entertainment', name: '娱乐', color: '#F6BD16' },
    { key: 'life', name: '生活', color: '#7262FD' },
    { key: 'other', name: '其他', color: '#78D3F8' },
];

/** 生成时间分布数据 (24小时) */
const generateDailyDistribution = (): TimeDistributionPoint[] => {
    const data: TimeDistributionPoint[] = [];
    for (let h = 0; h < 24; h++) {
        const isWorkHour = h >= 9 && h <= 18;
        const isEveningStudy = h >= 19 && h <= 22;
        const isEntertainment = h >= 20 && h <= 23;

        data.push({
            label: `${h}`,
            work: isWorkHour ? Math.floor(Math.random() * 40 + 20) : Math.floor(Math.random() * 10),
            study: isEveningStudy ? Math.floor(Math.random() * 30 + 10) : Math.floor(Math.random() * 5),
            entertainment: isEntertainment ? Math.floor(Math.random() * 25 + 5) : Math.floor(Math.random() * 5),
            life: Math.floor(Math.random() * 10 + 5),
            other: Math.floor(Math.random() * 5),
        });
    }
    return data;
};

/** 生成周度趋势数据 */
const generateWeeklyTrend = (): TimeDistributionPoint[] => {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const today = new Date();
    // Assuming today is somewhere in the week, let's just generate a week ending today or starting today.
    // To match backend logic somewhat, let's just create 7 dummy dates
    const start = new Date();
    start.setDate(start.getDate() - start.getDay() + 1); // Set to Monday

    return days.map((day, index) => {
        const date = new Date(start);
        date.setDate(start.getDate() + index);
        const dateStr = date.toISOString().split('T')[0];

        return {
            label: day,
            date: dateStr,
            work: day === 'Sat' || day === 'Sun'
                ? Math.floor(Math.random() * 60 + 30)
                : Math.floor(Math.random() * 180 + 300),
            study: Math.floor(Math.random() * 90 + 60),
            entertainment: day === 'Sat' || day === 'Sun'
                ? Math.floor(Math.random() * 120 + 60)
                : Math.floor(Math.random() * 60 + 30),
            life: Math.floor(Math.random() * 60 + 30),
            other: Math.floor(Math.random() * 30 + 10),
        };
    });
};

/** 生成热力图数据 (一个月) */
const generateHeatmapData = (year: number, month: number): HeatmapDay[] => {
    const daysInMonth = new Date(year, month, 0).getDate();
    const data: HeatmapDay[] = [];

    for (let d = 1; d <= daysInMonth; d++) {
        const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        const dayOfWeek = new Date(year, month - 1, d).getDay();
        const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;

        data.push({
            date: dateStr,
            value: isWeekend
                ? Math.floor(Math.random() * 300 + 200)
                : Math.floor(Math.random() * 400 + 400),
            categoryBreakdown: {
                work: isWeekend ? Math.floor(Math.random() * 60) : Math.floor(Math.random() * 200 + 200),
                study: Math.floor(Math.random() * 90 + 30),
                entertainment: isWeekend ? Math.floor(Math.random() * 120 + 60) : Math.floor(Math.random() * 60),
                life: Math.floor(Math.random() * 60 + 30),
                other: Math.floor(Math.random() * 30),
            }
        });
    }
    return data;
};

/** 生成旭日图数据 */
const generateSunburstData = (type: 'daily' | 'weekly' | 'monthly'): TimeOverviewData => {
    const multiplier = type === 'daily' ? 1 : type === 'weekly' ? 7 : 30;

    const workMinutes = Math.floor((300 + Math.random() * 120) * multiplier);
    const studyMinutes = Math.floor((90 + Math.random() * 60) * multiplier);
    const entertainmentMinutes = Math.floor((60 + Math.random() * 60) * multiplier);
    const lifeMinutes = Math.floor((45 + Math.random() * 30) * multiplier);
    const otherMinutes = Math.floor((20 + Math.random() * 20) * multiplier);

    const totalMinutes = workMinutes + studyMinutes + entertainmentMinutes + lifeMinutes + otherMinutes;

    return {
        title: type === 'daily' ? '今日时间分布' : type === 'weekly' ? '本周时间分布' : '本月时间分布',
        subTitle: `共计 ${Math.floor(totalMinutes / 60)} 小时 ${totalMinutes % 60} 分钟`,
        totalTrackedMinutes: totalMinutes,
        totalRangeMinutes: type === 'daily' ? 1440 : type === 'weekly' ? 10080 : 43200,
        pieData: [
            { key: 'work', name: '工作', value: workMinutes, color: '#5B8FF9' },
            { key: 'study', name: '学习', value: studyMinutes, color: '#61DDAA' },
            { key: 'entertainment', name: '娱乐', value: entertainmentMinutes, color: '#F6BD16' },
            { key: 'life', name: '生活', value: lifeMinutes, color: '#7262FD' },
            { key: 'other', name: '其他', value: otherMinutes, color: '#78D3F8' },
        ],
        barKeys: MOCK_CATEGORIES.map(c => ({ key: c.key, label: c.name, color: c.color })),
        barData: type === 'daily'
            ? generateDailyDistribution().filter((_, i) => i % 4 === 0).map(d => ({ ...d, timeRange: `${d.label}:00` }))
            : type === 'weekly'
                ? generateWeeklyTrend().map(d => ({ ...d, timeRange: d.label }))
                : generateWeeklyTrend().map((d, i) => ({ ...d, timeRange: `Week ${i + 1}` })),
        details: {
            '工作': {
                title: '工作详情',
                subTitle: `${Math.floor(workMinutes / 60)}h ${workMinutes % 60}m`,
                totalTrackedMinutes: workMinutes,
                pieData: [
                    { key: 'coding', name: '编程开发', value: Math.floor(workMinutes * 0.5), color: '#5B8FF9' },
                    { key: 'meeting', name: '会议沟通', value: Math.floor(workMinutes * 0.2), color: '#748FFC' },
                    { key: 'docs', name: '文档撰写', value: Math.floor(workMinutes * 0.2), color: '#91A7FF' },
                    { key: 'review', name: '代码审查', value: Math.floor(workMinutes * 0.1), color: '#BAC8FF' },
                ],
                barKeys: [
                    { key: 'coding', label: '编程开发', color: '#5B8FF9' },
                    { key: 'meeting', label: '会议沟通', color: '#748FFC' },
                    { key: 'docs', label: '文档撰写', color: '#91A7FF' },
                    { key: 'review', label: '代码审查', color: '#BAC8FF' },
                ],
                barData: [],
            },
            '学习': {
                title: '学习详情',
                subTitle: `${Math.floor(studyMinutes / 60)}h ${studyMinutes % 60}m`,
                totalTrackedMinutes: studyMinutes,
                pieData: [
                    { key: 'reading', name: '阅读', value: Math.floor(studyMinutes * 0.4), color: '#61DDAA' },
                    { key: 'course', name: '课程学习', value: Math.floor(studyMinutes * 0.35), color: '#7FE7BA' },
                    { key: 'practice', name: '实践练习', value: Math.floor(studyMinutes * 0.25), color: '#A3F0CC' },
                ],
                barKeys: [
                    { key: 'reading', label: '阅读', color: '#61DDAA' },
                    { key: 'course', label: '课程学习', color: '#7FE7BA' },
                    { key: 'practice', label: '实践练习', color: '#A3F0CC' },
                ],
                barData: [],
            },
        }
    };
};

/** 生成 Goal 进度数据 */
const generateGoalProgress = (): GoalProgressData[] => [
    {
        goalId: 'goal-1',
        goalName: '完成项目重构',
        goalColor: '#5B8FF9',
        timeInvested: 185,
        todoTotal: 8,
        todoCompleted: 5,
        todoList: [
            { id: 1, content: '重构数据库模型', completed: true },
            { id: 2, content: '优化 API 接口', completed: true },
            { id: 3, content: '更新前端组件', completed: true },
            { id: 4, content: '编写单元测试', completed: true },
            { id: 5, content: '代码审查', completed: true },
            { id: 6, content: '性能优化', completed: false },
            { id: 7, content: '文档更新', completed: false },
            { id: 8, content: '部署上线', completed: false },
        ]
    },
    {
        goalId: 'goal-2',
        goalName: '学习 TypeScript 进阶',
        goalColor: '#61DDAA',
        timeInvested: 90,
        todoTotal: 5,
        todoCompleted: 3,
        todoList: [
            { id: 9, content: '泛型深入学习', completed: true },
            { id: 10, content: '类型体操练习', completed: true },
            { id: 11, content: '装饰器使用', completed: true },
            { id: 12, content: '模块化设计', completed: false },
            { id: 13, content: '综合项目实践', completed: false },
        ]
    },
    {
        goalId: 'goal-3',
        goalName: '健身计划',
        goalColor: '#F6BD16',
        timeInvested: 45,
        todoTotal: 3,
        todoCompleted: 2,
        todoList: [
            { id: 14, content: '晨跑 30 分钟', completed: true },
            { id: 15, content: '力量训练', completed: true },
            { id: 16, content: '瑜伽拉伸', completed: false },
        ]
    }
];

// ============================================================================
// Daily Report Mock Data
// ============================================================================

export const getMockDailyReport = (date: string): DailyReportData => ({
    date,
    timeDistribution: generateDailyDistribution(),
    categories: MOCK_CATEGORIES,
    timeOverview: generateSunburstData('daily'),
    goalProgress: generateGoalProgress(),
    todoStats: {
        total: 16,
        completed: 10,
        pending: 6,
        procrastinationRate: 15.5
    },
    aiSummary: `📊 **今日效率分析**

今天你共追踪了 **8小时42分钟** 的有效活动时间。

**亮点：**
• 工作时段效率较高，9:00-12:00 是你今日最专注的时间段
• "完成项目重构" 目标完成了 5 个任务，进展顺利
• 学习时间集中在晚间，保持了良好的学习习惯

**建议：**
• 午后 14:00-16:00 可以安排更多高强度工作
• 娱乐时间可适当控制在 1 小时以内
• 明天可以优先处理未完成的性能优化任务

继续保持，你做得很棒！💪`,
});

// ============================================================================
// Weekly Report Mock Data
// ============================================================================

export const getMockWeeklyReport = (startDate: string, endDate: string): WeeklyReportData => ({
    startDate,
    endDate,
    weeklyTrend: generateWeeklyTrend(),
    categories: MOCK_CATEGORIES,
    timeOverview: generateSunburstData('weekly'),
    goalProgress: generateGoalProgress().map(g => ({
        ...g,
        timeInvested: g.timeInvested * 7,
        todoCompleted: Math.min(g.todoCompleted + 2, g.todoTotal),
    })),
    todoStats: {
        total: 112,
        completed: 88,
        pending: 24,
        procrastinationRate: 12.5
    },
    aiSummary: `📈 **本周规律总结**

本周累计有效时间 **52小时18分钟**，较上周增长 12%。

**工作模式：**
• 周一至周四工作效率最高，日均 6+ 小时深度工作
• 周五下午效率略有下降，建议安排较轻松的任务
• 周末保持了适度的学习和休息平衡

**目标进展：**
• "项目重构" 完成度已达 75%，预计下周可交付
• 学习目标保持稳定，每日约 1.5 小时
• 健身习惯形成良好，本周完成 5 次锻炼

**下周建议：**
1. 周一优先处理遗留的性能优化任务
2. 安排 2 小时进行代码审查
3. 周三可预留时间进行团队同步

你的时间投入正在稳步向目标靠近！🎯`,
});

// ============================================================================
// Monthly Report Mock Data
// ============================================================================

export const getMockMonthlyReport = (month: string): MonthlyReportData => {
    const [year, mon] = month.split('-').map(Number);

    return {
        month,
        heatmapData: generateHeatmapData(year, mon),
        categories: MOCK_CATEGORIES,
        timeOverview: generateSunburstData('monthly'),
        goalProgress: generateGoalProgress().map(g => ({
            ...g,
            timeInvested: g.timeInvested * 30,
            todoTotal: g.todoTotal * 4,
            todoCompleted: g.todoCompleted * 4 + Math.floor(Math.random() * 5),
        })),
        todoStats: {
            total: 190,
            completed: 156,
            pending: 34,
            procrastinationRate: 8.2
        },
        carryOverItems: [
            { id: 101, content: '完善产品文档', goalName: '完成项目重构' },
            { id: 102, content: '准备季度复盘报告', goalName: undefined },
            { id: 103, content: '学习 Rust 基础', goalName: '学习 TypeScript 进阶' },
        ],
        aiSummary: `🗓️ **${mon}月全局复盘**

本月累计追踪 **218小时35分钟**，日均活跃 7.2 小时。

**时间投资亮点：**
• 工作类目投入最多，占比 58%，主要集中在编程开发
• 学习时间稳步增长，月末较月初提升 25%
• 健身习惯逐渐稳固，完成率达到 85%

**目标达成情况：**
• "项目重构" 已进入收尾阶段，累计投入 55+ 小时
• TypeScript 进阶学习进度良好，完成 80% 的课程内容
• 健身计划超额完成，本月锻炼 22 次

**待完成事项：**
本月有 3 项任务需滚动至下月：
1. 完善产品文档（优先级：高）
2. 准备季度复盘报告（优先级：中）
3. 学习 Rust 基础（优先级：低）

**下月规划建议：**
• 优先完成项目重构的最后 25%
• 可开始规划新的学习目标
• 保持当前的健身节奏

你本月的表现非常出色！继续保持这样的势头！🌟`,
    };
};
