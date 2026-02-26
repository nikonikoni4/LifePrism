/**
 * WAID 计时器 Hook
 *
 * 功能：
 * - 全局互斥：同一时间只能有一个 todo 在计时
 * - 停止时自动创建 CustomBlock
 * - 窗口关闭时自动停止计时并保存
 * - 每秒更新 elapsed
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { CustomBlockAPI } from '../../../apps/lifewatch/pages/timeline/components/customBlockApi';
import { UserCustomBlockCreate } from '../../../apps/lifewatch/pages/timeline/components/types';
import { TodoItem } from '../../../apps/goals/types/todo';
import { formatLocalDateTime } from '../utils/formatTime';
import { getApiV2UrlSync } from '../../../core/services/apiConfig';

export interface UseWaidTimerReturn {
    activeTimerId: string | null;
    timerStart: Date | null;
    elapsed: number; // 秒
    startTimer: (todo: TodoItem) => Promise<void>;
    stopTimer: () => Promise<void>;
    updateActiveTodoContent: (id: string, content: string) => void;
}

export function useWaidTimer(
    onDurationAdded?: (todoId: string, minutes: number) => void
): UseWaidTimerReturn {
    const [activeTimerId, setActiveTimerId] = useState<string | null>(null);
    const [timerStart, setTimerStart] = useState<Date | null>(null);
    const [elapsed, setElapsed] = useState(0);

    // 用 ref 保存当前计时的 todo 信息，避免闭包问题
    const activeTodoRef = useRef<TodoItem | null>(null);
    const timerStartRef = useRef<Date | null>(null);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const clearTimer = useCallback(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
    }, []);

    const stopTimer = useCallback(async () => {
        clearTimer();

        const todo = activeTodoRef.current;
        const start = timerStartRef.current;

        if (!todo || !start) {
            setActiveTimerId(null);
            setTimerStart(null);
            setElapsed(0);
            activeTodoRef.current = null;
            timerStartRef.current = null;
            return;
        }

        const endTime = new Date();
        const elapsedSeconds = (endTime.getTime() - start.getTime()) / 1000;
        const durationMinutes = Math.ceil(elapsedSeconds / 60);

        // 重置状态
        setActiveTimerId(null);
        setTimerStart(null);
        setElapsed(0);
        activeTodoRef.current = null;
        timerStartRef.current = null;

        // 实际经过 >= 60 秒才创建 CustomBlock
        if (elapsedSeconds >= 60) {
            const blockData: UserCustomBlockCreate = {
                content: todo.content,
                start_time: formatLocalDateTime(start),
                end_time: formatLocalDateTime(endTime),
                duration: durationMinutes,
                todo_id: todo.id,
                color: '#bfdbfe',
            };
            try {
                await CustomBlockAPI.create(blockData);
                onDurationAdded?.(todo.id, durationMinutes);
            } catch (e) {
                console.error('[useWaidTimer] Failed to create CustomBlock:', e);
            }
        }
    }, [clearTimer, onDurationAdded]);

    const startTimer = useCallback(async (todo: TodoItem) => {
        // 互斥：先停止当前计时
        if (activeTodoRef.current) {
            await stopTimer();
        }

        const now = new Date();
        activeTodoRef.current = todo;
        timerStartRef.current = now;
        setActiveTimerId(todo.id);
        setTimerStart(now);
        setElapsed(0);

        // 每秒更新 elapsed
        intervalRef.current = setInterval(() => {
            setElapsed((prev) => prev + 1);
        }, 1000);
    }, [stopTimer]);

    // 窗口关闭时自动停止计时并保存
    useEffect(() => {
        const handleBeforeUnload = () => {
            if (!activeTodoRef.current || !timerStartRef.current) return;

            const endTime = new Date();
            const durationMinutes = Math.ceil(
                (endTime.getTime() - timerStartRef.current.getTime()) / 60000
            );
            const elapsedSec = (endTime.getTime() - timerStartRef.current.getTime()) / 1000;

            if (elapsedSec >= 60) {
                // 使用 sendBeacon 确保窗口关闭时请求能发出
                const blockData: UserCustomBlockCreate = {
                    content: activeTodoRef.current.content,
                    start_time: formatLocalDateTime(timerStartRef.current),
                    end_time: formatLocalDateTime(endTime),
                    duration: durationMinutes,
                    todo_id: activeTodoRef.current.id,
                    color: '#bfdbfe',
                };
                const url = `${getApiV2UrlSync()}/timeline/custom-blocks`;
                const blob = new Blob([JSON.stringify(blockData)], { type: 'application/json' });
                navigator.sendBeacon(url, blob);
            }
        };

        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, []);

    // 计时中修改 todo content 时同步更新 ref，确保 stopTimer/beforeunload 使用最新内容
    const updateActiveTodoContent = useCallback((id: string, content: string) => {
        if (activeTodoRef.current && activeTodoRef.current.id === id) {
            activeTodoRef.current = { ...activeTodoRef.current, content };
        }
    }, []);

    // 组件卸载时清理 interval
    useEffect(() => {
        return () => clearTimer();
    }, [clearTimer]);

    return { activeTimerId, timerStart, elapsed, startTimer, stopTimer, updateActiveTodoContent };
}
