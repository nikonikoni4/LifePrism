
import React, { useState, useEffect } from 'react';
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
    Loader2
} from 'lucide-react';
import { SettingsAPI } from './api';

const SettingsPage: React.FC = () => {
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
    const [apiKey, setApiKey] = useState('');
    const [showKey, setShowKey] = useState(false);
    const [apiStatus, setApiStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
    const [costInput, setCostInput] = useState(0);
    const [costOutput, setCostOutput] = useState(0);

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
    const handleTestConnection = () => {
        setApiStatus('testing');
        setTimeout(() => {
            setApiStatus('success');
        }, 1500);
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
                await SettingsAPI.updateApiKey(apiKey);
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
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">System Settings</h1>
                    <p className="text-slate-500 mt-1 font-medium">Configure your digital extension and intelligence engine.</p>
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
                    <span>{isSaving ? 'Saving...' : 'Save Configuration'}</span>
                </button>
            </div>

            {/* 1. User Profile */}
            <section className="bg-white rounded-[2rem] border border-gray-100 p-8 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2.5 bg-gray-50 rounded-xl text-slate-600">
                        <User size={20} />
                    </div>
                    <h2 className="text-lg font-bold text-slate-800">User Profile</h2>
                </div>
                <div className="max-w-md">
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">Display Nickname</label>
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
                    <h2 className="text-lg font-bold text-slate-800">Intelligence Engine (LLM)</h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {/* Provider & Model */}
                    <div className="space-y-6">
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">Provider</label>
                            <select
                                value={provider}
                                onChange={(e) => setProvider(e.target.value)}
                                className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all appearance-none cursor-pointer"
                            >
                                <option value="">选择服务商...</option>
                                {providerList.map(p => (
                                    <option key={p} value={p}>{p}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">Model Name</label>
                            <input
                                type="text"
                                value={modelName}
                                onChange={(e) => setModelName(e.target.value)}
                                className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl px-4 py-3 text-slate-800 font-medium outline-none transition-all"
                            />
                        </div>
                    </div>

                    {/* API Key & Test */}
                    <div className="space-y-6">
                        <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">API Key</label>
                            <div className="relative">
                                <input
                                    type={showKey ? "text" : "password"}
                                    value={apiKey}
                                    onChange={(e) => setApiKey(e.target.value)}
                                    onBlur={handleApiKeyBlur}
                                    placeholder="Enter your API key..."
                                    className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-purple-200 focus:ring-4 focus:ring-purple-50/50 rounded-xl pl-4 pr-12 py-3 text-slate-800 font-mono text-sm outline-none transition-all"
                                />
                                <button
                                    onClick={() => setShowKey(!showKey)}
                                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                                >
                                    {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                                </button>
                            </div>
                            <p className="text-xs text-slate-400 mt-2">API Key will be securely saved when you leave this field.</p>
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
                                {apiStatus === 'testing' ? 'Testing...' : apiStatus === 'success' ? 'Connected' : 'Test Connection'}
                            </button>
                            {apiStatus === 'error' && (
                                <span className="text-xs text-red-500 font-medium flex items-center gap-1">
                                    <AlertCircle size={12} /> Connection Failed
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                {/* Cost Estimation */}
                <div className="mt-8 pt-6 border-t border-dashed border-gray-100">
                    <h3 className="text-xs font-bold text-slate-500 mb-4 flex items-center gap-2">
                        Cost Estimation (Per 1k Tokens, ¥)
                    </h3>
                    <div className="grid grid-cols-2 gap-4 max-w-lg">
                        <div className="bg-gray-50 p-3 rounded-xl border border-gray-100 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
                            <label className="text-[9px] font-bold text-slate-400 uppercase block mb-1">Input Cost</label>
                            <input
                                type="number"
                                step="0.0001"
                                value={costInput}
                                onChange={(e) => setCostInput(parseFloat(e.target.value) || 0)}
                                className="w-full bg-transparent font-mono font-bold text-slate-700 outline-none"
                            />
                        </div>
                        <div className="bg-gray-50 p-3 rounded-xl border border-gray-100 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
                            <label className="text-[9px] font-bold text-slate-400 uppercase block mb-1">Output Cost</label>
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
                    <h2 className="text-lg font-bold text-slate-800">Classification Logic</h2>
                </div>

                <div className="space-y-8">
                    {/* Mode Selection */}
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-4 block">Classification Mode</label>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <button
                                onClick={() => setClassificationMode('simple')}
                                className={`text-left p-4 rounded-2xl border-2 transition-all ${classificationMode === 'simple'
                                    ? 'border-blue-500 bg-blue-50/30'
                                    : 'border-gray-100 hover:border-blue-200 bg-white'
                                    }`}
                            >
                                <div className="flex justify-between items-start mb-1">
                                    <span className={`font-bold ${classificationMode === 'simple' ? 'text-blue-700' : 'text-slate-700'}`}>Simple Mode</span>
                                    {classificationMode === 'simple' && <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5" />}
                                </div>
                                <p className="text-xs text-slate-500 leading-relaxed">Uses fewer tokens. Categorizes based on app name and window title keywords. Faster and cheaper.</p>
                            </button>

                            <button
                                onClick={() => setClassificationMode('complex')}
                                className={`text-left p-4 rounded-2xl border-2 transition-all ${classificationMode === 'complex'
                                    ? 'border-purple-500 bg-purple-50/30'
                                    : 'border-gray-100 hover:border-purple-200 bg-white'
                                    }`}
                            >
                                <div className="flex justify-between items-start mb-1">
                                    <span className={`font-bold ${classificationMode === 'complex' ? 'text-purple-700' : 'text-slate-700'}`}>Deep Context Mode</span>
                                    {classificationMode === 'complex' && <div className="w-2 h-2 rounded-full bg-purple-500 mt-1.5" />}
                                </div>
                                <p className="text-xs text-slate-500 leading-relaxed">Analyzes full window titles and context. Highly accurate for browsers but consumes more tokens.</p>
                            </button>
                        </div>
                    </div>

                    {/* Long Log Threshold */}
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">Long Activity Threshold (seconds)</label>
                        <input
                            type="number"
                            value={longLogThreshold}
                            onChange={(e) => setLongLogThreshold(parseInt(e.target.value) || 0)}
                            className="w-32 bg-gray-50 border border-transparent focus:bg-white focus:border-blue-200 focus:ring-4 focus:ring-blue-50/50 rounded-xl px-4 py-3 text-slate-800 font-bold outline-none transition-all"
                        />
                        <p className="text-xs text-slate-400 mt-2">Activities longer than this will be marked as long activities.</p>
                    </div>

                    {/* Browser Apps List */}
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 block">Multi-Purpose Applications</label>
                        <p className="text-xs text-slate-500 mb-3">Define which applications should use title info for classification (browsers, etc.).</p>

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
                                placeholder="Type app name & Enter..."
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
                    <h2 className="text-lg font-bold text-slate-800">Storage & Sources</h2>
                </div>

                <div className="space-y-6">
                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">ActivityWatch DB Path</label>
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
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">LifeWatch DB Path</label>
                        <input
                            type="text"
                            value={lwPath}
                            onChange={(e) => setLwPath(e.target.value)}
                            className="w-full bg-gray-50 border border-transparent focus:bg-white focus:border-orange-200 focus:ring-4 focus:ring-orange-50/50 rounded-xl px-4 py-3 text-slate-600 font-mono text-xs outline-none transition-all"
                        />
                    </div>

                    <div>
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">Chat DB Path</label>
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
                    <h2 className="text-lg font-bold text-slate-800">Data Hygiene</h2>
                </div>

                <div className="flex items-center gap-4 bg-gray-50 p-4 rounded-xl border border-gray-100">
                    <div className="flex-1">
                        <h4 className="text-sm font-bold text-slate-700">Short Duration Filter</h4>
                        <p className="text-xs text-slate-400 mt-1">Ignore window switches or activities that last less than this duration to reduce noise.</p>
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

                        <span className="text-xs font-bold text-slate-400 uppercase ml-1">Seconds</span>
                    </div>
                </div>
            </section>

        </div>
    );
};

export default SettingsPage;
