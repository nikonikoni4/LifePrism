/**
 * 同步状态展示区域
 *
 * 提供同步状态的可视化展示和手动同步功能：
 * - 上次同步时间（相对时间格式）
 * - 同步状态徽章（idle/syncing/error）
 * - 同步记录数（按表展开，可折叠）
 * - 手动同步按钮（带 loading 状态）
 * - 重置同步进度按钮（带二次确认弹窗，清空 last_sync_time 触发下次全量同步）
 * - 自动刷新（idle 每 30 秒，syncing 每 5 秒）
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    RefreshCw,
    CheckCircle,
    Loader2,
    AlertCircle,
    ChevronDown,
    ChevronUp,
    Server,
    RotateCcw,
} from 'lucide-react';
import { SyncConfigAPI } from '../syncApi';
import type { SyncStatus } from '../syncTypes';
import { formatRelativeTime } from '../syncUtils';
import { toast } from '../../../core/components';
import { ConfirmDialog } from '../../goals/components/shared/components/ConfirmDialog';

/** 同步进行中时的轮询间隔（毫秒） */
const POLL_INTERVAL_SYNCING = 5000;
/** 空闲时的轮询间隔（毫秒） */
const POLL_INTERVAL_IDLE = 30000;

const SyncStatusSection: React.FC = () => {
    const [status, setStatus] = useState<SyncStatus | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isTriggering, setIsTriggering] = useState(false);
    const [isExpanded, setIsExpanded] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isResetDialogOpen, setIsResetDialogOpen] = useState(false);
    const [isResetting, setIsResetting] = useState(false);

    // 用于在 fetchStatus 中引用最新状态（避免闭包陷阱）
    const statusRef = useRef<SyncStatus | null>(null);
    statusRef.current = status;

    // 获取同步状态
    const fetchStatus = useCallback(async () => {
        try {
            const data = await SyncConfigAPI.getSyncStatus();
            setStatus(data);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : '获取同步状态失败');
        } finally {
            setIsLoading(false);
        }
    }, []);

    // 初始加载
    useEffect(() => {
        fetchStatus();
    }, [fetchStatus]);

    // 自动刷新：idle 每 30 秒，syncing 每 5 秒
    useEffect(() => {
        const currentStatus = statusRef.current?.status;
        const interval = currentStatus === 'syncing' ? POLL_INTERVAL_SYNCING : POLL_INTERVAL_IDLE;
        const timer = setInterval(() => {
            fetchStatus();
        }, interval);
        return () => clearInterval(timer);
    }, [fetchStatus, status?.status]);

    // 手动触发同步
    const handleTriggerSync = useCallback(async () => {
        setIsTriggering(true);
        try {
            await SyncConfigAPI.triggerSync();
            // 触发后立即刷新状态
            await fetchStatus();
            toast.success('同步已触发，正在后台执行');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '触发同步失败');
        } finally {
            setIsTriggering(false);
        }
    }, [fetchStatus]);

    // 确认重置同步进度（清空 last_sync_time，下次同步将变为全量同步）
    const handleConfirmReset = useCallback(async () => {
        setIsResetting(true);
        try {
            await SyncConfigAPI.resetSyncProgress();
            // 重置后刷新状态（last_sync_time 会变为空）
            await fetchStatus();
            toast.success('同步进度已重置，下次同步将为全量同步');
            setIsResetDialogOpen(false);
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '重置同步进度失败');
        } finally {
            setIsResetting(false);
        }
    }, [fetchStatus]);

    // 计算总记录数
    const totalRecords = status
        ? Object.values(status.tables).reduce((sum, count) => sum + count, 0)
        : 0;
    const tableCount = status ? Object.keys(status.tables).length : 0;

    // 状态徽章配置
    const getBadgeConfig = () => {
        if (!status || isTriggering) {
            return {
                text: '同步中',
                bgClass: 'bg-blue-50 text-blue-700 border-blue-200',
                icon: <Loader2 size={14} className="animate-spin" />,
            };
        }
        switch (status.status) {
            case 'idle':
                return {
                    text: '已同步',
                    bgClass: 'bg-green-50 text-green-700 border-green-200',
                    icon: <CheckCircle size={14} />,
                };
            case 'syncing':
                return {
                    text: '同步中',
                    bgClass: 'bg-blue-50 text-blue-700 border-blue-200',
                    icon: <Loader2 size={14} className="animate-spin" />,
                };
            case 'error':
                return {
                    text: '同步错误',
                    bgClass: 'bg-red-50 text-red-700 border-red-200',
                    icon: <AlertCircle size={14} />,
                };
            default:
                return {
                    text: '未知',
                    bgClass: 'bg-gray-50 text-gray-700 border-gray-200',
                    icon: <AlertCircle size={14} />,
                };
        }
    };

    const badge = getBadgeConfig();
    const isSyncing = isTriggering || status?.status === 'syncing';

    return (
        <section className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm">
            {/* 标题 */}
            <div className="flex items-center gap-3 mb-6">
                <div className="p-2.5 bg-teal-50 rounded-xl text-teal-600">
                    <RefreshCw size={20} />
                </div>
                <h2 className="text-lg font-bold text-slate-800">同步状态</h2>
            </div>

            {/* 加载中状态 */}
            {isLoading && !status && !error && (
                <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
                    <span className="ml-2 text-sm text-slate-400">加载中...</span>
                </div>
            )}

            {/* 错误状态 */}
            {error && !isLoading && (
                <div className="flex items-center gap-2 py-4 text-red-600">
                    <AlertCircle size={18} />
                    <span className="text-sm">{error}</span>
                </div>
            )}

            {/* 正常显示 */}
            {status && !error && (
                <div className="space-y-5">
                    {/* 状态徽章 + 上次同步时间 */}
                    <div className="flex items-center justify-between flex-wrap gap-3">
                        <div className="flex items-center gap-3">
                            <span
                                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-bold ${badge.bgClass}`}
                            >
                                {badge.icon}
                                {badge.text}
                            </span>
                            <div className="text-sm text-slate-600">
                                <span className="text-slate-400">上次同步：</span>
                                <span className="font-medium">
                                    {formatRelativeTime(status.last_sync_time)}
                                </span>
                            </div>
                        </div>

                        {/* 手动同步按钮 + 重置同步进度按钮 */}
                        <div className="flex items-center gap-2">
                            <button
                                onClick={handleTriggerSync}
                                disabled={isSyncing}
                                className="px-5 py-2.5 bg-teal-600 text-white rounded-xl hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-bold text-sm flex items-center gap-2"
                            >
                                {isSyncing ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        同步中...
                                    </>
                                ) : (
                                    <>
                                        <RefreshCw className="w-4 h-4" />
                                        手动同步（增量）
                                    </>
                                )}
                            </button>
                            <button
                                onClick={() => setIsResetDialogOpen(true)}
                                disabled={isSyncing}
                                className="px-4 py-2.5 bg-white text-slate-600 border border-slate-200 rounded-xl hover:bg-slate-50 hover:text-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-bold text-sm flex items-center gap-2"
                                title="清空同步进度，下次同步将变为全量同步。适用于换服务器或云端数据重置场景。"
                            >
                                <RotateCcw className="w-4 h-4" />
                                重置同步进度
                            </button>
                        </div>
                    </div>

                    {/* 远程地址 */}
                    {status.remote_url && (
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                            <Server size={14} className="text-slate-400" />
                            <span className="font-mono break-all">{status.remote_url}</span>
                        </div>
                    )}

                    {/* 同步记录数 */}
                    <div className="bg-gray-50 rounded-xl p-4">
                        {/* 摘要 + 折叠按钮 */}
                        <div className="flex items-center justify-between">
                            <div className="text-sm text-slate-600">
                                <span className="font-bold text-slate-800">{tableCount}</span>
                                <span className="ml-1">张表</span>
                                <span className="mx-2 text-slate-300">|</span>
                                <span className="font-bold text-slate-800">{totalRecords}</span>
                                <span className="ml-1">条记录</span>
                            </div>
                            <button
                                onClick={() => setIsExpanded(!isExpanded)}
                                className="text-xs text-slate-500 hover:text-slate-700 flex items-center gap-1 transition-colors"
                            >
                                {isExpanded ? (
                                    <>
                                        收起
                                        <ChevronUp size={14} />
                                    </>
                                ) : (
                                    <>
                                        展开
                                        <ChevronDown size={14} />
                                    </>
                                )}
                            </button>
                        </div>

                        {/* 表详情列表 */}
                        {isExpanded && tableCount > 0 && (
                            <div className="mt-3 space-y-1.5">
                                {Object.entries(status.tables).map(([tableName, count]) => (
                                    <div
                                        key={tableName}
                                        className="flex items-center justify-between py-1.5 px-3 bg-white rounded-lg text-sm"
                                    >
                                        <span className="font-mono text-slate-700">{tableName}</span>
                                        <span className="font-bold text-slate-800">{count}</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        {isExpanded && tableCount === 0 && (
                            <div className="mt-3 text-center text-xs text-slate-400 py-2">
                                暂无同步记录
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* 重置同步进度二次确认弹窗 */}
            <ConfirmDialog
                isOpen={isResetDialogOpen}
                onClose={() => !isResetting && setIsResetDialogOpen(false)}
                onConfirm={handleConfirmReset}
                title="重置同步进度"
                variant="danger"
                confirmText={isResetting ? '重置中...' : '确认重置'}
                cancelText={isResetting ? undefined : '取消'}
                message={
                    <div className="space-y-2">
                        <p className="text-sm text-slate-600">
                            此操作将清空本地的同步进度记录（last_sync_time），使下次同步变为全量同步。
                        </p>
                        <p className="text-sm text-slate-600">
                            <span className="font-semibold text-slate-800">适用场景：</span>换服务器、云端数据库重置、本地数据库重置后需要全量同步。
                        </p>
                        <p className="text-sm text-red-600">
                            <span className="font-semibold">注意：</span>全量同步可能耗时较长（取决于数据量），期间同步状态会显示"同步中"。
                        </p>
                    </div>
                }
            />
        </section>
    );
};

export { SyncStatusSection };
