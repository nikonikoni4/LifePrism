import React from 'react';
import { Flame } from 'lucide-react';

export const DailyTips: React.FC = () => {
    return (
        <div className="w-full lg:w-3/12 bg-[linear-gradient(160deg,#ECFDF5_0%,#F0FDF4_100%)] rounded-[24px] p-6 shadow-[0_10px_28px_rgba(15,23,42,0.08)] border-none flex flex-col relative overflow-hidden min-h-[160px]">
            <div className="relative z-10 flex flex-col h-full">
                <h2 className="text-[14px] font-semibold text-slate-700 uppercase tracking-[0.02em] mb-4 flex items-center gap-1.5">
                    <Flame size={14} className="text-emerald-500" /> Daily Insight
                </h2>
                <div className="mb-2">
                    <p className="text-[18px] font-extrabold text-slate-900 leading-[1.4] mb-3">
                        当你不想做时，<br />执行“最小版本”。
                    </p>
                    <p className="text-[13px] font-medium text-slate-500 leading-[1.65]">
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
