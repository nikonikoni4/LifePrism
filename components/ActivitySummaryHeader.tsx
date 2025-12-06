
import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Calendar, Filter, RefreshCw, Clock, Database } from 'lucide-react';
import { ActivitySummaryResponse } from '../types';
import { DashboardAPI } from '../services/dashboardService';
import { incrementalSync, syncActivityWatchDataByTimeRange } from '../services/syncService';

// 安全的日期解析函数,支持多种格式
const parseLocalDate = (dateStr: string): Date => {
  // 判断输入格式
  const dateRegex = /^(\d{4})-(\d{2})-(\d{2})$/;
  const match = dateStr.match(dateRegex);

  if (match) {
    // 如果是 YYYY-MM-DD 格式，手动解析为本地时间
    const year = parseInt(match[1]);
    const month = parseInt(match[2]) - 1; // 月份从0开始
    const day = parseInt(match[3]);
    return new Date(year, month, day);
  } else {
    // 其他格式，尝试直接解析
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) {
      throw new Error(`Invalid date format: ${dateStr}`);
    }
    return date;
  }
};

// 格式化日期为 YYYY-MM-DD 格式，确保一致性
const formatDateToYYYYMMDD = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// 规范化日期到午夜（本地时间），用于日期比较
const normalizeDateToMidnight = (date: Date): Date => {
  const normalized = new Date(date);
  normalized.setHours(0, 0, 0, 0);
  return normalized;
};

// Generate 30 days of mock history data centered around the selected date
// Note: This function is kept for backward compatibility but not currently used
const generateMockHistory = (centerDateStr: string) => {
  const history = [];
  const centerDate = parseLocalDate(centerDateStr);
  const today = normalizeDateToMidnight(new Date());

  // Window: 15 days before + center date + 14 days after = 30 days
  const startDate = new Date(centerDate);
  startDate.setDate(centerDate.getDate() - 16);

  for (let i = 0; i < 30; i++) {
    const d = new Date(startDate);
    d.setDate(startDate.getDate() + i);

    const month = d.getMonth() + 1;
    const day = d.getDate();
    const dateStr = `${month}/${day}`;
    const fullDate = formatDateToYYYYMMDD(d);

    // Random value between 10 and 100, with some "weekend" dips
    const dayOfWeek = d.getDay();
    let baseValue = Math.floor(Math.random() * 60) + 30;
    if (dayOfWeek === 0 || dayOfWeek === 6) baseValue -= 20;

    const isActualToday = fullDate === formatDateToYYYYMMDD(today);
    const isFuture = d.getTime() > today.getTime();
    const isSelected = fullDate === centerDateStr;

    history.push({
      day: dateStr,
      fullDate: fullDate,
      value: Math.max(10, baseValue),
      isActualToday,
      isFuture,
      isSelected
    });
  }
  return history;
};

const getActivitySummary = async (centerDate: string, historyNumber: number, futureNumber: number) => {
  try {
    const ActivitySummaryData = await DashboardAPI.getActivitySummaryData(centerDate, historyNumber, futureNumber);
    console.log('ActivitySummaryData:', ActivitySummaryData);
    const dailyActivities = ActivitySummaryData.dailyActivities || [];
    const totalDay = historyNumber + futureNumber + 1;
    const TodayTotalActiveTime = ActivitySummaryData.todayActiveTime;

    // 使用安全的日期解析并规范化到午夜
    const centerDateObj = normalizeDateToMidnight(parseLocalDate(centerDate));
    const startDate = new Date(centerDateObj);
    startDate.setDate(startDate.getDate() - historyNumber);

    // 获取实际的今天日期（而不是中心日期）
    const actualToday = normalizeDateToMidnight(new Date());

    console.log("centerDate:", centerDate);
    console.log("centerDateObj:", formatDateToYYYYMMDD(centerDateObj));
    console.log("startDate:", formatDateToYYYYMMDD(startDate));
    console.log("actualToday:", formatDateToYYYYMMDD(actualToday));

    const history = []

    for (let i = 0; i < totalDay; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);

      // 格式化日期字符串
      const month = d.getMonth() + 1;
      const day = d.getDate();
      const dateStr = `${month}/${day}`;

      // 使用统一的日期格式 YYYY-MM-DD
      const fullDate = formatDateToYYYYMMDD(d);

      // 使用字符串比较，避免时区问题
      const isActualToday = fullDate === formatDateToYYYYMMDD(actualToday);
      const isFuture = d.getTime() > actualToday.getTime();
      const isSelected = fullDate === centerDate;

      console.log(`Date: ${fullDate}, isToday: ${isActualToday}, isFuture: ${isFuture}, isSelected: ${isSelected}`);

      // 安全地获取活动数据，防止数组越界
      const activityData = dailyActivities[i];
      const value = activityData ? activityData.activeTimePercentage : 0;

      history.push({
        day: dateStr,
        fullDate: fullDate,
        value: value,
        isActualToday,
        isFuture,
        isSelected
      })
      console.log(history[i])
    }

    return [history, TodayTotalActiveTime];
  } catch (error) {
    console.error('Error getting activity summary:', error);
    // 返回空数组作为后备方案
    return [];
  }
}

