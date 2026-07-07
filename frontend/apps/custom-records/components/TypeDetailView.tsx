/**
 * 类型详情视图 — 卡片视图（默认） + 表格视图 Tab 切换
 * 卡片按日期分组，日期头部显示"今天/昨天/具体日期"
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { ArrowLeft, Database, FileText, Clock, Trash2, AlertTriangle, ChevronLeft, ChevronRight, LayoutGrid, Table } from 'lucide-react';
import { CustomRecordsAPI } from '../api';
import { EntryCard } from './EntryCard';
import type { CustomRecordTypeItem, CustomRecordEntryItem } from '../types';

interface TypeDetailViewProps {
  typeId: string;
  onBack: () => void;
}

type ViewTab = 'card' | 'table';

// ==================== 日期分组工具 ====================

const getDateGroup = (dateStr: string): string => {
  if (!dateStr) return '未知日期';
  const date = new Date(dateStr.replace(' ', 'T'));
  if (isNaN(date.getTime())) return '未知日期';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const entryDate = new Date(date);
  entryDate.setHours(0, 0, 0, 0);
  const diffDays = Math.floor((today.getTime() - entryDate.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return '今天';
  if (diffDays === 1) return '昨天';
  if (diffDays === 2) return '前天';
  return `${entryDate.getMonth() + 1}月${entryDate.getDate()}日`;
};

const getDateKey = (dateStr: string): string => {
  if (!dateStr) return '0000-00-00';
  return dateStr.split('T')[0].split(' ')[0];
};

export const TypeDetailView: React.FC<TypeDetailViewProps> = ({ typeId, onBack }) => {
  const [type, setType] = useState<CustomRecordTypeItem | null>(null);
  const [entries, setEntries] = useState<CustomRecordEntryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<ViewTab>('card');

  // 筛选与分页
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const [typeData, entryData] = await Promise.all([
        CustomRecordsAPI.getTypeById(typeId),
        CustomRecordsAPI.getEntries(typeId, {
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          page,
          page_size: pageSize,
        }),
      ]);
      setType(typeData);
      setEntries(entryData.items);
      setTotal(entryData.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [typeId, startDate, endDate, page]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleDeleteEntry = async (entryId: string) => {
    try {
      await CustomRecordsAPI.deleteEntry(typeId, entryId);
      loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败');
    }
  };

  const handleFilter = () => {
    setPage(1);
    loadData();
  };

  // 日期分组
  const groupedEntries = useMemo(() => {
    const groups: { label: string; dateKey: string; items: CustomRecordEntryItem[] }[] = [];
    for (const entry of entries) {
      const dateKey = getDateKey(entry.created_at);
      const label = getDateGroup(entry.created_at);
      let group = groups.find(g => g.dateKey === dateKey);
      if (!group) {
        group = { label, dateKey, items: [] };
        groups.push(group);
      }
      group.items.push(entry);
    }
    return groups;
  }, [entries]);

  if (loading && !type) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-400">
        <div className="animate-pulse">加载中...</div>
      </div>
    );
  }

  if (error && !type) {
    return (
      <div className="flex flex-col items-center py-20">
        <AlertTriangle size={32} className="text-red-400 mb-3" />
        <p className="text-sm text-slate-500 mb-4">{error}</p>
        <button onClick={onBack} className="text-sm text-cyan-600">返回列表</button>
      </div>
    );
  }

  if (!type) return null;

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="animate-[fadeIn_0.3s_ease-out]">
      <button onClick={onBack} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-6">
        <ArrowLeft size={16} />返回
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-cyan-50 text-cyan-600 flex items-center justify-center">
            <Database size={22} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{type.name}</h1>
            <div className="flex items-center gap-3 mt-0.5">
              <p className="text-xs text-slate-400 font-mono">custom_{type.slug}</p>
              <span className="text-slate-300">·</span>
              <p className="text-xs text-slate-500">{total} 条记录</p>
            </div>
          </div>
        </div>
      </div>

      {/* 字段 chips */}
      <div className="mb-5 flex items-center gap-2 flex-wrap">
        {type.fields.map(f => (
          <span key={f.field_key} className="text-xs px-2.5 py-1 rounded-lg bg-slate-50 text-slate-600 border border-slate-100 flex items-center gap-1.5">
            <FileText size={11} className="opacity-40" />
            {f.field_name}
          </span>
        ))}
      </div>

      {/* Tab 栏 + 筛选栏 */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-xl">
          <button
            onClick={() => setActiveTab('card')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'card' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <LayoutGrid size={14} />卡片
          </button>
          <button
            onClick={() => setActiveTab('table')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'table' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <Table size={14} />表格
          </button>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-slate-400" />
            <input
              type="date"
              value={startDate}
              onChange={e => setStartDate(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/20"
            />
            <span className="text-slate-400 text-sm">~</span>
            <input
              type="date"
              value={endDate}
              onChange={e => setEndDate(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/20"
            />
          </div>
          <button onClick={handleFilter} className="px-3 py-1.5 rounded-lg text-sm font-medium text-white bg-slate-700 hover:bg-slate-800">
            筛选
          </button>
          {(startDate || endDate) && (
            <button
              onClick={() => { setStartDate(''); setEndDate(''); setPage(1); }}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              清除
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm flex items-center gap-2">
          <AlertTriangle size={16} />{error}
        </div>
      )}

      {/* 内容区 — 卡片视图 / 表格视图 */}
      {entries.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm py-16 flex flex-col items-center text-slate-400">
          <Database size={36} strokeWidth={1} className="mb-3 opacity-40" />
          <p className="text-sm font-medium">暂无记录</p>
          <p className="text-xs mt-1">通过 AI 对话或 API 录入数据</p>
        </div>
      ) : activeTab === 'card' ? (
        /* 卡片视图 — 按日期分组 */
        <div className="space-y-6">
          {groupedEntries.map(group => (
            <div key={group.dateKey}>
              {/* 日期头部 */}
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center">
                  <Clock size={13} className="text-slate-500" />
                </div>
                <span className="text-sm font-semibold text-slate-700">{group.label}</span>
                <span className="text-xs text-slate-400">{group.dateKey}</span>
                <span className="text-xs text-slate-300">·</span>
                <span className="text-xs text-slate-400">{group.items.length} 条</span>
              </div>
              {/* 卡片网格 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {group.items.map(entry => (
                  <EntryCard
                    key={entry.id}
                    fields={type.fields}
                    entry={entry}
                    accentColor="cyan"
                    onDelete={handleDeleteEntry}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* 表格视图 */
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-100">
                  {type.fields.map(f => (
                    <th key={f.field_key} className="px-5 py-3.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">
                      {f.field_name}
                    </th>
                  ))}
                  <th className="px-5 py-3.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">创建时间</th>
                  <th className="px-5 py-3.5 w-12"></th>
                </tr>
              </thead>
              <tbody>
                {entries.map(entry => (
                  <tr key={entry.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/50 group">
                    {type.fields.map(f => (
                      <td key={f.field_key} className="px-5 py-3.5 text-slate-700 max-w-xs truncate">
                        {entry[f.field_key] || <span className="text-slate-300">—</span>}
                      </td>
                    ))}
                    <td className="px-5 py-3.5 text-slate-400 text-xs whitespace-nowrap">
                      {entry.created_at ? entry.created_at.replace('T', ' ').slice(0, 16) : '—'}
                    </td>
                    <td className="px-5 py-3.5">
                      <button
                        onClick={() => handleDeleteEntry(entry.id)}
                        className="p-1.5 rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 mt-5">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-xs text-slate-400 px-2">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
};
