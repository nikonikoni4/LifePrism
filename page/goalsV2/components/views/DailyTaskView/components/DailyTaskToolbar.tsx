import React from 'react';
import { RotateCcw, ChevronDown, ChevronRight } from 'lucide-react';

interface DailyTaskToolbarProps {
    isAllExpanded: boolean;
    onToggleExpandAll: () => void;
    onReset: () => void;
}

/**
 * 每日任务操作工具栏
 * 包含重置、展开/折叠按钮
 */
export const DailyTaskToolbar: React.FC<DailyTaskToolbarProps> = ({
    isAllExpanded,
    onToggleExpandAll,
    onReset
}) => {
    return (
        <div className="bg-white shadow-sm rounded-xl mx-6 mt-4 p-3 flex items-center justify-between">
            {/* 左侧：重置按钮 */}
            <button
                onClick={onReset}
                className="text-blue-500 hover:bg-blue-50 rounded-lg px-3 py-1.5 text-sm font-medium flex items-center gap-1.5 transition-colors"
            >
                <RotateCcw size={14} />
                重置
            </button>

            {/* 右侧：展开/折叠按钮 */}
            <button
                onClick={onToggleExpandAll}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium flex items-center gap-1.5 transition-colors ${
                    isAllExpanded
                        ? 'bg-yellow-50 text-yellow-600 hover:bg-yellow-100'
                        : 'bg-amber-50 text-amber-600 hover:bg-amber-100'
                }`}
            >
                {isAllExpanded ? (
                    <>
                        <ChevronRight size={14} />
                        全部折叠
                    </>
                ) : (
                    <>
                        <ChevronDown size={14} />
                        展开子任务
                    </>
                )}
            </button>
        </div>
    );
};
