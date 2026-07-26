/**
 * 数据同步配置区域
 *
 * 提供云端地址输入和云端配置生成功能：
 * - 连接方式切换（HTTP/HTTPS ↔ SSH 隧道）
 * - HTTP/HTTPS 选项卡：云端地址输入 + 生成云端配置按钮
 * - SSH 隧道选项卡：SSH 参数表单 + 公钥展示 + 配置命令展示 + 测试连接按钮
 */

import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
    Cloud,
    Loader2,
    CheckCircle,
    AlertTriangle,
    FolderOpen,
    X,
    Key,
    RefreshCw,
    Copy,
    Terminal,
    Activity,
    Globe,
    Shield,
} from 'lucide-react';
import { SyncConfigAPI } from '../syncApi';
import type {
    ConnectionMode,
    GenerateCloudConfigResponse,
    SSHTunnelConfig,
    SSHTunnelTestResponse,
} from '../syncTypes';
import { toast } from '../../../core/components';

interface SyncConfigSectionProps {
    /** 初始云端地址（可选，不传则从 API 加载） */
    initialRemoteUrl?: string;
}

/**
 * 拼接云端 SSH 公钥配置命令模板
 *
 * 公钥值从 GET /public-key 响应中获取，前端动态拼接成完整命令。
 */
const buildConfigCommand = (publicKey: string): string => {
    return `# 在云端服务器执行以下命令（追加 SSH 公钥）
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo '${publicKey}' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys`;
};

const DEFAULT_SSH_CONFIG: SSHTunnelConfig = {
    host: '',
    port: 22,
    username: '',
    local_port: 8102,
    remote_port: 8102,
};