// Helper function to process ActivitySummaryResponse data (when passed as prop)
const processActivitySummaryData = (
  activitySummaryData: ActivitySummaryResponse,
  centerDate: string,
  historyNumber: number,
  futureNumber: number
) => {
  const dailyActivities = activitySummaryData.dailyActivities || [];
  const totalDay = historyNumber + futureNumber + 1;

  const centerDateObj = normalizeDateToMidnight(parseLocalDate(centerDate));
  const startDate = new Date(centerDateObj);
  startDate.setDate(startDate.getDate() - historyNumber);

  const actualToday = normalizeDateToMidnight(new Date());

  const history = [];

  for (let i = 0; i < totalDay && i < dailyActivities.length; i++) {
    const d = new Date(startDate);
    d.setDate(d.getDate() + i);

    const month = d.getMonth() + 1;
    const day = d.getDate();
    const dateStr = `${month}/${day}`;
    const fullDate = formatDateToYYYYMMDD(d);

    const isActualToday = fullDate === formatDateToYYYYMMDD(actualToday);
    const isFuture = d.getTime() > actualToday.getTime();
    const isSelected = fullDate === centerDate;

    const activityData = dailyActivities[i];
    const value = activityData ? activityData.activeTimePercentage : 0;

    history.push({
      day: dateStr,
      fullDate: fullDate,
      value: value,
      isActualToday,
      isFuture,
      isSelected
    });
  }

  return history;
};

interface ActivitySummaryHeaderProps {
  selectedDate: string;
  onDateChange: (date: string) => void;
  activitySummaryData?: ActivitySummaryResponse; // Optional: if provided, use this data instead of fetching
  onRefresh?: () => void;
}

