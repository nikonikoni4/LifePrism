/**
 * 拖拽组件测试页面
 * 
 * 用于测试 dragDrop 和 todoItem 两个组件库的交互
 * 包含：
 * - 任务池 + 日历的跨区域拖拽功能
 * - 多级嵌套 TodoItemTree 测试
 */

import React, { useState, useCallback } from 'react';
import {
    CrossAreaDndProvider,
    DraggableItem,
    DroppableDateCell,
    DroppablePoolRoot,
    type DragItemData,
    type DropAreaData,
} from '../../my-ui-kit/ui-kit/dragDrop';
import { TodoItem as TodoItemComponent } from '../../my-ui-kit/ui-kit/todoItem/TodoItem';
import { TodoItemDetailed } from '../../my-ui-kit/ui-kit/todoItem/TodoItemDetailed';
import { TodoItemTree, useExpandedState } from '../../my-ui-kit/ui-kit/todoItem/TodoItemTree';
import { TodoItemTreeDetailed } from '../../my-ui-kit/ui-kit/todoItem/TodoItemTreeDetailed';
import { TodoItem } from '../../my-ui-kit/ui-kit/todoItem/types';

// =============================================================================
// 模拟数据
// =============================================================================

const createMockTodoItem = (
    id: number,
    content: string,
    state: 'pool' | 'scheduled' | 'completed' | 'shelved' = 'pool',
    scheduledDate: string | null = null,
    children?: TodoItem[],
    parentId: string | number | null = null
): TodoItem => ({
    id,
    content,
    parentId: parentId !== null ? String(parentId) : null,
    goalId: null,
    planDocId: null,
    sourceType: 'manual',
    sourceAnchorId: null,
    state,
    scheduledDate,
    expectedFinishAt: null,
    actualFinishAt: null,
    delayDays: null,
    delayReason: null,
    color: '#FFFFFF',
    orderIndex: id,
    poolOrderIndex: state === 'pool' ? id : null,
    children,
});

// 拖拽测试用的简单任务列表
const initialDragTasks: TodoItem[] = [
    createMockTodoItem(1, '📝 完成项目文档', 'pool'),
    createMockTodoItem(2, '🔧 修复登录Bug', 'pool'),
    createMockTodoItem(3, '🎨 设计新首页', 'pool'),
    createMockTodoItem(4, '📊 准备周报', 'pool'),
    createMockTodoItem(5, '💻 代码审查', 'pool'),
];

// 多级嵌套测试用的树形结构
const createNestedTasks = (): TodoItem[] => [
    createMockTodoItem(100, '🎯 项目 A - 网站重构', 'pool', null, [
        createMockTodoItem(101, '📋 需求分析', 'pool', null, [
            createMockTodoItem(102, '用户调研', 'pool', null, undefined, '101'),
            createMockTodoItem(103, '竞品分析', 'completed', null, undefined, '101'),
            createMockTodoItem(104, '需求文档编写', 'pool', null, undefined, '101'),
        ], '100'),
        createMockTodoItem(105, '🎨 UI 设计', 'pool', null, [
            createMockTodoItem(106, '首页设计', 'pool', null, undefined, '105'),
            createMockTodoItem(107, '产品详情页设计', 'pool', null, undefined, 105),
            createMockTodoItem(108, '用户中心设计', 'pool', null, [
                createMockTodoItem(109, '个人资料页', 'pool', null, undefined, 108),
                createMockTodoItem(110, '订单列表页', 'pool', null, undefined, 108),
                createMockTodoItem(111, '设置页面', 'pool', null, undefined, 108),
            ], 105),
        ], 100),
        createMockTodoItem(112, '💻 前端开发', 'pool', null, [
            createMockTodoItem(113, '搭建项目框架', 'completed', null, undefined, 112),
            createMockTodoItem(114, '组件库开发', 'pool', null, [
                createMockTodoItem(115, 'Button 组件', 'completed', null, undefined, 114),
                createMockTodoItem(116, 'Input 组件', 'completed', null, undefined, 114),
                createMockTodoItem(117, 'Modal 组件', 'pool', null, undefined, 114),
                createMockTodoItem(118, 'Table 组件', 'pool', null, undefined, 114),
            ], 112),
            createMockTodoItem(119, '页面开发', 'pool', null, undefined, 112),
        ], 100),
    ]),
    createMockTodoItem(200, '🚀 项目 B - 移动端 App', 'pool', null, [
        createMockTodoItem(201, '技术选型', 'completed', null, undefined, 200),
        createMockTodoItem(202, '原型设计', 'pool', null, [
            createMockTodoItem(203, '登录流程', 'pool', null, undefined, 202),
            createMockTodoItem(204, '主页布局', 'pool', null, undefined, 202),
        ], 200),
        createMockTodoItem(205, '开发计划', 'pool', null, undefined, 200),
    ]),
    createMockTodoItem(300, '📚 学习计划', 'pool', null, [
        createMockTodoItem(301, 'TypeScript 进阶', 'pool', null, [
            createMockTodoItem(302, '泛型编程', 'pool', null, undefined, 301),
            createMockTodoItem(303, '类型体操', 'pool', null, undefined, 301),
        ], 300),
        createMockTodoItem(304, 'React 18 新特性', 'pool', null, undefined, 300),
    ]),
];

