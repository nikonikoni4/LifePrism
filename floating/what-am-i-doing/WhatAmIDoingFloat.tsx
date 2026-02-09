import React, { useState } from 'react';

export const WhatAmIDoingFloat: React.FC = () => {
    const [showAddMenu, setShowAddMenu] = useState(false);

    // 点击 [+] 按钮
    const handleAddClick = () => {
        setShowAddMenu(true);
    };

    // 点击"新建任务"
    const handleCreateNew = () => {
        setShowAddMenu(false);
        // TODO: 后续实现新建任务的逻辑
        console.log('新建任务');
    };

    // 点击"选择现有"
    const handleSelectExisting = async () => {
        setShowAddMenu(false);
        // 打开 Todo 选择对话框
        if (window.electronAPI?.openDialogWindow) {
            await window.electronAPI.openDialogWindow('todo-picker');
        } else {
            console.log('打开 Todo 选择对话框（开发模式）');
        }
    };

    // 点击遮罩关闭菜单
    const handleOverlayClick = () => {
        setShowAddMenu(false);
    };

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
            <div className="flex-1 flex flex-col p-3 gap-2 overflow-y-auto">
                {/* 任务列表占位 */}
                <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-10 h-10 mb-2 opacity-50">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 6v6l4 2" />
                    </svg>
                    <p className="text-xs">暂无进行中的任务</p>
                </div>
            </div>

            {/* [+] 添加按钮 */}
            <div className="shrink-0 p-3 border-t border-slate-700/50">
                <button
                    onClick={handleAddClick}
                    className="w-full h-10 flex items-center justify-center gap-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-600/50 hover:border-emerald-500/50 transition-all duration-200 group"
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5 text-emerald-400 group-hover:text-emerald-300">
                        <path d="M12 5v14M5 12h14" />
                    </svg>
                    <span className="text-sm text-slate-300 group-hover:text-white">添加任务</span>
                </button>
            </div>

            {/* 小对话框遮罩层 */}
            {showAddMenu && (
                <div
                    className="absolute inset-0 bg-black/60 flex items-center justify-center z-50"
                    onClick={handleOverlayClick}
                >
                    {/* 小对话框 */}
                    <div
                        className="bg-slate-800 rounded-xl border border-slate-600/50 shadow-2xl p-4 mx-4 w-full max-w-xs"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <p className="text-sm text-center text-slate-300 mb-4">选择添加方式</p>
                        <div className="flex gap-3">
                            <button
                                onClick={handleCreateNew}
                                className="flex-1 py-2.5 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors"
                            >
                                新建任务
                            </button>
                            <button
                                onClick={handleSelectExisting}
                                className="flex-1 py-2.5 px-4 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium transition-colors"
                            >
                                选择现有
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
