/**
 * TaskPoolView 组件类型定义
 */

export { TodoItem } from '../../shared/components/todoItem/types';

export interface TaskPoolViewProps {
    /** 禁用内部拖拽排序，用于跨区域拖拽场景 */
    disableInternalDnd?: boolean;
}