// =============================================================================
// 工具函数
// =============================================================================

function getWeekDates(): string[] {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const startOfWeek = new Date(today);
    startOfWeek.setDate(today.getDate() - dayOfWeek);

    return Array.from({ length: 7 }, (_, i) => {
        const date = new Date(startOfWeek);
        date.setDate(startOfWeek.getDate() + i);
        return date.toISOString().split('T')[0];
    });
}

function formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    const isToday = new Date().toISOString().split('T')[0] === dateStr;
    return `${date.getMonth() + 1}/${date.getDate()} ${weekDays[date.getDay()]}${isToday ? ' (今天)' : ''}`;
}

// =============================================================================
// 多级 TodoItem 测试区域
// =============================================================================

const NestedTodoTestSection: React.FC = () => {
    const [tasks, setTasks] = useState<TodoItem[]>(createNestedTasks);
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const expandState = useExpandedState([100, 101, 105, 112, 114, 200, 300, 301]); // 默认展开部分节点

    const handleUpdate = useCallback((id: number, updates: Partial<TodoItem>) => {
        const updateRecursive = (items: TodoItem[]): TodoItem[] => {
            return items.map(item => {
                if (item.id === id) {
                    return { ...item, ...updates };
                }
                if (item.children) {
                    return { ...item, children: updateRecursive(item.children) };
                }
                return item;
            });
        };
        setTasks(prev => updateRecursive(prev));
    }, []);

    const handleDelete = useCallback((id: number) => {
        const deleteRecursive = (items: TodoItem[]): TodoItem[] => {
            return items
                .filter(item => item.id !== id)
                .map(item => ({
                    ...item,
                    children: item.children ? deleteRecursive(item.children) : undefined,
                }));
        };
        setTasks(prev => deleteRecursive(prev));
    }, []);

    const handleReset = () => {
        setTasks(createNestedTasks());
        setSelectedId(null);
    };

    // 统计任务数量
    const countTasks = (items: TodoItem[]): { total: number; completed: number } => {
        let total = 0;
        let completed = 0;
        const count = (list: TodoItem[]) => {
            list.forEach(item => {
                total++;
                if (item.state === 'completed') completed++;
                if (item.children) count(item.children);
            });
        };
        count(items);
        return { total, completed };
    };

    const stats = countTasks(tasks);

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="bg-gradient-to-r from-emerald-500 to-teal-500 px-4 py-3">
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    🌳 多级任务树测试
                    <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">
                        {stats.completed}/{stats.total} 已完成
                    </span>
                </h2>
                <p className="text-emerald-100 text-xs mt-1">
                    测试 TodoItemTree 的无限层级嵌套、展开/折叠功能
                </p>
            </div>

            {/* 控制按钮 */}
            <div className="px-4 py-3 border-b border-slate-100 flex gap-2 flex-wrap">
                <button
                    onClick={handleReset}
                    className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors text-xs font-medium"
                >
                    🔄 重置
                </button>
                <button
                    onClick={() => expandState.expandAll([100, 101, 105, 108, 112, 114, 200, 202, 300, 301])}
                    className="px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded-lg hover:bg-emerald-200 transition-colors text-xs font-medium"
                >
                    📂 全部展开
                </button>
                <button
                    onClick={() => expandState.collapseAll()}
                    className="px-3 py-1.5 bg-amber-100 text-amber-700 rounded-lg hover:bg-amber-200 transition-colors text-xs font-medium"
                >
                    📁 全部折叠
                </button>
                <div className="ml-auto text-xs text-slate-400 self-center">
                    点击任务可选中 | 点击复选框可完成 | 点击箭头可展开/折叠
                </div>
            </div>

            {/* 任务树 */}
            <div className="p-4 max-h-[500px] overflow-y-auto">
                <TodoItemTree
                    items={tasks}
                    collapsible={true}
                    defaultExpandedIds={expandState.expandedIds}
                    selectedId={selectedId}
                    onUpdate={handleUpdate}
                    onDelete={handleDelete}
                    onSelect={setSelectedId}
                    showSource={false}
                    showDate={false}
                />
            </div>

            {selectedId && (
                <div className="px-4 py-3 bg-slate-50 border-t border-slate-100 text-xs text-slate-600">
                    <span className="font-medium">已选中任务 ID:</span> {selectedId}
                </div>
            )}
        </div>
    );
};

