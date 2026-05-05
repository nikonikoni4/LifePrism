import React, { useState, useEffect } from 'react';
import { FolderOpen, Plus, FolderSearch, Trash2, Edit3 } from 'lucide-react';
import { AddOnAPI } from '../api';
import { ExpandDir, ExpandDirCreate } from '../types';
import { toast } from '../../../core/components';

export const ExpandDirManager: React.FC = () => {
    const [expandDirs, setExpandDirs] = useState<ExpandDir[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isElectron, setIsElectron] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [tempData, setTempData] = useState<Partial<ExpandDirCreate>>({});

    // 加载数据
    useEffect(() => {
        const loadData = async () => {
            try {
                setIsLoading(true);
                const data = await AddOnAPI.getExpandDirs();
                setExpandDirs(data);
                setIsElectron(!!window.electronAPI);
            } catch (err) {
                toast.error(err instanceof Error ? err.message : '加载失败');
            } finally {
                setIsLoading(false);
            }
        };

        loadData();
    }, []);

    // 添加新文件夹
    const handleAddNew = () => {
        const tempId = 'temp-new';
        setEditingId(tempId);
        setTempData({
            name: '',
            path: '',
            description: '',
            ai_index: false,
        });

        const tempItem: ExpandDir = {
            id: tempId,
            name: '',
            path: '',
            description: '',
            ai_index: false,
            created_at: new Date().toISOString(),
        };
        setExpandDirs([tempItem, ...expandDirs]);
    };

    // 保存新文件夹
    const handleSaveNew = async () => {
        if (!tempData.name || !tempData.path) {
            toast.error('请填写名称和路径');
            return;
        }

        try {
            const createData: ExpandDirCreate = {
                name: tempData.name,
                path: tempData.path,
                description: tempData.description || '',
                ai_index: tempData.ai_index || false,
            };

            const created = await AddOnAPI.createExpandDir(createData);

            setExpandDirs(prev => [created, ...prev.filter(d => d.id !== 'temp-new')]);
            setEditingId(null);
            setTempData({});
            toast.success('创建成功');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '创建失败');
        }
    };

    // 取消创建
    const handleCancelNew = () => {
        setExpandDirs(prev => prev.filter(d => d.id !== 'temp-new'));
        setEditingId(null);
        setTempData({});
    };

    // 开始编辑
    const handleStartEdit = (dir: ExpandDir) => {
        setEditingId(dir.id);
        setTempData({
            name: dir.name,
            path: dir.path,
            description: dir.description,
            ai_index: dir.ai_index,
        });
    };

    // 保存编辑
    const handleSaveEdit = async (id: string) => {
        if (!tempData.name || !tempData.path) {
            toast.error('请填写名称和路径');
            return;
        }

        try {
            const updateData: ExpandDirCreate = {
                name: tempData.name,
                path: tempData.path,
                description: tempData.description || '',
                ai_index: tempData.ai_index || false,
            };

            const updated = await AddOnAPI.updateExpandDir(id, updateData);

            setExpandDirs(prev => prev.map(d => d.id === id ? updated : d));
            setEditingId(null);
            setTempData({});
            toast.success('更新成功');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '更新失败');
        }
    };

    // 取消编辑
    const handleCancelEdit = () => {
        setEditingId(null);
        setTempData({});
    };

    // 删除
    const handleDelete = async (id: string) => {
        if (!confirm('确定要删除这个扩展文件夹配置吗？（不会删除磁盘文件）')) {
            return;
        }

        try {
            await AddOnAPI.deleteExpandDir(id);
            setExpandDirs(prev => prev.filter(d => d.id !== id));
            toast.success('删除成功');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '删除失败');
        }
    };

    // 路径选择
    const handleSelectPath = async () => {
        if (!isElectron) {
            toast.error('路径选择仅在桌面版可用');
            return;
        }

        try {
            const dir = await window.electronAPI?.selectDirectory();
            if (dir) {
                setTempData(prev => ({ ...prev, path: dir }));
            }
        } catch (err) {
            toast.error('选择路径失败');
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-32">
                <div className="text-slate-500">加载中...</div>
            </div>
        );
    }

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <p className="text-sm text-slate-500">
                        建议增加诸如：读书笔记，个人文章等能够表达出个人价值观等内心活动的文件夹内容
                    </p>
                </div>
                <button
                    onClick={handleAddNew}
                    className="p-2.5 bg-gradient-to-br from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white rounded-xl transition-all duration-200 flex-shrink-0 shadow-sm hover:shadow-md hover:shadow-emerald-500/20"
                    title="添加扩展文件夹"
                >
                    <Plus size={20} />
                </button>
            </div>

            {/* 空状态 */}
            {expandDirs.length === 0 && (
                <div className="text-center py-16 text-slate-400">
                    <FolderOpen size={56} className="mx-auto mb-4 opacity-20" />
                    <p className="text-base">暂无扩展文件夹，点击右上角 + 添加</p>
                </div>
            )}

            {/* 文件夹列表 */}
            <div className="space-y-3">
                {expandDirs.map((dir) => {
                    const isEditing = editingId === dir.id;
                    const isNew = dir.id === 'temp-new';
                    const currentData = isEditing ? tempData : dir;

                    return (
                        <div
                            key={dir.id}
                            className={`
                                group relative p-5 bg-white rounded-2xl border transition-all duration-200
                                ${isEditing
                                    ? 'border-emerald-300 shadow-lg shadow-emerald-500/10'
                                    : 'border-emerald-100 hover:border-emerald-200 hover:shadow-md hover:shadow-emerald-500/5'
                                }
                            `}
                        >
                            {/* 编辑按钮（非编辑状态时显示） */}
                            {!isEditing && (
                                <button
                                    onClick={() => handleStartEdit(dir)}
                                    className="absolute top-4 right-4 p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                                    title="编辑"
                                >
                                    <Edit3 size={16} />
                                </button>
                            )}

                            <div className="space-y-4">
                                {/* 名称 */}
                                <div>
                                    <label className="block text-xs text-slate-400 mb-1.5">名称</label>
                                    {isEditing ? (
                                        <input
                                            type="text"
                                            value={currentData.name || ''}
                                            onChange={(e) => setTempData(prev => ({ ...prev, name: e.target.value }))}
                                            placeholder="例如：读书笔记"
                                            className="w-full bg-emerald-50/50 border border-emerald-200 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 rounded-xl px-4 py-2.5 text-slate-800 outline-none transition-all"
                                        />
                                    ) : (
                                        <div className="text-lg font-semibold text-slate-800">
                                            {dir.name}
                                        </div>
                                    )}
                                </div>

                                {/* 描述 */}
                                <div>
                                    <label className="block text-xs text-slate-400 mb-1.5">描述</label>
                                    {isEditing ? (
                                        <input
                                            type="text"
                                            value={currentData.description || ''}
                                            onChange={(e) => setTempData(prev => ({ ...prev, description: e.target.value }))}
                                            placeholder="描述该文件夹的内容..."
                                            className="w-full bg-emerald-50/50 border border-emerald-200 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 rounded-xl px-4 py-2.5 text-slate-800 outline-none transition-all"
                                        />
                                    ) : (
                                        <div className="text-sm text-slate-600">
                                            {dir.description || <span className="text-slate-400 italic">（无描述）</span>}
                                        </div>
                                    )}
                                </div>

                                {/* 路径 */}
                                <div>
                                    <label className="block text-xs text-slate-400 mb-1.5">路径</label>
                                    {isEditing ? (
                                        <div className="flex gap-2">
                                            <input
                                                type="text"
                                                value={currentData.path || ''}
                                                readOnly
                                                placeholder="默认地址 (lifeprism_data_path/expand_dir/{new_folder})"
                                                className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-600 outline-none"
                                            />
                                            <button
                                                onClick={handleSelectPath}
                                                disabled={!isElectron}
                                                className="px-4 py-2.5 bg-white border border-emerald-200 hover:bg-emerald-50 hover:border-emerald-300 text-emerald-700 rounded-xl text-sm flex items-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white"
                                                title={isElectron ? "选择文件夹" : "仅桌面版可用"}
                                            >
                                                <FolderSearch size={16} />
                                                <span>选择</span>
                                            </button>
                                        </div>
                                    ) : (
                                        <div className="text-sm text-slate-500 font-mono bg-slate-50 px-3 py-2 rounded-lg">
                                            {dir.path}
                                        </div>
                                    )}
                                </div>

                                {/* 底部操作栏 */}
                                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                                    {/* AI 索引开关 */}
                                    <div className="flex items-center gap-3">
                                        <span className="text-xs text-slate-500">AI 索引</span>
                                        {isEditing ? (
                                            <button
                                                onClick={() => setTempData(prev => ({ ...prev, ai_index: !prev.ai_index }))}
                                                className={`
                                                    relative w-11 h-6 rounded-full transition-all duration-200
                                                    ${currentData.ai_index
                                                        ? 'bg-gradient-to-r from-emerald-500 to-teal-600'
                                                        : 'bg-slate-300'
                                                    }
                                                `}
                                            >
                                                <span className={`
                                                    absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform duration-200
                                                    ${currentData.ai_index ? 'translate-x-5' : 'translate-x-0'}
                                                `} />
                                            </button>
                                        ) : (
                                            <div className={`
                                                relative w-11 h-6 rounded-full transition-all
                                                ${dir.ai_index
                                                    ? 'bg-gradient-to-r from-emerald-500 to-teal-600'
                                                    : 'bg-slate-300'
                                                }
                                            `}>
                                                <span className={`
                                                    absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform
                                                    ${dir.ai_index ? 'translate-x-5' : 'translate-x-0'}
                                                `} />
                                            </div>
                                        )}
                                    </div>

                                    {/* 操作按钮 */}
                                    {isEditing ? (
                                        <div className="flex gap-2">
                                            <button
                                                onClick={isNew ? handleCancelNew : handleCancelEdit}
                                                className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                                            >
                                                取消
                                            </button>
                                            <button
                                                onClick={isNew ? handleSaveNew : () => handleSaveEdit(dir.id)}
                                                className="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 rounded-lg transition-all shadow-sm hover:shadow-md"
                                            >
                                                保存
                                            </button>
                                        </div>
                                    ) : (
                                        <button
                                            onClick={() => handleDelete(dir.id)}
                                            className="px-3 py-2 text-sm text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors flex items-center gap-1.5"
                                        >
                                            <Trash2 size={14} />
                                            <span>删除</span>
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};
