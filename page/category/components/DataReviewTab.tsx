/**
 * DataReviewTab Component
 * 
 * 数据审核选项卡，用于查看和管理活动记录
 */

import React, { useState, useEffect } from 'react';
import { Search, Filter, Trash2, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { CategoryTreeItem, ActivityLogItem } from '../../common/types';
import { ActivityLogsAPI } from '../../common/api';

// 格式化日期为 YYYY-MM-DD
const formatDate = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

// 格式化时长（秒 → 可读格式）
const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
};

// 格式化时间（提取 HH:MM）
const formatTime = (timeStr: string): string => {
    try {
        const date = new Date(timeStr);
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${hours}:${minutes}`;
    } catch {
        return timeStr;
    }
};

interface DataReviewTabProps {
    categories: CategoryTreeItem[];
}

const DataReviewTab: React.FC<DataReviewTabProps> = ({ categories }) => {
    // 筛选状态 - 默认显示今天
    const today = formatDate(new Date());
    const [showUncategorized, setShowUncategorized] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [dateRange, setDateRange] = useState({ start: today, end: today });

    // 数据状态
    const [records, setRecords] = useState<ActivityLogItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // 分页状态
    const [currentPage, setCurrentPage] = useState(1);
    const [totalRecords, setTotalRecords] = useState(0);
    const [pageSize] = useState(50);

    // 加载数据
    useEffect(() => {
        const fetchLogs = async () => {
            setIsLoading(true);
            setError(null);

            try {
                // 构建时间范围参数
                const startTime = `${dateRange.start} 00:00:00`;
                const endTime = `${dateRange.end} 23:59:59`;

                const response = await ActivityLogsAPI.getLogs({
                    start_time: startTime,
                    end_time: endTime,
                    page: currentPage,
                    page_size: pageSize,
                    sort_by: 'duration',
                    sort_order: 'desc',
                    category_id: showUncategorized ? 'other' : undefined,
                    sub_category_id: showUncategorized ? 'untracked' : undefined,
                });

                setRecords(response.data);
                setTotalRecords(response.total);
            } catch (err) {
                console.error('Failed to fetch activity logs:', err);
                setError('Failed to load activity logs. Please try again.');
                setRecords([]);
            } finally {
                setIsLoading(false);
            }
        };

        fetchLogs();
    }, [dateRange, currentPage, pageSize, showUncategorized]);

    // 本地搜索过滤
    const filteredRecords = records.filter(record => {
        if (!searchTerm) return true;
        return (
            record.app.toLowerCase().includes(searchTerm.toLowerCase()) ||
            record.title.toLowerCase().includes(searchTerm.toLowerCase())
        );
    });

    const getCategoryColor = (catId: string | undefined) => {
        if (!catId) return '#CBD5E1';
        const cat = categories.find(c => c.id === catId);
        return cat ? cat.color : '#CBD5E1';
    };

    const totalPages = Math.ceil(totalRecords / pageSize);

    return (
        <div className="flex flex-col h-full">
            {/* Filter Bar */}
            <div className="p-6 border-b border-gray-100 flex flex-col xl:flex-row gap-4 justify-between items-center bg-gray-50/50">
                <div className="flex items-center gap-4 w-full xl:w-auto">
                    {/* Date Range Picker */}
                    <div className="flex items-center bg-white border border-gray-200 rounded-xl px-2 py-1.5 text-sm font-medium text-slate-600 shadow-sm gap-2">
                        <input
                            type="date"
                            value={dateRange.start}
                            onChange={(e) => {
                                setDateRange(prev => ({ ...prev, start: e.target.value }));
                                setCurrentPage(1);
                            }}
                            className="bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-100 rounded-lg p-1 text-slate-600 text-xs font-bold font-mono cursor-pointer hover:bg-gray-50 transition-colors"
                        />
                        <span className="text-gray-300">→</span>
                        <input
                            type="date"
                            value={dateRange.end}
                            onChange={(e) => {
                                setDateRange(prev => ({ ...prev, end: e.target.value }));
                                setCurrentPage(1);
                            }}
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

                {/* Toggles & Pagination Info */}
                <div className="flex items-center gap-6 w-full xl:w-auto justify-end">
                    <span className="text-sm text-slate-500">
                        {totalRecords} records
                    </span>
                    <div className="flex items-center gap-3 cursor-pointer" onClick={() => {
                        setShowUncategorized(!showUncategorized);
                        setCurrentPage(1);
                    }}>
                        <span className="text-sm font-semibold text-slate-600">Show Uncategorized Only</span>
                        <div className={`w-11 h-6 rounded-full p-1 transition-colors ${showUncategorized ? 'bg-indigo-600' : 'bg-gray-200'}`}>
                            <div className={`w-4 h-4 bg-white rounded-full shadow-sm transform transition-transform ${showUncategorized ? 'translate-x-5' : 'translate-x-0'}`} />
                        </div>
                    </div>
                </div>
            </div>

            {/* Loading State */}
            {isLoading && (
                <div className="flex-1 flex items-center justify-center">
                    <Loader2 size={32} className="animate-spin text-blue-500" />
                </div>
            )}

            {/* Error State */}
            {error && !isLoading && (
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                        <p className="text-red-500 mb-2">{error}</p>
                        <button
                            onClick={() => setCurrentPage(currentPage)}
                            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
                        >
                            Retry
                        </button>
                    </div>
                </div>
            )}

            {/* Table */}
            {!isLoading && !error && (
                <div className="flex-1 overflow-auto">
                    <table className="w-full text-left border-collapse">
                        <thead className="bg-gray-50 sticky top-0 z-10">
                            <tr>
                                <th className="py-4 px-6 w-12 border-b border-gray-100">
                                    <input type="checkbox" className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                                </th>
                                <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100">App</th>
                                <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100">Window Title</th>
                                <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-24">Duration</th>
                                <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-32">Time</th>
                                <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-40">Category</th>
                                <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-40">Sub-category</th>
                                <th className="py-4 px-6 w-16 border-b border-gray-100"></th>
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
                                                {record.app.charAt(0).toUpperCase()}
                                            </div>
                                            <div>
                                                <div className="text-sm font-bold text-slate-900">{record.app}</div>
                                                <div className="text-xs text-slate-400 mt-0.5 font-medium">{formatDuration(record.duration)}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="py-4 px-6">
                                        <div className="text-sm text-slate-600 font-medium truncate max-w-xs" title={record.title}>
                                            {record.title}
                                        </div>
                                    </td>
                                    <td className="py-4 px-6">
                                        <div className="text-sm font-mono font-semibold text-slate-700">
                                            {Math.round(record.duration / 60)}m
                                        </div>
                                    </td>
                                    <td className="py-4 px-6">
                                        <div className="text-xs text-slate-500 font-mono">
                                            {formatTime(record.start_time)} - {formatTime(record.end_time)}
                                        </div>
                                    </td>
                                    <td className="py-4 px-6">
                                        <div className="relative">
                                            <select
                                                className="appearance-none w-full pl-3 pr-8 py-1.5 bg-white border border-gray-200 rounded-lg text-sm font-semibold text-slate-700 focus:outline-none focus:border-blue-400 cursor-pointer hover:bg-gray-50"
                                                defaultValue={record.category_id || ''}
                                            >
                                                <option value="">-- Select --</option>
                                                {categories.map(cat => (
                                                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                                                ))}
                                            </select>
                                            <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
                                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getCategoryColor(record.category_id) }}></div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="py-4 px-6">
                                        <div className="relative">
                                            <select
                                                className="appearance-none w-full px-3 py-1.5 bg-gray-50 border border-transparent hover:border-gray-200 rounded-lg text-sm text-slate-600 focus:outline-none focus:bg-white focus:border-blue-400 cursor-pointer"
                                                defaultValue={record.sub_category_id || ''}
                                            >
                                                <option value="">-- Select --</option>
                                                {categories.find(c => c.id === record.category_id)?.subcategories?.map(sub => (
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
            )}

            {/* Pagination */}
            {!isLoading && !error && totalPages > 1 && (
                <div className="p-4 border-t border-gray-100 flex items-center justify-center gap-4">
                    <button
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                        className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <ChevronLeft size={20} />
                    </button>
                    <span className="text-sm text-slate-600">
                        Page {currentPage} of {totalPages}
                    </span>
                    <button
                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages}
                        className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <ChevronRight size={20} />
                    </button>
                </div>
            )}
        </div>
    );
};

export default DataReviewTab;
