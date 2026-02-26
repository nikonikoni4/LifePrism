/**
 * ModuleDock - 顶部悬浮模块切换 Dock
 * 
 * 特性：
 * - 默认隐藏，鼠标靠近顶部时弹出
 * - 类似 macOS Dock 的放大动效
 * - 支持 LifeWatch / MindSpace / Add-ons 三个模块切换
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence, useMotionValue } from 'framer-motion';
import { DockItem } from './DockItem';
import { ModuleDockProps, ModuleConfig, ModuleId } from './types';

// 模块配置
const MODULES: ModuleConfig[] = [
    {
        id: 'lifewatch',
        name: 'LifeWatch',
        icon: 'target',
        description: '效率与目标管理',
        color: '#6366F1', // indigo
    },
    {
        id: 'goals',
        name: 'Goals',
        icon: 'target',
        description: '目标管理',
        color: '#F59E0B', // amber
    },
    {
        id: 'habits',
        name: 'Habits',
        icon: 'zap',
        description: '习惯养成',
        color: '#10B981', // emerald
    },
    {
        id: 'settings',
        name: 'Settings',
        icon: 'settings',
        description: '系统设置',
        color: '#64748B', // slate
    },
    {
        id: 'mindspace',
        name: 'MindSpace',
        icon: 'brain',
        description: '心理与情绪空间',
        color: '#EC4899', // pink
    },
    {
        id: 'addons',
        name: 'Add-ons',
        icon: 'puzzle',
        description: '扩展插件',
        color: '#10B981', // emerald
    },
];

// 触发区域高度
const TRIGGER_ZONE_HEIGHT = 20;
// 隐藏延迟时间
const HIDE_DELAY = 50;

export const ModuleDock: React.FC<ModuleDockProps> = ({
    currentModule,
    onModuleChange,
}) => {
    const [isVisible, setIsVisible] = useState(false);
    const [isHovering, setIsHovering] = useState(false);
    const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const dockRef = useRef<HTMLDivElement>(null);

    // 鼠标 X 位置（用于计算放大效果）
    const mouseX = useMotionValue<number | null>(null);

    // 清除隐藏定时器
    const clearHideTimeout = useCallback(() => {
        if (hideTimeoutRef.current) {
            clearTimeout(hideTimeoutRef.current);
            hideTimeoutRef.current = null;
        }
    }, []);

    // 显示 Dock
    const showDock = useCallback(() => {
        clearHideTimeout();
        setIsVisible(true);
    }, [clearHideTimeout]);

    // 隐藏 Dock（带延迟）
    const hideDock = useCallback(() => {
        clearHideTimeout();
        hideTimeoutRef.current = setTimeout(() => {
            setIsVisible(false);
            mouseX.set(null);
        }, HIDE_DELAY);
    }, [clearHideTimeout, mouseX]);

    // 监听鼠标位置（触发区域检测）
    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            // 如果鼠标在顶部触发区域内，显示 Dock
            if (e.clientY <= TRIGGER_ZONE_HEIGHT) {
                showDock();
                return;
            }

            // 如果 Dock 可见，检测鼠标是否在 Dock 区域外
            if (isVisible && dockRef.current) {
                const rect = dockRef.current.getBoundingClientRect();
                // 增加一些边距，避免过于敏感
                const padding = 20;
                const isOutside =
                    e.clientX < rect.left - padding ||
                    e.clientX > rect.right + padding ||
                    e.clientY < rect.top - padding ||
                    e.clientY > rect.bottom + padding;

                if (isOutside) {
                    hideDock();
                }
            }
        };

        window.addEventListener('mousemove', handleMouseMove);
        return () => window.removeEventListener('mousemove', handleMouseMove);
    }, [showDock, hideDock, isVisible]);

    // 清理定时器
    useEffect(() => {
        return () => clearHideTimeout();
    }, [clearHideTimeout]);

    // Dock 区域鼠标事件
    const handleDockMouseEnter = () => {
        setIsHovering(true);
        showDock();
    };

    const handleDockMouseLeave = () => {
        setIsHovering(false);
        hideDock();
    };

    const handleDockMouseMove = (e: React.MouseEvent) => {
        mouseX.set(e.clientX);
    };

    // 模块点击
    const handleModuleClick = (moduleId: ModuleId) => {
        onModuleChange(moduleId);
    };

    return (
        <>
            {/* 顶部触发区域（始终存在，不可见） */}
            <div
                className="fixed top-0 left-0 right-0 z-[9999]"
                style={{ height: TRIGGER_ZONE_HEIGHT }}
                onMouseEnter={showDock}
            />

            {/* Dock 主体 */}
            <AnimatePresence>
                {isVisible && (
                    <motion.div
                        ref={dockRef}
                        className="fixed top-4 left-1/2 -translate-x-1/2 z-[9998]"
                        initial={{ opacity: 0, y: -20, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -20, scale: 0.95 }}
                        transition={{
                            type: 'spring',
                            stiffness: 400,
                            damping: 30,
                        }}
                        onMouseEnter={handleDockMouseEnter}
                        onMouseLeave={handleDockMouseLeave}
                        onMouseMove={handleDockMouseMove}
                    >
                        {/* 背景容器 */}
                        <div className="
                            px-4 py-3 
                            bg-white/70 backdrop-blur-xl 
                            border border-white/50 
                            rounded-[20px] 
                            shadow-[0_8px_32px_rgba(0,0,0,0.12),0_0_0_1px_rgba(255,255,255,0.5)_inset]
                        ">
                            {/* 图标容器 */}
                            <div className="flex items-end gap-2">
                                {MODULES.map((module, index) => (
                                    <DockItem
                                        key={module.id}
                                        module={module}
                                        isActive={currentModule === module.id}
                                        onClick={() => handleModuleClick(module.id)}
                                        mouseX={mouseX.get()}
                                        index={index}
                                        totalItems={MODULES.length}
                                    />
                                ))}
                            </div>
                        </div>

                        {/* 当前模块名称标签 */}
                        <motion.div
                            className="absolute -bottom-8 left-1/2 -translate-x-1/2"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: isHovering ? 0 : 1 }}
                            transition={{ duration: 0.2 }}
                        >
                            <span className="
                                px-3 py-1 
                                bg-slate-800/80 backdrop-blur-sm
                                text-white text-xs font-medium 
                                rounded-full
                                shadow-lg
                            ">
                                {MODULES.find(m => m.id === currentModule)?.name}
                            </span>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
};
