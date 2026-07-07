/**
 * ModuleDock 类型定义
 */

export type ModuleId = 'lifewatch' | 'mindspace' | 'addons' | 'goals' | 'habits' | 'settings' | 'custom-records';

export interface ModuleConfig {
    id: ModuleId;
    name: string;
    icon: string;  // emoji 或图标名
    description: string;
    color: string; // 主题色
}

export interface ModuleDockProps {
    currentModule: ModuleId;
    onModuleChange: (moduleId: ModuleId) => void;
}

export interface DockItemProps {
    module: ModuleConfig;
    isActive: boolean;
    onClick: () => void;
    mouseX: number | null;
    index: number;
    totalItems: number;
}
