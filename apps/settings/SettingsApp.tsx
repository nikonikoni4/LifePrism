
import React, { useState, useEffect, useRef } from 'react';
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
    Save,
    Filter,
    Plus,
    Minus,
    X,
    Loader2,
    Info,
    ChevronDown,
    Trash2
} from 'lucide-react';
import { SettingsAPI } from './api';

const SettingsApp: React.FC = () => {
    // Loading & Error States
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    // 1. User Settings
    const [nickname, setNickname] = useState('');

    // 2. API Settings
    const [provider, setProvider] = useState('');
    const [providerList, setProviderList] = useState<string[]>([]);
    const [modelName, setModelName] = useState('');
    const [modelHistory, setModelHistory] = useState<Record<string, string[]>>({});
    const [showModelDropdown, setShowModelDropdown] = useState(false);
    const [apiKey, setApiKey] = useState('');
    const [showKey, setShowKey] = useState(false);
    const [apiStatus, setApiStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
    const [costInput, setCostInput] = useState(0);
    const [costOutput, setCostOutput] = useState(0);

    // Provider 显示名称到 ID 的映射
    const PROVIDER_ID_MAP: Record<string, string> = {
        "阿里云百炼 (Aliyun)": "aliyun",
        "火山引擎 (VolcEngine)": "volcengine",
        "OpenAI": "openai",
        "MiniMax": "minimax"
    };

    // 3. Classification Settings
    const [classificationMode, setClassificationMode] = useState<'simple' | 'complex'>('simple');
    const [browserApps, setBrowserApps] = useState<string[]>([]);
    const [newBrowserApp, setNewBrowserApp] = useState('');
    const [longLogThreshold, setLongLogThreshold] = useState(600);

    // 4. Database Settings
    const [awPath, setAwPath] = useState('');
    const [lwPath, setLwPath] = useState('');
    const [chatPath, setChatPath] = useState('');
    const [pathStatus, setPathStatus] = useState<'idle' | 'checking' | 'success'>('idle');

    // 5. Data Processing
    const [filterDuration, setFilterDuration] = useState(10);

    // 6. Modal States
    const [showVolcEngineModal, setShowVolcEngineModal] = useState(false);

    // Refs
    const modelDropdownRef = useRef<HTMLDivElement>(null);

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

    // Load settings on mount
    useEffect(() => {
        const loadSettings = async () => {
            try {
                setIsLoading(true);
                setError(null);
                const settings = await SettingsAPI.getSettings();

                // Populate state from API response
                setNickname(settings.user_name);
                setProvider(settings.provider);
                setProviderList(settings.provider_list);
                setModelName(settings.model);
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
                setLwPath(settings.lw_db_path);
                setChatPath(settings.chat_db_path);
                setFilterDuration(settings.data_cleaning_threshold);
            } catch (err) {
                setError(err instanceof Error ? err.message : '加载配置失败');
            } finally {
                setIsLoading(false);
            }
        };

        loadSettings();
    }, []);

    // Handlers
    const handleTestConnection = async () => {
        setApiStatus('testing');
        try {
            const result = await SettingsAPI.testConnection();
            if (result.success) {
                setApiStatus('success');
                setSuccessMessage(`连接成功: ${result.model_response || 'LLM 响应正常'}`);
                setTimeout(() => setSuccessMessage(null), 5000);
            } else {
                setApiStatus('error');
                setError(result.message || '连接测试失败');
            }
        } catch (err) {
            setApiStatus('error');
            setError(err instanceof Error ? err.message : '连接测试失败，请检查配置');
        }
    };

    const handleCheckPath = () => {
        setPathStatus('checking');
        setTimeout(() => {
            setPathStatus('success');
        }, 1000);
    };

    const addBrowserApp = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && newBrowserApp.trim()) {
            if (!browserApps.includes(newBrowserApp.trim())) {
                setBrowserApps([...browserApps, newBrowserApp.trim()]);
            }
            setNewBrowserApp('');
        }
    };

    const removeBrowserApp = (app: string) => {
        setBrowserApps(browserApps.filter(a => a !== app));
    };

    const handleProviderChange = (newProvider: string) => {
        setProvider(newProvider);
        // 当选择火山引擎时显示说明弹窗
        if (newProvider.includes('火山引擎') || newProvider.toLowerCase().includes('volcengine')) {
            setShowVolcEngineModal(true);
        }
    };

    // 获取当前服务商的模型历史
    const getCurrentProviderModelHistory = (): string[] => {
        const providerId = PROVIDER_ID_MAP[provider] || provider.toLowerCase();
        return modelHistory[providerId] || [];
    };

    // 删除模型历史
    const handleDeleteModelHistory = async (model: string) => {
        const providerId = PROVIDER_ID_MAP[provider] || provider.toLowerCase();
        try {
            await SettingsAPI.deleteModelHistory(providerId, model);
            // 更新本地状态
            setModelHistory(prev => ({
                ...prev,
                [providerId]: (prev[providerId] || []).filter(m => m !== model)
            }));
        } catch (err) {
            setError(err instanceof Error ? err.message : '删除失败');
        }
    };

    // 选择历史模型
    const handleSelectModel = (model: string) => {
        setModelName(model);
        setShowModelDropdown(false);
    };

    const handleSaveAll = async () => {
        try {
            setIsSaving(true);
            setError(null);
            setSuccessMessage(null);

            await SettingsAPI.updateSettings({
                user_name: nickname,
                provider: provider,
                model: modelName,
                input_tokens_cost: costInput,
                output_tokens_cost: costOutput,
                classification_mode: classificationMode === 'complex' ? 'classify_graph' : 'classify_simple',
                long_log_threshold: longLogThreshold,
                multi_purpose_app_names: browserApps,
                aw_db_path: awPath,
                lw_db_path: lwPath,
                chat_db_path: chatPath,
                data_cleaning_threshold: filterDuration,
            });

            setSuccessMessage('配置已保存');
            setTimeout(() => setSuccessMessage(null), 3000);
        } catch (err) {
            setError(err instanceof Error ? err.message : '保存失败');
        } finally {
            setIsSaving(false);
        }
    };

    const handleApiKeyBlur = async () => {
        // Only save if it's a new key (not masked)
        if (apiKey && !apiKey.includes('*') && apiKey.length > 0) {
            try {
                // 传递当前选择的 provider，后端会自动转换为 provider_id
                await SettingsAPI.updateApiKey(apiKey, provider);
                // Reload to get masked version
                const settings = await SettingsAPI.getSettings();
                setApiKey(settings.api_key || '');
                setSuccessMessage('API Key 已安全保存');
                setTimeout(() => setSuccessMessage(null), 3000);
            } catch (err) {
                setError('API Key 保存失败');
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

            {/* Error/Success Messages */}
            {error && (
                <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-center gap-3">
                    <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                    <span className="text-red-700 text-sm font-medium">{error}</span>
                    <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">
                        <X size={16} />
                    </button>
                </div>
            )}
            {successMessage && (
                <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 flex items-center gap-3">
                    <Check className="w-5 h-5 text-green-500 flex-shrink-0" />
                    <span className="text-green-700 text-sm font-medium">{successMessage}</span>
                </div>
            )}

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">系统设置</h1>
                    <p className="text-slate-500 mt-1 font-medium">配置您的API。</p>
                </div>
                <button
                    onClick={handleSaveAll}
                    disabled={isSaving}
                    className="flex items-center gap-2 px-6 py-3 bg-slate-900 text-white rounded-xl font-bold text-sm shadow-lg shadow-slate-200 hover:bg-blue-600 hover:shadow-blue-200 transition-all active:scale-95 disabled:opacity-50"
                >
                    {isSaving ? (
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                        <Save size={18} />
                    )}
                    <span>{isSaving ? '保存中...' : '保存配置'}</span>
                </button>
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
                                onClick={() => setClassificationMode('simple')}
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
                                onClick={() => setClassificationMode('complex')}
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
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">ActivityWatch 数据库路径</label>
                        <div className="flex gap-3">
                            <input
                                type="text"
                                value={awPath}
                                onChange={(e) => setAwPath(e.target.value)}
                                className="flex-1 bg-gray-50 border border-transparent focus:bg-white focus:border-orange-200 focus:ring-4 focus:ring-orange-50/50 rounded-xl px-4 py-3 text-slate-600 font-mono text-xs outline-none transition-all"
                            />
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

                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">LifeWatch 数据库路径</label>
                        <input
                            type="text"
                            value={lwPath}
                            onChange={(e) => setLwPath(e.target.value)}
                            className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-orange-200 focus:ring-4 focus:ring-orange-50/50 rounded-xl px-4 py-3 text-slate-600 font-mono text-xs outline-none transition-all"
                        />
                    </div>

                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">聊天数据库路径</label>
                        <input
                            type="text"
                            value={chatPath}
                            onChange={(e) => setChatPath(e.target.value)}
                            className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-orange-200 focus:ring-4 focus:ring-orange-50/50 rounded-xl px-4 py-3 text-slate-600 font-mono text-xs outline-none transition-all"
                        />
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
                            onClick={() => setFilterDuration(Math.max(0, filterDuration - 1))}
                            className="w-8 h-8 flex items-center justify-center rounded-lg bg-white border border-gray-200 text-slate-500 hover:border-blue-300 hover:text-blue-600 transition-all"
                        >
                            <Minus size={14} />
                        </button>

                        <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-lg border border-gray-200 shadow-sm w-24 justify-center">
                            <input
                                type="number"
                                value={filterDuration}
                                onChange={(e) => setFilterDuration(parseInt(e.target.value) || 0)}
                                className="w-full text-center font-bold text-slate-800 outline-none bg-transparent"
                            />
                        </div>

                        <button
                            onClick={() => setFilterDuration(filterDuration + 1)}
                            className="w-8 h-8 flex items-center justify-center rounded-lg bg-white border border-gray-200 text-slate-500 hover:border-blue-300 hover:text-blue-600 transition-all"
                        >
                            <Plus size={14} />
                        </button>

                        <span className="text-xs font-bold text-slate-400 uppercase ml-1">秒</span>
                    </div>
                </div>
            </section>

            {/* VolcEngine Info Modal */}
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
            )}

        </div>
    );
};

export { SettingsApp };
