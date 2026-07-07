/**
 * DockItem - 单个 Dock 图标项
 * 实现类似 macOS Dock 的放大效果
 */

import React, { useRef, useState, useEffect } from 'react';
import { motion, useSpring } from 'framer-motion';
import { DockItemProps } from './types';

import { Target, Zap, Settings as SettingsIcon, Database } from 'lucide-react';

// 图标映射
const iconMap: Record<string, React.ReactNode> = {
    lifewatch: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-full h-full">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 6v6l4 2" />
            <path d="M12 2v2" />
            <path d="M12 20v2" />
            <path d="M2 12h2" />
            <path d="M20 12h2" />
        </svg>
    ),
    mindspace: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-full h-full">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" />
            <path d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4z" />
            <path d="M12 6v2" />
            <path d="M12 16v2" />
            <path d="M6 12h2" />
            <path d="M16 12h2" />
        </svg>
    ),
    addons: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-full h-full">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <path d="M17.5 14v7" />
            <path d="M14 17.5h7" />
        </svg>
    ),
    goals: <Target strokeWidth={1.5} className="w-full h-full" />,
    habits: <Zap strokeWidth={1.5} className="w-full h-full" />,
    settings: <SettingsIcon strokeWidth={1.5} className="w-full h-full" />,
    'custom-records': <Database strokeWidth={1.5} className="w-full h-full" />,
};

export const DockItem: React.FC<DockItemProps> = ({
    module,
    isActive,
    onClick,
    mouseX,
}) => {
    const ref = useRef<HTMLButtonElement>(null);
    const [targetScale, setTargetScale] = useState(1);
    const [targetY, setTargetY] = useState(0);

    // 计算距离并更新缩放
    useEffect(() => {
        if (mouseX === null || !ref.current) {
            setTargetScale(1);
            setTargetY(0);
            return;
        }

        const rect = ref.current.getBoundingClientRect();
        const itemCenterX = rect.left + rect.width / 2;
        const distance = Math.abs(mouseX - itemCenterX);

        // 根据距离计算缩放和位移
        if (distance < 50) {
            setTargetScale(1.35);
            setTargetY(-10);
        } else if (distance < 100) {
            setTargetScale(1.15);
            setTargetY(-4);
        } else {
            setTargetScale(1);
            setTargetY(0);
        }
    }, [mouseX]);

    // 使用弹簧动画
    const scaleSpring = useSpring(targetScale, { stiffness: 400, damping: 25 });
    const ySpring = useSpring(targetY, { stiffness: 400, damping: 25 });

    return (
        <motion.button
            ref={ref}
            onClick={onClick}
            className="relative flex flex-col items-center group outline-none"
            style={{
                scale: scaleSpring,
                y: ySpring,
            }}
            whileTap={{ scale: 0.95 }}
        >
            {/* 图标容器 */}
            <div
                className={`
                    w-12 h-12 rounded-2xl flex items-center justify-center
                    transition-all duration-200 ease-out
                    ${isActive
                        ? 'bg-white shadow-lg shadow-slate-200/50'
                        : 'bg-white/60 hover:bg-white/80'
                    }
                `}
                style={{
                    color: isActive ? module.color : '#64748b',
                }}
            >
                <div className="w-6 h-6">
                    {iconMap[module.id]}
                </div>
            </div>

            {/* 选中指示器 */}
            <motion.div
                className="absolute -bottom-2 w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: module.color }}
                initial={false}
                animate={{
                    scale: isActive ? 1 : 0,
                    opacity: isActive ? 1 : 0,
                }}
                transition={{ duration: 0.15 }}
            />

            {/* Tooltip */}
            <div className="
                absolute -bottom-10 left-1/2 -translate-x-1/2
                px-2.5 py-1 rounded-lg
                bg-slate-800 text-white text-xs font-medium
                opacity-0 group-hover:opacity-100
                transition-opacity duration-200
                whitespace-nowrap pointer-events-none
                shadow-lg
            ">
                {module.name}
                {/* 小三角 */}
                <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-800 rotate-45" />
            </div>
        </motion.button>
    );
};
