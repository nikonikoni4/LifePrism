/**
 * CustomBlockPopover 组件
 * 
 * 自定义时间块的编辑弹出框
 * 
 * 功能：
 * - 编辑内容描述
 * - 修改开始/结束时间
 * - 选择主分类/子分类
 * - 保存/取消/删除操作
 */

import React, { useState, useEffect, useRef } from 'react';
import { X, Trash2, Save, Clock, Tag, FileText, ListTodo } from 'lucide-react';
import { UserCustomBlock, PopoverFormData, TodoSelectItem, getRandomColor, TAILWIND_200_COLORS } from './types';
import { CategoryTreeItem } from '../../../../../core/types/common-components';

interface CustomBlockPopoverProps {
    /** 正在编辑的时间块（null 表示创建新块） */
    block: UserCustomBlock | null;
    /** 是否显示弹出框 */
    isOpen: boolean;
    /** 弹出框位置（相对于视口） */
    position?: { x: number; y: number };
    /** 分类列表 */
    categories: CategoryTreeItem[];
    /** 当天待办事项列表 */
    todos: TodoSelectItem[];
    /** 保存回调 */
    onSave: (data: PopoverFormData, blockId?: number) => void;
    /** 取消/关闭回调 */
    onClose: () => void;
    /** 删除回调 */
    onDelete?: (blockId: number) => void;
    /** 是否正在保存 */
    isSaving?: boolean;
    /** 当前日期（用于创建新块时） */
    currentDate?: string;
    /** 初始时间（通过 + 按钮创建时预填，格式 HH:MM） */
    initialTime?: string;
}

/**
 * 从时间字符串提取 HH:MM 格式
 *
 * ⚠️ 规则：接收 UTC ISO 时间，转换为本地时间后提取 HH:MM
 * 后端存储的是 UTC，前端编辑框显示必须是本地时间
 */
