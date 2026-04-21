
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    User,
    Cpu,
    Eye,
    EyeOff,
    Zap,
    Check,
    AlertCircle,
    LayoutGrid,
    Database,
    FolderSearch,
    FolderOpen,
    Filter,
    Plus,
    Minus,
    X,
    Loader2,
    Info,
    ChevronDown,
    Trash2,
    AlertTriangle
} from 'lucide-react';
import { SettingsAPI } from './api';
import type { ProviderInfo, ProviderModelHistory, SettingsResponse } from './types';
import { toast } from '../../core/components';
import { motion, AnimatePresence } from 'framer-motion';

const SettingsApp: React.FC = () => {
    // Loading & Saving States
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);

    // 1. User Settings
    const [nickname, setNickname] = useState('');

    // 2. API Settings
    const [provider, setProvider] = useState('');
    const [providerList, setProviderList] = useState<string[]>([]);
    const [modelName, setModelName] = useState('');
    const [apiBase, setApiBase] = useState('');
    const [modelHistory, setModelHistory] = useState<Record<string, ProviderModelHistory>>({});
    const [showModelDropdown, setShowModelDropdown] = useState(false);
    const [apiKey, setApiKey] = useState('');
    const [showKey, setShowKey] = useState(false);
    const [apiStatus, setApiStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
    const [costInput, setCostInput] = useState(0);
    const [costOutput, setCostOutput] = useState(0);

    // Provider 显示名称到 ID 的映射（从 API 动态获取）
    const [providerIdMap, setProviderIdMap] = useState<Record<string, string>>({});
    const [providerDefaults, setProviderDefaults] = useState<Record<string, ProviderInfo>>({});

    // 3. Classification Settings
    const [classificationMode, setClassificationMode] = useState<'simple' | 'complex'>('simple');
    const [browserApps, setBrowserApps] = useState<string[]>([]);
    const [newBrowserApp, setNewBrowserApp] = useState('');
    const [longLogThreshold, setLongLogThreshold] = useState(600);

    // 4. Database Settings
    const [awPath, setAwPath] = useState('');
    const [lifeprismDataPath, setLifeprismDataPath] = useState('');
    const [configBasePath, setConfigBasePath] = useState('');
    const [pathStatus, setPathStatus] = useState<'idle' | 'checking' | 'success'>('idle');
    const [isElectron, setIsElectron] = useState(false);

    // 数据路径迁移
    const [showMigrateConfirm, setShowMigrateConfirm] = useState(false);
    const [isMigrating, setIsMigrating] = useState(false);
    const [pendingMigratePath, setPendingMigratePath] = useState('');
    const isDev = import.meta.env.DEV;

    // 5. Data Processing
    const [filterDuration, setFilterDuration] = useState(10);

    // 6. Screenshot Monitor
    const [screenshotMonitor, setScreenshotMonitor] = useState(false);
    const [screenshotFrequencyLevel, setScreenshotFrequencyLevel] = useState(2);
    const [screenshotRetentionDays, setScreenshotRetentionDays] = useState(7);
    const [isVlmTesting, setIsVlmTesting] = useState(false);
    const [currentModelVlmStatus, setCurrentModelVlmStatus] = useState<boolean | null>(null);
    const [isVlmConfig, setIsVlmConfig] = useState<Record<string, boolean>>({}); // 完整 is_vlm 配置

    // 7. Modal States
    const [showVolcEngineModal, setShowVolcEngineModal] = useState(false);

    // Refs
    const modelDropdownRef = useRef<HTMLDivElement>(null);
    const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // 点击外部关闭模型下拉菜单
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (modelDropdownRef.current && !modelDropdownRef.current.contains(event.target as Node)) {
                setShowModelDropdown(false);
            }
        };

        if (showModelDropdown) {
            document.addEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [showModelDropdown]);

    // 防抖自动保存函数
    const debouncedSave = useCallback((settingsToSave: Record<string, unknown>) => {
        if (saveTimeoutRef.current) {
            clearTimeout(saveTimeoutRef.current);
        }

        saveTimeoutRef.current = setTimeout(async () => {
            try {
                setIsSaving(true);
                await SettingsAPI.updateSettings(settingsToSave);
                toast.success('已自动保存');
            } catch (err) {
                toast.error(err instanceof Error ? err.message : '保存失败');
            } finally {
                setIsSaving(false);
            }
        }, 800);
    }, []);

    // 立即保存函数，返回后端响应（用于需要检查 require_vlm_test 等场景）
    const immediateSave = useCallback(async (settingsToSave: Record<string, unknown>): Promise<SettingsResponse | null> => {
        try {
            const response = await SettingsAPI.updateSettings(settingsToSave);
            return response;
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '保存失败');
            return null;
        }
    }, []);

    // 清理定时器
    useEffect(() => {
        return () => {
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }
        };
    }, []);

    // Load settings on mount
    useEffect(() => {
        const loadSettings = async () => {
            try {
                setIsLoading(true);
                const [settings, providers] = await Promise.all([
                    SettingsAPI.getSettings(),
                    SettingsAPI.getProviders(),
                ]);

                // Populate state from API response
                setNickname(settings.user_name);
                setProvider(settings.provider);
                setProviderList(settings.provider_list);
                setProviderIdMap(settings.provider_id_map || {});
                setModelName(settings.model);
                setApiBase(settings.api_base || '');
                setModelHistory(settings.model_history || {});
                setApiKey(settings.api_key || '');
                setCostInput(settings.input_tokens_cost);
                setCostOutput(settings.output_tokens_cost);
                setClassificationMode(
                    settings.classification_mode === 'classify_graph' ? 'complex' : 'simple'
                );
                setLongLogThreshold(settings.long_log_threshold);
                setBrowserApps(settings.multi_purpose_app_names);
                setAwPath(settings.aw_db_path);
                setLifeprismDataPath(settings.lifeprism_data_path);
                setConfigBasePath(settings.config_base_path || '');
                setFilterDuration(settings.data_cleaning_threshold);
                setScreenshotMonitor(settings.screenshot_monitor || false);
                setScreenshotFrequencyLevel(settings.active_screenshot_frequency_level || 2);
                setScreenshotRetentionDays(settings.screenshot_retention_days || 7);
                setIsVlmConfig(settings.is_vlm || {}); // 保存完整 is_vlm 配置
                setIsElectron(!!window.electronAPI);
                setProviderDefaults(
                    Object.fromEntries(providers.map((item) => [item.name, item]))
                );
            } catch (err) {
                toast.error(err instanceof Error ? err.message : '加载配置失败');
            } finally {
                setIsLoading(false);
            }
        };

        loadSettings();
    }, []);

    // 实时从 isVlmConfig 计算当前模型的 VLM 状态
    useEffect(() => {
        const providerId = providerIdMap[provider] || '';
        if (providerId && modelName) {
            const isVlm = isVlmConfig[`${providerId}/${modelName}`];
            setCurrentModelVlmStatus(isVlm ?? null);
        } else {
            setCurrentModelVlmStatus(null);
        }
    }, [provider, modelName, isVlmConfig, providerIdMap]);

    // 触发自动保存（收集当前所有设置）
    const triggerAutoSave = useCallback((overrides: Record<string, unknown> = {}) => {
        const currentSettings = {
            user_name: nickname,
            provider: provider,
            model: modelName,
            api_base: apiBase,
            input_tokens_cost: costInput,
            output_tokens_cost: costOutput,
            classification_mode: classificationMode === 'complex' ? 'classify_graph' : 'classify_simple',
            long_log_threshold: longLogThreshold,
            multi_purpose_app_names: browserApps,
            aw_db_path: awPath,
            lifeprism_data_path: lifeprismDataPath,
            data_cleaning_threshold: filterDuration,
            active_screenshot_frequency_level: screenshotFrequencyLevel,
            screenshot_retention_days: screenshotRetentionDays,
            ...overrides,
        };
        debouncedSave(currentSettings);
    }, [nickname, provider, modelName, apiBase, costInput, costOutput, classificationMode, longLogThreshold, browserApps, awPath, lifeprismDataPath, filterDuration, screenshotFrequencyLevel, screenshotRetentionDays, debouncedSave]);

    // Handlers
    const handleTestConnection = async () => {
        setApiStatus('testing');
        try {
            const result = await SettingsAPI.testConnection();
            if (result.success) {
                setApiStatus('success');
                toast.success(`连接成功: ${result.model_response || 'LLM 响应正常'}`);
            } else {
                setApiStatus('error');
                toast.error(result.message || '连接测试失败');
            }
        } catch (err) {
            setApiStatus('error');
            toast.error(err instanceof Error ? err.message : '连接测试失败，请检查配置');
        }
    };

    const handleTestVlm = async () => {
        setIsVlmTesting(true);
        try {
            const result = await SettingsAPI.testVlm();
            if (result.success) {
                toast.success(`图像理解能力测试成功: ${result.model_response || ''}`);
                // 持久化 is_vlm 到后端
                const providerId = providerIdMap[provider] || '';
                if (providerId && modelName) {
                    const currentSettings = await SettingsAPI.getSettings();
                    const updatedIsVlm = {
                        ...(currentSettings.is_vlm || {}),
                        [`${providerId}/${modelName}`]: true
                    };
                    triggerAutoSave({ is_vlm: updatedIsVlm });
                }
            } else {
                toast.error(result.message || 'VLM 测试失败');
            }
            // 更新本地 VLM 状态
            setCurrentModelVlmStatus(result.is_vlm);
            // 同步更新 screenshot_monitor 状态（如果后端已更新）
            const updatedSettings = await SettingsAPI.getSettings();
            setScreenshotMonitor(updatedSettings.screenshot_monitor || false);
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'VLM 测试失败');
        } finally {
            setIsVlmTesting(false);
        }
    };

    const handleCheckPath = () => {
        setPathStatus('checking');
        setTimeout(() => {
            setPathStatus('success');
        }, 1000);
    };

    // 数据路径迁移处理
    const handleMigrateData = async (migrateData: boolean) => {
        setShowMigrateConfirm(false);
        setIsMigrating(true);
        try {
            const result = await SettingsAPI.migrateDataPath({
                target_base_path: pendingMigratePath,
                migrate_data: migrateData
            });
            if (result.success) {
                const msg = migrateData
                    ? `数据已迁移到 ${result.new_path}，即将退出程序...`
                    : `路径已切换到 ${result.new_path}，即将退出程序...`;
                toast.success(msg);
                setTimeout(() => {
                    window.electronAPI?.quitApp();
                }, 1500);
            }
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '操作失败');
            setIsMigrating(false);
        }
    };

    const addBrowserApp = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && newBrowserApp.trim()) {
            if (!browserApps.includes(newBrowserApp.trim())) {
                const newApps = [...browserApps, newBrowserApp.trim()];
                setBrowserApps(newApps);
                triggerAutoSave({ multi_purpose_app_names: newApps });
            }
            setNewBrowserApp('');
        }
    };

    const removeBrowserApp = (app: string) => {
        const newApps = browserApps.filter(a => a !== app);
        setBrowserApps(newApps);
        triggerAutoSave({ multi_purpose_app_names: newApps });
    };

    const getProviderHistorySnapshot = (providerId: string): ProviderModelHistory => {
        return modelHistory[providerId] || { api_base: '', models: [] };
    };

    const getDefaultProviderConfig = (providerId: string) => {
        return providerDefaults[providerId] || {
            name: providerId,
            display_name: providerId,
            default_model: '',
            default_api_base: '',
            has_api_key: true,
        };
    };

    const handleProviderChange = (newProvider: string) => {
        const providerId = providerIdMap[newProvider] || '';
        const historySnapshot = getProviderHistorySnapshot(providerId);
        const providerConfig = getDefaultProviderConfig(providerId);
        const nextModel = historySnapshot.models[0] || providerConfig.default_model || '';
        const nextApiBase = historySnapshot.api_base || providerConfig.default_api_base || '';

        setProvider(newProvider);
        setModelName(nextModel);
        setApiBase(nextApiBase);
        triggerAutoSave({
            provider: newProvider,
            model: nextModel,
            api_base: nextApiBase,
        });
        // 如果 screenshot_monitor 已开启，自动测试新模型的 VLM 能力
        if (screenshotMonitor) {
            setIsVlmTesting(true);
            SettingsAPI.testVlm()
                .then((result) => {
                    if (!result.success) {
                        setScreenshotMonitor(false);
                        triggerAutoSave({ screenshot_monitor: false });
                        toast.warning(`截图监控已自动关闭: ${result.message}`);
                    } else {
                        setCurrentModelVlmStatus(true);
                    }
                })
                .catch(() => {
                    setScreenshotMonitor(false);
                    triggerAutoSave({ screenshot_monitor: false });
                    toast.warning(`截图监控已自动关闭`);
                })
                .finally(() => {
                    setIsVlmTesting(false);
                });
        }
        // TODO: 暂时禁用火山引擎说明弹窗
        // if (newProvider.includes('火山引擎') || newProvider.toLowerCase().includes('volcengine')) {
        //     setShowVolcEngineModal(true);
        // }
    };

    // 获取当前服务商的模型历史
    const getCurrentProviderModelHistory = (): string[] => {
        const providerId = providerIdMap[provider] || '';
        if (!providerId) return [];
        return getProviderHistorySnapshot(providerId).models;
    };

    // 删除模型历史
    const handleDeleteModelHistory = async (model: string) => {
        const providerId = providerIdMap[provider] || '';
        if (!providerId) return;
        try {
            await SettingsAPI.deleteModelHistory(providerId, model);
            // 更新本地状态
            setModelHistory(prev => ({
                ...prev,
                [providerId]: {
                    api_base: prev[providerId]?.api_base || '',
                    models: (prev[providerId]?.models || []).filter(m => m !== model),
                }
            }));
        } catch (err) {
            toast.error(err instanceof Error ? err.message : '删除失败');
        }
    };

    // 选择历史模型
    const handleSelectModel = async (model: string) => {
        setModelName(model);
        setShowModelDropdown(false);
        triggerAutoSave({ model: model });
        // 如果 screenshot_monitor 已开启，自动测试新模型的 VLM 能力
        if (screenshotMonitor) {
            setIsVlmTesting(true);
            try {
                const result = await SettingsAPI.testVlm();
                if (!result.success) {
                    setScreenshotMonitor(false);
                    triggerAutoSave({ screenshot_monitor: false });
                    toast.warning(`截图监控已自动关闭: ${result.message}`);
                } else {
                    setCurrentModelVlmStatus(true);
                }
            } catch (err) {
                setScreenshotMonitor(false);
                triggerAutoSave({ screenshot_monitor: false });
                toast.warning(`截图监控已自动关闭`);
            } finally {
                setIsVlmTesting(false);
            }
        }
    };

    const handleApiKeyBlur = async () => {
        // Only save if it's a new key (not masked)
        if (apiKey && !apiKey.includes('*') && apiKey.length > 0) {
            try {
                // 传递 provider_id 而非显示名称
                await SettingsAPI.updateApiKey(apiKey, providerIdMap[provider]);
                // Reload to get masked version
                const settings = await SettingsAPI.getSettings();
                setApiKey(settings.api_key || '');
                toast.success('API Key 已安全保存');
            } catch (err) {
                toast.error('API Key 保存失败');
            }
        }
    };

    // Loading skeleton
    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto space-y-8 animate-fade-in pb-20">
                <div className="flex items-center justify-center h-64">
                    <div className="flex flex-col items-center gap-4">
                        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                        <span className="text-slate-500 font-medium">正在加载配置...</span>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-8 animate-fade-in pb-20">

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">系统设置</h1>
                    <p className="text-slate-500 mt-1 font-medium">配置您的API。</p>
                </div>
                {isSaving && (
                    <div className="flex items-center gap-2 text-slate-500 text-sm">
                        <div className="w-4 h-4 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
                        <span>保存中...</span>
                    </div>
                )}
            </div>

            {/* 1. User Profile */}
            <section className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2.5 bg-gray-50 rounded-xl text-slate-600">
                        <User size={20} />
                    </div>
                    <h2 className="text-lg font-bold text-slate-800">用户资料</h2>
                </div>
                <div className="max-w-md">
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">显示昵称</label>
                    <input
                        type="text"
                        value={nickname}
                        onChange={(e) => setNickname(e.target.value)}
                        onBlur={() => triggerAutoSave({ user_name: nickname })}
                        className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-blue-200 focus:ring-4 focus:ring-blue-50/50 rounded-xl px-4 py-3 text-slate-800 font-bold outline-none transition-all"
                    />
                </div>
            </section>

            {/* 2. Intelligence Engine (API) */}
            <section className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2.5 bg-purple-50 rounded-xl text-purple-600">
                        <Cpu size={20} />
                    </div>
                    <h2 className="text-lg font-bold text-slate-800">API 设置</h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {/* Provider & Model */}
                    <div className="space-y-6">
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">服务商</label>
                            <select
                                value={provider}
                                onChange={(e) => handleProviderChange(e.target.value)}
                                className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all appearance-none cursor-pointer"
                            >
                                <option value="">选择服务商...</option>
                                {providerList.map(p => (
                                    <option key={p} value={p}>{p}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">模型名称</label>
                            <div className="relative" ref={modelDropdownRef}>
                                <input
                                    type="text"
                                    value={modelName}
                                    onChange={(e) => setModelName(e.target.value)}
                                    onFocus={() => setShowModelDropdown(true)}
                                    onBlur={() => triggerAutoSave({ model: modelName })}
                                    placeholder="输入或选择模型..."
                                    className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl px-4 py-3 pr-10 text-slate-800 font-medium outline-none transition-all"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowModelDropdown(!showModelDropdown)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                                >
                                    <ChevronDown size={18} className={`transition-transform ${showModelDropdown ? 'rotate-180' : ''}`} />
                                </button>

                                {/* 模型历史下拉菜单 */}
                                {showModelDropdown && (
                                    <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
                                        <div className="px-3 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-widest border-b border-gray-100">
                                            历史记录
                                        </div>
                                        {getCurrentProviderModelHistory().length > 0 ? (
                                            getCurrentProviderModelHistory().map((model) => (
                                                <div
                                                    key={model}
                                                    className="flex items-center justify-between px-3 py-2 hover:bg-gray-50 cursor-pointer group"
                                                >
                                                    <span
                                                        onClick={() => handleSelectModel(model)}
                                                        className="flex-1 text-sm text-slate-700 font-medium truncate"
                                                    >
                                                        {model}
                                                    </span>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleDeleteModelHistory(model);
                                                        }}
                                                        className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500 transition-all"
                                                        title="删除此记录"
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                </div>
                                            ))
                                        ) : (
                                            <div className="px-3 py-3 text-sm text-slate-400 text-center">
                                                暂无历史记录
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">API Base</label>
                            <input
                                type="text"
                                value={apiBase}
                                onChange={(e) => setApiBase(e.target.value)}
                                onBlur={() => triggerAutoSave({ api_base: apiBase })}
                                placeholder="留空时使用该服务商默认 API Base"
                                className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all"
                            />
                        </div>
                    </div>

                    {/* API Key & Test */}
                    <div className="space-y-6">
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">API 密钥</label>
                            <div className="relative">
                                <input
                                    type={showKey ? "text" : "password"}
                                    value={apiKey}
                                    onChange={(e) => setApiKey(e.target.value)}
                                    onBlur={handleApiKeyBlur}
                                    placeholder="输入您的 API 密钥..."
                                    className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl pl-4 pr-12 py-3 text-slate-800 font-mono text-sm outline-none transition-all"
                                />
                                <button
                                    onClick={() => setShowKey(!showKey)}
                                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                                >
                                    {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                                </button>
                            </div>
                            <p className="text-xs text-slate-400 mt-2">离开此字段时，API 密钥将被安全保存。</p>
                        </div>

                        <div className="flex items-center gap-4">
                            <button
                                onClick={handleTestConnection}
                                disabled={apiStatus === 'testing'}
                                className={`flex items-center gap-2 px-4 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-all border ${apiStatus === 'success'
                                    ? 'bg-green-50 text-green-700 border-green-200'
                                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                                    }`}
                            >
                                {apiStatus === 'testing' ? (
                                    <div className="w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                                ) : apiStatus === 'success' ? (
                                    <Check size={14} />
                                ) : (
                                    <Zap size={14} />
                                )}
                                {apiStatus === 'testing' ? '测试中...' : apiStatus === 'success' ? '已连接' : '测试连接'}
                            </button>
                            {/* VLM 测试按钮 */}
                            <button
                                onClick={handleTestVlm}
                                disabled={isVlmTesting || !modelName}
                                className={`flex items-center gap-2 px-4 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-all border ${
                                    currentModelVlmStatus === true
                                        ? 'bg-green-50 text-green-700 border-green-200'
                                        : isVlmTesting
                                        ? 'bg-slate-50 text-slate-400 border-slate-200 cursor-not-allowed'
                                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                                }`}
                                title={currentModelVlmStatus === true ? '该模型具备图像理解能力，点击可重新验证' : '测试该模型的图像理解能力'}
                            >
                                {isVlmTesting ? (
                                    <div className="w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                                ) : currentModelVlmStatus === true ? (
                                    <Check size={14} />
                                ) : (
                                    <Cpu size={14} />
                                )}
                                {isVlmTesting ? '验证中...' : currentModelVlmStatus === true ? '具备图片理解能力' : '测试图片理解能力'}
                            </button>
                            {apiStatus === 'error' && (
                                <span className="text-xs text-red-500 font-medium flex items-center gap-1">
                                    <AlertCircle size={12} /> 连接失败
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                {/* Cost Estimation */}
                <div className="mt-8 pt-6 border-t border-dashed border-gray-100">
                    <h3 className="text-xs font-bold text-slate-500 mb-4 flex items-center gap-2">
                        成本估算 (每 1k Token, ¥)
                    </h3>
                    <div className="grid grid-cols-2 gap-4 max-w-lg">
                        <div className="bg-gray-50 p-3 rounded-xl border border-gray-100 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
                            <label className="text-[9px] font-bold text-slate-400 uppercase block mb-1">输入成本</label>
                            <input
                                type="number"
                                step="0.0001"
                                value={costInput}
                                onChange={(e) => setCostInput(parseFloat(e.target.value) || 0)}
                                onBlur={() => triggerAutoSave({ input_tokens_cost: costInput })}
                                className="w-full bg-transparent font-mono font-bold text-slate-700 outline-none"
                            />
                        </div>
                        <div className="bg-gray-50 p-3 rounded-xl border border-gray-100 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
                            <label className="text-[9px] font-bold text-slate-400 uppercase block mb-1">输出成本</label>
                            <input
                                type="number"
                                step="0.0001"
                                value={costOutput}
                                onChange={(e) => setCostOutput(parseFloat(e.target.value) || 0)}
                                onBlur={() => triggerAutoSave({ output_tokens_cost: costOutput })}
                                className="w-full bg-transparent font-mono font-bold text-slate-700 outline-none"
                            />
                        </div>
                    </div>
                </div>
            </section>

            {/* 3. Classification Logic */}
            <section className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2.5 bg-blue-50 rounded-xl text-blue-600">
                        <LayoutGrid size={20} />
                    </div>
                    <h2 className="text-lg font-bold text-slate-800">分类逻辑</h2>
                </div>

                <div className="space-y-8">
                    {/* Mode Selection */}
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-4 block">分类模式</label>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <button
                                onClick={() => {
                                    setClassificationMode('simple');
                                    triggerAutoSave({ classification_mode: 'classify_simple' });
                                }}
                                className={`text-left p-4 rounded-2xl border-2 transition-all ${classificationMode === 'simple'
                                    ? 'border-blue-500 bg-blue-50/30'
                                    : 'border-gray-100 hover:border-blue-200 bg-white'
                                    }`}
                            >
                                <div className="flex justify-between items-start mb-1">
                                    <span className={`font-bold ${classificationMode === 'simple' ? 'text-blue-700' : 'text-slate-700'}`}>极简模式</span>
                                    {classificationMode === 'simple' && <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5" />}
                                </div>
                                <p className="text-xs text-slate-500 leading-relaxed">消耗较少 Token。基于应用名称和窗口标题关键字进行分类。更快且更便宜。</p>
                            </button>

                            <button
                                onClick={() => {
                                    setClassificationMode('complex');
                                    triggerAutoSave({ classification_mode: 'classify_graph' });
                                }}
                                className={`text-left p-4 rounded-2xl border-2 transition-all ${classificationMode === 'complex'
                                    ? 'border-purple-500 bg-purple-50/30'
                                    : 'border-gray-100 hover:border-purple-200 bg-white'
                                    }`}
                            >
                                <div className="flex justify-between items-start mb-1">
                                    <span className={`font-bold ${classificationMode === 'complex' ? 'text-purple-700' : 'text-slate-700'}`}>复杂模式</span>
                                    {classificationMode === 'complex' && <div className="w-2 h-2 rounded-full bg-purple-500 mt-1.5" />}
                                </div>
                                <p className="text-xs text-slate-500 leading-relaxed">分析完整的窗口标题和上下文。对浏览器准确率更高一些，但消耗更多 Token。</p>
                            </button>
                        </div>
                    </div>

                    {/* Long Log Threshold */}
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">长活动阈值 (秒)</label>
                        <input
                            type="number"
                            value={longLogThreshold}
                            onChange={(e) => setLongLogThreshold(parseInt(e.target.value) || 0)}
                            onBlur={() => triggerAutoSave({ long_log_threshold: longLogThreshold })}
                            className="w-32 bg-gray-50 border border-transparent focus:bg-white focus:border-blue-200 focus:ring-4 focus:ring-blue-50/50 rounded-xl px-4 py-3 text-slate-800 font-bold outline-none transition-all"
                        />
                        <p className="text-xs text-slate-400 mt-2">超过此时间的活动将被标记为长活动。</p>
                    </div>

                    {/* Browser Apps List */}
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 block">多用途应用程序</label>
                        <p className="text-xs text-slate-500 mb-3">定义哪些应用程序应使用标题信息进行分类（浏览器等）。</p>

                        <div className="bg-gray-50 border border-gray-200 rounded-xl p-2 flex flex-wrap gap-2 min-h-[50px]">
                            {browserApps.map(app => (
                                <div key={app} className="flex items-center gap-1 bg-white border border-gray-200 px-2 py-1 rounded-lg shadow-sm">
                                    <span className="text-xs font-bold text-slate-700">{app}</span>
                                    <button onClick={() => removeBrowserApp(app)} className="text-slate-400 hover:text-red-500 transition-colors">
                                        <X size={12} />
                                    </button>
                                </div>
                            ))}
                            <input
                                type="text"
                                value={newBrowserApp}
                                onChange={(e) => setNewBrowserApp(e.target.value)}
                                onKeyDown={addBrowserApp}
                                placeholder="输入应用名称并回车..."
                                className="flex-1 bg-transparent text-xs font-medium text-slate-700 outline-none min-w-[120px] px-2"
                            />
                        </div>
                    </div>
                </div>
            </section>

            {/* 4. Data & Storage */}
            <section className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2.5 bg-orange-50 rounded-xl text-orange-500">
                        <Database size={20} />
                    </div>
                    <h2 className="text-lg font-bold text-slate-800">存储与数据源</h2>
                </div>

                <div className="space-y-6">
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">配置文件路径</label>
                        <div className="flex gap-3">
                            <input
                                type="text"
                                value={configBasePath ? `${configBasePath}/config` : ''}
                                readOnly
                                className="flex-1 bg-gray-50 border border-transparent rounded-xl px-4 py-3 text-slate-500 font-mono text-xs outline-none cursor-default"
                            />
                            {isElectron && configBasePath && (
                                <button
                                    onClick={() => {
                                        window.electronAPI?.openFolder(`${configBasePath}/config`);
                                    }}
                                    className="px-4 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-slate-600 rounded-xl font-bold text-xs shadow-sm flex items-center gap-2 transition-all"
                                    title="打开配置文件夹"
                                >
                                    <FolderOpen size={14} />
                                </button>
                            )}
                        </div>
                        <p className="text-xs text-slate-400 mt-2">config.yaml、providers.yaml 等配置文件的存储目录，不随数据迁移。</p>
                    </div>

                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">LifePrism 数据路径</label>
                        <div className="flex gap-3">
                            <input
                                type="text"
                                value={lifeprismDataPath}
                                onChange={(e) => {
                                    if (isDev) setLifeprismDataPath(e.target.value);
                                }}
                                onBlur={() => {
                                    if (isDev) triggerAutoSave({ lifeprism_data_path: lifeprismDataPath });
                                }}
                                readOnly={!isDev && isElectron}
                                placeholder="留空使用默认路径"
                                className="flex-1 bg-gray-50 border border-transparent focus:bg-white focus:border-orange-200 focus:ring-4 focus:ring-orange-50/50 rounded-xl px-4 py-3 text-slate-600 font-mono text-xs outline-none transition-all"
                            />
                            {isElectron && !isDev && (
                                <button
                                    onClick={async () => {
                                        const dir = await window.electronAPI?.selectDirectory();
                                        if (dir) {
                                            const installPath = await window.electronAPI?.getInstallPath();
                                            if (installPath && dir.startsWith(installPath)) {
                                                toast.error('数据路径不能位于安装目录内');
                                                return;
                                            }
                                            setPendingMigratePath(dir);
                                            setShowMigrateConfirm(true);
                                        }
                                    }}
                                    className="px-4 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-slate-600 rounded-xl font-bold text-xs shadow-sm flex items-center gap-2 transition-all"
                                    title="选择文件夹并迁移数据"
                                >
                                    <FolderOpen size={14} />
                                </button>
                            )}
                        </div>
                        <p className="text-xs text-slate-400 mt-2">
                            {isDev ? '开发模式：直接修改路径，不触发迁移。' : '数据库、计划书等数据的存储目录。修改后将迁移数据并重启程序。'}
                        </p>
                    </div>

                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">ActivityWatch 数据库路径</label>
                        <div className="flex gap-3">
                            <input
                                type="text"
                                value={awPath}
                                onChange={(e) => setAwPath(e.target.value)}
                                onBlur={() => triggerAutoSave({ aw_db_path: awPath })}
                                className="flex-1 bg-gray-50 border border-transparent focus:bg-white focus:border-orange-200 focus:ring-4 focus:ring-orange-50/50 rounded-xl px-4 py-3 text-slate-600 font-mono text-xs outline-none transition-all"
                            />
                            {isElectron && (
                                <button
                                    onClick={async () => {
                                        const file = await window.electronAPI?.selectFile([
                                            { name: 'SQLite Database', extensions: ['db'] }
                                        ]);
                                        if (file) {
                                            setAwPath(file);
                                            triggerAutoSave({ aw_db_path: file });
                                        }
                                    }}
                                    className="px-4 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-slate-600 rounded-xl font-bold text-xs shadow-sm flex items-center gap-2 transition-all"
                                    title="选择文件"
                                >
                                    <FolderSearch size={14} />
                                </button>
                            )}
                            <button
                                onClick={handleCheckPath}
                                className="px-4 py-2 bg-white border border-gray-200 hover:bg-gray-50 text-slate-600 rounded-xl font-bold text-xs shadow-sm flex items-center gap-2 transition-all"
                            >
                                {pathStatus === 'checking' ? (
                                    <div className="w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                                ) : pathStatus === 'success' ? (
                                    <Check size={14} className="text-green-500" />
                                ) : (
                                    <FolderSearch size={14} />
                                )}
                                Detect
                            </button>
                        </div>
                    </div>
                </div>
            </section>

            {/* 5. Data Hygiene */}
            <section className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2.5 bg-green-50 rounded-xl text-green-600">
                        <Filter size={20} />
                    </div>
                    <h2 className="text-lg font-bold text-slate-800">数据清洗</h2>
                </div>

                <div className="flex items-center gap-4 bg-gray-50 p-4 rounded-xl border border-gray-100">
                    <div className="flex-1">
                        <h4 className="text-sm font-bold text-slate-700">短时过滤</h4>
                        <p className="text-xs text-slate-400 mt-1">忽略持续时间小于此值的窗口切换或活动，以减少噪音。</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => {
                                const newValue = Math.max(0, filterDuration - 1);
                                setFilterDuration(newValue);
                                triggerAutoSave({ data_cleaning_threshold: newValue });
                            }}
                            className="w-8 h-8 flex items-center justify-center rounded-lg bg-white border border-gray-200 text-slate-500 hover:border-blue-300 hover:text-blue-600 transition-all"
                        >
                            <Minus size={14} />
                        </button>

                        <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-lg border border-gray-200 shadow-sm w-24 justify-center">
                            <input
                                type="number"
                                value={filterDuration}
                                onChange={(e) => setFilterDuration(parseInt(e.target.value) || 0)}
                                onBlur={() => triggerAutoSave({ data_cleaning_threshold: filterDuration })}
                                className="w-full text-center font-bold text-slate-800 outline-none bg-transparent"
                            />
                        </div>

                        <button
                            onClick={() => {
                                const newValue = filterDuration + 1;
                                setFilterDuration(newValue);
                                triggerAutoSave({ data_cleaning_threshold: newValue });
                            }}
                            className="w-8 h-8 flex items-center justify-center rounded-lg bg-white border border-gray-200 text-slate-500 hover:border-blue-300 hover:text-blue-600 transition-all"
                        >
                            <Plus size={14} />
                        </button>

                        <span className="text-xs font-bold text-slate-400 uppercase ml-1">秒</span>
                    </div>
                </div>
            </section>

            {/* 6. Screenshot Monitor */}
            <section className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2.5 bg-red-50 rounded-xl text-red-500">
                        <Eye size={20} />
                    </div>
                    <h2 className="text-lg font-bold text-slate-800">截图监控</h2>
                </div>

                <div className="space-y-6">
                    {/* 开关 */}
                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100">
                        <div>
                            <h4 className="text-sm font-bold text-slate-700">开启截图监控</h4>
                            <p className="text-xs text-slate-400 mt-1">启用后将对屏幕进行周期性截图分析</p>
                        </div>
                        <button
                            onClick={async () => {
                                if (!screenshotMonitor) {
                                    // 尝试开启：发送 PATCH 请求，由后端校验 is_vlm
                                    try {
                                        setIsVlmTesting(true);
                                        const response = await immediateSave({ screenshot_monitor: true });
                                        // 检查后端是否要求 VLM 测试
                                        if (response?.require_vlm_test) {
                                            // 需要先测试 VLM
                                            const testResult = await SettingsAPI.testVlm();
                                            if (testResult.success) {
                                                // VLM 测试成功，再次尝试开启截图监控
                                                await immediateSave({ screenshot_monitor: true });
                                                setScreenshotMonitor(true);
                                                setCurrentModelVlmStatus(true);
                                                toast.success('截图监控已开启');
                                            } else {
                                                toast.error(`无法开启截图监控: ${testResult.message}`);
                                            }
                                        } else {
                                            // 直接开启成功
                                            setScreenshotMonitor(true);
                                            toast.success('截图监控已开启');
                                        }
                                    } catch (err) {
                                        toast.error(err instanceof Error ? err.message : '开启失败');
                                    } finally {
                                        setIsVlmTesting(false);
                                    }
                                } else {
                                    // 关闭
                                    setScreenshotMonitor(false);
                                    triggerAutoSave({ screenshot_monitor: false });
                                }
                            }}
                            disabled={isVlmTesting || !modelName}
                            className={`relative w-14 h-8 rounded-full transition-all ${
                                screenshotMonitor ? 'bg-green-500' : 'bg-slate-200'
                            } ${isVlmTesting || !modelName ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                        >
                            <div
                                className={`absolute top-1 w-6 h-6 bg-white rounded-full shadow-sm transition-all ${
                                    screenshotMonitor ? 'left-7' : 'left-1'
                                }`}
                            />
                            {isVlmTesting && (
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                </div>
                            )}
                        </button>
                    </div>

                    {/* 当前模型状态 */}
                    <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-xs text-slate-400">当前模型</p>
                                <p className="text-sm font-bold text-slate-700 mt-1">{modelName || '未选择'}</p>
                            </div>
                            <div className="text-right">
                                <p className="text-xs text-slate-400">图片理解能力</p>
                                <p className={`text-sm font-bold mt-1 ${
                                    currentModelVlmStatus === true ? 'text-green-600' :
                                    currentModelVlmStatus === false ? 'text-red-500' : 'text-slate-400'
                                }`}>
                                    {currentModelVlmStatus === true ? '✓ 具备' :
                                     currentModelVlmStatus === false ? '✗ 不具备' : '未知'}
                                </p>
                            </div>
                        </div>
                        {isVlmTesting && (
                            <p className="text-xs text-slate-400 mt-2 flex items-center gap-1">
                                <div className="w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                                验证中...
                            </p>
                        )}
                    </div>
                </div>
            </section>

            {/* TODO: 暂时禁用火山引擎说明弹窗
            {showVolcEngineModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-fade-in">
                    <div className="bg-white rounded-2xl p-6 max-w-lg mx-4 shadow-2xl">
                        <div className="flex items-start gap-4 mb-4">
                            <div className="p-2 bg-orange-100 rounded-xl">
                                <Info className="w-6 h-6 text-orange-600" />
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-slate-800">火山引擎配置说明</h3>
                                <p className="text-sm text-slate-500 mt-1">使用火山引擎需要特殊配置</p>
                            </div>
                        </div>

                        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 mb-4">
                            <p className="text-sm text-slate-700 leading-relaxed">
                                火山引擎使用 <strong>Endpoint ID</strong> 而不是模型名称。
                            </p>
                            <p className="text-sm text-slate-600 mt-2">
                                请在「模型名称」字段填写您的 Endpoint ID，格式如：
                            </p>
                            <code className="block mt-2 bg-white px-3 py-2 rounded-lg text-sm font-mono text-orange-700 border border-orange-200">
                                ep-m-20260205214401-8rthb
                            </code>
                        </div>

                        <div className="text-sm text-slate-600 space-y-2 mb-6">
                            <p><strong>获取 Endpoint ID 步骤：</strong></p>
                            <ol className="list-decimal list-inside space-y-1 text-slate-500">
                                <li>登录火山引擎控制台</li>
                                <li>进入「模型推理」→「推理接入点管理」</li>
                                <li>创建或选择一个接入点</li>
                                <li>复制 Endpoint ID（以 ep- 开头）</li>
                            </ol>
                        </div>

                        <div className="flex justify-end gap-3">
                            <button
                                onClick={() => setShowVolcEngineModal(false)}
                                className="px-4 py-2 bg-slate-900 text-white rounded-xl font-bold text-sm hover:bg-slate-800 transition-colors"
                            >
                                我知道了
                            </button>
                        </div>
                    </div>
                </div>
            )} */}

            {/* 数据路径切换/迁移确认对话框 */}
            <AnimatePresence>
                {showMigrateConfirm && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[9999] flex items-center justify-center"
                    >
                        <div
                            className="absolute inset-0 bg-black/20 backdrop-blur-sm"
                            onClick={() => setShowMigrateConfirm(false)}
                        />
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: -20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: -10 }}
                            transition={{ type: "spring", stiffness: 400, damping: 30 }}
                            className="relative w-[460px] bg-white/95 backdrop-blur-xl rounded-2xl shadow-[0_20px_40px_-12px_rgba(0,0,0,0.15)] border border-white/40 overflow-hidden"
                        >
                            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
                                <div className="flex items-center gap-2">
                                    <AlertTriangle size={18} className="text-amber-500" />
                                    <h3 className="text-base font-semibold text-slate-700">更改数据路径</h3>
                                </div>
                                <button
                                    onClick={() => setShowMigrateConfirm(false)}
                                    className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                                >
                                    <X size={18} />
                                </button>
                            </div>
                            <div className="px-5 py-4 space-y-2">
                                <p className="text-sm text-slate-600">目标路径：</p>
                                <p className="text-sm font-mono bg-slate-50 px-3 py-2 rounded-lg text-slate-700">
                                    {pendingMigratePath}\lifeprismData
                                </p>
                                <p className="text-xs text-amber-600 mt-2">
                                    操作完成后程序将自动退出，请手动重新启动。
                                </p>
                            </div>
                            <div className="flex items-center justify-end gap-2 px-5 py-4 bg-slate-50/50 border-t border-slate-100">
                                <button
                                    onClick={() => setShowMigrateConfirm(false)}
                                    className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                                >
                                    取消
                                </button>
                                <button
                                    onClick={() => handleMigrateData(false)}
                                    className="px-4 py-2 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
                                >
                                    仅切换路径
                                </button>
                                <button
                                    onClick={() => handleMigrateData(true)}
                                    className="px-4 py-2 text-sm font-medium text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors"
                                >
                                    迁移数据并退出
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* 迁移中遮罩 */}
            {isMigrating && (
                <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-black/30 backdrop-blur-sm">
                    <div className="bg-white rounded-2xl p-8 shadow-xl flex flex-col items-center gap-4">
                        <Loader2 className="animate-spin text-orange-500" size={32} />
                        <p className="text-sm font-medium text-slate-700">正在处理，请勿关闭程序...</p>
                    </div>
                </div>
            )}

        </div>
    );
};

export { SettingsApp };
