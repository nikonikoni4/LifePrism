/**
 * DataReviewTab Component
 * 
 * 数据审核选项卡，用于查看和管理活动记录
 */

import React, { useState } from 'react';
import { Search, Filter, Trash2 } from 'lucide-react';
import { CategoryTreeItem, ActivityRecord } from '../types';

// Mock data - TODO: Replace with actual API call
const MOCK_ACTIVITY_RECORDS: ActivityRecord[] = [
    {
        id: '1',
        appName: 'Chrome',
        windowTitle: 'YouTube - Home',
        timestamp: '2023-10-25 14:30',
        duration: '45m',
        aiDescription: 'Watching videos',
        categoryId: 'entertainment',
        subCategoryId: 'video',
    },
    {
        id: '2',
        appName: 'VS Code',
        windowTitle: 'main.py - LifeWatch',
        timestamp: '2023-10-25 15:15',
        duration: '2h 30m',
        aiDescription: 'Programming',
        categoryId: 'work',
        subCategoryId: 'coding',
    },
];

interface DataReviewTabProps {
    categories: CategoryTreeItem[];
}

const DataReviewTab: React.FC<DataReviewTabProps> = ({ categories }) => {
    const [showUncategorized, setShowUncategorized] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [records, setRecords] = useState<ActivityRecord[]>(MOCK_ACTIVITY_RECORDS);
    const [dateRange, setDateRange] = useState({ start: '2023-10-25', end: '2023-10-26' });

    const filteredRecords = records.filter(record => {
        const matchesSearch =
            record.appName.toLowerCase().includes(searchTerm.toLowerCase()) ||
            record.windowTitle.toLowerCase().includes(searchTerm.toLowerCase());

        const matchesUncategorized = showUncategorized
            ? (record.categoryId === 'other' && record.subCategoryId === 'untracked')
            : true;

        return matchesSearch && matchesUncategorized;
    });

    const getCategoryColor = (catId: string) => {
        const cat = categories.find(c => c.id === catId);
        return cat ? cat.color : '#CBD5E1';
    };

    return (
        <div className="flex flex-col h-full">
            {/* Filter Bar */}
            <div className="p-6 border-b border-gray-100 flex flex-col xl:flex-row gap-4 justify-between items-center bg-gray-50/50">
                <div className="flex items-center gap-4 w-full xl:w-auto">
                    {/* Date Picker Range */}
                    <div className="flex items-center bg-white border border-gray-200 rounded-xl px-2 py-1.5 text-sm font-medium text-slate-600 shadow-sm gap-2">
                        <input
                            type="date"
                            value={dateRange.start}
                            onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
                            className="bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-100 rounded-lg p-1 text-slate-600 text-xs font-bold font-mono cursor-pointer hover:bg-gray-50 transition-colors"
                        />
                        <span className="text-gray-300">→</span>
                        <input
                            type="date"
                            value={dateRange.end}
                            onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
                            className="bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-100 rounded-lg p-1 text-slate-600 text-xs font-bold font-mono cursor-pointer hover:bg-gray-50 transition-colors"
                        />
                    </div>

                    {/* Search */}
                    <div className="relative flex-1 xl:w-64">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                        <input
                            type="text"
                            placeholder="Search App or Title..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full pl-9 pr-4 py-2 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300"
                        />
                    </div>
                </div>

                {/* Toggles */}
                <div className="flex items-center gap-6 w-full xl:w-auto justify-end">
                    <div className="flex items-center gap-3 cursor-pointer" onClick={() => setShowUncategorized(!showUncategorized)}>
                        <span className="text-sm font-semibold text-slate-600">Show Uncategorized Only</span>
                        <div className={`w-11 h-6 rounded-full p-1 transition-colors ${showUncategorized ? 'bg-indigo-600' : 'bg-gray-200'}`}>
                            <div className={`w-4 h-4 bg-white rounded-full shadow-sm transform transition-transform ${showUncategorized ? 'translate-x-5' : 'translate-x-0'}`} />
                        </div>
                    </div>
                </div>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto">
                <table className="w-full text-left border-collapse">
                    <thead className="bg-gray-50 sticky top-0 z-10">
                        <tr>
                            <th className="py-4 px-6 w-12 border-b border-gray-100">
                                <input type="checkbox" className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                            </th>
                            <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100">App Info</th>
                            <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100">Window Title</th>
                            <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-48">Category (L1)</th>
                            <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-48">Sub-category (L2)</th>
                            <th className="py-4 px-6 w-20 border-b border-gray-100"></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                        {filteredRecords.map((record) => (
                            <tr key={record.id} className="hover:bg-slate-50/80 transition-colors group">
                                <td className="py-4 px-6">
                                    <input type="checkbox" className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                                </td>
                                <td className="py-4 px-6">
                                    <div className="flex items-start gap-3">
                                        <div className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center text-slate-600 font-bold text-sm border border-gray-200">
                                            {record.appName.charAt(0)}
                                        </div>
                                        <div>
                                            <div className="text-sm font-bold text-slate-900">{record.appName}</div>
                                            <div className="text-xs text-slate-400 mt-0.5 font-medium">{record.aiDescription}</div>
                                        </div>
                                    </div>
                                </td>
                                <td className="py-4 px-6">
                                    <div className="text-sm text-slate-600 font-medium truncate max-w-xs" title={record.windowTitle}>
                                        {record.windowTitle}
                                    </div>
                                    <div className="text-xs text-slate-400 mt-0.5">{record.timestamp} • {record.duration}</div>
                                </td>
                                <td className="py-4 px-6">
                                    <div className="relative">
                                        <select
                                            className="appearance-none w-full pl-3 pr-8 py-1.5 bg-white border border-gray-200 rounded-lg text-sm font-semibold text-slate-700 focus:outline-none focus:border-blue-400 cursor-pointer hover:bg-gray-50"
                                            defaultValue={record.categoryId}
                                        >
                                            {categories.map(cat => (
                                                <option key={cat.id} value={cat.id}>{cat.name}</option>
                                            ))}
                                        </select>
                                        <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
                                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getCategoryColor(record.categoryId) }}></div>
                                        </div>
                                    </div>
                                </td>
                                <td className="py-4 px-6">
                                    <div className="relative">
                                        <select
                                            className="appearance-none w-full px-3 py-1.5 bg-gray-50 border border-transparent hover:border-gray-200 rounded-lg text-sm text-slate-600 focus:outline-none focus:bg-white focus:border-blue-400 cursor-pointer"
                                            defaultValue={record.subCategoryId}
                                        >
                                            {categories.find(c => c.id === record.categoryId)?.subcategories?.map(sub => (
                                                <option key={sub.id} value={sub.id}>{sub.name}</option>
                                            ))}
                                        </select>
                                    </div>
                                </td>
                                <td className="py-4 px-6 text-right">
                                    <button className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100">
                                        <Trash2 size={16} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>

                {filteredRecords.length === 0 && (
                    <div className="p-12 text-center text-slate-400">
                        <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4">
                            <Filter size={24} className="text-gray-300" />
                        </div>
                        <p className="font-medium">No records found matching your filters.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default DataReviewTab;
