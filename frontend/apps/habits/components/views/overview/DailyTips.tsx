import React from 'react';
import { Flame } from 'lucide-react';

export const DailyTips: React.FC = () => {
    return (
        <div className="w-full lg:w-3/12 bg-[#F0FDF4] rounded-[24px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.08)] border-none flex flex-col relative overflow-hidden min-h-[160px]">
            <div className="relative z-10 flex flex-col h-full">
                <h2 className="text-[11px] font-bold text-emerald-600/70 uppercase tracking-widest mb-4 flex items-center gap-1.5">
                    <Flame size={14} className="text-emerald-500" /> Daily Insight
                </h2>
                <div className="mb-2">
                    <p className="text-[15px] font-bold text-emerald-950 leading-relaxed mb-3">
                        当你不想做时，<br />执行“最小版本”。
                    </p>
                    <p className="text-[12px] font-medium text-emerald-800/80 leading-[1.7]">
                        即使抗拒，也承诺只做“迷你版”：说好跑3公里，那就只换鞋出门走一圈。99%的情况，只要开始了，就会多做一点。系统记录你的开始，这本身就是胜利。
                    </p>
                </div>
            </div>
            {/* Decorative Element */}
            <div className="absolute right-[-10px] bottom-[-30px] text-emerald-500/10 font-serif text-[140px] leading-none pointer-events-none tracking-tighter select-none">
                "
            </div>
        </div>
    );
};
