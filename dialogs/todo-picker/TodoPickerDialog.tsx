import React from 'react';

export const TodoPickerDialog: React.FC = () => {
    // 关闭对话框
    const handleClose = async () => {
        if (window.electronAPI?.closeDialogWindow) {
            await window.electronAPI.closeDialogWindow('todo-picker');
        }
    };

    // 确认选择（暂时只是关闭）
    const handleConfirm = async () => {
        // TODO: 后续实现选择逻辑，将选中的 todo 返回给浮窗
        console.log('确认选择 Todo');
        await handleClose();
    };

    return (
        <div className="h-screen flex flex-col bg-slate-900 text-white select-none overflow-hidden">
            {/* 拖拽区域 / 标题栏 */}
            <div
                className="h-10 flex items-center justify-between px-4 bg-gradient-to-r from-emerald-600 to-teal-600 shrink-0"
                style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
            >
                <span className="text-sm font-medium text-white/90">选择任务</span>
                <button
                    onClick={handleClose}
                    className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-white/20 transition-colors"
                    style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                        <path d="M18 6L6 18M6 6l12 12" />
                    </svg>
                </button>
            </div>

            {/* 搜索框 */}
            <div className="shrink-0 p-4 border-b border-slate-700/50">
                <div className="relative">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                        <circle cx="11" cy="11" r="8" />
                        <path d="M21 21l-4.35-4.35" />
                    </svg>
                    <input
                        type="text"
                        placeholder="搜索任务..."
                        className="w-full h-10 pl-10 pr-4 rounded-lg bg-slate-800 border border-slate-600/50 focus:border-emerald-500/50 focus:outline-none text-sm text-white placeholder-slate-500"
                    />
                </div>
            </div>

            {/* 任务列表 */}
            <div className="flex-1 overflow-y-auto p-4">
                {/* 分组示例：工作 */}
                <div className="mb-4">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">📁 工作</span>
                    </div>
                    <div className="space-y-2">
                        <TodoItem title="完成项目文档" />
                        <TodoItem title="代码审查" />
                        <TodoItem title="准备周报" />
                    </div>
                </div>

                {/* 分组示例：学习 */}
                <div className="mb-4">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">📁 学习</span>
                    </div>
                    <div className="space-y-2">
                        <TodoItem title="看 React 教程" />
                        <TodoItem title="练习 TypeScript" />
                    </div>
                </div>

                {/* 分组示例：生活 */}
                <div className="mb-4">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">📁 生活</span>
                    </div>
                    <div className="space-y-2">
                        <TodoItem title="健身" />
                        <TodoItem title="阅读" />
                    </div>
                </div>
            </div>

            {/* 底部按钮区 */}
            <div className="shrink-0 p-4 border-t border-slate-700/50 flex gap-3">
                <button
                    onClick={handleClose}
                    className="flex-1 py-2.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium transition-colors"
                >
                    取消
                </button>
                <button
                    onClick={handleConfirm}
                    className="flex-1 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors"
                >
                    确认添加
                </button>
            </div>
        </div>
    );
};

// 单个 Todo 项组件
const TodoItem: React.FC<{ title: string }> = ({ title }) => {
    const [isSelected, setIsSelected] = React.useState(false);

    return (
        <button
            onClick={() => setIsSelected(!isSelected)}
            className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-all ${isSelected
                ? 'bg-emerald-600/20 border-emerald-500/50'
                : 'bg-slate-800/50 border-slate-700/50 hover:bg-slate-800 hover:border-slate-600'
                }`}
        >
            {/* 复选框 */}
            <div className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${isSelected
                ? 'bg-emerald-500 border-emerald-500'
                : 'border-slate-500'
                }`}>
                {isSelected && (
                    <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" className="w-3 h-3">
                        <path d="M20 6L9 17l-5-5" />
                    </svg>
                )}
            </div>
            {/* 标题 */}
            <span className={`text-sm text-left ${isSelected ? 'text-white' : 'text-slate-300'}`}>
                {title}
            </span>
        </button>
    );
};
