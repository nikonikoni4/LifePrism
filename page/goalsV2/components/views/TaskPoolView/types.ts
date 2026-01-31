/**
 * TaskPoolView 组件类型定义
 */

export type { TodoItemType as TodoItem } from '@my-ui-kit/core';

export interface TaskPoolViewProps {
    /** 禁用内部拖拽排序，用于跨区域拖拽场景 */
    disableInternalDnd?: boolean;
}
