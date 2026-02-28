// @ts-nocheck
import { TimelineEvent } from '../types/views';

export const mockHabits: Habit[] = [
    {
        id: 'h1', name: '晨间冥想', frequency: '每天', streak: 23,
        level: { value: 2, name: '枝繁' }, progress: { current: 12, total: 18 },
        tags: { anchor: '07:05 晨间流程', value: '内心平和' },
        status: 'active', todayStatus: 'done'
    },
    {
        id: 'h2', name: '阅读专业书籍', frequency: '工作日', streak: 5,
        level: { value: 1, name: '生根' }, progress: { current: 3, total: 15 },
        tags: { value: '持续成长', commitment: '每日精进' },
        status: 'active', todayStatus: 'pending'
    },
    {
        id: 'h3', name: '核心力量训练', frequency: '周一、三、五', streak: 0,
        level: { value: 0, name: '萌芽' }, progress: { current: 1, total: 5 },
        tags: { anchor: '下班后' },
        status: 'active', todayStatus: 'pending'
    },
    {
        id: 'h4', name: '睡前断网', frequency: '每天', streak: 12,
        level: { value: 3, name: '稳固' }, progress: { current: 20, total: 21 },
        tags: { anchor: '22:30 晚间流程' },
        status: 'active', todayStatus: 'done'
    },
    {
        id: 'h5', name: '学习西班牙语', frequency: '周末', streak: 0,
        level: { value: 0, name: '萌芽' }, progress: { current: 0, total: 4 },
        tags: {},
        status: 'paused', todayStatus: 'pending'
    }
];

export const mockChains: ChainData[] = [
    {
        id: 'c1',
        name: '晨间流程',
        nodes: [
            { id: 'n1', name: '起床喝水', isHabit: false },
            { id: 'n2', name: '晨间冥想', isHabit: true },
            { id: 'n3', name: '吃早饭', isHabit: false },
            { id: 'n8', name: '换衣服', isHabit: false },
            { id: 'n9', name: '出门', isHabit: false }
        ]
    },
    {
        id: 'c2',
        name: '晚间流程',
        nodes: [
            { id: 'n4', name: '洗漱', isHabit: false },
            { id: 'n5', name: '睡前断网', isHabit: true }
        ]
    }
];

export const timelineEvents: TimelineEvent[] = [
    { id: '1', title: '睡眠', startTime: '00:00', endTime: '07:00', isHabit: false },
    { id: '2', title: '起床喝水', startTime: '07:00', endTime: '07:10', isHabit: false },
    { id: '3', title: '晨间冥想', startTime: '07:15', endTime: '07:45', isHabit: true },
    { id: '4', title: '吃早饭', startTime: '07:45', endTime: '08:15', isHabit: false },
    { id: '5', title: '出门通勤', startTime: '08:30', endTime: '09:00', isHabit: false },
    { id: '6', title: '核心力量训练', startTime: '18:30', endTime: '19:15', isHabit: true },
    { id: '7', title: '写需求文档', startTime: '20:00', endTime: '21:30', isHabit: true },
    { id: '8', title: '晚间洗漱', startTime: '22:00', endTime: '22:30', isHabit: false },
    { id: '9', title: '睡前断网', startTime: '22:30', endTime: '23:00', isHabit: true },
];