const ActivitySummaryHeader: React.FC<ActivitySummaryHeaderProps> = ({ selectedDate, onDateChange, activitySummaryData, onRefresh }) => {
  const dateInputRef = React.useRef<HTMLInputElement>(null);
  const [history, setHistory] = React.useState<any[]>([]);
  const [TodayTotalActiveTime, setTodayTotalActiveTime] = React.useState<string>('');
  const [isLoading, setIsLoading] = React.useState(true);
  const [isSyncing, setIsSyncing] = React.useState(false);
  const [showSyncDialog, setShowSyncDialog] = React.useState(false);
  const [syncStartDate, setSyncStartDate] = React.useState('');
  const [syncEndDate, setSyncEndDate] = React.useState('');

  // 使用useEffect处理异步数据获取
  React.useEffect(() => {
    // If activitySummaryData is provided, use it directly
    if (activitySummaryData) {
      // Process the provided data
      const processedHistory = processActivitySummaryData(activitySummaryData, selectedDate, 15, 14);
      setHistory(processedHistory);
      setTodayTotalActiveTime(activitySummaryData.todayActiveTime);
      setIsLoading(false);
      return;
    }

    // Otherwise, fetch data from API (backward compatibility)
    const fetchHistory = async () => {
      setIsLoading(true);
      try {
        const [historyData, TodayTotalActiveTime] = await getActivitySummary(selectedDate, 15, 14);
        setHistory(historyData);
        setTodayTotalActiveTime(TodayTotalActiveTime);
      } catch (error) {
        console.error('Failed to fetch history:', error);
        setHistory([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchHistory();
  }, [selectedDate, activitySummaryData]);

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onDateChange(e.target.value);
  };

  const formatDateDisplay = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' });
  };

  const handleCalendarClick = () => {
    if (dateInputRef.current) {
      if ('showPicker' in dateInputRef.current) {
        (dateInputRef.current as any).showPicker();
      } else {
        dateInputRef.current.click();
      }
    }
  };

  const handlePrevDay = () => {
    const date = parseLocalDate(selectedDate);
    date.setDate(date.getDate() - 1);
    onDateChange(formatDateToYYYYMMDD(date));
  };

  const handleNextDay = () => {
    const date = parseLocalDate(selectedDate);
    date.setDate(date.getDate() + 1);
    onDateChange(formatDateToYYYYMMDD(date));
  };

  // 格式化日期时间为 YYYY-MM-DD HH:MM:SS
  const formatDateTime = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  };

  // 打开同步对话框，设置默认时间范围
  const handleOpenSyncDialog = () => {
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    yesterday.setHours(0, 0, 0, 0);

    const endOfToday = new Date(now);
    endOfToday.setHours(23, 59, 59, 0);

    setSyncStartDate(formatDateToYYYYMMDD(yesterday));
    setSyncEndDate(formatDateToYYYYMMDD(now));
    setShowSyncDialog(true);
  };

  // 执行时间范围同步
  const handleTimeRangeSync = async () => {
    if (!syncStartDate || !syncEndDate) {
      alert('请选择开始和结束日期');
      return;
    }

    setIsSyncing(true);
    setShowSyncDialog(false);

    try {
      // 构建完整的时间字符串
      const startDateTime = `${syncStartDate} 00:00:00`;
      const endDateTime = `${syncEndDate} 23:59:59`;

      await syncActivityWatchDataByTimeRange({
        start_time: startDateTime,
        end_time: endDateTime,
        auto_classify: true,
      });

      if (onRefresh) {
        onRefresh();
      }
      alert('数据同步成功！');
    } catch (error) {
      console.error('Sync failed:', error);
      alert('数据同步失败，请查看控制台了解详情');
    } finally {
      setIsSyncing(false);
    }
  };

  // Calculate start and end dates for labels based on the window
  const startDateLabel = history.length > 0 ? history[0].day : "";
  const endDateLabel = history.length > 0 ? history[history.length - 1].day : "";

  // 错误状态显示
  if (history.length === 0 && !isLoading) {
    return (
      <div className="bg-white rounded-3xl p-6 lg:p-8 shadow-sm border border-gray-100 mb-8 animate-fade-in w-full">
        <div className="text-center text-gray-500">
          <p>No activity data available</p>
          <p className="text-sm mt-1">Please check your connection or try refreshing</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white rounded-3xl p-6 lg:p-8 shadow-sm border border-gray-100 mb-8 animate-fade-in w-full transition-opacity duration-300 ${isLoading ? 'opacity-50' : 'opacity-100'}`}>

      {/* Top Row: Title & Stats */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
            Activity Summary
            <span className="text-slate-300 font-light hidden md:inline">|</span>
            <span className="text-slate-500 font-medium text-lg">{formatDateDisplay(selectedDate)}</span>
          </h2>
          <div className="flex items-center gap-2 mt-2 text-morandi-blue font-semibold">
            <Clock size={16} />
            <span>Total Active Time: <span className="font-mono text-lg font-bold">{TodayTotalActiveTime}</span></span>
          </div>
        </div>
      </div>

      {/* Middle Row: Controls */}
      <div className="flex flex-col md:flex-row justify-between items-center gap-4 mb-8">
        {/* Date Navigation */}
        <div className="flex items-center w-full md:w-auto bg-gray-50 p-1 rounded-xl border border-gray-200 relative group">
          <button
            onClick={handlePrevDay}
            className="p-2 hover:bg-white hover:shadow-sm rounded-lg text-slate-500 transition-all z-10"
          >
            <ChevronLeft size={20} />
          </button>

          <div
            className="flex-1 md:flex-none px-4 flex items-center justify-center gap-2 border-l border-r border-gray-200/50 mx-1 relative cursor-pointer"
            onClick={handleCalendarClick}
          >
            {/* Invisible Date Picker Trigger */}
            <input
              ref={dateInputRef}
              type="date"
              value={selectedDate}
              onChange={handleDateChange}
              className="absolute inset-0 opacity-0 cursor-pointer z-20 w-full h-full pointer-events-none"
            />
            <Calendar size={18} className="text-morandi-blue pointer-events-none" />
            <span className="text-sm font-bold text-slate-700 whitespace-nowrap pointer-events-none">{selectedDate}</span>
          </div>

          <button
            onClick={handleNextDay}
            className="p-2 hover:bg-white hover:shadow-sm rounded-lg text-slate-500 transition-all z-10"
          >
            <ChevronRight size={20} />
          </button>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 w-full md:w-auto">
          <button className="flex-1 md:flex-none flex items-center justify-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-slate-600 text-sm font-semibold hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm">
            <Filter size={16} />
            Filters
          </button>
          <button
            onClick={async () => {
              if (isSyncing) return;
              setIsSyncing(true);
              try {
                await incrementalSync();
                if (onRefresh) {
                  onRefresh();
                }
              } catch (error) {
                console.error('Sync failed:', error);
              } finally {
                setIsSyncing(false);
              }
            }}
            className={`flex-1 md:flex-none flex items-center justify-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-slate-600 text-sm font-semibold hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm ${isSyncing ? 'opacity-70 cursor-not-allowed' : ''}`}
            disabled={isSyncing}
          >
            <RefreshCw size={16} className={isSyncing ? 'animate-spin' : ''} />
            {isSyncing ? 'Syncing...' : 'Refresh'}
          </button>
          <button
            onClick={handleOpenSyncDialog}
            className="flex-1 md:flex-none flex items-center justify-center gap-2 px-4 py-2.5 bg-morandi-blue text-white border border-morandi-blue rounded-xl text-sm font-semibold hover:bg-opacity-90 transition-all shadow-sm"
            disabled={isSyncing}
          >
            <Database size={16} />
            Sync Data
          </button>
        </div>
      </div>

      {/* Bottom Row: Mini Trend Chart (Sparkline) */}
      <div className="relative pt-6 border-t border-dashed border-gray-100">
        <div className="h-[80px] flex items-end justify-between gap-1 md:gap-2">
          {history.map((item, index) => (
            <div key={index} className="flex-1 flex flex-col justify-end group relative h-full">
              {/* Tooltip on Hover */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-800 text-white text-[10px] py-1 px-2 rounded pointer-events-none whitespace-nowrap z-10 shadow-lg">
                {item.day}: {item.value * 24 / 100}h
              </div>

              {/* The Bar */}
              <div
                onClick={() => !item.isFuture && onDateChange(item.fullDate)}
                className={`w-full rounded-t-sm transition-all duration-300 relative min-h-[4px] 
                  ${item.isFuture
                    ? 'bg-transparent border-2 border-dashed border-gray-300 cursor-default'
                    : 'cursor-pointer hover:opacity-80'
                  }
                  ${!item.isFuture && item.isSelected ? 'bg-morandi-orange' : ''}
                  ${!item.isFuture && !item.isSelected ? 'bg-gray-200' : ''}
                `}
                style={{ height: item.isFuture ? '40%' : `${item.value}%` }}
              >
                {/* "Today" Indicator Label - Always on actual today */}
                {item.isActualToday && (
                  <div className="absolute -top-8 left-1/2 -translate-x-1/2 flex flex-col items-center animate-bounce-slight z-20">
                    <span className="bg-morandi-orange text-white text-[10px] font-bold px-2 py-0.5 rounded-full shadow-sm whitespace-nowrap">
                      Today
                    </span>
                    <div className="w-0 h-0 border-l-[4px] border-l-transparent border-r-[4px] border-r-transparent border-t-[4px] border-t-morandi-orange mt-0.5"></div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* X-Axis Labels */}
        <div className="flex justify-between mt-2 px-1">
          <span className="text-[10px] font-bold text-gray-400">{startDateLabel}</span>
          <span className="text-[10px] font-bold text-gray-400">{endDateLabel}</span>
        </div>
      </div>

      {/* Sync Time Range Dialog */}
      {showSyncDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 shadow-2xl max-w-md w-full mx-4 animate-fade-in">
            <h3 className="text-xl font-bold text-slate-900 mb-4">同步数据</h3>
            <p className="text-sm text-slate-600 mb-6">选择要同步的时间范围</p>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  开始日期
                </label>
                <input
                  type="date"
                  value={syncStartDate}
                  onChange={(e) => setSyncStartDate(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-morandi-blue focus:border-transparent"
                />
                <p className="text-xs text-slate-500 mt-1">时间将从 00:00:00 开始</p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  结束日期
                </label>
                <input
                  type="date"
                  value={syncEndDate}
                  onChange={(e) => setSyncEndDate(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-morandi-blue focus:border-transparent"
                />
                <p className="text-xs text-slate-500 mt-1">时间将到 23:59:59 结束</p>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowSyncDialog(false)}
                className="flex-1 px-4 py-2.5 bg-gray-100 text-slate-700 rounded-xl font-semibold hover:bg-gray-200 transition-all"
              >
                取消
              </button>
              <button
                onClick={handleTimeRangeSync}
                className="flex-1 px-4 py-2.5 bg-morandi-blue text-white rounded-xl font-semibold hover:bg-opacity-90 transition-all"
              >
                开始同步
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default ActivitySummaryHeader;
