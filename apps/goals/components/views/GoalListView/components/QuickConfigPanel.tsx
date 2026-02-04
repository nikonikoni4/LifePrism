import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp, Check, Settings, RefreshCw } from 'lucide-react';
import { ThemeKey } from '../../../../types';
import { THEMES } from '../../../../hooks/useGoalStore';
import CategoryFilter, { CategoryFilterValue } from '../../../../../../core/components/CategoryFilter';
import { goalsV2Api } from '../../../../api';

interface QuickConfigPanelProps {
  goalId: string;
  theme: ThemeKey;
  category: string;
  startDate: string;
  endDate: string;
  timeInvested: string;
  trackTimeAutomatically: boolean;
  onThemeChange: (theme: ThemeKey) => void;
  onCategoryChange: (category: string) => void;
  onStartDateChange: (date: string) => void;
  onEndDateChange: (date: string) => void;
  onTimeInvestedChange: (time: string) => void;
  onTrackModeChange: (auto: boolean) => void;
  defaultExpanded?: boolean;
}

const QuickConfigPanel: React.FC<QuickConfigPanelProps> = ({
  goalId,
  theme,
  category,
  startDate,
  endDate,
  timeInvested,
  trackTimeAutomatically,
  onThemeChange,
  onCategoryChange,
  onStartDateChange,
  onEndDateChange,
  onTimeInvestedChange,
  onTrackModeChange,
  defaultExpanded = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // 刷新投入时间
  const handleRefreshTime = async () => {
    if (isRefreshing || !trackTimeAutomatically) return;

    setIsRefreshing(true);
    try {
      const result = await goalsV2Api.refreshTimeInvested(goalId);
      if (result.success) {
        const minutes = result.timeInvested;
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        onTimeInvestedChange(`${hours}h ${mins}m`);
      }
    } catch (error) {
      console.error('Failed to refresh time invested:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="border border-slate-200 rounded-xl bg-slate-50/50 overflow-hidden">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setIsExpanded(!isExpanded);
        }}
        className="w-full flex items-center justify-between p-3 px-4 hover:bg-slate-100/50 transition-colors group"
      >
        <div className="flex items-center gap-2 text-slate-600 font-medium text-sm">
          <Settings size={14} className="text-slate-400 group-hover:text-indigo-500 transition-colors" />
          <span>配置</span>
        </div>
        {isExpanded ? (
          <ChevronUp size={14} className="text-slate-400" />
        ) : (
          <ChevronDown size={14} className="text-slate-400" />
        )}
      </button>

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-4 pt-0 space-y-4" onClick={(e) => e.stopPropagation()}>
              <div className="h-px w-full bg-slate-200 mb-4"></div>

              {/* Theme Selection */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  主题颜色
                </label>
                <div className="flex gap-2">
                  {Object.entries(THEMES).map(([key, config]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => onThemeChange(key as ThemeKey)}
                      className={`w-7 h-7 rounded-full shadow-sm transition-all hover:scale-110 flex items-center justify-center ${theme === key ? 'ring-2 ring-offset-2 ring-slate-400' : ''
                        }`}
                      style={{ backgroundColor: config.accentColor }}
                    >
                      {theme === key && <Check size={12} className="text-white" />}
                    </button>
                  ))}
                </div>
              </div>

              {/* Category & Time Invested */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                    分类
                  </label>
                  <CategoryFilter
                    value={{
                      categoryId: category || null,
                      subCategoryId: null,
                      color: null,
                    }}
                    onChange={(val: CategoryFilterValue) => onCategoryChange(val.categoryId || '')}
                    buttonClassName="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all font-medium flex items-center gap-2"
                    showLabel={true}
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                      已投入
                    </label>
                    {/* 自动/手动切换下拉 */}
                    <select
                      value={trackTimeAutomatically ? 'auto' : 'manual'}
                      onChange={(e) => onTrackModeChange(e.target.value === 'auto')}
                      className="text-[10px] font-medium text-slate-500 bg-transparent border-none focus:outline-none cursor-pointer hover:text-indigo-500 transition-colors"
                    >
                      <option value="auto">自动跟踪</option>
                      <option value="manual">手动记录</option>
                    </select>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      className={`w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all tabular-nums font-medium ${trackTimeAutomatically ? 'bg-slate-50 cursor-not-allowed' : ''}`}
                      placeholder="0"
                      value={timeInvested}
                      onChange={(e) => onTimeInvestedChange(e.target.value)}
                      disabled={trackTimeAutomatically}
                    />
                    {trackTimeAutomatically && category ? (
                      <button
                        type="button"
                        onClick={handleRefreshTime}
                        disabled={isRefreshing}
                        className="flex items-center justify-center bg-slate-100 hover:bg-slate-200 rounded-lg px-2 text-slate-500 hover:text-indigo-500 transition-colors disabled:opacity-50"
                        title="刷新投入时间"
                      >
                        <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
                      </button>
                    ) : (
                      <span className="flex items-center justify-center bg-slate-100 rounded-lg px-2 text-[10px] font-bold text-slate-400">
                        h
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Date Range */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                    开始日期
                  </label>
                  <input
                    type="date"
                    className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all font-medium"
                    value={startDate}
                    onChange={(e) => onStartDateChange(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                    目标日期
                  </label>
                  <input
                    type="date"
                    className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all font-medium"
                    value={endDate}
                    onChange={(e) => onEndDateChange(e.target.value)}
                  />
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default QuickConfigPanel;
