import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Anchor, Activity, Zap, Layers, Hash, Disc, MapPin, ChevronRight, Terminal, Cpu } from 'lucide-react';

// --- Theme & Data (Cyber-Swiss Style) ---

// 核心：颜色代表"稳定性等级"，而非分类。越稳定，越亮，越实。
const STABILITY_LEVELS = {
    0: { label: 'INIT_PHASE', color: '#10b981', glow: '0 0 5px rgba(16, 185, 129, 0.2)', opacity: 0.3, shape: 'dashed' }, // 萌芽：暗淡，虚线
    1: { label: 'ROOTING', color: '#34d399', glow: '0 0 8px rgba(52, 211, 153, 0.3)', opacity: 0.5, shape: 'solid' },
    2: { label: 'GROWING', color: '#4ade80', glow: '0 0 12px rgba(74, 222, 128, 0.4)', opacity: 0.7, shape: 'solid' },
    3: { label: 'STABLE', color: '#4ecdc4', glow: '0 0 15px rgba(78, 205, 196, 0.6)', opacity: 0.9, shape: 'complex' },
    4: { label: 'ANCHORED', color: '#2dd4bf', glow: '0 0 20px rgba(45, 212, 191, 0.9)', opacity: 1.0, shape: 'complex' }, // 根深蒂固：高亮青色
};

const HABIT_DATA = [
    { id: 1, time: '07:00', title: 'SYSTEM.WAKE', subTitle: '早起唤醒', type: 'BIO_CLOCK', level: 4, category: '生活', desc: '生物钟校准程序执行', streak: 42 },
    { id: 2, time: '07:30', title: 'HYDRATION', subTitle: '饮水 & 冥想', type: 'PRE_CONDITION', level: 3, category: '健康', desc: '前置事件触发：系统启动后', streak: 108 },
    { id: 3, time: '08:45', title: 'INPUT.READ', subTitle: '通勤阅读', type: 'SCENE_TRIGGER', level: 1, category: '学习', desc: '场景触发：移动载具环境', streak: 12 },
    { id: 4, time: '12:00', title: 'ENERGY.REFILL', subTitle: '能量午餐', type: 'TIME_LOCK', level: 4, category: '健康', desc: '固定时间触发：血糖水平维持', streak: 192 },
    { id: 5, time: '13:00', title: 'SYS.NAP', subTitle: '午休小憩', type: 'RECOVERY', level: 2, category: '恢复', desc: '低功耗模式：20min', streak: 5 },
    { id: 6, time: '19:30', title: 'DEEP.WORK', subTitle: '深层工作', type: 'FLOW_STATE', level: 0, category: '创造', desc: '理想锚点：期望达成的状态', streak: 0 },
    { id: 7, time: '22:30', title: 'DIGITAL.DETOX', subTitle: '数字断舍离', type: 'SHUTDOWN', level: 2, category: '睡眠', desc: '蓝光过滤器开启', streak: 15 },
];

const timeToMinutes = (timeStr) => {
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
};

const DAY_HEIGHT = 1800;

// --- Components ---

const NoiseTexture = () => (
    <div className="absolute inset-0 z-0 opacity-[0.07] pointer-events-none mix-blend-overlay">
        <svg className="h-full w-full">
            <filter id="noise">
                <feTurbulence type="fractalNoise" baseFrequency="0.7" numOctaves="3" stitchTiles="stitch" />
            </filter>
            <rect width="100%" height="100%" filter="url(#noise)" />
        </svg>
    </div>
);

const Scanline = () => (
    <div className="absolute inset-0 z-50 pointer-events-none bg-[linear-gradient(to_bottom,transparent_50%,rgba(0,0,0,0.5)_50%)] bg-[length:100%_4px] opacity-10" />
);

