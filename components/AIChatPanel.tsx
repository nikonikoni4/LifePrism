import React, { useState, useEffect, useRef } from 'react';
import { X, Send, Sparkles, Bot, User } from 'lucide-react';
import { sendMessageToGemini } from '../services/geminiService';
import { ChatMessage } from '../types';

interface AIChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const AIChatPanel: React.FC<AIChatPanelProps> = ({ isOpen, onClose }) => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 'init', role: 'model', text: "Hi Alex! I've analyzed your focus time today. You've been crushing it in VS Code, but your entertainment usage is creeping up. How can I help you optimize?" }
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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

  return (
    <>
      {/* Backdrop - Only visible on mobile/tablet (hidden on lg) */}
      <div 
        className={`fixed inset-0 bg-black/20 backdrop-blur-sm z-40 transition-opacity duration-300 lg:hidden ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      {/* Slide-over Panel (Right Sidebar on Desktop) */}
      <aside 
        className={`fixed right-0 top-0 h-full w-full sm:w-[400px] bg-white z-50 transform transition-transform duration-300 ease-in-out flex flex-col border-l border-gray-200 shadow-2xl lg:shadow-none ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
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
          <button 
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full text-gray-500 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#F9FAFB]">
          {messages.map((msg) => (
            <div 
              key={msg.id} 
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                msg.role === 'user' ? 'bg-gray-800 text-white' : 'bg-indigo-100 text-indigo-600'
              }`}>
                {msg.role === 'user' ? <User size={14} /> : <Bot size={16} />}
              </div>
              
              <div className={`max-w-[80%] rounded-2xl p-3 text-sm leading-relaxed ${
                msg.role === 'user' 
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