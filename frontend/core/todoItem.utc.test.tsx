/**
 * TodoItem / TodoItemDetailed UTC 时区迁移测试
 *
 * Seam: toggleComplete 行为 — 当用户点击 checkbox 完成 Todo 时，
 *       onUpdate 回调应收到基于本地日期的 actualFinishAt（YYYY-MM-DD），
 *       而非 UTC 日期（toISOString().split('T')[0] 在 UTC+ 午夜会少一天）。
 *
 * 背景：Issue #15 — 前端 UI Kit 和 Core Services 迁移
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, cleanup } from '@testing-library/react';
import type { BaseTodoItem } from '../my-ui-kit/ui-kit/todoItem/types';

// Mock @dnd-kit/sortable 以避免 DndContext 依赖
vi.mock('@dnd-kit/sortable', () => ({
    useSortable: () => ({
        attributes: {},
        listeners: {},
        setNodeRef: () => {},
        transform: null,
        transition: null,
        isDragging: false,
    }),
}));

// Mock @dnd-kit/utilities
vi.mock('@dnd-kit/utilities', () => ({
    CSS: {
        Transform: {
            toString: () => '',
        },
    },
}));

import { TodoItem } from '../my-ui-kit/ui-kit/todoItem/TodoItem';
import { TodoItemDetailed } from '../my-ui-kit/ui-kit/todoItem/TodoItemDetailed';

// ============================================================================
// 测试数据
// ============================================================================

const incompleteItem: BaseTodoItem = {
    id: 'test-1',
    content: '测试任务',
    state: 'pool',
};

// ============================================================================
// TodoItem 测试
// ============================================================================

describe('TodoItem - UTC 时区迁移', () => {
    const originalTZ = process.env.TZ;

    beforeEach(() => {
        // 模拟 UTC+8（Asia/Shanghai）
        process.env.TZ = 'Asia/Shanghai';
        // 固定系统时间为本地 2026-03-03 00:00:00（UTC+8 午夜）
        // 此时 UTC 为 2026-03-02T16:00:00Z — UTC 日期是前一天
        vi.useFakeTimers();
        vi.setSystemTime(new Date(2026, 2, 3, 0, 0, 0));
    });

    afterEach(() => {
        vi.useRealTimers();
        if (originalTZ === undefined) {
            delete process.env.TZ;
        } else {
            process.env.TZ = originalTZ;
        }
        cleanup();
    });

    it('完成 Todo 时 actualFinishAt 应使用本地日期（非 UTC 日期）', () => {
        // 本地 2026-03-03 00:00 (UTC+8) = UTC 2026-03-02T16:00:00Z
        // toISOString().split('T')[0] 会返回 '2026-03-02'（错误 — UTC 日期）
        // toLocalDateString(new Date()) 会返回 '2026-03-03'（正确 — 本地日期）
        const onUpdate = vi.fn();
        const { container } = render(
            <TodoItem item={incompleteItem} onUpdate={onUpdate} />
        );

        // checkbox 是组件中第一个 button 元素
        const checkbox = container.querySelector('button');
        expect(checkbox).not.toBeNull();

        fireEvent.click(checkbox!);

        expect(onUpdate).toHaveBeenCalledTimes(1);
        expect(onUpdate).toHaveBeenCalledWith(
            'test-1',
            expect.objectContaining({
                state: 'completed',
                actualFinishAt: '2026-03-03',
            })
        );
    });

    it('UTC+8 午夜前一刻完成 Todo 日期仍为当天', () => {
        // 本地 2026-03-03 23:59:59 (UTC+8) = UTC 2026-03-03 15:59:59Z
        // 此时 UTC 日期和本地日期相同，但仍然应该使用 toLocalDateString
        vi.setSystemTime(new Date(2026, 2, 3, 23, 59, 59));

        const onUpdate = vi.fn();
        const { container } = render(
            <TodoItem item={incompleteItem} onUpdate={onUpdate} />
        );

        const checkbox = container.querySelector('button');
        fireEvent.click(checkbox!);

        expect(onUpdate).toHaveBeenCalledWith(
            'test-1',
            expect.objectContaining({
                state: 'completed',
                actualFinishAt: '2026-03-03',
            })
        );
    });
});

// ============================================================================
// TodoItemDetailed 测试
// ============================================================================

describe('TodoItemDetailed - UTC 时区迁移', () => {
    const originalTZ = process.env.TZ;

    beforeEach(() => {
        process.env.TZ = 'Asia/Shanghai';
        vi.useFakeTimers();
        vi.setSystemTime(new Date(2026, 2, 3, 0, 0, 0));
    });

    afterEach(() => {
        vi.useRealTimers();
        if (originalTZ === undefined) {
            delete process.env.TZ;
        } else {
            process.env.TZ = originalTZ;
        }
        cleanup();
    });

    it('完成 Todo 时 actualFinishAt 应使用本地日期（非 UTC 日期）', () => {
        const onUpdate = vi.fn();
        const { container } = render(
            <TodoItemDetailed item={incompleteItem} onUpdate={onUpdate} />
        );

        const checkbox = container.querySelector('button');
        expect(checkbox).not.toBeNull();

        fireEvent.click(checkbox!);

        expect(onUpdate).toHaveBeenCalledTimes(1);
        expect(onUpdate).toHaveBeenCalledWith(
            'test-1',
            expect.objectContaining({
                state: 'completed',
                actualFinishAt: '2026-03-03',
            })
        );
    });
});
