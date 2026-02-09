import React from 'react';

export const WhatAmIDoingFloat: React.FC = () => {
    return (
        <div className="h-screen flex flex-col bg-slate-900 text-white select-none overflow-hidden">
            {/* 拖拽区域 */}
            <div
                className="h-8 flex items-center px-3 bg-gradient-to-r from-emerald-600 to-teal-600 shrink-0"
                style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
            >
                <span className="text-xs font-medium text-white/90">What Am I Doing?</span>
            </div>

            {/* 内容区域 */}
            <div className="flex-1 flex flex-col items-center justify-center p-6">
                <div className="w-16 h-16 mb-4 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                    <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" className="w-8 h-8">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 6v6l4 2" />
                    </svg>
                </div>
                <h2 className="text-lg font-semibold mb-2">What Am I Doing?</h2>
                <p className="text-sm text-slate-400 text-center leading-relaxed">
                    浮窗框架搭建完成
                </p>
                <p className="text-xs text-slate-500 mt-4">
                    右键点击可关闭此浮窗
                </p>
            </div>
        </div>
    );
};