const TimeRuler = () => {
    const hours = Array.from({ length: 25 }, (_, i) => i);
    return (
        <div className="absolute top-0 bottom-0 left-0 w-full pointer-events-none z-0">
            {hours.map((h) => {
                const top = (h * 60 / 1440) * 100;
                return (
                    <div
                        key={h}
                        className="absolute w-full flex items-center group opacity-40"
                        style={{ top: `${top}%` }}
                    >
                        {/* Label */}
                        <div className="w-16 text-right pr-4 text-[10px] font-mono font-medium text-zinc-600">
                            {h.toString().padStart(2, '0')}00
                        </div>
                        {/* Tick */}
                        <div className="h-px w-2 bg-zinc-700" />
                        {/* Guide Line */}
                        <div className="h-px flex-1 bg-zinc-800/50 ml-2" />
                    </div>
                );
            })}
        </div>
    );
};

const CurrentTimeIndicator = ({ scrollRef }) => {
    const [minutes, setMinutes] = useState(0);

    useEffect(() => {
        const update = () => {
            const now = new Date();
            setMinutes(now.getHours() * 60 + now.getMinutes());
        };
        update();
        const timer = setInterval(update, 60000);
        return () => clearInterval(timer);
    }, []);

    useEffect(() => {
        if (scrollRef.current) {
            const top = (minutes / 1440) * DAY_HEIGHT;
            scrollRef.current.scrollTo({ top: top - 300, behavior: 'smooth' });
        }
    }, [scrollRef]);

    const top = (minutes / 1440) * 100;

    return (
        <div
            className="absolute left-0 w-full z-20 flex items-center pointer-events-none"
            style={{ top: `${top}%` }}
        >
            <div className="w-16 text-right pr-4">
                <span className="text-[9px] font-mono text-red-500 bg-red-900/20 border border-red-900/50 px-1 rounded animate-pulse">LIVE</span>
            </div>
            <div className="flex-1 h-px bg-red-500/50 relative">
                <div className="absolute left-0 -top-[3px] w-1.5 h-1.5 bg-red-500 shadow-[0_0_10px_#ef4444]" />
            </div>
        </div>
    );
};

const TimelineRail = () => (
    <div className="absolute left-[4.5rem] top-0 bottom-0 w-4 z-0 flex justify-center">
        {/* Core Rail */}
        <div className="w-[1px] h-full bg-zinc-800" />
        {/* Glowing Energy Line */}
        <div className="absolute w-[1px] h-full bg-gradient-to-b from-transparent via-emerald-500/20 to-transparent blur-[1px]" />
    </div>
);

const HabitAnchor = ({ data, onClick, isActive }) => {
    const levelStyle = STABILITY_LEVELS[data.level];
    const minutes = timeToMinutes(data.time);
    const topPercent = (minutes / 1440) * 100;

    return (
        <motion.div
            className="absolute left-0 w-full flex items-center group z-10"
            style={{ top: `${topPercent}%` }}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
        >
            {/* 1. Time Label */}
            <div
                className={`w-16 text-right pr-4 text-xs font-mono transition-all duration-300 ${isActive ? 'text-white' : 'text-zinc-600'}`}
                style={{ textShadow: isActive ? `0 0 10px ${levelStyle.color}` : 'none' }}
            >
                {data.time}
            </div>

            {/* 2. Mechanical Clamp (The Anchor) */}
            <div className="relative flex items-center justify-center w-6 -ml-[0.75rem]">
                <motion.div
                    onClick={() => onClick(data)}
                    className="relative z-20 cursor-pointer transition-all duration-300"
                    style={{
                        width: isActive ? 16 : 12,
                        height: isActive ? 16 : 12,
                        backgroundColor: '#050505',
                        border: `1px solid ${isActive ? levelStyle.color : '#3f3f46'}`,
                        boxShadow: isActive ? levelStyle.glow : 'none',
                        borderRadius: data.level === 0 ? '50%' : '1px'
                    }}
                >
                    {/* Internal Logic State Indicator */}
                    <div className={`w-full h-full opacity-50 ${isActive ? 'bg-current' : 'bg-transparent'}`} style={{ color: levelStyle.color }} />
                </motion.div>

                {/* Connector Arm */}
                <div
                    className={`h-[1px] transition-all duration-500 origin-left ${isActive ? 'w-16 bg-current' : 'w-8 bg-zinc-800'}`}
                    style={{ color: levelStyle.color }}
                />
            </div>

            {/* 3. The Habit Module */}
            <motion.div
                onClick={() => onClick(data)}
                layoutId={`card-${data.id}`}
                className={`
                relative pl-4 pr-6 py-2 cursor-pointer transition-all duration-300 ml-0 border-l-[1px]
                hover:bg-white/[0.02] overflow-hidden group/card
             `}
                style={{
                    borderColor: isActive ? levelStyle.color : '#27272a',
                    backgroundColor: isActive ? 'rgba(255,255,255,0.02)' : 'transparent',
                }}
            >
                {/* Decorative Corners */}
                {isActive && (
                    <>
                        <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-current" style={{ color: levelStyle.color }} />
                        <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-current" style={{ color: levelStyle.color }} />
                    </>
                )}

                <div className="flex flex-col gap-1">
                    <div className="flex items-baseline gap-2">
                        <h3 className={`text-sm font-bold tracking-wider font-mono uppercase ${isActive ? 'text-white' : 'text-zinc-500 group-hover/card:text-zinc-300'}`}>
                            {data.title}
                        </h3>
                        <span className="text-[10px] text-zinc-600 truncate hidden sm:inline-block">
                        // {data.subTitle}
                        </span>
                    </div>

                    <div className="flex items-center gap-3 text-[10px] text-zinc-600 font-mono">
                        <span className="flex items-center gap-1">
                            <Terminal size={10} />
                            {data.type}
                        </span>
                        <span style={{ color: isActive ? levelStyle.color : '#52525b' }}>
                            LV.{data.level}
                        </span>
                    </div>
                </div>
            </motion.div>
        </motion.div>
    );
};

