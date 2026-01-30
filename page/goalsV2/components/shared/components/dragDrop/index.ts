/**
 * 跨区域拖拽组件库
 * 
 * 基于 @dnd-kit 封装的通用跨区域拖拽解决方案
 * 
 * @example
 * ```tsx
 * import {
 *   CrossAreaDndProvider,
 *   DraggableItem,
 *   DroppableArea,
 *   DroppableDateCell,
 *   useCrossAreaDnd,
 * } from '@/other_project/dragDrop';
 * 
 * // 方式一：使用 Provider 组件
 * <CrossAreaDndProvider
 *   onCrossAreaDrop={(dragItem, dropArea) => {
 *     console.log('跨区域拖拽', dragItem, dropArea);
 *   }}
 *   renderDragOverlay={(item) => <TaskPreview task={item.payload} />}
 * >
 *   <TaskPool />
 *   <Calendar />
 * </CrossAreaDndProvider>
 * 
 * // 方式二：使用 Hook 自定义
 * const { handleDragStart, handleDragEnd, activeItem } = useCrossAreaDnd({
 *   onCrossAreaDrop: (dragItem, dropArea) => {
 *     // 处理跨区域拖拽
 *   },
 * });
 * ```
 */

// =============================================================================
// Types
// =============================================================================
export type {
    // 基础类型
    DragSourceType,
    DropTargetType,
    // 数据结构
    DragItemData,
    DropAreaData,
    // 事件类型
    DragStartEventData,
    DragEndEventData,
    DragOverEventData,
    // 回调类型
    OnCrossAreaDrop,
    OnSameAreaReorder,
    OnDragStateChange,
    // Props 类型
    DraggableItemProps,
    DroppableAreaProps,
    CrossAreaDndContextProps,
    // 状态类型
    DragState,
} from './types';

// =============================================================================
// Context
// =============================================================================
export {
    CrossAreaDndProvider,
    useCrossAreaDndState,
} from './context/CrossAreaDndContext';

// =============================================================================
// Components
// =============================================================================
export {
    DraggableItem,
    DragHandle,
    useDraggableData,
} from './components/DraggableItem';

export {
    DroppableArea,
    DroppableDateCell,
    DroppableFolder,
    DroppablePoolRoot,
    DroppableTrash,
    useDroppableArea,
} from './components/DroppableArea';

// =============================================================================
// Hooks
// =============================================================================
export { useCrossAreaDnd } from './hooks/useCrossAreaDnd';
