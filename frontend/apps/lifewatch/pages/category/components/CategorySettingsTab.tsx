/**
 * CategorySettingsTab Component
 * 
 * 分类设置选项卡，用于管理主分类和子分类
 * 
 * ⚠️ 调色盘维护说明：
 * 当前使用 Tailwind CSS 500 系列颜色（见 PRESET_COLORS 和 handleAddCategory）。
 * 后端 Timeline 缩略图使用对应的 200 系列颜色映射。
 * 
 * 如果更换调色盘（不再使用 Tailwind 500 系列），请同步更新：
 * @see lifeprism/server/providers/category_color_provider.py 中的 TAILWIND_500_TO_300 映射表
 * 后端有备用方案（动态计算柔和色），但 Tailwind 映射效果更好。
 */

import React, { useState } from 'react';
import { Trash2, Edit2, Plus, Check, X as XIcon, Ban, CircleCheck } from 'lucide-react';
import { CategoryTreeItem, SubCategoryTreeItem } from '../types';
import { CategoryAPI } from '../api';

interface CategorySettingsTabProps {
    categories: CategoryTreeItem[];
    setCategories: React.Dispatch<React.SetStateAction<CategoryTreeItem[]>>;
}

const CategorySettingsTab: React.FC<CategorySettingsTabProps> = ({ categories, setCategories }) => {
    const [selectedCatId, setSelectedCatId] = useState<string>(categories[0]?.id || '');

    // Edit State for L1 Category
    const [editingCatId, setEditingCatId] = useState<string | null>(null);
    const [editCatName, setEditCatName] = useState('');

    // Edit State for L2 Sub-category
    const [editingSubId, setEditingSubId] = useState<string | null>(null);
    const [editSubName, setEditSubName] = useState('');

    // Add State
    const [newSubName, setNewSubName] = useState('');

    // Color Picker State
    const [colorPickerCatId, setColorPickerCatId] = useState<string | null>(null);

    const activeCategory = categories.find(c => c.id === selectedCatId) || categories[0];

    // --- L1 Logic ---

    const handleAddCategory = async () => {
        // Tailwind CSS 500 series colors for random selection
        const colors = ['#EF4444', '#F97316', '#EAB308', '#22C55E', '#14B8A6', '#06B6D4', '#3B82F6', '#6366F1', '#A855F7', '#EC4899'];
        const randomColor = colors[Math.floor(Math.random() * colors.length)];

        try {
            const newCat = await CategoryAPI.createCategory({ name: 'New Category', color: randomColor });
            setCategories([...categories, newCat]);
            setSelectedCatId(newCat.id);
            setEditingCatId(newCat.id);
            setEditCatName('New Category');
        } catch (error) {
            console.error('Failed to create category:', error);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: 'Failed to create category. Please try again.' });
            } else {
                alert('Failed to create category. Please try again.');
            }
        }
    };

    const handleDeleteCategory = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();

        // 使用 Electron 对话框或原生 confirm
        const confirmed = window.electronAPI?.showConfirm
            ? await window.electronAPI.showConfirm({ message: 'Are you sure? This will delete all sub-categories and associated rules.' })
            : confirm('Are you sure? This will delete all sub-categories and associated rules.');

        if (!confirmed) return;

        try {
            await CategoryAPI.deleteCategory(id);
            const newCats = categories.filter(c => c.id !== id);
            setCategories(newCats);
            if (selectedCatId === id && newCats.length > 0) {
                setSelectedCatId(newCats[0].id);
            }
        } catch (error) {
            console.error('Failed to delete category:', error);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: 'Failed to delete category. Please try again.' });
            } else {
                alert('Failed to delete category. Please try again.');
            }
        }
    };

    const startEditCategory = (id: string, name: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setEditingCatId(id);
        setEditCatName(name);
    };

    const saveEditCategory = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!editingCatId) return;

        try {
            const updated = await CategoryAPI.updateCategory(editingCatId, { name: editCatName });
            setCategories(categories.map(c =>
                c.id === editingCatId ? updated : c
            ));
            setEditingCatId(null);
        } catch (error) {
            console.error('Failed to update category:', error);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: 'Failed to update category. Please try again.' });
            } else {
                alert('Failed to update category. Please try again.');
            }
        }
    };

    const cancelEditCategory = (e: React.MouseEvent) => {
        e.stopPropagation();
        setEditingCatId(null);
    };

    // --- Color Picker Logic ---

    // Tailwind CSS 500 series color palette
    const PRESET_COLORS = [
        '#EF4444', // red-500
        '#F97316', // orange-500
        '#EAB308', // yellow-500
        '#22C55E', // green-500
        '#14B8A6', // teal-500
        '#06B6D4', // cyan-500
        '#3B82F6', // blue-500
        '#6366F1', // indigo-500
        '#A855F7', // purple-500
        '#EC4899', // pink-500
    ];

    const handleColorChange = async (catId: string, newColor: string) => {
        try {
            const updated = await CategoryAPI.updateCategory(catId, { color: newColor });
            setCategories(categories.map(c =>
                c.id === catId ? updated : c
            ));
            setColorPickerCatId(null);
        } catch (error) {
            console.error('Failed to update category color:', error);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: 'Failed to update color. Please try again.' });
            } else {
                alert('Failed to update color. Please try again.');
            }
        }
    };

    // --- Toggle State Logic ---

    const handleToggleCategoryState = async (id: string, currentState: number, e: React.MouseEvent) => {
        e.stopPropagation();
        const newState = currentState === 1 ? 0 : 1;
        const action = newState === 0 ? '禁用' : '启用';

        if (newState === 0) {
            const confirmed = window.electronAPI?.showConfirm
                ? await window.electronAPI.showConfirm({ message: `确定要禁用此分类吗？\n\n禁用后，已分类的历史数据不会受影响，但该分类将不再参与后续的自动分类处理。` })
                : confirm(`确定要禁用此分类吗？\n\n禁用后，已分类的历史数据不会受影响，但该分类将不再参与后续的自动分类处理。`);
            if (!confirmed) return;
        }

        try {
            const updated = await CategoryAPI.toggleCategoryState(id, newState);
            setCategories(categories.map(c =>
                c.id === id ? updated : c
            ));
        } catch (error) {
            console.error(`Failed to ${action} category:`, error);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: `Failed to ${action} category. Please try again.` });
            } else {
                alert(`Failed to ${action} category. Please try again.`);
            }
        }
    };

    const handleToggleSubCategoryState = async (subId: string, currentState: number) => {
        if (!activeCategory) return;

        const newState = currentState === 1 ? 0 : 1;
        const action = newState === 0 ? '禁用' : '启用';

        if (newState === 0) {
            const confirmed = window.electronAPI?.showConfirm
                ? await window.electronAPI.showConfirm({ message: `确定要禁用此子分类吗？\n\n禁用后，已分类的历史数据不会受影响，但该子分类将不再参与后续的自动分类处理。` })
                : confirm(`确定要禁用此子分类吗？\n\n禁用后，已分类的历史数据不会受影响，但该子分类将不再参与后续的自动分类处理。`);
            if (!confirmed) return;
        }

        try {
            const updated = await CategoryAPI.toggleSubCategoryState(activeCategory.id, subId, newState);
            setCategories(categories.map(c => {
                if (c.id === activeCategory.id) {
                    return {
                        ...c,
                        subcategories: (c.subcategories || []).map(s =>
                            s.id === subId ? updated : s
                        )
                    };
                }
                return c;
            }));
        } catch (error) {
            console.error(`Failed to ${action} sub-category:`, error);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: `Failed to ${action} sub-category. Please try again.` });
            } else {
                alert(`Failed to ${action} sub-category. Please try again.`);
            }
        }
    };

    // --- L2 Logic ---

    const handleAddSubCategory = async () => {
        if (!newSubName.trim() || !activeCategory) return;

        try {
            const newSub = await CategoryAPI.createSubCategory(activeCategory.id, { name: newSubName });
            setCategories(categories.map(c => {
                if (c.id === activeCategory.id) {
                    return {
                        ...c,
                        subcategories: [...(c.subcategories || []), newSub]
                    };
                }
                return c;
            }));
            setNewSubName('');
        } catch (error) {
            console.error('Failed to create sub-category:', error);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: 'Failed to create sub-category. Please try again.' });
            } else {
                alert('Failed to create sub-category. Please try again.');
            }
        }
    };

    const handleDeleteSubCategory = async (subId: string) => {
        if (!activeCategory) return;

        try {
            await CategoryAPI.deleteSubCategory(activeCategory.id, subId);
            setCategories(categories.map(c => {
                if (c.id === activeCategory.id) {
                    return {
                        ...c,
                        subcategories: (c.subcategories || []).filter(s => s.id !== subId)
                    };
                }
                return c;
            }));
        } catch (error) {
            console.error('Failed to delete sub-category:', error);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: 'Failed to delete sub-category. Please try again.' });
            } else {
                alert('Failed to delete sub-category. Please try again.');
            }
        }
    };

    const startEditSub = (subId: string, name: string) => {
        setEditingSubId(subId);
        setEditSubName(name);
    };

    const saveEditSub = async () => {
        if (!activeCategory || !editingSubId) return;

        try {
            const updated = await CategoryAPI.updateSubCategory(activeCategory.id, editingSubId, { name: editSubName });
            setCategories(categories.map(c => {
                if (c.id === activeCategory.id) {
                    return {
                        ...c,
                        subcategories: (c.subcategories || []).map(s =>
                            s.id === editingSubId ? updated : s
                        )
                    };
                }
                return c;
            }));
            setEditingSubId(null);
        } catch (error) {
            console.error('Failed to update sub-category:', error);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: 'Failed to update sub-category. Please try again.' });
            } else {
                alert('Failed to update sub-category. Please try again.');
            }
        }
    };

    return (
        <div className="flex h-full divide-x divide-gray-100" onClick={() => setColorPickerCatId(null)}>

            {/* Left Column: L1 Categories */}
            <div className="w-1/3 min-w-[250px] bg-gray-50/50 flex flex-col p-6">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4 px-2">Main Categories</h3>

                <div className="flex-1 space-y-2 overflow-y-auto">
                    {categories.map((cat) => {
                        const isEditing = editingCatId === cat.id;
                        const isSelected = selectedCatId === cat.id;

                        return (
                            <div
                                key={cat.id}
                                onClick={() => !isEditing && setSelectedCatId(cat.id)}
                                className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer border transition-all ${isSelected
                                    ? 'bg-white border-blue-200 shadow-sm ring-1 ring-blue-100'
                                    : 'bg-transparent border-transparent hover:bg-white hover:border-gray-200'
                                    }`}
                            >
                                {isEditing ? (
                                    <div className="flex items-center gap-2 w-full" onClick={e => e.stopPropagation()}>
                                        <input
                                            value={editCatName}
                                            onChange={(e) => setEditCatName(e.target.value)}
                                            className="w-full bg-white border border-blue-300 rounded px-2 py-1 text-sm focus:outline-none"
                                            autoFocus
                                        />
                                        <button onClick={saveEditCategory} className="p-1 text-green-600 hover:bg-green-50 rounded"><Check size={14} /></button>
                                        <button onClick={cancelEditCategory} className="p-1 text-gray-400 hover:bg-gray-100 rounded"><XIcon size={14} /></button>
                                    </div>
                                ) : (
                                    <>
                                        <div className="flex items-center gap-3">
                                            <div className="relative">
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setColorPickerCatId(colorPickerCatId === cat.id ? null : cat.id);
                                                    }}
                                                    className="w-5 h-5 rounded-full border border-black/10 shadow-inner flex-shrink-0 cursor-pointer hover:ring-2 hover:ring-blue-300 hover:ring-offset-1 transition-all"
                                                    style={{ backgroundColor: cat.color }}
                                                    title="Change color"
                                                />

                                                {/* Color Picker Popup */}
                                                {colorPickerCatId === cat.id && (
                                                    <div
                                                        className="absolute left-0 top-8 z-50 bg-white rounded-xl shadow-xl border border-gray-200 p-3 animate-fade-in min-w-max"
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        <div className="grid grid-cols-5 gap-2 w-max">
                                                            {PRESET_COLORS.map((color) => (
                                                                <button
                                                                    key={color}
                                                                    onClick={() => handleColorChange(cat.id, color)}
                                                                    className="w-7 h-7 rounded-full border-2 border-transparent hover:border-blue-400 hover:scale-110 transition-all shadow-sm flex-shrink-0"
                                                                    style={{ backgroundColor: color }}
                                                                    title={color}
                                                                />
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                            <span className={`font-semibold ${isSelected ? 'text-slate-900' : 'text-slate-600'}`}>
                                                {cat.name}
                                            </span>
                                        </div>
                                        <div className={`flex items-center gap-1 opacity-0 ${isSelected ? 'opacity-100' : 'group-hover:opacity-100'} transition-opacity`}>
                                            <button onClick={(e) => startEditCategory(cat.id, cat.name, e)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Edit">
                                                <Edit2 size={14} />
                                            </button>
                                            <button
                                                onClick={(e) => handleToggleCategoryState(cat.id, cat.state ?? 1, e)}
                                                className={`p-1.5 rounded-lg ${cat.state === 0 ? 'text-green-500 hover:text-green-600 hover:bg-green-50' : 'text-slate-400 hover:text-orange-600 hover:bg-orange-50'}`}
                                                title={cat.state === 0 ? 'Enable' : 'Disable'}
                                            >
                                                {cat.state === 0 ? <CircleCheck size={14} /> : <Ban size={14} />}
                                            </button>
                                            <button onClick={(e) => handleDeleteCategory(cat.id, e)} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg" title="Delete">
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </>
                                )}
                            </div>
                        );
                    })}
                </div>

                <button
                    onClick={handleAddCategory}
                    className="mt-4 flex items-center justify-center gap-2 w-full py-3 bg-white border border-dashed border-gray-300 rounded-xl text-slate-500 font-bold text-sm hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-all"
                >
                    <Plus size={16} />
                    Add New Category
                </button>
            </div>

            {/* Right Column: L2 Sub-categories */}
            <div className="flex-1 p-8 flex flex-col bg-white">
                {activeCategory ? (
                    <>
                        <div className="flex justify-between items-end mb-8 border-b border-gray-100 pb-6">
                            <div>
                                <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Sub-categories for</span>
                                <div className="flex items-center gap-3 mt-1">
                                    <h2 className="text-2xl font-bold text-slate-900" style={{ color: activeCategory.color }}>
                                        {activeCategory.name}
                                    </h2>
                                    <span className="bg-gray-100 text-gray-500 text-xs font-bold px-2 py-1 rounded-md">
                                        {(activeCategory.subcategories || []).length} items
                                    </span>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-3 flex-1 overflow-y-auto pr-2">
                            {(activeCategory.subcategories || []).map((sub) => {
                                const isEditing = editingSubId === sub.id;
                                return (
                                    <div key={sub.id} className="flex items-center justify-between p-4 rounded-xl border border-gray-100 hover:border-gray-300 hover:shadow-sm transition-all group">
                                        {isEditing ? (
                                            <div className="flex items-center gap-2 w-full">
                                                <input
                                                    value={editSubName}
                                                    onChange={(e) => setEditSubName(e.target.value)}
                                                    className="flex-1 bg-gray-50 border border-blue-300 rounded px-2 py-1 text-sm font-semibold focus:outline-none"
                                                    autoFocus
                                                />
                                                <button onClick={saveEditSub} className="p-2 text-green-600 hover:bg-green-50 rounded"><Check size={16} /></button>
                                                <button onClick={() => setEditingSubId(null)} className="p-2 text-gray-400 hover:bg-gray-100 rounded"><XIcon size={16} /></button>
                                            </div>
                                        ) : (
                                            <>
                                                <span className="font-semibold text-slate-700">{sub.name}</span>
                                                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <button onClick={() => startEditSub(sub.id, sub.name)} className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Edit">
                                                        <Edit2 size={16} />
                                                    </button>
                                                    <button
                                                        onClick={() => handleToggleSubCategoryState(sub.id, sub.state ?? 1)}
                                                        className={`p-2 rounded-lg ${sub.state === 0 ? 'text-green-500 hover:text-green-600 hover:bg-green-50' : 'text-slate-400 hover:text-orange-600 hover:bg-orange-50'}`}
                                                        title={sub.state === 0 ? 'Enable' : 'Disable'}
                                                    >
                                                        {sub.state === 0 ? <CircleCheck size={16} /> : <Ban size={16} />}
                                                    </button>
                                                    <button onClick={() => handleDeleteSubCategory(sub.id)} className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg" title="Delete">
                                                        <Trash2 size={16} />
                                                    </button>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                );
                            })}
                            {(activeCategory.subcategories || []).length === 0 && (
                                <div className="text-center py-12 text-slate-400 italic">
                                    No sub-categories defined. Add one below.
                                </div>
                            )}
                        </div>

                        <div className="mt-6 pt-6 border-t border-gray-100">
                            <label className="block text-xs font-bold text-slate-500 mb-2 uppercase">Create new sub-category</label>
                            <div className="flex gap-3">
                                <input
                                    type="text"
                                    value={newSubName}
                                    onChange={(e) => setNewSubName(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleAddSubCategory()}
                                    placeholder={`Add to ${activeCategory.name}...`}
                                    className="flex-1 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300 transition-all"
                                />
                                <button
                                    onClick={handleAddSubCategory}
                                    className="px-6 bg-slate-900 text-white rounded-xl font-bold text-sm hover:bg-slate-800 transition-colors shadow-lg shadow-slate-200"
                                >
                                    Add
                                </button>
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="flex items-center justify-center h-full text-slate-400">
                        Select a category to manage details
                    </div>
                )}
            </div>

        </div>
    );
};

export default CategorySettingsTab;
