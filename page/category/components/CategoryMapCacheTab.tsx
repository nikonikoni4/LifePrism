/**
 * CategoryMapCacheTab Component
 * 
 * 展示和管理 category_map_cache 表的 AI 分类元数据
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Search, Trash2, ChevronLeft, ChevronRight, Loader2, Edit3, X, Save, Globe, AppWindow, HelpCircle } from 'lucide-react';
import { CategoryTreeItem } from '../../common/types';
import { CategoryMapCacheItem } from '../types';
import { CategoryMapCacheAPI } from '../api';

interface CategoryMapCacheTabProps {
    categories: CategoryTreeItem[];
}

const CategoryMapCacheTab: React.FC<CategoryMapCacheTabProps> = ({ categories }) => {
    // 数据状态
    const [records, setRecords] = useState<CategoryMapCacheItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // 搜索状态
    const [searchTerm, setSearchTerm] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');

    // 应用类型筛选: 'all' | 'multi' | 'single'
    const [appTypeFilter, setAppTypeFilter] = useState<'all' | 'multi' | 'single'>('all');

    // 分页状态
    const [currentPage, setCurrentPage] = useState(1);
    const [totalRecords, setTotalRecords] = useState(0);
    const [totalPages, setTotalPages] = useState(0);
    const [pageSize] = useState(50);

    // 选择状态
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
    const [isProcessing, setIsProcessing] = useState(false);

    // 单条编辑状态
    const [editingRecord, setEditingRecord] = useState<CategoryMapCacheItem | null>(null);
    const [editForm, setEditForm] = useState({
        app_description: '',
        title_analysis: '',
        category_id: '',
        sub_category_id: '',
    });

    // 批量编辑弹窗
    const [showBatchEditModal, setShowBatchEditModal] = useState(false);
    const [batchForm, setBatchForm] = useState({
        app_description: '',
        category_id: '',
        sub_category_id: '',
    });

    // 防抖搜索
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(searchTerm);
            setCurrentPage(1);
        }, 300);
        return () => clearTimeout(timer);
    }, [searchTerm]);

    // 加载数据
    useEffect(() => {
        const fetchData = async () => {
            setIsLoading(true);
            setError(null);

            try {
                const response = await CategoryMapCacheAPI.getList({
                    page: currentPage,
                    page_size: pageSize,
                    search: debouncedSearch || undefined,
                });

                setRecords(response.data);
                setTotalRecords(response.total);
                setTotalPages(response.total_pages);
                setSelectedIds(new Set());
            } catch (err) {
                console.error('Failed to fetch category map cache:', err);
                setError('加载数据失败，请重试');
                setRecords([]);
            } finally {
                setIsLoading(false);
            }
        };

        fetchData();
    }, [currentPage, pageSize, debouncedSearch]);

    // 根据应用类型筛选本地过滤
    const filteredRecords = useMemo(() => {
        if (appTypeFilter === 'all') return records;
        if (appTypeFilter === 'multi') return records.filter(r => r.is_multipurpose_app);
        return records.filter(r => !r.is_multipurpose_app);
    }, [records, appTypeFilter]);

    // 全选/取消全选
    const handleSelectAll = () => {
        if (selectedIds.size === filteredRecords.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(filteredRecords.map(r => r.id)));
        }
    };

    // 单选切换
    const handleSelectOne = (id: number) => {
        const newSelected = new Set(selectedIds);
        if (newSelected.has(id)) {
            newSelected.delete(id);
        } else {
            newSelected.add(id);
        }
        setSelectedIds(newSelected);
    };

    // 打开单条编辑
    const handleOpenEdit = (record: CategoryMapCacheItem) => {
        setEditingRecord(record);
        setEditForm({
            app_description: record.app_description || '',
            title_analysis: record.title_analysis || '',
            category_id: record.category_id || '',
            sub_category_id: record.sub_category_id || '',
        });
    };

    // 保存单条编辑
    const handleSaveEdit = async () => {
        if (!editingRecord) return;

        try {
            setIsProcessing(true);
            await CategoryMapCacheAPI.update(editingRecord.id, {
                app_description: editForm.app_description || null,
                title_analysis: editForm.title_analysis || null,
                category_id: editForm.category_id || null,
                sub_category_id: editForm.sub_category_id || null,
            });

            // 更新本地状态
            setRecords(prev => prev.map(r =>
                r.id === editingRecord.id
                    ? {
                        ...r,
                        app_description: editForm.app_description || null,
                        title_analysis: editForm.title_analysis || null,
                        category_id: editForm.category_id || null,
                        sub_category_id: editForm.sub_category_id || null,
                        category: categories.find(c => c.id === editForm.category_id)?.name || null,
                        sub_category: categories.find(c => c.id === editForm.category_id)?.subcategories?.find(s => s.id === editForm.sub_category_id)?.name || null,
                    }
                    : r
            ));
            setEditingRecord(null);
        } catch (err) {
            console.error('Failed to update record:', err);
            alert('更新失败，请重试');
        } finally {
            setIsProcessing(false);
        }
    };

    // 批量更新
    const handleBatchUpdate = async () => {
        if (selectedIds.size === 0) return;
        if (!batchForm.app_description && !batchForm.category_id) {
            alert('请至少填写一项要修改的内容');
            return;
        }

        try {
            setIsProcessing(true);
            await CategoryMapCacheAPI.batchUpdate({
                ids: Array.from(selectedIds),
                app_description: batchForm.app_description || null,
                category_id: batchForm.category_id || null,
                sub_category_id: batchForm.sub_category_id || null,
            });

            // 刷新数据
            const response = await CategoryMapCacheAPI.getList({
                page: currentPage,
                page_size: pageSize,
                search: debouncedSearch || undefined,
            });
            setRecords(response.data);
            setTotalRecords(response.total);

            setShowBatchEditModal(false);
            setBatchForm({ app_description: '', category_id: '', sub_category_id: '' });
            setSelectedIds(new Set());
            alert(`成功更新 ${selectedIds.size} 条记录`);
        } catch (err) {
            console.error('Failed to batch update:', err);
            alert('批量更新失败，请重试');
        } finally {
            setIsProcessing(false);
        }
    };

    // 单条删除
    const handleDelete = async (recordId: number) => {
        if (!confirm('确定要删除这条记录吗？')) return;

        try {
            await CategoryMapCacheAPI.delete(recordId);
            setRecords(prev => prev.filter(r => r.id !== recordId));
            setTotalRecords(prev => prev - 1);
            selectedIds.delete(recordId);
            setSelectedIds(new Set(selectedIds));
        } catch (err) {
            console.error('Failed to delete record:', err);
            alert('删除失败，请重试');
        }
    };

    // 批量删除
    const handleBatchDelete = async () => {
        if (!confirm(`确定要删除选中的 ${selectedIds.size} 条记录吗？`)) return;

        try {
            setIsProcessing(true);
            await CategoryMapCacheAPI.batchDelete(Array.from(selectedIds));
            setRecords(prev => prev.filter(r => !selectedIds.has(r.id)));
            setTotalRecords(prev => prev - selectedIds.size);
            setSelectedIds(new Set());
            alert(`成功删除 ${selectedIds.size} 条记录`);
        } catch (err) {
            console.error('Failed to batch delete:', err);
            alert('批量删除失败，请重试');
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Filter Bar */}
            <div className="p-6 border-b border-gray-100 flex flex-col xl:flex-row gap-4 justify-between items-center bg-gray-50/50">
                <div className="flex items-center gap-4 w-full xl:w-auto">
                    {/* Search */}
                    <div className="relative flex-1 xl:w-80">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                        <input
                            type="text"
                            placeholder="搜索应用名称或窗口标题..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full pl-9 pr-4 py-2 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300"
                        />
                    </div>
                </div>

                <div className="flex items-center gap-6 w-full xl:w-auto justify-end">
                    {/* App Type Filter */}
                    <div className="bg-gray-100 p-1 rounded-lg inline-flex text-xs font-semibold">
                        <button
                            onClick={() => { setAppTypeFilter('all'); setCurrentPage(1); }}
                            className={`px-3 py-1.5 rounded-md transition-all ${appTypeFilter === 'all'
                                ? 'bg-white text-slate-900 shadow-sm'
                                : 'text-slate-500 hover:text-slate-700'
                                }`}
                        >
                            全部
                        </button>
                        <button
                            onClick={() => { setAppTypeFilter('multi'); setCurrentPage(1); }}
                            className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1 ${appTypeFilter === 'multi'
                                ? 'bg-white text-slate-900 shadow-sm'
                                : 'text-slate-500 hover:text-slate-700'
                                }`}
                        >
                            <Globe size={12} />
                            多用途
                        </button>
                        <button
                            onClick={() => { setAppTypeFilter('single'); setCurrentPage(1); }}
                            className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1 ${appTypeFilter === 'single'
                                ? 'bg-white text-slate-900 shadow-sm'
                                : 'text-slate-500 hover:text-slate-700'
                                }`}
                        >
                            <AppWindow size={12} />
                            单用途
                        </button>
                    </div>

                    <span className="text-sm text-slate-500">
                        {appTypeFilter !== 'all' ? `${filteredRecords.length} / ` : ''}共 {totalRecords} 条记录
                    </span>
                </div>
            </div>

            {/* Batch Actions Bar */}
            {selectedIds.size > 0 && (
                <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-6 py-3 bg-white border border-gray-200 rounded-2xl shadow-xl flex items-center gap-4">
                    <span className="text-sm font-semibold text-indigo-700">
                        已选择 {selectedIds.size} 项
                    </span>
                    <button
                        onClick={() => setShowBatchEditModal(true)}
                        disabled={isProcessing}
                        className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2"
                    >
                        <Edit3 size={14} />
                        批量修改
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
                            重试
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
                                <th className="py-4 px-4 w-14 border-b border-gray-100">
                                    <input
                                        type="checkbox"
                                        checked={selectedIds.size === filteredRecords.length && filteredRecords.length > 0}
                                        onChange={handleSelectAll}
                                        className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                                    />
                                </th>
                                <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-36">应用</th>
                                <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-48">应用描述</th>
                                <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100">窗口标题</th>
                                <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-48">标题分析</th>
                                <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-28">主分类</th>
                                <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-28">子分类</th>
                                <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-20">
                                    <div className="flex items-center gap-1">
                                        状态
                                        <div className="relative group/tooltip">
                                            <HelpCircle size={12} className="text-gray-400 cursor-help" />
                                            <div className="absolute top-1/2 right-full -translate-y-1/2 mr-2 px-3 py-2 bg-slate-800 text-white text-xs rounded-lg opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all whitespace-nowrap z-50 shadow-lg">
                                                当类别被ban时，该缓存也不能使用
                                                <div className="absolute top-1/2 left-full -translate-y-1/2 border-4 border-transparent border-l-slate-800"></div>
                                            </div>
                                        </div>
                                    </div>
                                </th>
                                <th className="py-4 px-4 w-20 border-b border-gray-100"></th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                            {filteredRecords.map((record) => (
                                <tr key={record.id} className="hover:bg-slate-50/80 transition-colors group">
                                    <td className="py-3 px-4">
                                        <input
                                            type="checkbox"
                                            checked={selectedIds.has(record.id)}
                                            onChange={() => handleSelectOne(record.id)}
                                            className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                                        />
                                    </td>
                                    <td className="py-3 px-4">
                                        <div className="text-sm font-semibold text-slate-900 truncate max-w-[130px]" title={record.app}>
                                            {record.app}
                                        </div>
                                    </td>
                                    <td className="py-3 px-4">
                                        <div className="text-sm text-slate-600 truncate max-w-[180px]" title={record.app_description || ''}>
                                            {record.app_description || <span className="text-gray-400 italic">-</span>}
                                        </div>
                                    </td>
                                    <td className="py-3 px-4">
                                        <div className="text-sm text-slate-700 truncate max-w-xs" title={record.title}>
                                            {record.title}
                                        </div>
                                    </td>
                                    <td className="py-3 px-4">
                                        <div className="text-sm text-slate-600 truncate max-w-[180px]" title={record.title_analysis || ''}>
                                            {record.title_analysis || <span className="text-gray-400 italic">-</span>}
                                        </div>
                                    </td>
                                    <td className="py-3 px-4">
                                        <span className="inline-block px-2 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-lg">
                                            {record.category || '-'}
                                        </span>
                                    </td>
                                    <td className="py-3 px-4">
                                        <span className="inline-block px-2 py-1 bg-gray-100 text-gray-600 text-xs font-medium rounded-lg">
                                            {record.sub_category || '-'}
                                        </span>
                                    </td>
                                    <td className="py-3 px-4">
                                        {record.state === 1 ? (
                                            <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs font-medium rounded-lg">
                                                <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                                                启用
                                            </span>
                                        ) : (
                                            <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-50 text-red-600 text-xs font-medium rounded-lg">
                                                <span className="w-1.5 h-1.5 bg-red-500 rounded-full"></span>
                                                禁用
                                            </span>
                                        )}
                                    </td>
                                    <td className="py-3 px-4 text-right">
                                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button
                                                onClick={() => handleOpenEdit(record)}
                                                className="p-2 text-slate-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition-colors"
                                            >
                                                <Edit3 size={16} />
                                            </button>
                                            <button
                                                onClick={() => handleDelete(record.id)}
                                                className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {filteredRecords.length === 0 && (
                        <div className="p-12 text-center text-slate-400">
                            <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4">
                                <Search size={24} className="text-gray-300" />
                            </div>
                            <p className="font-medium">没有找到匹配的记录</p>
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
                        第 {currentPage} / {totalPages} 页
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

            {/* Single Edit Modal */}
            {editingRecord && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl shadow-xl p-6 w-[500px] max-h-[80vh] overflow-y-auto">
                        <h3 className="text-lg font-bold text-slate-900 mb-4">编辑记录</h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">应用</label>
                                <div className="px-3 py-2 bg-gray-100 rounded-lg text-sm text-slate-600">
                                    {editingRecord.app}
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">窗口标题</label>
                                <div className="px-3 py-2 bg-gray-100 rounded-lg text-sm text-slate-600 truncate">
                                    {editingRecord.title}
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">应用描述</label>
                                <textarea
                                    value={editForm.app_description}
                                    onChange={(e) => setEditForm(prev => ({ ...prev, app_description: e.target.value }))}
                                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm"
                                    rows={2}
                                    placeholder="输入应用描述..."
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">标题分析</label>
                                <textarea
                                    value={editForm.title_analysis}
                                    onChange={(e) => setEditForm(prev => ({ ...prev, title_analysis: e.target.value }))}
                                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm"
                                    rows={2}
                                    placeholder="输入标题分析..."
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">主分类</label>
                                <select
                                    value={editForm.category_id}
                                    onChange={(e) => {
                                        setEditForm(prev => ({
                                            ...prev,
                                            category_id: e.target.value,
                                            sub_category_id: '',
                                        }));
                                    }}
                                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm"
                                >
                                    <option value="">-- 请选择 --</option>
                                    {categories.map(cat => (
                                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                                    ))}
                                </select>
                            </div>
                            {editForm.category_id && (
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">子分类</label>
                                    <select
                                        value={editForm.sub_category_id}
                                        onChange={(e) => setEditForm(prev => ({ ...prev, sub_category_id: e.target.value }))}
                                        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm"
                                    >
                                        <option value="">-- 请选择 --</option>
                                        {categories.find(c => c.id === editForm.category_id)?.subcategories?.map(sub => (
                                            <option key={sub.id} value={sub.id}>{sub.name}</option>
                                        ))}
                                    </select>
                                </div>
                            )}
                        </div>
                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={() => setEditingRecord(null)}
                                className="flex-1 px-4 py-2 text-slate-600 bg-gray-100 rounded-lg hover:bg-gray-200 font-medium"
                            >
                                取消
                            </button>
                            <button
                                onClick={handleSaveEdit}
                                disabled={isProcessing}
                                className="flex-1 px-4 py-2 text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 font-medium flex items-center justify-center gap-2"
                            >
                                <Save size={16} />
                                {isProcessing ? '保存中...' : '保存'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Batch Edit Modal */}
            {showBatchEditModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl shadow-xl p-6 w-96">
                        <h3 className="text-lg font-bold text-slate-900 mb-4">批量修改</h3>
                        <p className="text-sm text-slate-500 mb-4">
                            将为选中的 {selectedIds.size} 条记录设置以下内容
                        </p>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">应用描述</label>
                                <textarea
                                    value={batchForm.app_description}
                                    onChange={(e) => setBatchForm(prev => ({ ...prev, app_description: e.target.value }))}
                                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm"
                                    rows={2}
                                    placeholder="留空则不修改..."
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">主分类</label>
                                <select
                                    value={batchForm.category_id}
                                    onChange={(e) => {
                                        setBatchForm(prev => ({
                                            ...prev,
                                            category_id: e.target.value,
                                            sub_category_id: '',
                                        }));
                                    }}
                                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm"
                                >
                                    <option value="">-- 不修改 --</option>
                                    {categories.map(cat => (
                                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                                    ))}
                                </select>
                            </div>
                            {batchForm.category_id && (
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">子分类</label>
                                    <select
                                        value={batchForm.sub_category_id}
                                        onChange={(e) => setBatchForm(prev => ({ ...prev, sub_category_id: e.target.value }))}
                                        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm"
                                    >
                                        <option value="">-- 请选择 --</option>
                                        {categories.find(c => c.id === batchForm.category_id)?.subcategories?.map(sub => (
                                            <option key={sub.id} value={sub.id}>{sub.name}</option>
                                        ))}
                                    </select>
                                </div>
                            )}
                        </div>
                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={() => {
                                    setShowBatchEditModal(false);
                                    setBatchForm({ app_description: '', category_id: '', sub_category_id: '' });
                                }}
                                className="flex-1 px-4 py-2 text-slate-600 bg-gray-100 rounded-lg hover:bg-gray-200 font-medium"
                            >
                                取消
                            </button>
                            <button
                                onClick={handleBatchUpdate}
                                disabled={isProcessing}
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

export default CategoryMapCacheTab;
