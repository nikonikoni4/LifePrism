/**
 * DataReviewTab Component
 * 
 * 数据审核选项卡，用于查看和管理活动记录
 */

import React, { useState, useEffect } from 'react';
import { Search, Filter, Trash2, ChevronLeft, ChevronRight, Loader2, Edit3, X, ArrowUp, ArrowDown } from 'lucide-react';
import { CategoryTreeItem, ActivityLogItem } from '../../../../../core/types/common-components';
import { ActivityLogsAPI } from '../../../../../core/services/commonApi';
import { toISOStringUTC } from '../../../../../core/utils/dateUtils';

// 排序字段类型
type SortField = 'duration' | 'timestamp';

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

    // 排序状态
    const [sortBy, setSortBy] = useState<SortField>('duration');
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

    // 数据状态
    const [records, setRecords] = useState<ActivityLogItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // 分页状态
    const [currentPage, setCurrentPage] = useState(1);
    const [totalRecords, setTotalRecords] = useState(0);
    const [pageSize] = useState(50);

    // 选择状态
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [isProcessing, setIsProcessing] = useState(false);

    // 批量分类修改弹窗
    const [showBatchCategoryModal, setShowBatchCategoryModal] = useState(false);
    const [batchCategoryId, setBatchCategoryId] = useState('');
    const [batchSubCategoryId, setBatchSubCategoryId] = useState('');

    // 加载数据
    useEffect(() => {
        const fetchLogs = async () => {
            setIsLoading(true);
            setError(null);

            try {
                // 构建时间范围参数（本地日期 → UTC ISO 8601）
                // 符合 time-handling-rules 组件内转换原则
                const startOfDay = new Date(`${dateRange.start}T00:00:00`);
                const endOfDay = new Date(`${dateRange.end}T23:59:59.999`);

                // 将前端排序字段映射到后端字段
                const backendSortBy = sortBy === 'timestamp' ? 'start_time' : sortBy;

                const response = await ActivityLogsAPI.getLogs({
                    start_time: toISOStringUTC(startOfDay),
                    end_time: toISOStringUTC(endOfDay),
                    page: currentPage,
                    page_size: pageSize,
                    sort_by: backendSortBy,
                    sort_order: sortOrder,
                    category_id: showUncategorized ? 'other' : undefined,
                    sub_category_id: showUncategorized ? 'untracked' : undefined,
                });

                setRecords(response.data);
                setTotalRecords(response.total);
                // 清除选择
                setSelectedIds(new Set());
            } catch (err) {
                console.error('Failed to fetch activity logs:', err);
                setError('Failed to load activity logs. Please try again.');
                setRecords([]);
            } finally {
                setIsLoading(false);
            }
        };

        fetchLogs();
    }, [dateRange, currentPage, pageSize, showUncategorized, sortBy, sortOrder]);

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

    // 处理排序点击
    const handleSort = (field: SortField) => {
        if (sortBy === field) {
            // 如果点击同一列，切换排序方向
            setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
        } else {
            // 切换到新的排序字段，默认降序
            setSortBy(field);
            setSortOrder('desc');
        }
        setCurrentPage(1); // 排序后回到第一页
    };

    // 渲染排序图标 - 双箭头样式
    const renderSortIcon = (field: SortField) => {
        const isActive = sortBy === field;
        return (
            <span className="inline-flex flex-col items-center ml-1 -my-1">
                <ArrowUp
                    size={10}
                    className={`${isActive && sortOrder === 'asc' ? 'text-indigo-600' : 'text-gray-300'} transition-colors`}
                    strokeWidth={2.5}
                />
                <ArrowDown
                    size={10}
                    className={`-mt-1 ${isActive && sortOrder === 'desc' ? 'text-indigo-600' : 'text-gray-300'} transition-colors`}
                    strokeWidth={2.5}
                />
            </span>
        );
    };

    // 全选/取消全选
    const handleSelectAll = () => {
        if (selectedIds.size === filteredRecords.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(filteredRecords.map(r => r.id)));
        }
    };

    // 单选切换
    const handleSelectOne = (id: string) => {
        const newSelected = new Set(selectedIds);
        if (newSelected.has(id)) {
            newSelected.delete(id);
        } else {
            newSelected.add(id);
        }
        setSelectedIds(newSelected);
    };

    // 单条分类变更处理
    const handleCategoryChange = async (logId: string, newCategoryId: string) => {
        try {
            await ActivityLogsAPI.updateCategory(logId, newCategoryId);
            // 更新本地状态
            setRecords(prev => prev.map(r =>
                r.id === logId ? { ...r, category_id: newCategoryId, sub_category_id: undefined } : r
            ));
        } catch (err) {
            console.error('Failed to update category:', err);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: '更新分类失败，请重试' });
            } else {
                alert('更新分类失败，请重试');
            }
        }
    };

    // 子分类变更处理
    const handleSubCategoryChange = async (logId: string, categoryId: string, newSubCategoryId: string) => {
        try {
            await ActivityLogsAPI.updateCategory(logId, categoryId, newSubCategoryId || undefined);
            // 更新本地状态
            setRecords(prev => prev.map(r =>
                r.id === logId ? { ...r, sub_category_id: newSubCategoryId || undefined } : r
            ));
        } catch (err) {
            console.error('Failed to update sub-category:', err);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: '更新子分类失败，请重试' });
            } else {
                alert('更新子分类失败，请重试');
            }
        }
    };

    // 单条删除处理
    const handleDelete = async (logId: string) => {
        console.log('=== [DataReview] handleDelete 开始 ===');

        console.log('[DataReview] 即将显示 confirm 对话框');

        const confirmed = window.electronAPI?.showConfirm
            ? await window.electronAPI.showConfirm({ message: '确定要删除这条记录吗？此操作不可撤销。' })
            : confirm('确定要删除这条记录吗？此操作不可撤销。');

        if (!confirmed) {
            console.log('[DataReview] confirm 取消');

            // 检查所有输入框的状态
            setTimeout(() => {
                const inputs = document.querySelectorAll('input, textarea');
                console.log('[DataReview] confirm取消后，输入框总数:', inputs.length);
                inputs.forEach((input, idx) => {
                    const el = input as HTMLInputElement;
                    if (idx < 5) { // 只检查前5个
                        console.log(`  输入框 ${idx}:`, {
                            tagName: el.tagName,
                            type: el.type || 'N/A',
                            disabled: el.disabled,
                            readOnly: el.readOnly,
                            tabIndex: el.tabIndex,
                            style_pointerEvents: el.style.pointerEvents,
                            computed_pointerEvents: window.getComputedStyle(el).pointerEvents,
                            computed_display: window.getComputedStyle(el).display,
                        });
                    }
                });

                // 尝试手动聚焦到第一个输入框
                const firstInput = inputs[0] as HTMLInputElement;
                if (firstInput) {
                    console.log('[DataReview] 尝试focus到第一个输入框');
                    firstInput.focus();
                    setTimeout(() => {
                        console.log('[DataReview] focus后，activeElement:', document.activeElement?.tagName);
                        console.log('[DataReview] focus后，是否是该输入框:', document.activeElement === firstInput);
                    }, 100);
                }
            }, 100);

            console.log('=== [DataReview] handleDelete 结束（取消） ===');
            return;
        }

        console.log('[DataReview] confirm 确认');

        try {
            await ActivityLogsAPI.deleteLog(logId);
            setRecords(prev => prev.filter(r => r.id !== logId));
            setTotalRecords(prev => prev - 1);
            selectedIds.delete(logId);
            setSelectedIds(new Set(selectedIds));
        } catch (err) {
            console.error('Failed to delete log:', err);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: '删除失败，请重试' });
            } else {
                alert('删除失败，请重试');
            }
        }
        console.log('=== [DataReview] handleDelete 结束 ===');
    };

    // 批量删除
    const handleBatchDelete = async () => {
        const confirmed = window.electronAPI?.showConfirm
            ? await window.electronAPI.showConfirm({ message: `确定要删除选中的 ${selectedIds.size} 条记录吗？此操作不可撤销。` })
            : confirm(`确定要删除选中的 ${selectedIds.size} 条记录吗？此操作不可撤销。`);

        if (!confirmed) return;

        try {
            setIsProcessing(true);
            const result = await ActivityLogsAPI.batchDeleteLogs(Array.from(selectedIds));
            const deletedCount = result?.data?.deleted_count ?? selectedIds.size;
            setRecords(prev => prev.filter(r => !selectedIds.has(r.id)));
            setTotalRecords(prev => prev - deletedCount);
            setSelectedIds(new Set());
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: `成功删除 ${deletedCount} 条记录` });
            } else {
                alert(`成功删除 ${deletedCount} 条记录`);
            }
        } catch (err) {
            console.error('Failed to batch delete:', err);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: '批量删除失败，请重试' });
            } else {
                alert('批量删除失败，请重试');
            }
        } finally {
            setIsProcessing(false);
        }
    };

    // 批量分类修改
    const handleBatchCategoryUpdate = async () => {
        if (!batchCategoryId) {
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: '请选择分类' });
            } else {
                alert('请选择分类');
            }
            return;
        }
        try {
            setIsProcessing(true);
            const result = await ActivityLogsAPI.batchUpdateCategory(
                Array.from(selectedIds),
                batchCategoryId,
                batchSubCategoryId || undefined
            );
            const updatedCount = result?.data?.updated_count ?? selectedIds.size;
            // 更新本地状态
            setRecords(prev => prev.map(r =>
                selectedIds.has(r.id) ? { ...r, category_id: batchCategoryId, sub_category_id: batchSubCategoryId || undefined } : r
            ));
            setShowBatchCategoryModal(false);
            setBatchCategoryId('');
            setBatchSubCategoryId('');
            setSelectedIds(new Set());
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: `成功更新 ${updatedCount} 条记录的分类` });
            } else {
                alert(`成功更新 ${updatedCount} 条记录的分类`);
            }
        } catch (err) {
            console.error('Failed to batch update category:', err);
            if (window.electronAPI?.showAlert) {
                window.electronAPI.showAlert({ message: '批量更新分类失败，请重试' });
            } else {
                alert('批量更新分类失败，请重试');
            }
        } finally {
            setIsProcessing(false);
        }
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

            {/* Batch Actions Bar - 固定在底部，不影响布局 */}
            {selectedIds.size > 0 && (
                <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-6 py-3 bg-white border border-gray-200 rounded-2xl shadow-xl flex items-center gap-4">
                    <span className="text-sm font-semibold text-indigo-700">
                        已选择 {selectedIds.size} 项
                    </span>
                    <button
                        onClick={() => setShowBatchCategoryModal(true)}
                        disabled={isProcessing}
                        className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2"
                    >
                        <Edit3 size={14} />
                        批量修改分类
                    </button>
                    <button
                        onClick={handleBatchDelete}
                        disabled={isProcessing}
                        className="px-4 py-2 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 disabled:opacity-50 flex items-center gap-2"
                    >
                        <Trash2 size={14} />
                        批量删除
                    </button>
                    <button
                        onClick={() => setSelectedIds(new Set())}
                        className="px-4 py-2 text-slate-600 text-sm font-medium hover:bg-gray-100 rounded-lg flex items-center gap-2"
                    >
                        <X size={14} />
                        取消选择
                    </button>
                </div>
            )}

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
                                <th className="py-4 px-6 w-14 border-b border-gray-100">
                                    <input
                                        type="checkbox"
                                        checked={selectedIds.size === filteredRecords.length && filteredRecords.length > 0}
                                        onChange={handleSelectAll}
                                        className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                                    />
                                </th>
                                <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100">App</th>
                                <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100">Window Title</th>
                                <th
                                    className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-24 cursor-pointer hover:bg-gray-100 hover:text-slate-700 transition-colors select-none"
                                    onClick={() => handleSort('duration')}
                                >
                                    Duration{renderSortIcon('duration')}
                                </th>
                                <th
                                    className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-32 cursor-pointer hover:bg-gray-100 hover:text-slate-700 transition-colors select-none"
                                    onClick={() => handleSort('timestamp')}
                                >
                                    Time{renderSortIcon('timestamp')}
                                </th>
                                <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-40">Category</th>
                                <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-40">Sub-category</th>
                                <th className="py-4 px-6 w-16 border-b border-gray-100"></th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                            {filteredRecords.map((record) => (
                                <tr key={record.id} className="hover:bg-slate-50/80 transition-colors group">
                                    <td className="py-4 px-6">
                                        <input
                                            type="checkbox"
                                            checked={selectedIds.has(record.id)}
                                            onChange={() => handleSelectOne(record.id)}
                                            className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                                        />
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
                                                value={record.category_id || ''}
                                                onChange={(e) => handleCategoryChange(record.id, e.target.value)}
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
                                                value={record.sub_category_id || ''}
                                                onChange={(e) => handleSubCategoryChange(record.id, record.category_id || '', e.target.value)}
                                                disabled={!record.category_id}
                                            >
                                                <option value="">-- Select --</option>
                                                {categories.find(c => c.id === record.category_id)?.subcategories?.map(sub => (
                                                    <option key={sub.id} value={sub.id}>{sub.name}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </td>
                                    <td className="py-4 px-6 text-right">
                                        <button
                                            onClick={() => handleDelete(record.id)}
                                            className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                                        >
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

            {/* Batch Category Modal */}
            {showBatchCategoryModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl shadow-xl p-6 w-96">
                        <h3 className="text-lg font-bold text-slate-900 mb-4">批量修改分类</h3>
                        <p className="text-sm text-slate-500 mb-4">
                            将为选中的 {selectedIds.size} 条记录设置新的分类
                        </p>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">主分类</label>
                                <select
                                    value={batchCategoryId}
                                    onChange={(e) => {
                                        setBatchCategoryId(e.target.value);
                                        setBatchSubCategoryId('');
                                    }}
                                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400"
                                >
                                    <option value="">-- 请选择 --</option>
                                    {categories.map(cat => (
                                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                                    ))}
                                </select>
                            </div>
                            {batchCategoryId && (
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">子分类（可选）</label>
                                    <select
                                        value={batchSubCategoryId}
                                        onChange={(e) => setBatchSubCategoryId(e.target.value)}
                                        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400"
                                    >
                                        <option value="">-- 请选择 --</option>
                                        {categories.find(c => c.id === batchCategoryId)?.subcategories?.map(sub => (
                                            <option key={sub.id} value={sub.id}>{sub.name}</option>
                                        ))}
                                    </select>
                                </div>
                            )}
                        </div>
                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={() => {
                                    setShowBatchCategoryModal(false);
                                    setBatchCategoryId('');
                                    setBatchSubCategoryId('');
                                }}
                                className="flex-1 px-4 py-2 text-slate-600 bg-gray-100 rounded-lg hover:bg-gray-200 font-medium"
                            >
                                取消
                            </button>
                            <button
                                onClick={handleBatchCategoryUpdate}
                                disabled={!batchCategoryId || isProcessing}
                                className="flex-1 px-4 py-2 text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 font-medium"
                            >
                                {isProcessing ? '处理中...' : '确认修改'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default DataReviewTab;
