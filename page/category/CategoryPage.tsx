/**
 * Category Page (V2)
 * 
 * 分类管理页面，包含分类设置和数据审核两个选项卡
 */

import React, { useState, useEffect } from 'react';
import { CategoryTreeItem } from './types';
import { CategoryAPI } from './api';
import DataReviewTab from './components/DataReviewTab';
import CategorySettingsTab from './components/CategorySettingsTab';

type Tab = 'settings' | 'review';

const CategoryPage: React.FC = () => {
    const [activeTab, setActiveTab] = useState<Tab>('settings');
    const [categories, setCategories] = useState<CategoryTreeItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Load categories from API on mount
    useEffect(() => {
        loadCategories();
    }, []);

    const loadCategories = async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await CategoryAPI.getTree(2);
            setCategories(data);
        } catch (err) {
            console.error('Failed to load categories:', err);
            setError('Failed to load categories. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="max-w-7xl mx-auto h-[calc(100vh-100px)] flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                    <p className="text-slate-500">Loading categories...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="max-w-7xl mx-auto h-[calc(100vh-100px)] flex items-center justify-center">
                <div className="text-center">
                    <p className="text-red-500 mb-4">{error}</p>
                    <button
                        onClick={loadCategories}
                        className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                    >
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-7xl mx-auto h-[calc(100vh-100px)] flex flex-col">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 flex-shrink-0">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Categorization</h1>
                    <p className="text-slate-500 mt-1 font-medium">Manage activity data and classification rules.</p>
                </div>

                {/* Segmented Control */}
                <div className="bg-gray-100 p-1.5 rounded-xl inline-flex font-semibold text-sm">
                    <button
                        onClick={() => setActiveTab('settings')}
                        className={`px-6 py-2 rounded-lg transition-all ${activeTab === 'settings'
                            ? 'bg-white text-slate-900 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700'
                            }`}
                    >
                        Category Settings
                    </button>
                    <button
                        onClick={() => setActiveTab('review')}
                        className={`px-6 py-2 rounded-lg transition-all ${activeTab === 'review'
                            ? 'bg-white text-slate-900 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700'
                            }`}
                    >
                        Data Review
                    </button>
                </div>
            </div>

            {/* Tab Content */}
            <div className="flex-1 min-h-0 bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                {activeTab === 'review' ? (
                    <DataReviewTab categories={categories} />
                ) : (
                    <CategorySettingsTab categories={categories} setCategories={setCategories} />
                )}
            </div>
        </div>
    );
};

export default CategoryPage;