function extractTime(timeStr: string): string {
    if (!timeStr) return '00:00';

    // 解析 UTC ISO 字符串为 Date 对象（浏览器自动转为本地时间）
    const date = new Date(timeStr);
    const hours = date.getHours();
    const minutes = date.getMinutes();
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

const CustomBlockPopover: React.FC<CustomBlockPopoverProps> = ({
    block,
    isOpen,
    position,
    categories,
    todos,
    onSave,
    onClose,
    onDelete,
    isSaving = false,
    currentDate,
    initialTime,
}) => {
    // 表单状态
    const [formData, setFormData] = useState<PopoverFormData>({
        content: '',
        startTime: '08:00',
        endTime: '09:00',
        categoryId: undefined,
        subCategoryId: undefined,
        todoId: undefined,
        color: getRandomColor(),
    });

    const popoverRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // 监控组件挂载和卸载
    useEffect(() => {
        console.log('[Popover] 组件挂载，isOpen:', isOpen);
        return () => {
            console.log('[Popover] 组件卸载');
            // 检查卸载时的遮罩层
            const overlays = document.querySelectorAll('.fixed.inset-0');
            console.log('[Popover] 卸载时遮罩层数量:', overlays.length);
        };
    }, []);

    // 监控isOpen变化
    useEffect(() => {
        console.log('[Popover] isOpen 变化:', isOpen);
        if (!isOpen) {
            console.log('[Popover] isOpen=false，组件应该返回null');
            // 检查此时的遮罩层
            setTimeout(() => {
                const overlays = document.querySelectorAll('.fixed.inset-0');
                console.log('[Popover] isOpen=false 100ms后，遮罩层数量:', overlays.length);
                overlays.forEach((overlay, idx) => {
                    console.log(`  遮罩层 ${idx}:`, overlay.className);
                });
            }, 100);
        }
    }, [isOpen]);

    // 初始化/更新表单数据
    useEffect(() => {
        if (block) {
            setFormData({
                content: block.content,
                startTime: extractTime(block.start_time),
                endTime: extractTime(block.end_time),
                categoryId: block.category_id,
                subCategoryId: block.sub_category_id,
                todoId: block.todo_id,
                color: block.color || getRandomColor(),
            });
        } else {
            // 创建新块时的默认值
            // 如果有 initialTime，使用它作为开始时间，结束时间为开始时间 +1 小时
            const startTime = initialTime || '08:00';
            // 结束时间默认为当前时间
            const now = new Date();
            const endH = now.getHours();
            const endM = now.getMinutes();
            const endTime = `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;

            setFormData({
                content: '',
                startTime,
                endTime,
                categoryId: undefined,
                subCategoryId: undefined,
                todoId: undefined,
                color: getRandomColor(),
            });
        }
    }, [block, initialTime]);

    // 自动聚焦到输入框
    useEffect(() => {
        if (isOpen && inputRef.current) {
            setTimeout(() => inputRef.current?.focus(), 100);
        }
    }, [isOpen]);

    // 点击外部关闭
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
                onClose();
            }
        };

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen, onClose]);

    // ESC 键关闭
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                onClose();
            }
            // Ctrl+Enter 保存
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                handleSave();
            }
        };

        if (isOpen) {
            document.addEventListener('keydown', handleKeyDown);
        }

        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [isOpen, onClose]);

    // 获取当前选中的主分类对象
    const selectedCategory = categories.find(c => c.id === formData.categoryId);

    // 处理主分类变更
    const handleCategoryChange = (categoryId: string) => {
        const category = categories.find(c => c.id === categoryId);
        setFormData(prev => ({
            ...prev,
            categoryId,
            // 自动选择第一个子分类
            subCategoryId: category?.subcategories?.[0]?.id || '',
        }));
    };

    // 处理保存
    const handleSave = () => {
        if (!formData.content.trim()) {
            inputRef.current?.focus();
            return;
        }
        // 分类不再强制要求
        onSave(formData, block?.id);
    };

    // 处理删除
    const handleDelete = async () => {
        console.log('=== [Popover] handleDelete 开始 ===');
        console.log('[Popover] block:', block);
        console.log('[Popover] isOpen:', isOpen);

        if (block && onDelete) {
            // 记录删除前的DOM状态
            console.log('[Popover] 删除前 - 遮罩层详情:');
            const overlaysBefore = document.querySelectorAll('.fixed.inset-0');
            overlaysBefore.forEach((overlay, idx) => {
                console.log(`  遮罩层 ${idx}:`, {
                    className: overlay.className,
                    zIndex: window.getComputedStyle(overlay).zIndex,
                    display: window.getComputedStyle(overlay).display,
                    pointerEvents: window.getComputedStyle(overlay).pointerEvents,
                    parentElement: overlay.parentElement?.tagName,
                });
            });

            console.log('[Popover] 即将显示 confirm 对话框');
            const confirmStart = Date.now();

            const confirmed = window.electronAPI?.showConfirm
                ? await window.electronAPI.showConfirm({ message: '确定要删除这个时间块吗？' })
                : confirm('确定要删除这个时间块吗？');

            if (confirmed) {
                const confirmEnd = Date.now();
                console.log(`[Popover] confirm 确认，耗时: ${confirmEnd - confirmStart}ms`);

                // 记录confirm后的DOM状态
                console.log('[Popover] confirm后 - 遮罩层详情:');
                const overlaysAfterConfirm = document.querySelectorAll('.fixed.inset-0');
                overlaysAfterConfirm.forEach((overlay, idx) => {
                    console.log(`  遮罩层 ${idx}:`, {
                        className: overlay.className,
                        zIndex: window.getComputedStyle(overlay).zIndex,
                        display: window.getComputedStyle(overlay).display,
                        pointerEvents: window.getComputedStyle(overlay).pointerEvents,
                    });
                });

                console.log('[Popover] 调用 onDelete');
                onDelete(block.id);
            } else {
                const confirmEnd = Date.now();
                console.log(`[Popover] confirm 取消，耗时: ${confirmEnd - confirmStart}ms`);
            }
        }
        console.log('=== [Popover] handleDelete 结束 ===');
    };

    if (!isOpen) return null;

    console.log('[Popover] 渲染中 - isOpen:', isOpen, 'block:', block?.id);

    // 是否使用固定位置（跟随鼠标）还是居中显示
    const useFixedPosition = !!position;

    // 固定位置样式（跟随点击位置）
    const fixedPositionStyle: React.CSSProperties = position
        ? {
            position: 'fixed',
            left: Math.min(position.x, window.innerWidth - 340),
            top: Math.min(position.y, window.innerHeight - 400),
            zIndex: 1000,
        }
        : {};

    return (
        <>
            {/* 遮罩层 */}
            <div
                className="fixed inset-0 bg-black/20 z-[999]"
                onClick={onClose}
            />

            {/* 弹出框容器 - 居中显示时使用 flex 居中 */}
            {!useFixedPosition ? (
                <div className="fixed inset-0 z-[1000] flex items-center justify-center pointer-events-none">
                    <div
                        ref={popoverRef}
                        className="w-[560px] max-w-[90vw] bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden animate-fade-in pointer-events-auto"
                    >
                        {/* 标题栏 */}
                        <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-indigo-50 to-purple-50 border-b border-gray-100">
                            <div className="flex items-center gap-2">
                                <FileText size={16} className="text-indigo-500" />
                                <span className="text-sm font-bold text-gray-800">
                                    {block ? '编辑备注' : '新建备注'}
                                </span>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-1.5 hover:bg-white/80 rounded-lg transition-colors"
                            >
                                <X size={16} className="text-gray-400" />
                            </button>
                        </div>

                        {/* 表单内容 - 横向双栏布局 */}
                        <div className="p-4 flex gap-4">
                            {/* 左侧：内容、时间、颜色 */}
                            <div className="flex-1 space-y-4 min-w-0">
                                {/* 内容输入 */}
                                <div>
                                    <label className="flex items-center gap-1.5 text-xs font-bold text-gray-600 mb-2">
                                        <FileText size={12} />
                                        内容
                                    </label>
                                    <input
                                        ref={inputRef}
                                        type="text"
                                        value={formData.content}
                                        onChange={(e) => setFormData(prev => ({ ...prev, content: e.target.value }))}
                                        placeholder="输入活动描述..."
                                        className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg 
                                         focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300
                                         placeholder:text-gray-400 transition-all"
                                    />
                                </div>

                                {/* 时间选择 */}
                                <div>
                                    <label className="flex items-center gap-1.5 text-xs font-bold text-gray-600 mb-2">
                                        <Clock size={12} />
                                        时间
                                    </label>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="time"
                                            value={formData.startTime}
                                            onChange={(e) => setFormData(prev => ({ ...prev, startTime: e.target.value }))}
                                            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg
                                             focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300"
                                        />
                                        <span className="text-gray-400">→</span>
                                        <input
                                            type="time"
                                            value={formData.endTime}
                                            onChange={(e) => setFormData(prev => ({ ...prev, endTime: e.target.value }))}
                                            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg
                                             focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300"
                                        />
                                    </div>
                                </div>

                                {/* 颜色选择 */}
                                <div>
                                    <label className="flex items-center gap-1.5 text-xs font-bold text-gray-600 mb-2">
                                        <div
                                            className="w-3 h-3 rounded-full border border-gray-300"
                                            style={{ backgroundColor: formData.color }}
                                        />
                                        颜色
                                    </label>
                                    <div className="flex flex-wrap gap-1.5">
                                        {TAILWIND_200_COLORS.map(color => (
                                            <button
                                                key={color}
                                                type="button"
                                                onClick={() => setFormData(prev => ({ ...prev, color }))}
                                                className={`w-6 h-6 rounded-md border-2 transition-all
                                                    ${formData.color === color
                                                        ? 'border-gray-600 scale-110 shadow-md'
                                                        : 'border-transparent hover:scale-105'
                                                    }`}
                                                style={{ backgroundColor: color }}
                                            />
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* 右侧：待办绑定、分类、子分类 */}
                            <div className="flex-1 space-y-4 min-w-0">
                                {/* 待办事项绑定 */}
                                <div>
                                    <label className="flex items-center gap-1.5 text-xs font-bold text-gray-600 mb-2">
                                        <ListTodo size={12} />
                                        绑定待办（可选）
                                    </label>
                                    <select
                                        value={formData.todoId ?? ''}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            todoId: e.target.value ? Number(e.target.value) : undefined
                                        }))}
                                        className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg
                                         focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300
                                         bg-white cursor-pointer"
                                    >
                                        <option value="">不绑定待办事项</option>
                                        {todos.map(todo => (
                                            <option key={todo.id} value={todo.id}>
                                                {todo.content}
                                            </option>
                                        ))}
                                    </select>
                                </div>

                                {/* 主分类选择 */}
                                <div>
                                    <label className="flex items-center gap-1.5 text-xs font-bold text-gray-600 mb-2">
                                        <Tag size={12} />
                                        分类（可选）
                                    </label>
                                    <div className="flex flex-wrap gap-1.5">
                                        <button
                                            onClick={() => setFormData(prev => ({ ...prev, categoryId: undefined, subCategoryId: undefined }))}
                                            className={`px-2 py-1 text-xs font-medium rounded-md border transition-all
                                            ${!formData.categoryId
                                                    ? 'bg-gray-500 text-white border-gray-500'
                                                    : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                                                }`}
                                        >
                                            不选择
                                        </button>
                                        {categories.map(cat => (
                                            <button
                                                key={cat.id}
                                                onClick={() => handleCategoryChange(cat.id)}
                                                className={`px-2 py-1 text-xs font-medium rounded-md border transition-all
                                                ${formData.categoryId === cat.id
                                                        ? 'bg-indigo-500 text-white border-indigo-500'
                                                        : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                                                    }`}
                                            >
                                                {cat.name}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* 子分类选择 */}
                                <div>
                                    <label className="flex items-center gap-1.5 text-xs font-bold text-gray-600 mb-2">
                                        <Tag size={12} />
                                        子分类
                                    </label>
                                    <select
                                        value={formData.subCategoryId}
                                        onChange={(e) => setFormData(prev => ({ ...prev, subCategoryId: e.target.value }))}
                                        className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg
                                         focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300
                                         bg-white cursor-pointer"
                                    >
                                        <option value="">选择子分类...</option>
                                        {selectedCategory?.subcategories?.map(sub => (
                                            <option key={sub.id} value={sub.id}>
                                                {sub.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        </div>

                        {/* 操作按钮 */}
                        <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-t border-gray-100">
                            <div>
                                {block && onDelete && (
                                    <button
                                        onClick={handleDelete}
                                        disabled={isSaving}
                                        className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium
                                         text-red-600 hover:bg-red-50 rounded-lg transition-colors
                                         disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <Trash2 size={14} />
                                        删除
                                    </button>
                                )}
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={onClose}
                                    disabled={isSaving}
                                    className="px-4 py-2 text-xs font-medium text-gray-600 
                                     hover:bg-gray-100 rounded-lg transition-colors
                                     disabled:opacity-50"
                                >
                                    取消
                                </button>
                                <button
                                    onClick={handleSave}
                                    disabled={isSaving || !formData.content.trim()}
                                    className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium
                                     bg-indigo-500 text-white rounded-lg
                                     hover:bg-indigo-600 transition-colors
                                     disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <Save size={14} />
                                    {isSaving ? '保存中...' : '保存'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            ) : null}
        </>
    );
};

export default CustomBlockPopover;
