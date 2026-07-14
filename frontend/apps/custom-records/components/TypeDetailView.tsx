/**
 * 类型详情视图 — 卡片视图（默认） + 表格视图 + 模板对比 Tab
 * 卡片按日期分组，支持模板切换和字段角色配置
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { ArrowLeft, Database, FileText, Clock, Trash2, AlertTriangle, ChevronLeft, ChevronRight, LayoutGrid, Table, Columns3, Settings2, LineChart as LineChartIcon } from 'lucide-react';
import { CustomRecordsAPI } from '../api';
import { EntryCard } from './EntryCard';
import { EntryChart } from './EntryChart';
import { TemplatePicker } from './TemplatePicker';
import { FieldRoleModal } from './FieldRoleModal';
import { TEMPLATE_PRESETS, getTemplatePreset } from '../utils/templatePresets';
import { toISOStringUTC, parseISOString, toLocalDateString, toLocalDateTimeString } from '../../../core/utils/dateUtils';
import type { CustomRecordTypeItem, CustomRecordEntryItem, FieldDefinition } from '../types';
import { formatFieldValue, isNumericField } from '../utils/fieldFormatter';

interface TypeDetailViewProps {
  typeId: string;
  onBack: () => void;
}

type ViewTab = 'card' | 'table' | 'chart' | 'compare';

// ==================== 日期分组工具 ====================

const getDateGroup = (dateStr: string): string => {
  if (!dateStr) return '未知日期';
  const date = parseISOString(dateStr);
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
  return toLocalDateString(parseISOString(dateStr));
};

export const TypeDetailView: React.FC<TypeDetailViewProps> = ({ typeId, onBack }) => {
  const [type, setType] = useState<CustomRecordTypeItem | null>(null);
  const [entries, setEntries] = useState<CustomRecordEntryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<ViewTab>('card');

  // 模板和字段配置
  const [currentTemplate, setCurrentTemplate] = useState('clean');
  const [showFieldModal, setShowFieldModal] = useState(false);
  const [localFields, setLocalFields] = useState<FieldDefinition[]>([]);

  // 筛选与分页
  // 默认时间范围：进入详情页时自动填充最近一周（今天 ~ 7 天前）
  // 用户主动"清除"后会变为空字符串，不再自动填充
  const [startDate, setStartDate] = useState(() => {
    const today = new Date();
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);
    return toLocalDateString(weekAgo);
  });
  const [endDate, setEndDate] = useState(() => toLocalDateString(new Date()));
  const [page, setPage] = useState(1);
  // chart 视图需要展示时间范围内所有数据点，使用较大 page_size；
  // card/table 视图维持 20 条/页的分页体验
  // 后端限制 page_size ≤ 500（见 custom_records_api.py），取上限值
  const pageSize = activeTab === 'chart' ? 500 : 20;

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      // 组件内转换：YYYY-MM-DD → UTC 时间范围（就近原则）
      let start_time: string | undefined;
      let end_time: string | undefined;
      if (startDate) {
        start_time = toISOStringUTC(new Date(`${startDate}T00:00:00`));
      }
      if (endDate) {
        end_time = toISOStringUTC(new Date(`${endDate}T23:59:59.999`));
      }

      const [typeData, entryData] = await Promise.all([
        CustomRecordsAPI.getTypeById(typeId),
        CustomRecordsAPI.getEntries(typeId, {
          start_time,
          end_time,
          page,
          page_size: pageSize,
        }),
      ]);
      setType(typeData);
      setLocalFields(typeData.fields);
      setCurrentTemplate(typeData.card_template || 'clean');
      setEntries(entryData.items);
      setTotal(entryData.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [typeId, startDate, endDate, page, pageSize]);

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
    if (page === 1) {
      // 已经在第 1 页，useEffect 不会因 page 变化而触发，需要手动加载
      loadData();
    } else {
      // page 变化会触发 useEffect 自动加载
      setPage(1);
    }
  };

  // 模板切换 — debounce 自动保存
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const savedStatusTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  // 组件卸载时清理所有定时器
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (savedStatusTimerRef.current) clearTimeout(savedStatusTimerRef.current);
    };
  }, []);

  const handleTemplateChange = (templateId: string) => {
    setCurrentTemplate(templateId);
    setSaveStatus('saving');
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        await CustomRecordsAPI.updateTypeConfig(typeId, { card_template: templateId });
        setSaveStatus('saved');
        if (savedStatusTimerRef.current) clearTimeout(savedStatusTimerRef.current);
        savedStatusTimerRef.current = setTimeout(() => setSaveStatus('idle'), 1500);
      } catch {
        setSaveStatus('idle');
      }
    }, 600);
  };

  // 字段角色切换 — 持久化到后端
  const handleFieldRoleChange = async (fieldKey: string, displayRole: string) => {
    // 找到对应字段的 id
    const field = localFields.find(f => f.field_key === fieldKey);
    if (!field || !field.id) return;

    // 本地立即更新
    setLocalFields(prev => prev.map(f =>
      f.field_key === fieldKey ? { ...f, display_role: displayRole } : f
    ));

    // 持久化到后端
    try {
      await CustomRecordsAPI.updateFieldRole(typeId, field.id, { display_role: displayRole });
    } catch (e) {
      // 持久化失败时回滚本地状态
      setLocalFields(prev => prev.map(f =>
        f.field_key === fieldKey ? { ...f, display_role: field.display_role } : f
      ));
      setError(e instanceof Error ? e.message : '更新字段角色失败');
    }
  };

  // 日期分组
  const groupedEntries = useMemo(() => {
    const groups: { label: string; dateKey: string; items: CustomRecordEntryItem[] }[] = [];
    for (const entry of entries) {
      const dateKey = getDateKey(entry.event_time);
      const label = getDateGroup(entry.event_time);
      let group = groups.find(g => g.dateKey === dateKey);
      if (!group) {
        group = { label, dateKey, items: [] };
        groups.push(group);
      }
      group.items.push(entry);
    }
    return groups;
  }, [entries]);

  // 是否含数值字段 — 决定 chart Tab 是否显示
  const hasNumericField = useMemo(
    () => localFields.some(f => isNumericField(f.field_type)),
    [localFields]
  );

  // 当前时间范围描述 — 用于 EntryChart subtitle
  const timeRangeLabel = useMemo(() => {
    if (!startDate && !endDate) return '';
    if (startDate && endDate) return `${startDate} ~ ${endDate}`;
    return startDate || endDate || '';
  }, [startDate, endDate]);

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

      {/* 字段 chips + 配置按钮 */}
      <div className="mb-5 flex items-center gap-2 flex-wrap">
        {localFields.map(f => (
          <span key={f.field_key} className="text-xs px-2.5 py-1 rounded-lg bg-slate-50 text-slate-600 border border-slate-100 flex items-center gap-1.5">
            <FileText size={11} className="opacity-40" />
            {f.field_name}
            {f.display_role && f.display_role !== 'auto' && (
              <span className="text-[9px] px-1 rounded bg-cyan-100 text-cyan-600 font-medium">
                {f.display_role}
              </span>
            )}
          </span>
        ))}
        <button
          onClick={() => setShowFieldModal(true)}
          className="text-xs px-2.5 py-1 rounded-lg text-slate-400 hover:text-cyan-600 hover:bg-cyan-50 border border-dashed border-slate-200 flex items-center gap-1"
        >
          <Settings2 size={11} />配置角色
        </button>
      </div>

      {/* Tab 栏 + 模板选择器 + 筛选栏 */}
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
          {hasNumericField && (
            <button
              onClick={() => setActiveTab('chart')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'chart' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <LineChartIcon size={14} />图表
            </button>
          )}
          <button
            onClick={() => setActiveTab('compare')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'compare' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <Columns3 size={14} />模板对比
          </button>
        </div>

        {activeTab !== 'compare' && (
          <div className="flex items-center gap-2 flex-wrap">
            {/* 模板选择器（卡片视图时显示） */}
            {activeTab === 'card' && (
              <div className="flex items-center gap-2">
                {saveStatus !== 'idle' && (
                  <span className="text-[10px] text-slate-400">
                    {saveStatus === 'saving' ? '保存中...' : '已保存'}
                  </span>
                )}
                <TemplatePicker
                  currentTemplate={currentTemplate}
                  onTemplateChange={handleTemplateChange}
                />
              </div>
            )}

            {/* 日期筛选 */}
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
        )}
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm flex items-center gap-2">
          <AlertTriangle size={16} />{error}
        </div>
      )}

      {/* 内容区 */}
      {activeTab === 'compare' ? (
        /* 模板对比 Tab — 5 套模板并排展示同一条数据 */
        <div className="space-y-6">
          <p className="text-sm text-slate-500">选择一个模板应用到当前类型的所有卡片：</p>
          {entries.length === 0 ? (
            <div className="bg-white rounded-2xl border border-slate-100 shadow-sm py-16 flex flex-col items-center text-slate-400">
              <Database size={36} strokeWidth={1} className="mb-3 opacity-40" />
              <p className="text-sm">暂无记录可供对比</p>
            </div>
          ) : (
            TEMPLATE_PRESETS.map(tpl => (
              <div key={tpl.id} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-700">{tpl.name}</h3>
                    <span className="text-xs text-slate-400">{tpl.description}</span>
                  </div>
                  {currentTemplate === tpl.id ? (
                    <span className="text-xs px-2 py-0.5 rounded bg-cyan-100 text-cyan-600 font-medium">当前</span>
                  ) : (
                    <button
                      onClick={() => handleTemplateChange(tpl.id)}
                      className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-500 hover:bg-slate-200"
                    >
                      应用
                    </button>
                  )}
                </div>
                {/* 用第一条记录预览模板效果 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {entries.slice(0, 2).map(entry => (
                    <EntryCard
                      key={entry.id}
                      fields={localFields}
                      entry={entry}
                      templateId={tpl.id}
                    />
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      ) : activeTab === 'chart' ? (
        /* 图表视图 — 即使无数值字段或无记录，EntryChart 内部都会处理空状态 */
        <EntryChart
          entries={entries}
          fields={localFields}
          timeRangeLabel={timeRangeLabel}
        />
      ) : entries.length === 0 ? (
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
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center">
                  <Clock size={13} className="text-slate-500" />
                </div>
                <span className="text-sm font-semibold text-slate-700">{group.label}</span>
                <span className="text-xs text-slate-400">{group.dateKey}</span>
                <span className="text-xs text-slate-300">·</span>
                <span className="text-xs text-slate-400">{group.items.length} 条</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {group.items.map(entry => (
                  <EntryCard
                    key={entry.id}
                    fields={localFields}
                    entry={entry}
                    templateId={currentTemplate}
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
                  {localFields.map(f => (
                    <th key={f.field_key} className="px-5 py-3.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">
                      {f.field_name}
                    </th>
                  ))}
                  <th className="px-5 py-3.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">事件时间</th>
                  <th className="px-5 py-3.5 w-12"></th>
                </tr>
              </thead>
              <tbody>
                {entries.map(entry => (
                  <tr key={entry.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/50 group">
                    {localFields.map(f => {
                      const val = entry[f.field_key];
                      return (
                        <td key={f.field_key} className="px-5 py-3.5 text-slate-700 max-w-xs truncate">
                          {val != null && val !== ''
                            ? formatFieldValue(val, f.field_type)
                            : <span className="text-slate-300">—</span>}
                        </td>
                      );
                    })}
                    <td className="px-5 py-3.5 text-slate-400 text-xs whitespace-nowrap">
                      {entry.event_time ? toLocalDateTimeString(parseISOString(entry.event_time)).replace('T', ' ').slice(0, 16) : '—'}
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

      {/* 分页 — chart 视图展示全部数据点，不分页 */}
      {totalPages > 1 && activeTab !== 'compare' && activeTab !== 'chart' && (
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

      {/* 字段角色配置弹窗 */}
      {showFieldModal && (
        <FieldRoleModal
          fields={localFields}
          onClose={() => setShowFieldModal(false)}
          onFieldRoleChange={handleFieldRoleChange}
        />
      )}
    </div>
  );
};
