import React, { useState, useEffect, useRef } from 'react';
import { X, Send, Sparkles, Bot, User, ChevronLeft, ChevronRight, Plus, History, MoreHorizontal, Trash2, Search } from 'lucide-react';
import { sendMessageToGemini } from '../services/geminiService';
import { ChatMessage } from '../shared/types';

export type ChatDisplayMode = 'fullscreen' | 'sidebar' | 'hidden';

interface AIChatPanelProps {
  displayMode: ChatDisplayMode;
  onModeChange: (mode: ChatDisplayMode) => void;
}

const AIChatPanel: React.FC<AIChatPanelProps> = ({ displayMode, onModeChange }) => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 'init', role: 'model', text: "Hi Alex! I've analyzed your focus time today. You've been crushing it in VS Code, but your entertainment usage is creeping up. How can I help you optimize?" }
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historySearch, setHistorySearch] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Mock history data (placeholder)
  const mockHistory = [
    { id: '1', title: 'AI Chat Panel Expansion', time: '15 分钟前', isCurrent: true },
    { id: '2', title: 'Fix Timeline Category Display', time: '35 分钟前', isCurrent: false },
    { id: '3', title: 'Fixing Timeline Duplicates', time: '4 小时前', isCurrent: false },
    { id: '4', title: 'Frontend Usage API Implementation', time: '8 小时前', isCurrent: false },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

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

    try {
      const stream = sendMessageToGemini(userMsg.text);

      // Create a placeholder message for the AI response
      const aiMsgId = (Date.now() + 1).toString();
      setMessages(prev => [...prev, { id: aiMsgId, role: 'model', text: '', isLoading: true }]);

      let fullText = '';

      for await (const chunk of stream) {
        fullText += chunk;
        setMessages(prev =>
          prev.map(msg =>
            msg.id === aiMsgId ? { ...msg, text: fullText, isLoading: false } : msg
          )
        );
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsTyping(false);
    }
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
      onModeChange('fullscreen');
    } else if (displayMode === 'hidden') {
      onModeChange('sidebar');
    }
  };

  const handleCollapseMode = () => {
    if (displayMode === 'fullscreen') {
      onModeChange('sidebar');
    } else if (displayMode === 'sidebar') {
      onModeChange('hidden');
    }
  };

  const getPanelWidthClass = () => {
    switch (displayMode) {
      case 'fullscreen':
        // 全屏模式：从左侧导航栏右边缘开始（lg:left-64，对应导航栏宽度）
        return 'lg:left-64 left-0 w-full lg:w-auto';
      case 'sidebar':
        return 'w-full sm:w-[400px]';
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
        className={`fixed right-0 top-0 h-full ${getPanelWidthClass()} bg-white z-50 transform transition-all duration-300 ease-in-out flex flex-col border-l border-gray-200 shadow-2xl lg:shadow-none ${isVisible ? 'translate-x-0' : 'translate-x-full'
          } ${displayMode === 'fullscreen' ? '!right-0' : ''}`}
      >
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
            {/* Collapse Button (Right Arrow) - visible in fullscreen and sidebar modes */}
            <button
              onClick={handleCollapseMode}
              className="w-6 h-12 bg-white border border-gray-200 border-r-0 rounded-l-lg shadow-md hover:bg-gray-50 transition-colors flex items-center justify-center text-gray-500 hover:text-indigo-600"
              title={displayMode === 'fullscreen' ? '侧边栏模式' : '隐藏'}
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
              <p className="text-xs text-gray-500">Powered by Gemini</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* New Chat Button */}
            <button
              onClick={() => {
                // TODO: 新建对话功能
                console.log('New chat');
              }}
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
                  placeholder="Select a conversation"
                  className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all text-sm"
                />
              </div>
            </div>

            {/* Conversation List */}
            <div className="flex-1 overflow-y-auto">
              {/* Current Section */}
              <div className="px-4 pt-4 pb-2">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Current</p>
              </div>
              {mockHistory.filter(h => h.isCurrent).map((item) => (
                <div
                  key={item.id}
                  className="mx-3 mb-1 px-3 py-3 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-between group cursor-pointer hover:bg-amber-100 transition-colors"
                  onClick={() => {
                    // TODO: 切换到当前对话
                    setShowHistory(false);
                  }}
                >
                  <span className="text-sm font-medium text-gray-800 truncate">{item.title}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 whitespace-nowrap">{item.time}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        // TODO: 删除对话
                        console.log('Delete conversation', item.id);
                      }}
                      className="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}

              {/* Recent Section */}
              <div className="px-4 pt-4 pb-2">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Recent in LifeWatch-AI</p>
              </div>
              {mockHistory.filter(h => !h.isCurrent).map((item) => (
                <div
                  key={item.id}
                  className="mx-3 mb-1 px-3 py-3 rounded-lg flex items-center justify-between group cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => {
                    // TODO: 切换到该对话
                    setShowHistory(false);
                  }}
                >
                  <span className="text-sm text-gray-700 truncate">{item.title}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 whitespace-nowrap">{item.time}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        // TODO: 删除对话
                        console.log('Delete conversation', item.id);
                      }}
                      className="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}

              {/* Show More */}
              <div className="px-4 py-3">
                <button className="text-sm text-indigo-600 hover:text-indigo-700 font-medium">
                  Show 93 more...
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#F9FAFB]">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-gray-800 text-white' : 'bg-indigo-100 text-indigo-600'
                }`}>
                {msg.role === 'user' ? <User size={14} /> : <Bot size={16} />}
              </div>

              <div className={`max-w-[80%] rounded-2xl p-3 text-base leading-relaxed ${msg.role === 'user'
                ? 'bg-gray-800 text-white rounded-tr-none'
                : 'bg-white shadow-sm border border-gray-100 text-gray-700 rounded-tl-none'
                }`}>
                {msg.text}
                {msg.isLoading && msg.text === '' && (
                  <span className="inline-flex gap-1 items-center h-4">
                    <span className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                  </span>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white border-t border-gray-100">
          <div className="relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your productivity..."
              disabled={isTyping}
              className="w-full pl-4 pr-12 py-3 bg-gray-50 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-sm"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:hover:bg-indigo-600 transition-colors"
            >
              <Send size={16} />
            </button>
          </div>
          <p className="text-[10px] text-center text-gray-400 mt-2">
            AI can make mistakes. Please check important info.
          </p>
        </div>
      </aside>
    </>
  );
};

export default AIChatPanel;