const DetailOverlay = ({ data, onClose }) => {
    if (!data) return null;
    const levelStyle = STABILITY_LEVELS[data.level];

    return (
        <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 50 }}
            className="fixed top-24 right-8 w-80 bg-[#080808] border border-zinc-800 shadow-[0_0_50px_rgba(0,0,0,0.8)] z-50"
        >
            {/* Cyber Header */}
            <div className="h-1 w-full bg-zinc-800 relative overflow-hidden">
                <motion.div
                    initial={{ x: '-100%' }} animate={{ x: '100%' }} transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                    className="absolute inset-y-0 w-1/2 bg-gradient-to-r from-transparent via-emerald-500 to-transparent opacity-50"
                />
            </div>

            <div className="p-6">
                <div className="flex justify-between items-start mb-8">
                    <div className="space-y-1">
                        <span className="text-[9px] font-mono text-emerald-500/70 block border border-emerald-900/30 w-fit px-1 rounded">
                            ID_{data.id.toString().padStart(3, '0')} ACCESS
                        </span>
                        <h2 className="text-xl font-bold text-white tracking-widest font-mono uppercase">{data.title}</h2>
                        <div className="text-xs text-zinc-500 font-sans">{data.subTitle}</div>
                    </div>
                    <button onClick={onClose} className="hover:text-white text-zinc-600 transition-colors">
                        <span className="font-mono text-xs">[X]</span>
                    </button>
                </div>

                <div className="space-y-8 font-mono">
                    {/* Stability Matrix */}
                    <div className="p-4 bg-zinc-900/30 border border-white/5 relative">
                        <div className="absolute top-0 left-0 text-[8px] text-zinc-600 -mt-2 bg-[#080808] px-1">STABILITY_MATRIX</div>
                        <div className="flex gap-1 h-16 items-end">
                            {Array.from({ length: 12 }).map((_, i) => (
                                <div
                                    key={i}
                                    className="flex-1 bg-zinc-800/50"
                                    style={{
                                        height: `${Math.random() * 80 + 20}%`,
                                        backgroundColor: i > 8 ? '#27272a' : levelStyle.color,
                                        opacity: i > 8 ? 0.2 : 0.6
                                    }}
                                />
                            ))}
                        </div>
                    </div>

                    {/* Description Block */}
                    <div>
                        <div className="text-[10px] text-zinc-500 mb-2 uppercase flex items-center gap-2">
                            <Cpu size={12} />
                            Logic Protocol
                        </div>
                        <p className="text-xs text-zinc-400 leading-relaxed border-l border-zinc-800 pl-3 font-sans">
                            {data.desc}
                        </p>
                    </div>

                    {/* Stats */}
                    <div className="flex gap-4 pt-4 border-t border-white/5">
                        <div>
                            <div className="text-[9px] text-zinc-600 uppercase">Streak</div>
                            <div className="text-lg text-white font-bold">{data.streak}<span className="text-xs text-zinc-600 font-normal">D</span></div>
                        </div>
                        <div>
                            <div className="text-[9px] text-zinc-600 uppercase">Level</div>
                            <div className="text-lg font-bold" style={{ color: levelStyle.color }}>{data.level}</div>
                        </div>
                    </div>
                </div>
            </div>
        </motion.div>
    )
}

