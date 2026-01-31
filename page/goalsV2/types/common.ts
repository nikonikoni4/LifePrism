/**
 * 通用类型定义
 */

export type ViewMode = 'single' | 'dual';

export type ActiveTab = 'goals' | 'plans' | 'pool' | 'assign' | 'daily';

// 重导出 TodoItem 类型供外部使用
export type { TodoItemType as TodoItem } from '@my-ui-kit/core';
