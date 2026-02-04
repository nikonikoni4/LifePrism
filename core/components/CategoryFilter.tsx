/**
 * CategoryFilter - 通用分类筛选器组件
 *
 * 提供主分类和子分类的两栏筛选界面
 */

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Filter, X, Check } from 'lucide-react';
import { CategoryTreeItem } from '../types/common-components';
import { CategoryAPI } from '../services/commonApi';

export interface CategoryFilterValue {
    categoryId: string | null;
    subCategoryId: string | null;
    color: string | null;
}

export interface CategoryFilterProps {
    /** 当前筛选值 */
    value: CategoryFilterValue;
    /** 筛选值变化回调 */
    onChange: (value: CategoryFilterValue) => void;
    /** 自定义按钮类名 */
    buttonClassName?: string;
    /** 是否显示按钮文字 */
    showLabel?: boolean;
}

const CategoryFilter: React.FC<CategoryFilterProps> = ({
    value,
    onChange,
    buttonClassName,
    showLabel = true,
}) => {
    const [showDialog, setShowDialog] = useState(false);
    const [categories, setCategories] = useState<CategoryTreeItem[]>([]);

    // 临时选择状态（对话框内部使用）
    const [tempCategoryId, setTempCategoryId] = useState<string | null>(value.categoryId);
    const [tempSubCategoryId, setTempSubCategoryId] = useState<string | null>(value.subCategoryId);
    const [tempColor, setTempColor] = useState<string | null>(value.color);

    // 加载分类数据
    useEffect(() => {
        const loadCategories = async () => {
            try {
                const cats = await CategoryAPI.getTree();
                setCategories(cats);
            } catch (error) {
                console.error('Failed to load categories:', error);
            }
        };
        loadCategories();
    }, []);

    // 同步外部值到临时状态
    useEffect(() => {
        setTempCategoryId(value.categoryId);
        setTempSubCategoryId(value.subCategoryId);
        setTempColor(value.color);
    }, [value]);

    const handleOpenDialog = () => {
        setTempCategoryId(value.categoryId);
        setTempSubCategoryId(value.subCategoryId);
        setTempColor(value.color);
        setShowDialog(true);
    };

    const handleReset = () => {
        setTempCategoryId(null);
        setTempSubCategoryId(null);
        setTempColor(null);
    };

    const handleApply = () => {
        onChange({
            categoryId: tempCategoryId,
            subCategoryId: tempSubCategoryId,
            color: tempColor,
        });
        setShowDialog(false);
    };

    const handleClearFilter = (e: React.MouseEvent) => {
        e.stopPropagation();
        onChange({
            categoryId: null,
            subCategoryId: null,
            color: null,
        });
    };

    const hasFilter = value.categoryId !== null;

    const defaultButtonClass = `flex items-center justify-center gap-2 px-4 py-2.5 border rounded-xl text-sm font-semibold hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm ${hasFilter
        ? 'bg-opacity-20 border-2'
        : 'bg-white border-gray-200 text-slate-600'
        }`;

    return (
        <>
            {/* Filter Button */}
            <button
                type="button"
                onClick={handleOpenDialog}
                className={buttonClassName || defaultButtonClass}
                style={hasFilter && value.color ? {
                    backgroundColor: `${value.color}20`,
                    borderColor: value.color,
                    color: value.color
                } : {}}
            >
                <Filter size={16} />
                {showLabel && (hasFilter ? 'Filtered' : 'Filters')}
                {hasFilter && (
                    <span
                        onClick={handleClearFilter}
                        className="ml-1 hover:bg-white/50 rounded-full p-0.5"
                    >
                        <X size={12} />
                    </span>
                )}
            </button>

            {/* Filter Dialog */}
            {showDialog && createPortal(
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl p-6 shadow-2xl max-w-lg w-full mx-4 animate-fade-in">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-xl font-bold text-slate-900">筛选分类</h3>
                            <button
                                onClick={() => setShowDialog(false)}
                                className="p-1 hover:bg-gray-100 rounded-full transition-all"
                            >
                                <X size={20} className="text-gray-500" />
                            </button>
                        </div>
                        <p className="text-sm text-slate-600 mb-6">选择分类以筛选数据</p>

                        <div className="flex gap-4 mb-6">
                            {/* Categories Column */}
                            <div className="flex-1">
                                <label className="block text-sm font-semibold text-slate-700 mb-2">
                                    主分类
                                </label>
                                <div className="space-y-2 max-h-60 overflow-y-auto">
                                    {categories.map((cat) => (
                                        <button
                                            key={cat.id}
                                            onClick={() => {
                                                setTempCategoryId(cat.id);
                                                setTempSubCategoryId(null);
                                                setTempColor(cat.color);
                                            }}
                                            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all ${tempCategoryId === cat.id
                                                ? 'border-2 bg-opacity-10'
                                                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                                }`}
                                            style={tempCategoryId === cat.id ? {
                                                borderColor: cat.color,
                                                backgroundColor: `${cat.color}15`
                                            } : {}}
                                        >
                                            <span
                                                className="w-3 h-3 rounded-full flex-shrink-0"
                                                style={{ backgroundColor: cat.color }}
                                            />
                                            <span className="text-sm font-medium text-slate-700 truncate">
                                                {cat.name}
                                            </span>
                                            {tempCategoryId === cat.id && (
                                                <Check size={16} className="ml-auto text-green-500" />
                                            )}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Sub-Categories Column */}
                            <div className="flex-1">
                                <label className="block text-sm font-semibold text-slate-700 mb-2">
                                    子分类 <span className="font-normal text-slate-400">(可选)</span>
                                </label>
                                <div className="space-y-2 max-h-60 overflow-y-auto">
                                    {tempCategoryId ? (
                                        categories
                                            .find(c => c.id === tempCategoryId)
                                            ?.subcategories?.map((sub) => (
                                                <button
                                                    key={sub.id}
                                                    onClick={() => setTempSubCategoryId(
                                                        tempSubCategoryId === sub.id ? null : sub.id
                                                    )}
                                                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all ${tempSubCategoryId === sub.id
                                                        ? 'border-2 border-morandi-blue bg-blue-50'
                                                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                                        }`}
                                                >
                                                    <span className="text-sm font-medium text-slate-700 truncate">
                                                        {sub.name}
                                                    </span>
                                                    {tempSubCategoryId === sub.id && (
                                                        <Check size={16} className="ml-auto text-green-500" />
                                                    )}
                                                </button>
                                            ))
                                    ) : (
                                        <p className="text-sm text-slate-400 italic py-4 text-center">
                                            请先选择主分类
                                        </p>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={handleReset}
                                className="flex-1 px-4 py-2.5 bg-gray-100 text-slate-700 rounded-xl font-semibold hover:bg-gray-200 transition-all"
                            >
                                重置
                            </button>
                            <button
                                onClick={handleApply}
                                className="flex-1 px-4 py-2.5 bg-morandi-blue text-white rounded-xl font-semibold hover:bg-opacity-90 transition-all"
                            >
                                应用筛选
                            </button>
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </>
    );
};

export default CategoryFilter;