// =============================================================================
// 每日聚焦详细版测试区域 (Daily Focus - Detailed TodoItem)
// =============================================================================

// 创建带时间信息的测试任务
const createDailyFocusTasks = (): TodoItem[] => {
    const today = new Date().toISOString().split('T')[0];
    const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];
    const twoDaysAgo = new Date(Date.now() - 2 * 86400000).toISOString().split('T')[0];
    const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];
    const inThreeDays = new Date(Date.now() + 3 * 86400000).toISOString().split('T')[0];

    return [
        // 已完成且按时
        {
            id: 501,
            content: '✅ 完成需求文档评审',
            parentId: null,
            goalId: 'goal-1',
            planDocId: '1',
            sourceType: 'plan_doc' as const,
            sourceAnchorId: 'lp:abc123',
            state: 'completed' as const,
            scheduledDate: twoDaysAgo,
            expectedFinishAt: yesterday,
            actualFinishAt: yesterday,
            delayDays: 0,
            delayReason: null,
            color: '#DCFCE7',
            orderIndex: 1,
            poolOrderIndex: null,
        },
        // 已完成但延迟
        {
            id: 502,
            content: '🎨 设计首页 UI 原型',
            parentId: null,
            goalId: 'goal-2',
            planDocId: '1',
            sourceType: 'plan_doc' as const,
            sourceAnchorId: 'lp:def456',
            state: 'completed' as const,
            scheduledDate: twoDaysAgo,
            expectedFinishAt: twoDaysAgo,
            actualFinishAt: yesterday,
            delayDays: 1,
            delayReason: '设计稿修改了三版，客户反馈较多',
            color: '#FEF3C7',
            orderIndex: 2,
            poolOrderIndex: null,
        },
        // 进行中，今天截止
        {
            id: 503,
            content: '💻 实现登录模块前端',
            parentId: null,
            goalId: null,
            planDocId: '1',
            sourceType: 'plan_doc' as const,
            sourceAnchorId: 'lp:ghi789',
            state: 'scheduled' as const,
            scheduledDate: yesterday,
            expectedFinishAt: today,
            actualFinishAt: null,
            delayDays: null,
            delayReason: null,
            color: '#E0F2FE',
            orderIndex: 3,
            poolOrderIndex: null,
            children: [
                {
                    id: 5031,
                    content: '登录表单组件',
                    parentId: '503',
                    goalId: null,
                    planDocId: '1',
                    sourceType: 'plan_doc' as const,
                    sourceAnchorId: 'lp:jkl012',
                    state: 'completed' as const,
                    scheduledDate: yesterday,
                    expectedFinishAt: yesterday,
                    actualFinishAt: yesterday,
                    delayDays: 0,
                    delayReason: null,
                    color: '#DCFCE7',
                    orderIndex: 1,
                    poolOrderIndex: null,
                },
                {
                    id: 5032,
                    content: '验证码逻辑',
                    parentId: '503',
                    goalId: null,
                    planDocId: '1',
                    sourceType: 'plan_doc' as const,
                    sourceAnchorId: 'lp:mno345',
                    state: 'scheduled' as const,
                    scheduledDate: today,
                    expectedFinishAt: today,
                    actualFinishAt: null,
                    delayDays: null,
                    delayReason: null,
                    color: '#FAE8FF',
                    orderIndex: 2,
                    poolOrderIndex: null,
                },
                {
                    id: 5033,
                    content: '第三方登录集成',
                    parentId: '503',
                    goalId: null,
                    planDocId: '1',
                    sourceType: 'plan_doc' as const,
                    sourceAnchorId: 'lp:pqr678',
                    state: 'scheduled' as const,
                    scheduledDate: today,
                    expectedFinishAt: tomorrow,
                    actualFinishAt: null,
                    delayDays: null,
                    delayReason: null,
                    color: '#FFFFFF',
                    orderIndex: 3,
                    poolOrderIndex: null,
                },
            ],
        },
        // 已逾期
        {
            id: 504,
            content: '📊 编写单元测试',
            parentId: null,
            goalId: null,
            planDocId: '2',
            sourceType: 'plan_doc' as const,
            sourceAnchorId: 'lp:stu901',
            state: 'scheduled' as const,
            scheduledDate: twoDaysAgo,
            expectedFinishAt: yesterday,
            actualFinishAt: null,
            delayDays: 1,
            delayReason: '优先级被其他任务压下来了',
            color: '#FEE2E2',
            orderIndex: 4,
            poolOrderIndex: null,
        },
        // 手动创建，剩余3天
        {
            id: 505,
            content: '📚 阅读《Clean Code》第5章',
            parentId: null,
            goalId: null,
            planDocId: null,
            sourceType: 'manual' as const,
            sourceAnchorId: null,
            state: 'scheduled' as const,
            scheduledDate: today,
            expectedFinishAt: inThreeDays,
            actualFinishAt: null,
            delayDays: null,
            delayReason: null,
            color: '#F3F4F6',
            orderIndex: 5,
            poolOrderIndex: null,
        },
    ];
};

