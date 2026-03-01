import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Flame } from 'lucide-react';

interface InsightItem {
    title: string;
    content: string;
}

const INSIGHT_ITEMS: InsightItem[] = [
    {
        title: '当你不想做时，执行“最小版本”。',
        content: '即使你内心极度抗拒，也承诺只做“迷你版”：说好跑3公里，那就只换鞋出门走一圈；说好写500字，那就只打开文档写一句。99%的情况下，一旦你开始了“最小版本”，你就会愿意多做一点。系统会记录你的“开始”，这本身就是胜利。',
    },
    {
        title: '成为“做那种事的人”。',
        content: '最终，不要把习惯看作一系列待办任务。每次打卡时，在心里对自己说：“我是一个运动者”、“我是一个阅读者”、“我是一个早睡者”。习惯系统不是在管理行为，而是在帮助你构建一个新的身份。行为只是这种身份的证据。',
    },
    {
        title: '用“习惯链条”串联你的早晨或晚间。',
        content: '不要同时攻击多个分散的时间。尝试在系统里创建一个“晨间链条”：起床 → 喝水 → 冥想5分钟 → 写下当日要事。让动作一个接一个自动触发，能大幅减少每个环节的决策消耗。',
    },
    {
        title: '设计你的环境，而非依赖毅力。',
        content: '想睡前阅读？就把书放在枕头上，而不是书架上。想多喝水？就让水杯永远满着。你的系统（打卡）是提醒，而优化物理环境，是让好习惯毫不费力、坏习惯难以发生的最强杠杆。',
    },
    {
        title: '允许暂停，但不要删除。',
        content: '生活总有波动。如果一连几天没完成，系统可能会将习惯“降级”并暂停。这没关系，这是系统在帮你保护这个习惯，防止你因内疚而彻底放弃。等你准备好，重新“激活”它，从当前等级继续即可，所有历史记录都还在。',
    },
    {
        title: '给你的习惯一个“为什么”。',
        content: '在创建习惯时，花一分钟关联你的“价值”或“承诺”。问自己：“我为什么想要这个习惯？”（例如：关联“健康”价值，或“成为更有活力的人”的承诺）。当你想偷懒时，这个深层的“理由”比意志力更管用。',
    },
    {
        title: '从“小到不可能失败”开始。',
        content: '目标不是“每天锻炼30分钟”，而是“换上运动鞋”；不是“读完一本书”，而是“翻开书读一页”。在系统里，哪怕只记录了最低限度的完成，也远胜于因目标过高而放弃。微小胜利能持续带来动力。',
    },
    {
        title: '找到你的“锚点”，而不是创造时间。',
        content: '不要总想着“等我有时间了就开始…”。看看你每天已经雷打不动在做的事（比如起床后第一杯咖啡、睡前刷手机），尝试把新习惯“绑”在这些固定动作之后。系统支持你用“事件锚点”来触发。',
    },
];

const AUTO_ROTATE_MS = 10000;

export const DailyTips: React.FC = () => {
    const [activeIndex, setActiveIndex] = useState(0);

    useEffect(() => {
        if (INSIGHT_ITEMS.length <= 1) return;
        const timer = window.setInterval(() => {
            setActiveIndex(prev => (prev + 1) % INSIGHT_ITEMS.length);
        }, AUTO_ROTATE_MS);
        return () => window.clearInterval(timer);
    }, []);

    const currentInsight = useMemo(
        () => INSIGHT_ITEMS[activeIndex] ?? INSIGHT_ITEMS[0],
        [activeIndex]
    );

    return (
        <div className="w-full lg:w-3/12 bg-[linear-gradient(160deg,#ECFDF5_0%,#F0FDF4_100%)] rounded-[24px] p-6 shadow-[0_10px_28px_rgba(15,23,42,0.08)] border-none flex flex-col relative overflow-hidden min-h-[160px]">
            <div className="relative z-10 flex flex-col h-full">
                <h2 className="text-[14px] font-semibold text-slate-700 uppercase tracking-[0.02em] mb-4 flex items-center justify-between">
                    <span className="inline-flex items-center gap-1.5">
                        <Flame size={14} className="text-emerald-500" /> Insight
                    </span>
                    <span className="text-[11px] font-semibold text-emerald-600/90">
                        {activeIndex + 1}/{INSIGHT_ITEMS.length}
                    </span>
                </h2>
                <div className="mb-3 min-h-[190px]">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={activeIndex}
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -12 }}
                            transition={{ duration: 0.35, ease: 'easeOut' }}
                        >
                            <p className="text-[18px] font-extrabold text-slate-900 leading-[1.4] mb-3">
                                {currentInsight.title}
                            </p>
                            <p className="text-[13px] font-medium text-slate-500 leading-[1.65]">
                                {currentInsight.content}
                            </p>
                        </motion.div>
                    </AnimatePresence>
                </div>
                <div className="flex items-center gap-1.5 mt-auto">
                    {INSIGHT_ITEMS.map((_, index) => (
                        <span
                            key={index}
                            className={`h-1.5 rounded-full transition-all duration-300 ${
                                index === activeIndex ? 'w-4 bg-emerald-500' : 'w-1.5 bg-emerald-300/70'
                            }`}
                        />
                    ))}
                </div>
            </div>
            {/* Decorative Element */}
            <div className="absolute right-[-10px] bottom-[-30px] text-emerald-500/10 font-serif text-[140px] leading-none pointer-events-none tracking-tighter select-none">
                "
            </div>
        </div>
    );
};
