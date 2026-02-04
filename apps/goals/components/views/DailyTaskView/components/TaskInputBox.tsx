import React, { useState, useRef, useEffect } from 'react';
import { Plus, Target, FileText, ChevronDown } from 'lucide-react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';

interface SelectOption {
    id: string;
    label: string;
}

interface TaskInputBoxProps {
    goals: SelectOption[];
    planDocs: SelectOption[];
    selectedGoalId: string | null;
    selectedPlanDocId: string | null;
    onGoalChange: (id: string | null) => void;
    onPlanDocChange: (id: string | null) => void;
    onAddTask: (content: string) => void;
}

/**
 * 简单的下拉选择器组件
 */
const SimpleSelect: React.FC<{
    icon: React.ReactNode;
    label: string;
    value: string | null;
    options: SelectOption[];
    onChange: (id: string | null) => void;
}> = ({ icon, label, value, options, onChange }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [position, setPosition] = useState({ top: 0, left: 0, width: 0 });
    const triggerRef = useRef<HTMLButtonElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);

    const selectedOption = options.find(o => o.id === value);

    useEffect(() => {
        if (isOpen && triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect();
            setPosition({
                top: rect.bottom + 4,
                left: rect.left,
                width: Math.max(rect.width, 180)
            });
        }
    }, [isOpen]);

    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (
                triggerRef.current && !triggerRef.current.contains(e.target as Node) &&
                menuRef.current && !menuRef.current.contains(e.target as Node)
            ) {
                setIsOpen(false);
            }
        };
        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isOpen]);

    return (
        <div className="relative">
            <button
                ref={triggerRef}
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors text-sm"
            >
                <span className="text-slate-400">{icon}</span>
                <span className="text-slate-500">{label}</span>
                <span className="text-slate-700 font-medium truncate max-w-[100px]">
                    {selectedOption?.label || '无'}
                </span>
                <ChevronDown size={14} className="text-slate-400" />
            </button>

            {createPortal(
                <AnimatePresence>
                    {isOpen && (
                        <motion.div
                            ref={menuRef}
                            initial={{ opacity: 0, y: -8 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -4 }}
                            transition={{ duration: 0.15 }}
                            className="fixed z-[9999] bg-white rounded-xl shadow-lg border border-slate-200 py-1 overflow-hidden"
                            style={{
                                top: position.top,
                                left: position.left,
                                minWidth: position.width
                            }}
                        >
                            {/* 无选项 */}
                            <button
                                onClick={() => { onChange(null); setIsOpen(false); }}
                                className={`w-full px-3 py-2 text-left text-sm hover:bg-slate-50 transition-colors ${
                                    value === null ? 'bg-slate-50 text-slate-900 font-medium' : 'text-slate-600'
                                }`}
                            >
                                无
                            </button>
                            {options.map(option => (
                                <button
                                    key={option.id}
                                    onClick={() => { onChange(option.id); setIsOpen(false); }}
                                    className={`w-full px-3 py-2 text-left text-sm hover:bg-slate-50 transition-colors truncate ${
                                        value === option.id ? 'bg-slate-50 text-slate-900 font-medium' : 'text-slate-600'
                                    }`}
                                >
                                    {option.label}
                                </button>
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>,
                document.body
            )}
        </div>
    );
};

/**
 * 任务输入框组件
 * 包含目标/计划书选择器和输入框
 */
export const TaskInputBox: React.FC<TaskInputBoxProps> = ({
    goals,
    planDocs,
    selectedGoalId,
    selectedPlanDocId,
    onGoalChange,
    onPlanDocChange,
    onAddTask
}) => {
    const [inputValue, setInputValue] = useState('');
    const inputRef = useRef<HTMLInputElement>(null);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && inputValue.trim()) {
            onAddTask(inputValue.trim());
            setInputValue('');
        }
    };

    const handleAddClick = () => {
        if (inputValue.trim()) {
            onAddTask(inputValue.trim());
            setInputValue('');
            inputRef.current?.focus();
        }
    };

    return (
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl border border-slate-200/60 mx-6 mt-4 overflow-hidden shadow-sm">
            {/* 上半部分：选择器 */}
            <div className="flex items-center gap-4 px-4 py-3 border-b border-slate-100">
                <SimpleSelect
                    icon={<Target size={14} />}
                    label="目标"
                    value={selectedGoalId}
                    options={goals}
                    onChange={onGoalChange}
                />
                <SimpleSelect
                    icon={<FileText size={14} />}
                    label="计划书"
                    value={selectedPlanDocId}
                    options={planDocs}
                    onChange={onPlanDocChange}
                />
            </div>

            {/* 下半部分：输入框 */}
            <div className="flex items-center px-4 py-3">
                <button
                    onClick={handleAddClick}
                    className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-emerald-500 hover:bg-emerald-50 transition-colors flex-shrink-0"
                >
                    <Plus size={18} />
                </button>
                <div className="w-px h-6 bg-slate-200 mx-3 flex-shrink-0" />
                <input
                    ref={inputRef}
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="输入任务内容，按 Enter 添加..."
                    className="flex-1 bg-transparent text-slate-700 placeholder-slate-400 text-sm outline-none"
                />
            </div>
        </div>
    );
};