const SyncConfigSection: React.FC<SyncConfigSectionProps> = ({ initialRemoteUrl }) => {
    // ===== HTTP/HTTPS 选项卡状态 =====
    const [remoteUrl, setRemoteUrl] = useState(initialRemoteUrl || '');
    const [isLoadingUrl, setIsLoadingUrl] = useState(!initialRemoteUrl);
    const [isSaving, setIsSaving] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [result, setResult] = useState<GenerateCloudConfigResponse | null>(null);
    const [showChoiceDialog, setShowChoiceDialog] = useState(false);

    // ===== 连接方式切换状态 =====
    const [connectionMode, setConnectionMode] = useState<ConnectionMode>('http');
    const [isLoadingMode, setIsLoadingMode] = useState(true);
    const [isEnabling, setIsEnabling] = useState(false);

    // ===== SSH 选项卡状态 =====
    // 注意：sshConfig 在切换回 HTTP 模式时保留不重置（参考验收标准）
    const [sshConfig, setSshConfig] = useState<SSHTunnelConfig>(DEFAULT_SSH_CONFIG);
    const [publicKey, setPublicKey] = useState('');
    const [isTesting, setIsTesting] = useState(false);
    const [testResult, setTestResult] = useState<SSHTunnelTestResponse | null>(null);

    // 加载云端地址
    useEffect(() => {
        if (initialRemoteUrl !== undefined) {
            setRemoteUrl(initialRemoteUrl);
            setIsLoadingUrl(false);
        } else {
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
        }
    }, [initialRemoteUrl]);

    // 加载连接方式
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const mode = await SyncConfigAPI.getConnectionMode();
                if (cancelled) return;
                setConnectionMode(mode);
                // 如果初始就是 SSH 模式，自动加载公钥（不再调 enable，因为私钥已存在）
                if (mode === 'ssh') {
                    try {
                        const keyResp = await SyncConfigAPI.getPublicKey();
                        if (!cancelled) {
                            setPublicKey(keyResp.public_key);
                        }
                    } catch (err) {
                        if (!cancelled) {
                            toast.error(err instanceof Error ? err.message : '获取 SSH 公钥失败');
                        }
                    }
                }
            } catch (err) {
                if (!cancelled) {
                    toast.error(err instanceof Error ? err.message : '获取连接方式失败');
                }
            } finally {
                if (!cancelled) {
                    setIsLoadingMode(false);
                }
            }
        })();
        return () => { cancelled = true; };
    }, []);

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

    // 切换到 SSH 模式：enable → getPublicKey → saveConnectionMode
    const handleSwitchToSsh = useCallback(async () => {
        if (isEnabling) return;
        setIsEnabling(true);
        setConnectionMode('ssh');
        setTestResult(null);

        try {
            // 1. 调 enable 触发密钥准备（如已存在则保留）
            await SyncConfigAPI.enableSshTunnel();

            // 2. 调 getPublicKey 加载公钥展示
            try {
                const keyResp = await SyncConfigAPI.getPublicKey();
                setPublicKey(keyResp.public_key);
            } catch (err) {
                toast.error(err instanceof Error ? err.message : '获取 SSH 公钥失败');
            }

            // 3. 调 saveConnectionMode 保存连接方式
            try {
                await SyncConfigAPI.saveConnectionMode('ssh');
            } catch (err) {
                toast.error(err instanceof Error ? err.message : '保存连接方式失败');
            }
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '启用 SSH 隧道失败');
        } finally {
            setIsEnabling(false);
        }
    }, [isEnabling]);

    // 切换回 HTTP 模式：仅保存 connection_mode，SSH 配置保留
    const handleSwitchToHttp = useCallback(async () => {
        setConnectionMode('http');
        setTestResult(null);

        try {
            await SyncConfigAPI.saveConnectionMode('http');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '保存连接方式失败');
        }
    }, []);

    // 切换连接方式入口
    const handleSwitchMode = useCallback((mode: ConnectionMode) => {
        if (mode === connectionMode) return;
        if (mode === 'ssh') {
            handleSwitchToSsh();
        } else {
            handleSwitchToHttp();
        }
    }, [connectionMode, handleSwitchToSsh, handleSwitchToHttp]);

    // 复制公钥到剪贴板
    const handleCopyPublicKey = useCallback(async () => {
        if (!publicKey) return;
        try {
            await navigator.clipboard.writeText(publicKey);
            toast.success('公钥已复制到剪贴板');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '复制公钥失败');
        }
    }, [publicKey]);

    // 复制配置命令到剪贴板
    const handleCopyCommand = useCallback(async () => {
        const cmd = buildConfigCommand(publicKey);
        try {
            await navigator.clipboard.writeText(cmd);
            toast.success('配置命令已复制到剪贴板');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '复制命令失败');
        }
    }, [publicKey]);

    // 测试 SSH 连接
    const handleTestConnection = useCallback(async () => {
        if (isTesting) return;
        setIsTesting(true);
        setTestResult(null);

        try {
            const resp = await SyncConfigAPI.testConnection({
                host: sshConfig.host,
                port: sshConfig.port,
                username: sshConfig.username,
                local_port: sshConfig.local_port,
                remote_port: sshConfig.remote_port,
            });
            setTestResult(resp);
        } catch (err) {
            setTestResult({
                status: 'error',
                error: err instanceof Error ? err.message : '测试连接失败',
            });
        } finally {
            setIsTesting(false);
        }
    }, [isTesting, sshConfig]);

    // 更新 SSH 配置字段
    const updateSshField = useCallback(<K extends keyof SSHTunnelConfig>(
        field: K,
        value: SSHTunnelConfig[K],
    ) => {
        setSshConfig(prev => ({ ...prev, [field]: value }));
    }, []);

    const configCommand = buildConfigCommand(publicKey);

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
                {/* 连接方式切换 */}
                <div>
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-4 block">
                        连接方式
                    </label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* HTTP/HTTPS 选项卡 */}
                        <button
                            type="button"
                            aria-pressed={connectionMode === 'http'}
                            onClick={() => handleSwitchMode('http')}
                            disabled={isEnabling || isLoadingMode}
                            className={`text-left p-4 rounded-2xl border-2 transition-all ${
                                connectionMode === 'http'
                                    ? 'border-blue-500 bg-blue-50/30'
                                    : 'border-gray-100 hover:border-blue-200 bg-white'
                            }`}
                        >
                            <div className="flex justify-between items-start mb-1">
                                <span className={`font-bold flex items-center gap-2 ${connectionMode === 'http' ? 'text-blue-700' : 'text-slate-700'}`}>
                                    <Globe size={16} />
                                    HTTP/HTTPS
                                </span>
                                {connectionMode === 'http' && <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5" />}
                            </div>
                            <p className="text-xs text-slate-500 leading-relaxed">
                                直接通过云端地址连接。需要公网可达，适合有固定 IP 或域名的场景。
                            </p>
                        </button>

                        {/* SSH 隧道选项卡 */}
                        <button
                            type="button"
                            aria-pressed={connectionMode === 'ssh'}
                            onClick={() => handleSwitchMode('ssh')}
                            disabled={isEnabling || isLoadingMode}
                            className={`text-left p-4 rounded-2xl border-2 transition-all ${
                                connectionMode === 'ssh'
                                    ? 'border-purple-500 bg-purple-50/30'
                                    : 'border-gray-100 hover:border-purple-200 bg-white'
                            }`}
                        >
                            <div className="flex justify-between items-start mb-1">
                                <span className={`font-bold flex items-center gap-2 ${connectionMode === 'ssh' ? 'text-purple-700' : 'text-slate-700'}`}>
                                    <Shield size={16} />
                                    SSH 隧道
                                </span>
                                {connectionMode === 'ssh' && <div className="w-2 h-2 rounded-full bg-purple-500 mt-1.5" />}
                            </div>
                            <p className="text-xs text-slate-500 leading-relaxed">
                                通过 SSH 加密隧道访问云端。无需公网暴露 8102 端口，适合动态 IP 或无域名场景。
                            </p>
                        </button>
                    </div>
                </div>

                {/* HTTP/HTTPS 选项卡内容 */}
                {connectionMode === 'http' && (
                    <div className="space-y-6 animate-fade-in">
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
                )}

                {/* SSH 隧道选项卡内容 */}
                {connectionMode === 'ssh' && (
                    <div className="space-y-6 animate-fade-in">
                        {isEnabling && (
                            <div className="flex items-center gap-2 text-sm text-purple-700 bg-purple-50 border border-purple-200 rounded-xl px-4 py-3">
                                <Loader2 className="w-4 h-4 animate-spin" />
                                正在准备 SSH 密钥...
                            </div>
                        )}

                        {/* SSH 连接参数表单 */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* SSH 主机 */}
                            <div>
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">
                                    SSH 主机
                                </label>
                                <input
                                    type="text"
                                    aria-label="SSH 主机"
                                    value={sshConfig.host}
                                    onChange={(e) => updateSshField('host', e.target.value)}
                                    placeholder="your-server-ip"
                                    className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all"
                                />
                            </div>

                            {/* SSH 端口 */}
                            <div>
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">
                                    SSH 端口
                                </label>
                                <input
                                    type="number"
                                    aria-label="SSH 端口"
                                    value={sshConfig.port}
                                    onChange={(e) => updateSshField('port', parseInt(e.target.value) || 0)}
                                    min={1}
                                    max={65535}
                                    className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all"
                                />
                            </div>

                            {/* SSH 用户名 */}
                            <div>
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">
                                    SSH 用户名
                                </label>
                                <input
                                    type="text"
                                    aria-label="SSH 用户名"
                                    value={sshConfig.username}
                                    onChange={(e) => updateSshField('username', e.target.value)}
                                    placeholder="lifeprism"
                                    className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all"
                                />
                            </div>

                            {/* 本地监听端口 */}
                            <div>
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">
                                    本地监听端口
                                </label>
                                <input
                                    type="number"
                                    aria-label="本地监听端口"
                                    value={sshConfig.local_port}
                                    onChange={(e) => updateSshField('local_port', parseInt(e.target.value) || 0)}
                                    min={1}
                                    max={65535}
                                    className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all"
                                />
                            </div>

                            {/* 远程目标端口 */}
                            <div>
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">
                                    远程目标端口
                                </label>
                                <input
                                    type="number"
                                    aria-label="远程目标端口"
                                    value={sshConfig.remote_port}
                                    onChange={(e) => updateSshField('remote_port', parseInt(e.target.value) || 0)}
                                    min={1}
                                    max={65535}
                                    className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all"
                                />
                            </div>
                        </div>

                        {/* 公钥展示区 + 复制公钥按钮 */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                                    SSH 公钥
                                </label>
                                <button
                                    type="button"
                                    onClick={handleCopyPublicKey}
                                    disabled={!publicKey}
                                    className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-xs font-bold flex items-center gap-1.5"
                                >
                                    <Copy className="w-3.5 h-3.5" />
                                    复制公钥
                                </button>
                            </div>
                            <textarea
                                readOnly
                                aria-label="公钥"
                                value={publicKey}
                                placeholder="切换到 SSH 模式后将自动加载公钥..."
                                rows={3}
                                className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-slate-700 font-mono text-xs outline-none resize-none"
                            />
                            <p className="text-xs text-slate-500 mt-2">
                                将此公钥部署到云端 <code className="font-mono bg-slate-100 px-1 rounded">~/.ssh/authorized_keys</code> 文件中。
                            </p>
                        </div>

                        {/* 配置命令展示区 + 复制命令按钮 */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                                    云端配置命令
                                </label>
                                <button
                                    type="button"
                                    onClick={handleCopyCommand}
                                    disabled={!publicKey}
                                    className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-xs font-bold flex items-center gap-1.5"
                                >
                                    <Terminal className="w-3.5 h-3.5" />
                                    复制命令
                                </button>
                            </div>
                            <textarea
                                readOnly
                                aria-label="配置命令"
                                value={configCommand}
                                placeholder="公钥加载后将自动拼接配置命令..."
                                rows={6}
                                className="w-full bg-gray-900 text-gray-100 border border-gray-700 rounded-xl px-4 py-3 font-mono text-xs outline-none resize-none"
                            />
                            <p className="text-xs text-slate-500 mt-2">
                                在云端服务器终端粘贴执行此命令，将公钥追加到 <code className="font-mono bg-slate-100 px-1 rounded">authorized_keys</code>。
                            </p>
                        </div>

                        {/* 测试连接按钮 + 结果展示 */}
                        <div>
                            <button
                                type="button"
                                onClick={handleTestConnection}
                                disabled={isTesting || isEnabling}
                                className="px-5 py-2.5 bg-purple-600 text-white rounded-xl hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-bold text-sm flex items-center gap-2"
                            >
                                {isTesting ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        测试中...
                                    </>
                                ) : (
                                    <>
                                        <Activity className="w-4 h-4" />
                                        测试连接
                                    </>
                                )}
                            </button>
                            <p className="text-xs text-slate-500 mt-2">
                                验证 SSH 隧道能否建立 + 云端 8102 端口可达。结果显示一次性测试结果（不会持续监控）。
                            </p>

                            {/* 测试结果（一次性展示） */}
                            {testResult && (
                                <div
                                    className={`mt-4 border rounded-xl p-4 ${
                                        testResult.status === 'ok'
                                            ? 'border-green-200 bg-green-50'
                                            : 'border-red-200 bg-red-50'
                                    }`}
                                >
                                    <div className="flex items-start gap-3">
                                        {testResult.status === 'ok' ? (
                                            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                                        ) : (
                                            <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                                        )}
                                        <div className="flex-1 min-w-0">
                                            {testResult.status === 'ok' ? (
                                                <div className="space-y-1">
                                                    <p className="text-sm font-bold text-green-800">
                                                        连接成功
                                                    </p>
                                                    <p className="text-xs text-green-700">
                                                        SSH 隧道已建立，云端 8102 端口可达。
                                                    </p>
                                                </div>
                                            ) : (
                                                <div className="space-y-1">
                                                    <p className="text-sm font-bold text-red-800">
                                                        连接失败
                                                    </p>
                                                    {testResult.error && (
                                                        <p className="text-xs text-red-700 break-all">
                                                            {testResult.error}
                                                        </p>
                                                    )}
                                                    {testResult.code && (
                                                        <p className="text-xs text-red-500 font-mono">
                                                            错误码：{testResult.code}
                                                        </p>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* 生成云端配置按钮（与 HTTP 模式一致） */}
                        <div className="border-t border-slate-100 pt-4 mt-2">
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
                                生成 cloud_init.yaml 配置文件（包含所有 API Key），复制到云端服务器即可使用。SSH 隧道模式下同样需要此配置文件。
                            </p>

                            {/* 生成结果信息面板（与 HTTP 模式共享 state） */}
                            {result && (
                                <div
                                    className={`mt-4 border rounded-xl p-4 ${
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
                                                        配置文件路径：{result.cloud_config_path}
                                                    </p>
                                                </div>
                                            ) : (
                                                <div className="space-y-1">
                                                    <p className="text-sm font-bold text-green-800">
                                                        配置已生成！使用已有的同步 API Key。
                                                    </p>
                                                    <p className="text-xs text-green-700">
                                                        配置文件路径：{result.cloud_config_path}
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
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