export default function App() {
    const [selectedHabit, setSelectedHabit] = useState(null);
    const scrollRef = useRef(null);

    return (
        <div className="h-screen bg-[#050505] text-zinc-300 font-sans overflow-hidden flex flex-col relative selection:bg-emerald-900 selection:text-white">
            <NoiseTexture />
            <Scanline />

            {/* Header */}
            <header className="h-16 border-b border-white/5 bg-[#050505]/90 backdrop-blur-sm flex items-center justify-between px-8 z-40 shrink-0">
                <div className="flex items-center gap-4">
                    <div className="w-8 h-8 border border-zinc-800 flex items-center justify-center bg-zinc-900/50">
                        <Disc className="text-emerald-500 animate-[spin_10s_linear_infinite]" size={16} />
                    </div>
                    <div>
                        <h1 className="font-bold text-sm tracking-[0.2em] text-white uppercase font-mono">
                            Chrono<span className="text-zinc-600">_</span>Sync
                        </h1>
                        <div className="text-[9px] text-zinc-600 font-mono tracking-widest">
                            V2.0.4 // STABLE
                        </div>
                    </div>
                </div>

                <div className="flex gap-6 font-mono text-xs">
                    <div className="text-right hidden sm:block">
                        <div className="text-[8px] text-zinc-600 uppercase">System Status</div>
                        <div className="text-emerald-500">ONLINE</div>
                    </div>
                    <div className="text-right">
                        <div className="text-[8px] text-zinc-600 uppercase">Anchors</div>
                        <div className="text-zinc-300">07 / 12</div>
                    </div>
                </div>
            </header>

            {/* Main Timeline Area */}
            <div className="flex-1 relative flex overflow-hidden">
                {/* Sidebar Decor */}
                <div className="w-12 border-r border-white/5 hidden md:flex flex-col items-center py-8 gap-8 z-30 bg-[#050505]">
                    <div className="h-24 w-px bg-gradient-to-b from-transparent via-zinc-700 to-transparent" />
                    <Hash size={12} className="text-zinc-800" />
                    <Layers size={12} className="text-zinc-800" />
                    <div className="h-24 w-px bg-gradient-to-b from-transparent via-zinc-700 to-transparent" />
                </div>

                {/* Scrollable Container */}
                <div
                    ref={scrollRef}
                    className="flex-1 relative overflow-y-auto custom-scrollbar"
                >
                    <div className="relative w-full max-w-2xl mx-auto mt-12 mb-32" style={{ height: `${DAY_HEIGHT}px` }}>
                        <TimeRuler />
                        <TimelineRail />
                        <CurrentTimeIndicator scrollRef={scrollRef} />

                        {HABIT_DATA.map((habit) => (
                            <HabitAnchor
                                key={habit.id}
                                data={habit}
                                isActive={selectedHabit?.id === habit.id}
                                onClick={setSelectedHabit}
                            />
                        ))}
                    </div>
                </div>
            </div>

            <AnimatePresence>
                {selectedHabit && (
                    <DetailOverlay data={selectedHabit} onClose={() => setSelectedHabit(null)} />
                )}
            </AnimatePresence>

            <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Inter:wght@300;400;600;800&display=swap');
        
        body {
            font-family: 'Inter', sans-serif;
        }
        .font-mono {
            font-family: 'JetBrains Mono', monospace;
        }

        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: #050505;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #27272a;
          border-radius: 0px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #3f3f46;
        }
      `}</style>
        </div>
    );
}