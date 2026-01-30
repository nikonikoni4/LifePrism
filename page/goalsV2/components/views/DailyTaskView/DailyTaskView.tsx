import React from 'react';
import { CheckSquare } from 'lucide-react';
import { viewBackground } from '../../shared/background';

export const DailyTaskView: React.FC = () => {
  return (
    <div className={`flex-1 flex flex-col items-center justify-center p-8 text-center ${viewBackground.className}`} style={viewBackground.style}>
      <div className="w-20 h-20 bg-emerald-50 rounded-[24px] flex items-center justify-center mb-6 text-emerald-500 shadow-inner-light">
        <CheckSquare size={40} strokeWidth={1.5} />
      </div>
      <h3 className="font-heading text-2xl font-bold text-aurora-text-primary mb-2">每日任务</h3>
      <p className="font-body text-aurora-text-muted max-w-xs leading-relaxed">
        今日专注与执行。<br />记录完成情况与进度。
      </p>
      <div className="mt-8 px-4 py-2 bg-aurora-state-completed text-emerald-600 text-xs font-mono rounded-full border border-emerald-200">
        Module: Daily Tasks
      </div>
    </div>
  );
};