const DailyFocusTestSection: React.FC = () => {
    const [tasks, setTasks] = useState<TodoItem[]>(createDailyFocusTasks);
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const expandState = useExpandedState([503]); // 默认展开第一个有子任务的

    // Mock data for goals and plans
    const goalsMap: Record<string, string> = {
        'goal-1': '学习目标',
        'goal-2': '工作目标',
    };
    const plansMap: Record<string, string> = {
        '1': '周计划 A',
        '2': '周计划 B',
    };

    const getGoalName = (goalId: string | null) => goalId ? goalsMap[goalId] : undefined;
    const getPlanName = (planDocId: string | null) => planDocId ? plansMap[planDocId] : undefined;

    const handleAddChild = useCallback((parentId: number) => {
        const newId = Date.now();
        const newTask: TodoItem = {
            id: newId,
            content: '新子任务',
            parentId: String(parentId),
            goalId: null,
            planDocId: null,
            sourceType: 'manual',
            sourceAnchorId: null,
            state: 'scheduled',
            scheduledDate: new Date().toISOString().split('T')[0],
            expectedFinishAt: null,
            actualFinishAt: null,
            delayDays: null,
            delayReason: null,
            color: '#FFFFFF',
            orderIndex: newId,
            poolOrderIndex: null,
        };

        const addChildRecursive = (items: TodoItem[]): TodoItem[] => {
            return items.map(item => {
                if (item.id === parentId) {
                    return {
                        ...item,
                        children: [...(item.children || []), newTask],
                    };
                }
                if (item.children) {
                    return { ...item, children: addChildRecursive(item.children) };
                }
                return item;
            });
        };
        setTasks(prev => addChildRecursive(prev));
    }, []);

    const handleUpdate = useCallback((id: number, updates: Partial<TodoItem>) => {
        const updateRecursive = (items: TodoItem[]): TodoItem[] => {
            return items.map(item => {
                if (item.id === id) {
                    return { ...item, ...updates };
                }
                if (item.children) {
                    return { ...item, children: updateRecursive(item.children) };
                }
                return item;
            });
        };
        setTasks(prev => updateRecursive(prev));
    }, []);

    const handleDelete = useCallback((id: number) => {
        const deleteRecursive = (items: TodoItem[]): TodoItem[] => {
            return items
                .filter(item => item.id !== id)
                .map(item => ({
                    ...item,
                    children: item.children ? deleteRecursive(item.children) : undefined,
                }));
        };
        setTasks(prev => deleteRecursive(prev));
    }, []);

    const handleReset = () => {
        setTasks(createDailyFocusTasks());
        setSelectedId(null);
    };

    // 统计任务
    const countTasks = (items: TodoItem[]): { total: number; completed: number; overdue: number } => {
        let total = 0;
        let completed = 0;
        let overdue = 0;
        const today = new Date().toISOString().split('T')[0];

        const count = (list: TodoItem[]) => {
            list.forEach(item => {
                total++;
                if (item.state === 'completed') completed++;
                if (item.state !== 'completed' && item.expectedFinishAt && item.expectedFinishAt < today) {
                    overdue++;
                }
                if (item.children) count(item.children);
            });
        };
        count(items);
        return { total, completed, overdue };
    };

    const stats = countTasks(tasks);

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="bg-gradient-to-r from-rose-500 to-pink-500 px-4 py-3">
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    🎯 每日聚焦（详细版）
                    <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">
                        {stats.completed}/{stats.total} 完成
                    </span>
                    {stats.overdue > 0 && (
                        <span className="text-xs bg-red-600/80 px-2 py-0.5 rounded-full">
                            ⚠️ {stats.overdue} 项逾期
                        </span>
                    )}
                </h2>
                <p className="text-rose-100 text-xs mt-1">
                    使用 TodoItemDetailed 组件，展示时间信息、拖延状态和原因记录
                </p>
            </div>

            {/* 控制按钮 */}
            <div className="px-4 py-3 border-b border-slate-100 flex gap-2 flex-wrap">
                <button
                    onClick={handleReset}
                    className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors text-xs font-medium"
                >
                    🔄 重置
                </button>
                <button
                    onClick={() => expandState.expandAll([503])}
                    className="px-3 py-1.5 bg-rose-100 text-rose-700 rounded-lg hover:bg-rose-200 transition-colors text-xs font-medium"
                >
                    📂 展开子任务
                </button>
                <button
                    onClick={() => expandState.collapseAll()}
                    className="px-3 py-1.5 bg-amber-100 text-amber-700 rounded-lg hover:bg-amber-200 transition-colors text-xs font-medium"
                >
                    📁 全部折叠
                </button>
                <div className="ml-auto text-xs text-slate-400 self-center">
                    点击展开按钮查看详情 | 直接编辑预期日期 | 记录拖延原因
                </div>
            </div>

            {/* 详细任务列表 */}
            <div className="p-4 max-h-[600px] overflow-y-auto">
                <TodoItemTreeDetailed
                    items={tasks}
                    collapsible={true}
                    defaultExpandedIds={expandState.expandedIds}
                    selectedId={selectedId}
                    onUpdate={handleUpdate}
                    onDelete={handleDelete}
                    onSelect={setSelectedId}
                    showSource={true}
                    showDate={true}
                    onAddChild={handleAddChild}
                    getGoalName={getGoalName}
                    getPlanName={getPlanName}
                />
            </div>

            {/* 说明面板 */}
            <div className="px-4 py-3 bg-gradient-to-r from-slate-50 to-slate-100 border-t border-slate-200">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-emerald-500"></span>
                        <span className="text-slate-600">按时/提前完成</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-amber-500"></span>
                        <span className="text-slate-600">延迟完成</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-red-500"></span>
                        <span className="text-slate-600">已逾期</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-blue-500"></span>
                        <span className="text-slate-600">进行中</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

// =============================================================================
// 拖拽测试区域
// =============================================================================

const DragDropTestSection: React.FC = () => {
    const [tasks, setTasks] = useState<TodoItem[]>(initialDragTasks);
    const [dragLog, setDragLog] = useState<string[]>([]);

    // 分离任务池任务和已安排任务
    const poolTasks = tasks.filter(t => t.state === 'pool');
    const scheduledTasks = tasks.filter(t => t.state === 'scheduled');

    // 按日期分组已安排的任务
    const tasksByDate = scheduledTasks.reduce((acc, task) => {
        if (task.scheduledDate) {
            if (!acc[task.scheduledDate]) {
                acc[task.scheduledDate] = [];
            }
            acc[task.scheduledDate].push(task);
        }
        return acc;
    }, {} as Record<string, TodoItem[]>);

    // 添加日志
    const addLog = (message: string) => {
        const timestamp = new Date().toLocaleTimeString();
        setDragLog(prev => [`[${timestamp}] ${message}`, ...prev.slice(0, 9)]);
    };

    // 安排任务到某天
    const handleScheduleTask = useCallback((task: TodoItem, date: string) => {
        setTasks(prev => prev.map(t =>
            t.id === task.id
                ? { ...t, state: 'scheduled' as const, scheduledDate: date }
                : t
        ));
        addLog(`✅ 任务 "${task.content}" 安排到 ${date}`);
    }, []);

    // 取消安排（拖回任务池）
    const handleUnscheduleTask = useCallback((task: TodoItem) => {
        setTasks(prev => prev.map(t =>
            t.id === task.id
                ? { ...t, state: 'pool' as const, scheduledDate: null }
                : t
        ));
        addLog(`↩️ 任务 "${task.content}" 移回任务池`);
    }, []);

    // 处理跨区域拖拽
    const handleCrossAreaDrop = useCallback((
        dragItem: DragItemData<TodoItem>,
        dropArea: DropAreaData<{ date?: string }>
    ) => {
        const task = dragItem.payload;

        if (dropArea.type === 'date-cell' && dropArea.payload?.date) {
            handleScheduleTask(task, dropArea.payload.date);
        } else if (dropArea.type === 'pool-root') {
            handleUnscheduleTask(task);
        }
    }, [handleScheduleTask, handleUnscheduleTask]);

    // 重置数据
    const handleReset = () => {
        setTasks(initialDragTasks);
        setDragLog([]);
        addLog('🔄 数据已重置');
    };

    const weekDates = getWeekDates();

    return (
        <CrossAreaDndProvider
            onCrossAreaDrop={handleCrossAreaDrop}
            renderDragOverlay={(dragItem) => (
                <div className="bg-white shadow-2xl rounded-xl border-2 border-indigo-400 p-3 opacity-95 rotate-2 max-w-xs">
                    <span className="text-sm font-medium text-slate-700">
                        {(dragItem.payload as TodoItem).content}
                    </span>
                </div>
            )}
        >
            <div className="flex gap-6">
                {/* 左侧：任务池 */}
                <div className="w-72 flex-shrink-0">
                    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                        <div className="bg-gradient-to-r from-violet-500 to-purple-500 px-4 py-3">
                            <h2 className="text-lg font-bold text-white flex items-center gap-2">
                                📋 任务池
                                <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">
                                    {poolTasks.length} 项
                                </span>
                            </h2>
                            <p className="text-violet-100 text-xs mt-1">
                                拖拽任务到右侧日历安排
                            </p>
                        </div>

                        <DroppablePoolRoot className="p-3 space-y-2 min-h-[200px]">
                            {poolTasks.map(task => (
                                <DraggableItem
                                    key={task.id}
                                    id={task.id}
                                    type="task"
                                    source="task-pool"
                                    data={task}
                                    draggingClassName="opacity-50 scale-105 shadow-xl"
                                >
                                    <TodoItemComponent
                                        todo={task}
                                        onUpdate={() => { }}
                                        onDelete={() => { }}
                                        showDate={false}
                                    />
                                </DraggableItem>
                            ))}

                            {poolTasks.length === 0 && (
                                <div className="text-center text-slate-400 text-sm py-8 border-2 border-dashed border-slate-200 rounded-xl">
                                    <div className="text-2xl mb-2">🎉</div>
                                    任务池已清空
                                </div>
                            )}
                        </DroppablePoolRoot>

                        <div className="px-3 pb-3">
                            <button
                                onClick={handleReset}
                                className="w-full px-3 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors text-xs font-medium"
                            >
                                🔄 重置数据
                            </button>
                        </div>
                    </div>

                    {/* 操作日志 */}
                    <div className="mt-4 bg-slate-800 rounded-xl p-3 text-xs font-mono">
                        <h3 className="text-slate-400 mb-2 font-bold">📝 操作日志</h3>
                        <div className="space-y-1 max-h-32 overflow-y-auto">
                            {dragLog.length === 0 ? (
                                <div className="text-slate-500">等待操作...</div>
                            ) : (
                                dragLog.map((log, i) => (
                                    <div key={i} className="text-green-400">{log}</div>
                                ))
                            )}
                        </div>
                    </div>
                </div>

                {/* 右侧：日历 */}
                <div className="flex-1">
                    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                        <div className="bg-gradient-to-r from-blue-500 to-cyan-500 px-4 py-3">
                            <h2 className="text-lg font-bold text-white flex items-center gap-2">
                                📅 本周日历
                                <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">
                                    {scheduledTasks.length} 项已安排
                                </span>
                            </h2>
                        </div>

                        <div className="p-3">
                            <div className="grid grid-cols-7 gap-1.5">
                                {weekDates.map(date => {
                                    const isToday = new Date().toISOString().split('T')[0] === date;
                                    const dateTasks = tasksByDate[date] || [];

                                    return (
                                        <DroppableDateCell
                                            key={date}
                                            date={date}
                                            className={`rounded-lg border-2 transition-all min-h-[140px] ${isToday
                                                ? 'bg-blue-50 border-blue-300'
                                                : 'bg-slate-50 border-slate-200 hover:border-blue-300'
                                                }`}
                                        >
                                            {/* 日期标题 */}
                                            <div className={`text-xs font-bold p-1.5 border-b ${isToday
                                                ? 'text-blue-600 border-blue-200 bg-blue-100'
                                                : 'text-slate-500 border-slate-200'
                                                }`}>
                                                {formatDate(date)}
                                            </div>

                                            {/* 已安排的任务 */}
                                            <div className="p-1.5 space-y-1">
                                                {dateTasks.map(task => (
                                                    <DraggableItem
                                                        key={task.id}
                                                        id={task.id}
                                                        type="task"
                                                        source="calendar"
                                                        data={task}
                                                        draggingClassName="opacity-50"
                                                    >
                                                        <div className="text-xs bg-gradient-to-r from-violet-500 to-purple-500 text-white px-1.5 py-1 rounded truncate shadow-sm cursor-grab">
                                                            {task.content}
                                                        </div>
                                                    </DraggableItem>
                                                ))}

                                                {dateTasks.length === 0 && (
                                                    <div className="text-center text-slate-300 text-xs py-3">
                                                        拖拽到此
                                                    </div>
                                                )}
                                            </div>
                                        </DroppableDateCell>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </CrossAreaDndProvider>
    );
};

// =============================================================================
// 测试页面主组件
// =============================================================================

const DragDropTestPage: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'nested' | 'dailyfocus' | 'dragdrop'>('dailyfocus');

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-100 to-slate-200 p-6">
            {/* 页面标题 */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-800 mb-2">
                    🧪 组件测试实验室
                </h1>
                <p className="text-slate-500">
                    测试 <code className="bg-slate-200 px-1 rounded">dragDrop</code> 和{' '}
                    <code className="bg-slate-200 px-1 rounded">todoItem</code> 组件库
                </p>
            </div>

            {/* Tab 切换 */}
            <div className="mb-6 flex gap-2 flex-wrap">
                <button
                    onClick={() => setActiveTab('dailyfocus')}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === 'dailyfocus'
                        ? 'bg-gradient-to-r from-rose-500 to-pink-500 text-white shadow-md'
                        : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'
                        }`}
                >
                    🎯 每日聚焦（详细版）
                </button>
                <button
                    onClick={() => setActiveTab('nested')}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === 'nested'
                        ? 'bg-emerald-500 text-white shadow-md'
                        : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'
                        }`}
                >
                    🌳 多级任务树
                </button>
                <button
                    onClick={() => setActiveTab('dragdrop')}
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === 'dragdrop'
                        ? 'bg-violet-500 text-white shadow-md'
                        : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'
                        }`}
                >
                    🔄 跨区域拖拽
                </button>
            </div>

            {/* 测试内容区 */}
            {activeTab === 'dailyfocus' && <DailyFocusTestSection />}
            {activeTab === 'nested' && <NestedTodoTestSection />}
            {activeTab === 'dragdrop' && <DragDropTestSection />}

            {/* 使用说明 */}
            <div className="mt-6 bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
                <h3 className="font-bold mb-2">💡 测试说明</h3>
                {activeTab === 'dailyfocus' && (
                    <ul className="list-disc list-inside space-y-1">
                        <li>使用 <strong>TodoItemDetailed</strong> 组件，专门用于每日聚焦页面</li>
                        <li>直接展示<strong>开始时间</strong>、<strong>预期完成时间</strong>、<strong>拖延状态</strong></li>
                        <li>点击<strong>展开按钮</strong>可以查看和编辑<strong>拖延原因</strong></li>
                        <li>直接在任务上<strong>编辑预期日期</strong>，无需打开弹窗</li>
                        <li>不同状态有不同的<strong>颜色标签</strong>（逾期/今日截止/剩余天数等）</li>
                    </ul>
                )}
                {activeTab === 'nested' && (
                    <ul className="list-disc list-inside space-y-1">
                        <li>展示了 <strong>4 级嵌套</strong>的任务结构（项目 → 阶段 → 模块 → 具体任务）</li>
                        <li>点击 <strong>箭头图标</strong> 可以展开/折叠子任务</li>
                        <li>点击 <strong>复选框</strong> 可以标记任务完成</li>
                        <li>点击任务可以<strong>选中</strong>并高亮显示</li>
                        <li>支持<strong>全部展开</strong>和<strong>全部折叠</strong>快捷操作</li>
                    </ul>
                )}
                {activeTab === 'dragdrop' && (
                    <ul className="list-disc list-inside space-y-1">
                        <li>从左侧<strong>任务池</strong>拖拽任务到右侧<strong>日历</strong>的某个日期</li>
                        <li>从日历拖拽任务回到任务池可以<strong>取消安排</strong></li>
                        <li>日历中的任务也可以拖到其他日期进行<strong>重新安排</strong></li>
                    </ul>
                )}
            </div>
        </div>
    );
};

export default DragDropTestPage;

