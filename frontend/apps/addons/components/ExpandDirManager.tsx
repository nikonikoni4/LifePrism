import React, { useState, useEffect } from 'react';
import { FolderOpen, Plus, FolderSearch, Trash2 } from 'lucide-react';
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
                    <p className="text-sm text-slate-600">
                        建议增加诸如：读书笔记，个人文章等能够表达出个人价值观等内心活动的文件夹内容
                    </p>
                </div>
                <button
                    onClick={handleAddNew}
                    className="p-2.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl transition-colors flex-shrink-0"
                    title="添加扩展文件夹"
                >
                    <Plus size={20} />
                </button>
            </div>

            {/* 空状态 */}
            {expandDirs.length === 0 && (
                <div className="text-center py-12 text-slate-400">
                    <FolderOpen size={48} className="mx-auto mb-3 opacity-30" />
                    <p>暂无扩展文件夹，点击 + 添加</p>
                </div>
            )}

            {/* 文件夹列表 */}
            <div className="space-y-4">
                {expandDirs.map((dir) => {
                    const isEditing = editingId === dir.id;
                    const isNew = dir.id === 'temp-new';
                    const currentData = isEditing ? tempData : dir;

                    return (
                        <div
                            key={dir.id}
                            className="p-6 bg-gray-50 rounded-xl border border-gray-100 space-y-4"
                        >
                            {/* 名称 */}
                            <div>
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">
                                    名称
                                </label>
                                {isEditing ? (
                                    <input
                                        type="text"
                                        value={currentData.name || ''}
                                        onChange={(e) => setTempData(prev => ({ ...prev, name: e.target.value }))}
                                        placeholder="例如：读书笔记"
                                        className="w-full bg-white border border-gray-200 focus:border-emerald-300 focus:ring-2 focus:ring-emerald-100 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all"
                                    />
                                ) : (
                                    <div
                                        className="text-sm font-bold text-slate-700 cursor-pointer hover:text-emerald-600 transition-colors"
                                        onClick={() => handleStartEdit(dir)}
                                    >
                                        {dir.name}
                                    </div>
                                )}
                            </div>

                            {/* 描述 */}
                            <div>
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">
                                    文件夹主要内容说明
                                </label>
                                {isEditing ? (
                                    <input
                                        type="text"
                                        value={currentData.description || ''}
                                        onChange={(e) => setTempData(prev => ({ ...prev, description: e.target.value }))}
                                        placeholder="描述该文件夹的内容..."
                                        className="w-full bg-white border border-gray-200 focus:border-emerald-300 focus:ring-2 focus:ring-emerald-100 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all"
                                    />
                                ) : (
                                    <div
                                        className="text-sm text-slate-600 cursor-pointer hover:text-emerald-600 transition-colors"
                                        onClick={() => handleStartEdit(dir)}
                                    >
                                        {dir.description || '（无描述）'}
                                    </div>
                                )}
                            </div>

                            {/* 路径 */}
                            <div>
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">
                                    文件夹地址
                                </label>
                                <div className="flex gap-3">
                                    {isEditing ? (
                                        <>
                                            <input
                                                type="text"
                                                value={currentData.path || ''}
                                                readOnly
                                                placeholder="点击右侧按钮选择文件夹"
                                                className="flex-1 bg-white border border-gray-200 rounded-xl px-4 py-3 text-slate-600 font-mono text-xs outline-none"
                                            />
                                            <button
                                                onClick={handleSelectPath}
                                                disabled={!isElectron}
                                                className="px-4 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-slate-600 rounded-xl font-bold text-xs shadow-sm flex items-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                                title={isElectron ? "选择文件夹" : "仅桌面版可用"}
                                            >
                                                <FolderSearch size={14} />
                                            </button>
                                        </>
                                    ) : (
                                        <div className="flex-1 text-xs font-mono text-slate-600 bg-white px-4 py-3 rounded-xl border border-gray-100">
                                            {dir.path}
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* AI 索引开关和操作按钮 */}
                            <div className="flex items-center justify-between pt-2">
                                <div className="flex items-center gap-3">
                                    <label className="text-xs font-bold text-slate-600">索引目录：</label>
                                    {isEditing ? (
                                        <button
                                            onClick={() => setTempData(prev => ({ ...prev, ai_index: !prev.ai_index }))}
                                            className={`relative w-12 h-6 rounded-full transition-all ${
                                                currentData.ai_index ? 'bg-emerald-500' : 'bg-slate-200'
                                            }`}
                                        >
                                            <div
                                                className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-all ${
                                                    currentData.ai_index ? 'left-6' : 'left-0.5'
                                                }`}
                                            />
                                        </button>
                                    ) : (
                                        <div className={`text-xs font-bold ${dir.ai_index ? 'text-emerald-600' : 'text-slate-400'}`}>
                                            {dir.ai_index ? 'ON' : 'OFF'}
                                        </div>
                                    )}
                                </div>

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
                                            className="px-4 py-2 text-sm font-medium text-white bg-emerald-500 hover:bg-emerald-600 rounded-lg transition-colors"
                                        >
                                            保存
                                        </button>
                                    </div>
                                ) : (
                                    <button
                                        onClick={() => handleDelete(dir.id)}
                                        className="text-slate-400 hover:text-red-500 transition-colors"
                                        title="删除"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};
