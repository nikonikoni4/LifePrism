
import { TodoItem } from '../../../types';

export const INITIAL_POOL_TASKS: TodoItem[] = [
    {
        id: 101,
        content: "Complete React Documentation",
        parentId: null,
        goalId: "1",
        planDocId: "p1",

        sourceAnchorId: "lp:react-docs",
        state: "pool",
        scheduledDate: null,
        expectedFinishAt: null,
        actualFinishAt: null,
        delayDays: null,
        delayReason: null,
        color: "#FFFFFF",
        orderIndex: 0,
        poolOrderIndex: 0,
        children: []
    },
    {
        id: 102,
        content: "Learn Hooks",
        parentId: "101",
        goalId: "1",
        planDocId: "p1",

        sourceAnchorId: "lp:hooks",
        state: "pool",
        scheduledDate: null,
        expectedFinishAt: null,
        actualFinishAt: null,
        delayDays: null,
        delayReason: null,
        color: "#FFFFFF",
        orderIndex: 0,
        poolOrderIndex: 1,
        children: []
    },
    {
        id: 103,
        content: "Master useEffect",
        parentId: "102",
        goalId: "1",
        planDocId: "p1",

        sourceAnchorId: "lp:use-effect",
        state: "pool",
        scheduledDate: null,
        expectedFinishAt: null,
        actualFinishAt: null,
        delayDays: null,
        delayReason: null,
        color: "#FFFFFF",
        orderIndex: 0,
        poolOrderIndex: 2,
        children: []
    },
    {
        id: 104,
        content: "Understand useContext",
        parentId: "102",
        goalId: "1",
        planDocId: "p1",

        sourceAnchorId: "lp:use-context",
        state: "pool",
        scheduledDate: null,
        expectedFinishAt: null,
        actualFinishAt: null,
        delayDays: null,
        delayReason: null,
        color: "#FFFFFF",
        orderIndex: 1,
        poolOrderIndex: 3,
        children: []
    },
    {
        id: 201,
        content: "Half Marathon Training: Week 1",
        parentId: null,
        goalId: "2",
        planDocId: "p3",

        sourceAnchorId: "lp:run-w1",
        state: "pool",
        scheduledDate: null,
        expectedFinishAt: null,
        actualFinishAt: null,
        delayDays: null,
        delayReason: null,
        color: "#FFFFFF",
        orderIndex: 1,
        poolOrderIndex: 4,
        children: []
    },
    {
        id: 202,
        content: "Easy Run 5k",
        parentId: "201",
        goalId: "2",
        planDocId: "p3",

        sourceAnchorId: "lp:run-5k-1",
        state: "scheduled", // Simulate one item already scheduled
        scheduledDate: "2024-02-10",
        expectedFinishAt: null,
        actualFinishAt: null,
        delayDays: null,
        delayReason: null,
        color: "#FFFFFF",
        orderIndex: 0,
        poolOrderIndex: 5,
        children: []
    },
    {
        id: 203,
        content: "Interval Training",
        parentId: "201",
        goalId: "2",
        planDocId: "p3",

        sourceAnchorId: "lp:run-interval",
        state: "pool",
        scheduledDate: null,
        expectedFinishAt: null,
        actualFinishAt: null,
        delayDays: null,
        delayReason: null,
        color: "#FFFFFF",
        orderIndex: 1,
        poolOrderIndex: 6,
        children: []
    },
    {
        id: 301,
        content: "Buy new running shoes",
        parentId: null,
        goalId: null,
        planDocId: null,

        sourceAnchorId: null,
        state: "pool",
        scheduledDate: null,
        expectedFinishAt: null,
        actualFinishAt: null,
        delayDays: null,
        delayReason: null,
        color: "#FFFFFF",
        orderIndex: 2,
        poolOrderIndex: 7,
        children: []
    }
];
