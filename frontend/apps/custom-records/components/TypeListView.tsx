/**
 * 类型列表视图 — 模块默认视图
 * 展示所有自定义记录类型，支持新建和进入详情
 */
import React, { useState, useEffect } from 'react';
import { Plus, Database, FileText, Clock, ChevronRight, Trash2, AlertTriangle } from 'lucide-react';
import { CustomRecordsAPI } from '../api';
import type { CustomRecordTypeItem } from '../types';

interface TypeListViewProps {
  onCreate: () => void;
  onViewType: (typeId: string) => void;
}

export const TypeListView: React.FC<TypeListViewProps> = ({ onCreate, onViewType }) => {
  const [types, setTypes] = useState<CustomRecordTypeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<CustomRecordTypeItem | null>(null);

  const loadTypes = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await CustomRecordsAPI.getTypes();
      setTypes(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTypes(); }, []);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await CustomRecordsAPI.deleteType(deleteTarget.id);
      setDeleteTarget(null);
      loadTypes();
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败');
      setDeleteTarget(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-400">
        <div className="animate-pulse">加载中...</div>
      </div>
    );
  }

  return (
    <div className="animate-[fadeIn_0.3s_ease-out]">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">自定义记录</h1>
          <p className="text-sm text-slate-500">创建和管理你的自定义数据类型</p>
        </div>
        <button
          onClick={onCreate}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium text-white bg-gradient-to-r from-cyan-500 to-teal-500 shadow-md shadow-cyan-500/20 hover:shadow-lg transition-shadow"
        >
          <Plus size={16} />新建类型
        </button>
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm flex items-center gap-2">
          <AlertTriangle size={16} />{error}
        </div>
      )}

      {/* Empty state */}
      {types.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center py-20 text-slate-400">
          <Database size={48} strokeWidth={1} className="mb-4 opacity-40" />
          <p className="text-base font-medium mb-1">还没有自定义记录类型</p>
          <p className="text-sm mb-4">点击"新建类型"开始创建你的第一个数据类型</p>
        </div>
      )}

      {/* Type cards grid */}
      {types.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {types.map((type) => (
            <div
              key={type.id}
              className="group bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-lg hover:border-slate-200 transition-all p-5 cursor-pointer relative overflow-hidden"
              onClick={() => onViewType(type.id)}
            >
              <div className="absolute top-0 left-0 right-0 h-0.5 bg-cyan-500"></div>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-cyan-50 text-cyan-600 flex items-center justify-center">
                    <Database size={18} />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-slate-900">{type.name}</h3>
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5">custom_{type.slug}</p>
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setDeleteTarget(type); }}
                  className="p-1.5 rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-500 mb-3">
                <span className="flex items-center gap-1"><FileText size={12} />{type.fields.length} 字段</span>
                {type.created_at && (
                  <span className="flex items-center gap-1"><Clock size={12} />{type.created_at.split('T')[0]}</span>
                )}
              </div>
              <div className="flex gap-1 flex-wrap">
                {type.fields.map(f => (
                  <span key={f.field_key} className="text-[10px] px-2 py-0.5 rounded-md bg-slate-50 text-slate-600 border border-slate-100">
                    {f.field_name}
                  </span>
                ))}
              </div>
              <div className="pt-3 mt-3 border-t border-slate-50 flex items-center justify-end">
                <span className="text-[11px] text-cyan-600 font-medium flex items-center gap-0.5 group-hover:gap-1.5 transition-all">
                  进入 <ChevronRight size={12} />
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4" onClick={() => setDeleteTarget(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-red-50 text-red-500 flex items-center justify-center">
                <AlertTriangle size={20} />
              </div>
              <div>
                <h3 className="text-base font-semibold text-slate-900">删除类型</h3>
                <p className="text-xs text-slate-500">此操作不可撤销</p>
              </div>
            </div>
            <p className="text-sm text-slate-600 mb-5">
              确认删除「{deleteTarget.name}」？该类型下的所有记录将被永久删除。
            </p>
            <div className="flex items-center justify-end gap-2">
              <button onClick={() => setDeleteTarget(null)} className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100">取消</button>
              <button onClick={handleDelete} className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-500 hover:bg-red-600">确认删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
