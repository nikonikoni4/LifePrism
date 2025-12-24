
import React, { useState, useEffect } from 'react';
import { X, Check } from 'lucide-react';
import { CategoryDef } from '../types';

interface CategorySelectionModalProps {
    isOpen: boolean;
    onClose: () => void;
    categories: CategoryDef[];
    initialCategoryId?: string | null;
    initialSubCategoryId?: string | null;
    onApply: (categoryId: string | null, subCategoryId: string | null) => void;
}

const CategorySelectionModal: React.FC<CategorySelectionModalProps> = ({
    isOpen,
    onClose,
    categories,
    initialCategoryId,
    initialSubCategoryId,
    onApply,
}) => {
    const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(initialCategoryId || null);
    const [selectedSubCategoryId, setSelectedSubCategoryId] = useState<string | null>(initialSubCategoryId || null);

    useEffect(() => {
        if (isOpen) {
            setSelectedCategoryId(initialCategoryId || null);
            setSelectedSubCategoryId(initialSubCategoryId || null);
        }
    }, [isOpen, initialCategoryId, initialSubCategoryId]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <div
                className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity"
                onClick={onClose}
            />
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg relative z-10 animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-gray-100">
                    <div>
                        <h3 className="text-xl font-bold text-slate-900">Select Category</h3>
                        <p className="text-sm text-slate-500 mt-1">Classify your goal for better tracking</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-gray-100 rounded-full transition-all text-slate-400 hover:text-slate-600"
                    >
                        <X size={20} />
                    </button>
                </div>

                <div className="p-6 overflow-y-auto">
                    <div className="flex flex-col md:flex-row gap-6">
                        {/* Categories Column */}
                        <div className="flex-1">
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-3">
                                Main Category
                            </label>
                            <div className="space-y-2">
                                {categories.map((cat) => (
                                    <button
                                        key={cat.id}
                                        onClick={() => {
                                            setSelectedCategoryId(cat.id);
                                            setSelectedSubCategoryId(null);
                                        }}
                                        className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl border transition-all text-left ${selectedCategoryId === cat.id
                                                ? 'border-transparent bg-opacity-10 ring-1'
                                                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                            }`}
                                        style={selectedCategoryId === cat.id ? {
                                            backgroundColor: `${cat.color}15`,
                                            borderColor: cat.color,
                                            boxShadow: `0 0 0 1px ${cat.color}`
                                        } : {}}
                                    >
                                        <span
                                            className="w-3 h-3 rounded-full flex-shrink-0"
                                            style={{ backgroundColor: cat.color }}
                                        />
                                        <span className={`text-sm font-bold truncate flex-1 ${selectedCategoryId === cat.id ? 'text-slate-900' : 'text-slate-600'}`}>
                                            {cat.name}
                                        </span>
                                        {selectedCategoryId === cat.id && (
                                            <Check size={16} className="ml-auto" style={{ color: cat.color }} strokeWidth={3} />
                                        )}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Sub-Categories Column */}
                        <div className="flex-1">
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-3">
                                Sub-category <span className="font-normal text-slate-300 normal-case">(Optional)</span>
                            </label>
                            <div className="space-y-2">
                                {selectedCategoryId ? (
                                    categories
                                        .find(c => c.id === selectedCategoryId)
                                        ?.subCategories.map((sub) => (
                                            <button
                                                key={sub.id}
                                                onClick={() => setSelectedSubCategoryId(
                                                    selectedSubCategoryId === sub.id ? null : sub.id
                                                )}
                                                className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl border transition-all text-left ${selectedSubCategoryId === sub.id
                                                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                                                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50 text-slate-600'
                                                    }`}
                                            >
                                                <span className="text-sm font-semibold truncate flex-1">
                                                    {sub.name}
                                                </span>
                                                {selectedSubCategoryId === sub.id && (
                                                    <Check size={16} className="ml-auto text-blue-600" strokeWidth={3} />
                                                )}
                                            </button>
                                        ))
                                ) : (
                                    <div className="flex flex-col items-center justify-center py-10 text-slate-400 bg-gray-50 rounded-xl border border-dashed border-gray-200">
                                        <p className="text-xs font-medium italic">Select a main category first</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-gray-100 flex gap-3">
                    <button
                        onClick={() => {
                            setSelectedCategoryId(null);
                            setSelectedSubCategoryId(null);
                        }}
                        className="flex-1 px-4 py-3 bg-white border border-gray-200 text-slate-600 rounded-xl font-bold text-sm hover:bg-gray-50 transition-all"
                    >
                        Reset
                    </button>
                    <button
                        onClick={() => onApply(selectedCategoryId, selectedSubCategoryId)}
                        className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl font-bold text-sm hover:bg-blue-700 transition-all shadow-lg shadow-blue-200"
                    >
                        Apply Filter
                    </button>
                </div>
            </div>
        </div>
    );
};

export default CategorySelectionModal;
