import React, { useState, useEffect, useRef } from 'react';
import { X, Send, Sparkles, Bot, User, ChevronLeft, ChevronRight, Plus, History, MoreHorizontal, Trash2, Search, Brain, Globe, ChevronUp, MessageCircle, BookOpen, Square, Loader2, Zap } from 'lucide-react';
import { sendMessageStream, getSessions, deleteSession, getChatHistory, getModelConfig, updateModelConfig } from '../api';
import { ChatMessage, ChatSession, ChatDisplayMode, ModelConfig, SSEEvent, FeatureMode, TokenUsage } from '../types';
import { MarkdownRenderer } from '../../common';

interface ChatPanelProps {
    displayMode: ChatDisplayMode;
    onModeChange: (mode: ChatDisplayMode) => void;
    onWidthChange?: (width: number) => void;
}

const ChatPanel: React.FC<ChatPanelProps> = ({ displayMode, onModeChange, onWidthChange }) => {
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState<ChatMessage[]>([
        { id: 'init', role: 'model', text: "你好！我是 LifeWatch AI 助手。我可以帮助你分析时间使用情况、提供生产力建议。有什么可以帮你的吗？" }
    ]);
    const [isTyping, setIsTyping] = useState(false);
    const [showHistory, setShowHistory] = useState(false);
    const [historySearch, setHistorySearch] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // 新增状态：会话管理
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
    const [sessions, setSessions] = useState<ChatSession[]>([]);
    const [isLoadingSessions, setIsLoadingSessions] = useState(false);

    // 新增状态：模型配置
    const [modelConfig, setModelConfig] = useState<ModelConfig>({ enableSearch: false, enableThinking: false });

    // 新增状态：功能菜单
    const [showFeatureMenu, setShowFeatureMenu] = useState(false);
    const [selectedFeature, setSelectedFeature] = useState<string>('default');

    // 新增状态：取消请求
    const [abortController, setAbortController] = useState<AbortController | null>(null);

    // 新增状态：当前处理状态和 Token 使用
    const [currentStatus, setCurrentStatus] = useState<string | null>(null);
    const [lastTokenUsage, setLastTokenUsage] = useState<TokenUsage | null>(null);

    // 新增状态：面板宽度拖拽调整
    const [panelWidth, setPanelWidth] = useState(400); // 默认宽度 400px
    const [isResizing, setIsResizing] = useState(false);
    const [isHoveringResizer, setIsHoveringResizer] = useState(false);
    const panelRef = useRef<HTMLElement>(null);
    const MIN_WIDTH = 320; // 最小宽度
    const MAX_WIDTH = 800; // 最大宽度

    // 拖拽开始
    const handleResizeMouseDown = (e: React.MouseEvent) => {
        e.preventDefault();
        setIsResizing(true);
    };

    // 拖拽移动
    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isResizing) return;

            const windowWidth = window.innerWidth;
            const newWidth = windowWidth - e.clientX;

            // 限制宽度在最小和最大值之间
            const clampedWidth = Math.min(Math.max(newWidth, MIN_WIDTH), MAX_WIDTH);
            setPanelWidth(clampedWidth);
        };

        const handleMouseUp = () => {
            setIsResizing(false);
        };

        if (isResizing) {
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
            // 拖拽时禁止选择文本
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'ew-resize';
        }

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
        };
    }, [isResizing]);

    // 通知父组件面板宽度变化
    useEffect(() => {
        if (displayMode === 'sidebar' && onWidthChange) {
            onWidthChange(panelWidth);
        } else if (displayMode === 'hidden' && onWidthChange) {
            onWidthChange(0);
        } else if (displayMode === 'overlay' && onWidthChange) {
            // overlay 模式下不需要预留空间
            onWidthChange(0);
        }
    }, [panelWidth, displayMode, onWidthChange]);

    // 功能模式列表
    const FEATURE_MODES: FeatureMode[] = [
        { id: 'default', name: '正常聊天', icon: <MessageCircle size={16} /> },
        { id: 'lifeprism', name: 'LifeWatch 功能讲解', icon: <BookOpen size={16} /> },
    ];

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    // 加载会话列表
    const loadSessions = async () => {
        setIsLoadingSessions(true);
        try {
            const data = await getSessions();
            setSessions(data.items);
        } catch (e) {
            console.error('Failed to load sessions:', e);
        } finally {
            setIsLoadingSessions(false);
        }
    };

    // 加载模型配置
    const loadModelConfig = async () => {
        try {
            const config = await getModelConfig();
            setModelConfig(config);
        } catch (e) {
            console.error('Failed to load model config:', e);
        }
    };

    // 初始化加载
    useEffect(() => {
        loadSessions();
        loadModelConfig();
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping]);

    // 发送消息
    const handleSend = async () => {
        if (!input.trim()) return;

        const userMsg: ChatMessage = {
            id: Date.now().toString(),
            role: 'user',
            text: input
        };

        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsTyping(true);

        // 创建 AbortController 用于暂停
        const controller = new AbortController();
        setAbortController(controller);

        try {
            // 创建 AI 消息占位
            const aiMsgId = (Date.now() + 1).toString();
            setMessages(prev => [...prev, { id: aiMsgId, role: 'model', text: '', isLoading: true }]);

            let fullText = '';

            let newSessionId = currentSessionId;

            await sendMessageStream(
                currentSessionId,
                userMsg.text,
                (event: SSEEvent) => {
                    switch (event.type) {
                        case 'session':
                            // 更新会话信息
                            newSessionId = event.sessionId || null;
                            setCurrentSessionId(newSessionId);
                            if (event.isNewSession) {
                                // 刷新会话列表
                                loadSessions();
                            }
                            break;
                        case 'status':
                            // 显示节点状态
                            setCurrentStatus(event.message || null);
                            break;
                        case 'content':
                            // 清除状态，追加内容
                            setCurrentStatus(null);
                            fullText += event.message || event.content || '';
                            setMessages(prev =>
                                prev.map(msg =>
                                    msg.id === aiMsgId ? { ...msg, text: fullText, isLoading: false } : msg
                                )
                            );
                            break;
                        case 'done':
                            // 完成，从事件中获取 token 使用情况
                            setCurrentStatus(null);
                            if (event.usage) {
                                setLastTokenUsage(event.usage);
                                // 将 token 信息附加到最后一条 AI 消息
                                setMessages(prev =>
                                    prev.map(msg =>
                                        msg.id === aiMsgId ? { ...msg, tokenUsage: event.usage } : msg
                                    )
                                );
                            }
                            break;
                        case 'error':
                            console.error('SSE Error:', event.error);
                            setCurrentStatus(null);
                            setMessages(prev =>
                                prev.map(msg =>
                                    msg.id === aiMsgId ? { ...msg, text: event.error || '发生错误', isLoading: false } : msg
                                )
                            );
                            break;
                    }
                },
                controller.signal
            );
        } catch (e) {
            if (e instanceof Error && e.name === 'AbortError') {
                console.log('Request aborted by user');
            } else {
                console.error(e);
            }
        } finally {
            setIsTyping(false);
            setAbortController(null);
        }
    };

    // 暂停输出
    const handleStop = () => {
        if (abortController) {
            abortController.abort();
            setAbortController(null);
            setIsTyping(false);
        }
    };

    // 切换深度思考
    const handleToggleThinking = async () => {
        try {
            const newConfig = await updateModelConfig({ enableThinking: !modelConfig.enableThinking });
            setModelConfig(newConfig);
        } catch (e) {
            console.error('Failed to update thinking mode:', e);
        }
    };

    // 切换联网搜索
    const handleToggleSearch = async () => {
        try {
            const newConfig = await updateModelConfig({ enableSearch: !modelConfig.enableSearch });
            setModelConfig(newConfig);
        } catch (e) {
            console.error('Failed to update search mode:', e);
        }
    };

    // 新建对话
    const handleNewChat = () => {
        setCurrentSessionId(null);
        setMessages([
            { id: 'init', role: 'model', text: "你好！我是 LifeWatch AI 助手。我可以帮助你分析时间使用情况、提供生产力建议。有什么可以帮你的吗？" }
        ]);
        setShowHistory(false);
    };

    // 删除会话
    const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            await deleteSession(sessionId);
            setSessions(prev => prev.filter(s => s.id !== sessionId));
            if (currentSessionId === sessionId) {
                handleNewChat();
            }
        } catch (e) {
            console.error('Failed to delete session:', e);
        }
    };

    // 切换会话
    const handleSelectSession = async (session: ChatSession) => {
        setCurrentSessionId(session.id);
        setShowHistory(false);

        // 加载会话历史
        try {
            const history = await getChatHistory(session.id);

            if (history.length > 0) {
                setMessages(history);
            } else {
                // 没有历史消息时显示提示
                setMessages([
                    { id: 'init', role: 'model', text: `已切换到会话：${session.name}（无历史消息）` }
                ]);
            }
        } catch (e) {
            console.error('Failed to load chat history:', e);
            setMessages([
                { id: 'init', role: 'model', text: `已切换到会话：${session.name}（加载历史失败）` }
            ]);
        }
    };

    // 格式化时间
    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);

        if (minutes < 60) return `${minutes} 分钟前`;
        if (hours < 24) return `${hours} 小时前`;
        return `${days} 天前`;
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // Handle mode transitions
    const handleExpandMode = () => {
        if (displayMode === 'sidebar') {
            onModeChange('overlay');
        } else if (displayMode === 'hidden') {
            onModeChange('sidebar');
        }
    };

    const handleCollapseMode = () => {
        if (displayMode === 'overlay') {
            onModeChange('sidebar');
        } else if (displayMode === 'sidebar') {
            onModeChange('hidden');
        }
    };

    const getPanelWidthClass = () => {
        switch (displayMode) {
            case 'overlay':
                // overlay 模式：从左侧导航栏右边缘开始（lg:left-64，对应导航栏宽度）
                return 'lg:left-64 left-0 w-full lg:w-auto';
            case 'sidebar':
                // sidebar 模式：宽度由内联样式控制，移动端使用全宽
                return 'w-full sm:w-auto';
            case 'hidden':
                return 'w-full sm:w-[400px]';
        }
    };

    const isVisible = displayMode !== 'hidden';

    return (
        <>
            {/* Hidden State: Edge Trigger Button */}
            {displayMode === 'hidden' && (
                <button
                    onClick={() => onModeChange('sidebar')}
                    className="fixed right-0 top-1/2 -translate-y-1/2 z-50 h-20 w-6 bg-gradient-to-l from-indigo-500 to-indigo-600 text-white rounded-l-lg shadow-lg hover:w-8 hover:from-indigo-600 hover:to-indigo-700 transition-all duration-200 flex items-center justify-center group"
                    title="打开 AI 助手"
                >
                    <ChevronLeft size={16} className="group-hover:scale-110 transition-transform" />
                </button>
            )}

            {/* Backdrop - Only visible on mobile/tablet (hidden on lg) when panel is visible */}
            <div
                className={`fixed inset-0 bg-black/20 backdrop-blur-sm z-40 transition-opacity duration-300 lg:hidden ${isVisible ? 'opacity-100' : 'opacity-0 pointer-events-none'
                    }`}
                onClick={() => onModeChange('hidden')}
            />

            {/* Slide-over Panel */}
            <aside
                ref={panelRef}
                style={displayMode === 'sidebar' ? { width: `${panelWidth}px` } : undefined}
                className={`fixed right-0 top-0 h-full ${getPanelWidthClass()} bg-white z-50 transform transition-all duration-300 ease-in-out flex flex-col border-l border-gray-200 shadow-2xl lg:shadow-none ${isVisible ? 'translate-x-0' : 'translate-x-full'
                    } ${displayMode === 'overlay' ? '!right-0' : ''} ${isResizing ? '!transition-none' : ''}`}
            >
                {/* Resize Handle - 拖拽调整宽度 */}
                {displayMode === 'sidebar' && isVisible && (
                    <div
                        className="absolute left-0 top-0 h-full w-1 cursor-ew-resize z-50 group"
                        onMouseDown={handleResizeMouseDown}
                        onMouseEnter={() => setIsHoveringResizer(true)}
                        onMouseLeave={() => setIsHoveringResizer(false)}
                    >
                        {/* 扩大点击区域的透明层 */}
                        <div className="absolute left-[-4px] top-0 h-full w-[12px]" />
                        {/* 视觉指示条 - 悬停或拖拽时显示 */}
                        <div
                            className={`absolute left-0 top-0 h-full w-1 transition-all duration-200 ${isResizing
                                ? 'bg-indigo-500'
                                : isHoveringResizer
                                    ? 'bg-indigo-400'
                                    : 'bg-transparent hover:bg-gray-300'
                                }`}
                        />
                        {/* 中间拖拽指示器 - 悬停时显示 */}
                        <div
                            className={`absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 transition-opacity duration-200 ${isHoveringResizer || isResizing ? 'opacity-100' : 'opacity-0'
                                }`}
                        >
                            <div className="flex flex-col items-center gap-1 px-1 py-3 bg-white rounded-full shadow-lg border border-gray-200">
                                <div className="w-1 h-1 rounded-full bg-gray-400" />
                                <div className="w-1 h-1 rounded-full bg-gray-400" />
                                <div className="w-1 h-1 rounded-full bg-gray-400" />
                            </div>
                        </div>
                    </div>
                )}

                {/* Mode Control Buttons (Left Edge) */}
                {isVisible && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-full flex flex-col gap-1 z-50">
                        {/* Expand Button (Left Arrow) - visible in sidebar mode */}
                        {displayMode === 'sidebar' && (
                            <button
                                onClick={handleExpandMode}
                                className="w-6 h-12 bg-white border border-gray-200 border-r-0 rounded-l-lg shadow-md hover:bg-gray-50 transition-colors flex items-center justify-center text-gray-500 hover:text-indigo-600"
                                title="全屏模式"
                            >
                                <ChevronLeft size={16} />
                            </button>
                        )}
                        {/* Collapse Button (Right Arrow) - visible in overlay and sidebar modes */}
                        <button
                            onClick={handleCollapseMode}
                            className="w-6 h-12 bg-white border border-gray-200 border-r-0 rounded-l-lg shadow-md hover:bg-gray-50 transition-colors flex items-center justify-center text-gray-500 hover:text-indigo-600"
                            title={displayMode === 'overlay' ? '侧边栏模式' : '隐藏'}
                        >
                            <ChevronRight size={16} />
                        </button>
                    </div>
                )}

                {/* Header */}
                <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-blue-50/50 to-purple-50/50">
                    <div className="flex items-center gap-2">
                        <div className="p-2 bg-white rounded-lg shadow-sm text-indigo-500">
                            <Sparkles size={18} />
                        </div>
                        <div>
                            <h3 className="font-bold text-gray-800">AI Assistant</h3>
                            <p className="text-xs text-gray-500">LifeWatch AI</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-1">
                        {/* New Chat Button */}
                        <button
                            onClick={handleNewChat}
                            className="p-2 hover:bg-white/80 rounded-lg text-gray-500 hover:text-indigo-600 transition-colors"
                            title="新建对话"
                        >
                            <Plus size={18} />
                        </button>
                        {/* History Button */}
                        <button
                            onClick={() => setShowHistory(!showHistory)}
                            className={`p-2 hover:bg-white/80 rounded-lg transition-colors ${showHistory ? 'text-indigo-600 bg-white/80' : 'text-gray-500 hover:text-indigo-600'}`}
                            title="历史对话"
                        >
                            <History size={18} />
                        </button>
                        {/* More Menu Button */}
                        <button
                            onClick={() => {
                                // TODO: 更多菜单功能
                                console.log('More menu');
                            }}
                            className="p-2 hover:bg-white/80 rounded-lg text-gray-500 hover:text-indigo-600 transition-colors"
                            title="更多选项"
                        >
                            <MoreHorizontal size={18} />
                        </button>
                        {/* Close Button */}
                        <button
                            onClick={() => onModeChange('hidden')}
                            className="p-2 hover:bg-white/80 rounded-lg text-gray-500 hover:text-red-500 transition-colors"
                            title="关闭"
                        >
                            <X size={18} />
                        </button>
                    </div>
                </div>

                {/* History Panel (Slides over messages) */}
                {showHistory && (
                    <div className="absolute inset-0 top-[73px] bg-white z-10 flex flex-col animate-in slide-in-from-top duration-200">
                        {/* Search Box */}
                        <div className="p-4 border-b border-gray-100">
                            <div className="relative">
                                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                                <input
                                    type="text"
                                    value={historySearch}
                                    onChange={(e) => setHistorySearch(e.target.value)}
                                    placeholder="搜索对话..."
                                    className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all text-sm"
                                />
                            </div>
                        </div>

                        {/* Conversation List */}
                        <div className="flex-1 overflow-y-auto">
                            {isLoadingSessions ? (
                                <div className="flex items-center justify-center py-8">
                                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600"></div>
                                </div>
                            ) : sessions.length === 0 ? (
                                <div className="text-center py-8 text-gray-400">
                                    <p>暂无历史对话</p>
                                </div>
                            ) : (
                                <>
                                    {/* Current Session */}
                                    {currentSessionId && sessions.filter(s => s.id === currentSessionId).map((session) => (
                                        <div key={session.id}>
                                            <div className="px-4 pt-4 pb-2">
                                                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">当前对话</p>
                                            </div>
                                            <div
                                                className="mx-3 mb-1 px-3 py-3 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-between group cursor-pointer hover:bg-amber-100 transition-colors"
                                                onClick={() => handleSelectSession(session)}
                                            >
                                                <span className="text-sm font-medium text-gray-800 truncate">{session.name}</span>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-gray-400 whitespace-nowrap">{formatTime(session.updatedAt)}</span>
                                                    <button
                                                        onClick={(e) => handleDeleteSession(session.id, e)}
                                                        className="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    ))}

                                    {/* Other Sessions */}
                                    <div className="px-4 pt-4 pb-2">
                                        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">最近对话</p>
                                    </div>
                                    {sessions
                                        .filter(s => s.id !== currentSessionId)
                                        .filter(s => !historySearch || s.name.toLowerCase().includes(historySearch.toLowerCase()))
                                        .map((session) => (
                                            <div
                                                key={session.id}
                                                className="mx-3 mb-1 px-3 py-3 rounded-lg flex items-center justify-between group cursor-pointer hover:bg-gray-50 transition-colors"
                                                onClick={() => handleSelectSession(session)}
                                            >
                                                <span className="text-sm text-gray-700 truncate">{session.name}</span>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-gray-400 whitespace-nowrap">{formatTime(session.updatedAt)}</span>
                                                    <button
                                                        onClick={(e) => handleDeleteSession(session.id, e)}
                                                        className="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                </div>
                                            </div>
                                        ))}
                                </>
                            )}
                        </div>
                    </div>
                )}

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#F9FAFB] scrollbar-light">
                    {messages.map((msg) => (
                        <div key={msg.id} className="space-y-1">
                            <div
                                className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                            >
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-gray-800 text-white' : 'bg-indigo-100 text-indigo-600'
                                    }`}>
                                    {msg.role === 'user' ? <User size={14} /> : <Bot size={16} />}
                                </div>

                                <div className={`max-w-[85%] rounded-2xl p-3 text-base leading-relaxed ${msg.role === 'user'
                                    ? 'bg-gray-800 text-white rounded-tr-none'
                                    : 'bg-white shadow-sm border border-gray-100 text-gray-700 rounded-tl-none'
                                    }`}>
                                    {msg.isLoading && msg.text === '' ? (
                                        <span className="inline-flex gap-1 items-center h-4">
                                            <span className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                                            <span className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                                            <span className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                                        </span>
                                    ) : msg.role === 'model' ? (
                                        <MarkdownRenderer content={msg.text} />
                                    ) : (
                                        msg.text
                                    )}
                                </div>
                            </div>

                            {/* Token 使用统计 - 仅显示在 AI 回复下方 */}
                            {msg.role === 'model' && msg.tokenUsage && msg.tokenUsage.turn_usage && msg.tokenUsage.turn_usage.total_tokens > 0 && (() => {
                                // 格式化 token 数量（以 k 为单位）
                                const formatTokens = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n.toString();
                                const turn = msg.tokenUsage.turn_usage;
                                const session = msg.tokenUsage.session_usage;
                                return (
                                    <div className="flex items-center justify-start gap-1 ml-11 text-xs text-gray-400">
                                        <Zap size={10} className="text-amber-400" />
                                        <span>输入: {formatTokens(turn.input_tokens)}</span>
                                        <span className="text-gray-300">|</span>
                                        <span>输出: {formatTokens(turn.output_tokens)}</span>
                                        <span className="text-gray-300">|</span>
                                        <span>本轮: {formatTokens(turn.total_tokens)}</span>
                                        <span className="text-gray-300">|</span>
                                        <span className="text-indigo-400">会话: {formatTokens(session.total_tokens)}</span>
                                    </div>
                                );
                            })()}
                        </div>
                    ))}

                    {/* 状态显示条 */}
                    {currentStatus && (
                        <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 border border-blue-100 rounded-lg text-blue-600 text-sm animate-pulse">
                            <Loader2 size={14} className="animate-spin" />
                            <span>{currentStatus}</span>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="bg-white border-t border-gray-100">
                    {/* 底部工具栏 */}
                    <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-50">
                        {/* 功能菜单按钮 */}
                        <div className="relative">
                            <button
                                onClick={() => setShowFeatureMenu(!showFeatureMenu)}
                                className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                            >
                                <span>{FEATURE_MODES.find(m => m.id === selectedFeature)?.name || '正常聊天'}</span>
                                <ChevronUp size={14} className={`transition-transform ${showFeatureMenu ? 'rotate-180' : ''}`} />
                            </button>

                            {/* 弹出菜单 */}
                            {showFeatureMenu && (
                                <div className="absolute bottom-full left-0 mb-2 w-52 bg-gray-800 rounded-lg shadow-xl py-2 z-50">
                                    {FEATURE_MODES.map(mode => (
                                        <button
                                            key={mode.id}
                                            onClick={() => {
                                                setSelectedFeature(mode.id);
                                                setShowFeatureMenu(false);
                                            }}
                                            className={`w-full px-4 py-2.5 text-left text-sm text-white hover:bg-gray-700 flex items-center gap-3 ${selectedFeature === mode.id ? 'bg-gray-700' : ''
                                                }`}
                                        >
                                            <span className="text-gray-400">{mode.icon}</span>
                                            <span>{mode.name}</span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="flex-1" />

                        {/* 深度思考开关 */}
                        <button
                            onClick={handleToggleThinking}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${modelConfig.enableThinking
                                ? 'bg-emerald-100 text-emerald-700'
                                : 'text-gray-500 hover:bg-gray-100'
                                }`}
                            title="深度思考模式"
                        >
                            <Brain size={14} />
                            <span>深度思考</span>
                        </button>

                        {/* 联网搜索开关 */}
                        <button
                            onClick={handleToggleSearch}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${modelConfig.enableSearch
                                ? 'bg-emerald-100 text-emerald-700'
                                : 'text-gray-500 hover:bg-gray-100'
                                }`}
                            title="联网搜索"
                        >
                            <Globe size={14} />
                            <span>联网搜索</span>
                        </button>
                    </div>

                    {/* 输入框 */}
                    <div className="p-4">
                        <div className="relative">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="输入消息..."
                                disabled={isTyping}
                                className="w-full pl-4 pr-12 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-sm"
                            />
                            {isTyping ? (
                                <button
                                    onClick={handleStop}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
                                    title="停止生成"
                                >
                                    <Square size={16} />
                                </button>
                            ) : (
                                <button
                                    onClick={handleSend}
                                    disabled={!input.trim()}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:hover:bg-indigo-600 transition-colors"
                                >
                                    <Send size={16} />
                                </button>
                            )}
                        </div>
                        <p className="text-[10px] text-center text-gray-400 mt-2">
                            AI 可能会出错，请核实重要信息。
                        </p>
                    </div>
                </div>
            </aside>
        </>
    );
};

export default ChatPanel;
