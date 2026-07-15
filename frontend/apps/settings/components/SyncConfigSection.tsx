/**
 * 数据同步配置区域
 *
 * 提供云端地址输入和云端配置生成功能：
 * - 云端地址输入框（保存到 config.yaml::sync.remote_url）
 * - 生成云端配置按钮（弹出选择框：保留 Key / 更换 Key）
 */

import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Cloud, Loader2, CheckCircle, AlertTriangle, FolderOpen, X, Key, RefreshCw } from 'lucide-react';
import { SyncConfigAPI } from '../syncApi';
import type { GenerateCloudConfigResponse } from '../syncTypes';
import { toast } from '../../../core/components';

interface SyncConfigSectionProps {
    /** 初始云端地址（可选，不传则从 API 加载） */
    initialRemoteUrl?: string;
}

const SyncConfigSection: React.FC<SyncConfigSectionProps> = ({ initialRemoteUrl }) => {
    const [remoteUrl, setRemoteUrl] = useState(initialRemoteUrl || '');
    const [isLoadingUrl, setIsLoadingUrl] = useState(!initialRemoteUrl);
    const [isSaving, setIsSaving] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [result, setResult] = useState<GenerateCloudConfigResponse | null>(null);
    const [showChoiceDialog, setShowChoiceDialog] = useState(false);

    // 加载云端地址
    useEffect(() => {
        if (initialRemoteUrl !== undefined) {
            setRemoteUrl(initialRemoteUrl);
            setIsLoadingUrl(false);
            return;
        }
        let cancelled = false;
        (async () => {
            try {
                const url = await SyncConfigAPI.getRemoteUrl();
                if (!cancelled) {
                    setRemoteUrl(url);
                }
            } catch (err) {
                if (!cancelled) {
                    toast.error(err instanceof Error ? err.message : '获取云端地址失败');
                }
            } finally {
                if (!cancelled) {
                    setIsLoadingUrl(false);
                }
            }
        })();
        return () => { cancelled = true; };
    }, [initialRemoteUrl]);

    // 保存云端地址（失焦时触发）
    const handleSaveUrl = useCallback(async () => {
        setIsSaving(true);
        try {
            await SyncConfigAPI.saveRemoteUrl(remoteUrl);
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '保存云端地址失败');
        } finally {
            setIsSaving(false);
        }
    }, [remoteUrl]);

    // 点击生成按钮 -> 弹出选择框
    const handleGenerateClick = useCallback(() => {
        setShowChoiceDialog(true);
    }, []);

    // 执行生成（带 replace_key 参数）
    const doGenerate = useCallback(async (replaceKey: boolean) => {
        setShowChoiceDialog(false);
        setIsGenerating(true);
        setResult(null);
        try {
            const res = await SyncConfigAPI.generateCloudConfig(replaceKey);
            setResult(res);

            // 打开文件夹并选中文件
            await SyncConfigAPI.openFolderAndSelect(res.cloud_config_path);

            if (res.key_is_new) {
                toast.warning(
                    '配置已生成！新的同步 API Key 已生成。' +
                    '请在云端执行 reinit-config 以使用新 Key，否则同步将无法认证。'
                );
            } else {
                toast.success('配置已生成！使用已有的同步 API Key，请将配置文件复制到云端。');
            }
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '生成云端配置失败');
        } finally {
            setIsGenerating(false);
        }
    }, []);

    return (
        <section className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm">
            {/* 标题 */}
            <div className="flex items-center gap-3 mb-6">
                <div className="p-2.5 bg-blue-50 rounded-xl text-blue-600">
                    <Cloud size={20} />
                </div>
                <h2 className="text-lg font-bold text-slate-800">数据同步</h2>
            </div>

            <div className="space-y-6">
                {/* 云端地址输入框 */}
                <div>
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">
                        云端地址
                    </label>
                    <input
                        type="text"
                        aria-label="云端地址"
                        value={remoteUrl}
                        onChange={(e) => setRemoteUrl(e.target.value)}
                        onBlur={handleSaveUrl}
                        disabled={isLoadingUrl}
                        placeholder="https://your-cloud-server.com"
                        className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-blue-200 focus:ring-4 focus:ring-blue-50/50 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all disabled:opacity-50"
                    />
                    <p className="text-xs text-slate-500 mt-2">
                        云端服务器的完整地址（含 https://），用于数据同步。
                    </p>
                </div>

                {/* 生成云端配置按钮 */}
                <div>
                    <button
                        onClick={handleGenerateClick}
                        disabled={isGenerating}
                        className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-bold text-sm"
                    >
                        {isGenerating ? (
                            <span className="flex items-center gap-2">
                                <Loader2 className="w-4 h-4 animate-spin" />
                                生成中...
                            </span>
                        ) : (
                            <span className="flex items-center gap-2">
                                <FolderOpen className="w-4 h-4" />
                                生成云端配置
                            </span>
                        )}
                    </button>
                    <p className="text-xs text-slate-500 mt-2">
                        生成 cloud_init.yaml 配置文件（包含所有 API Key），复制到云端服务器即可使用。
                    </p>
                </div>

                {/* 生成结果信息面板 */}
                {result && (
                    <div
                        className={`border rounded-xl p-4 ${
                            result.key_is_new
                                ? 'border-amber-200 bg-amber-50'
                                : 'border-green-200 bg-green-50'
                        }`}
                    >
                        <div className="flex items-start gap-3">
                            {result.key_is_new ? (
                                <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                            ) : (
                                <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                            )}
                            <div className="flex-1 min-w-0">
                                {result.key_is_new ? (
                                    <div className="space-y-2">
                                        <p className="text-sm font-bold text-amber-800">
                                            配置已生成！同步 API Key 已更换。
                                        </p>
                                        <ol className="list-decimal list-inside space-y-1 text-xs text-amber-700">
                                            <li>将配置文件复制到云端 LifePrism/localData/ 目录</li>
                                            <li>在云端 LifePrism 目录下执行：python lifeprism/server/main_agent_only.py reinit-config</li>
                                            <li>重启云端服务使新 Key 生效</li>
                                        </ol>
                                        <p className="text-xs text-amber-700 font-medium">
                                            如果云端仍使用旧 Key，同步将无法认证。
                                        </p>
                                        <p className="text-xs text-amber-600 font-mono break-all">
                                            {result.cloud_config_path}
                                        </p>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        <p className="text-sm font-bold text-green-800">
                                            配置已生成！
                                        </p>
                                        <p className="text-xs text-green-700">
                                            使用已有的同步 API Key。请将配置文件复制到云端并执行 reinit-config。
                                        </p>
                                        <p className="text-xs text-green-600 font-mono break-all">
                                            {result.cloud_config_path}
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* 生成选项弹框：通过 Portal 挂到 document.body，
                避免 SettingsApp 根容器 animate-fade-in 的 transform 导致 fixed 失效 */}
            {showChoiceDialog && createPortal(
                <div
                    className="fixed inset-0 bg-black/30 flex items-center justify-center z-[9999]"
                    onClick={() => setShowChoiceDialog(false)}
                >
                    <div
                        className="bg-white rounded-2xl shadow-xl max-w-md w-full mx-4 overflow-hidden"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* 弹框标题 */}
                        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                            <h3 className="text-base font-bold text-slate-800">生成云端配置</h3>
                            <button
                                onClick={() => setShowChoiceDialog(false)}
                                className="text-gray-400 hover:text-gray-600 transition-colors"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        {/* 弹框内容 */}
                        <div className="p-6 space-y-3">
                            {/* 选项 1：保留 Key */}
                            <button
                                onClick={() => doGenerate(false)}
                                className="w-full text-left p-4 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all group"
                            >
                                <div className="flex items-start gap-3">
                                    <div className="p-2 bg-green-50 rounded-lg text-green-600 group-hover:bg-green-100 transition-colors">
                                        <Key size={18} />
                                    </div>
                                    <div className="flex-1">
                                        <p className="text-sm font-bold text-slate-800">保留当前 Key</p>
                                        <p className="text-xs text-slate-500 mt-1">
                                            使用已有的 sync_api_key，仅生成配置文档。适用于更新 LLM 配置或测试。
                                        </p>
                                    </div>
                                </div>
                            </button>

                            {/* 选项 2：更换 Key */}
                            <button
                                onClick={() => doGenerate(true)}
                                className="w-full text-left p-4 rounded-xl border border-gray-200 hover:border-amber-300 hover:bg-amber-50/50 transition-all group"
                            >
                                <div className="flex items-start gap-3">
                                    <div className="p-2 bg-amber-50 rounded-lg text-amber-600 group-hover:bg-amber-100 transition-colors">
                                        <RefreshCw size={18} />
                                    </div>
                                    <div className="flex-1">
                                        <p className="text-sm font-bold text-slate-800">更换 Key 并生成</p>
                                        <p className="text-xs text-slate-500 mt-1">
                                            重新生成 sync_api_key。适用于 Key 轮换或可能泄露。
                                        </p>
                                        <div className="mt-2 px-2 py-1 bg-amber-50 rounded text-[11px] text-amber-700">
                                            更换后必须将 cloud_init.yaml 复制到云端并执行 reinit-config，否则同步无法认证。
                                        </div>
                                    </div>
                                </div>
                            </button>
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </section>
    );
};

export { SyncConfigSection };
