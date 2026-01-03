/**
 * AI Summary Card Component
 * 
 * AI 总结卡片组件，支持加载状态和生成按钮
 */

import React, { useState, useEffect } from 'react';
import { Sparkles, RefreshCw, Loader2 } from 'lucide-react';
import { MarkdownRenderer } from '../../common';
import { ReportsAPI } from '../api';

interface AISummaryCardProps {
    title?: string;
    content?: string;
    date: string;
    className?: string;
    onSummaryGenerated?: (content: string) => void;
}

const AISummaryCard: React.FC<AISummaryCardProps> = ({
    title = 'AI 总结',
    content: initialContent = '',
    date,
    className = '',
    onSummaryGenerated
}) => {
    const [content, setContent] = useState(initialContent);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [tokensUsage, setTokensUsage] = useState<{
        inputTokens: number;
        outputTokens: number;
        totalTokens: number;
    } | null>(null);

    // 当外部传入的 content 变化时，同步更新内部状态
    useEffect(() => {
        setContent(initialContent);
    }, [initialContent]);

    const handleGenerateSummary = async () => {
        setIsLoading(true);
        setError(null);

        try {
            const result = await ReportsAPI.getAISummary(date, ['all']);
            setContent(result.content);
            setTokensUsage(result.tokensUsage);
            onSummaryGenerated?.(result.content);
        } catch (err) {
            setError(err instanceof Error ? err.message : '生成总结失败');
        } finally {
            setIsLoading(false);
        }
    };

    // 加载状态骨架屏
    const LoadingSkeleton = () => (
        <div className="animate-pulse space-y-3">
            <div className="flex items-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-purple-500" />
                <span className="text-sm text-slate-500">AI 正在分析您的数据...</span>
            </div>
            <div className="space-y-2">
                <div className="h-4 bg-slate-200 rounded w-full"></div>
                <div className="h-4 bg-slate-200 rounded w-5/6"></div>
                <div className="h-4 bg-slate-200 rounded w-4/6"></div>
            </div>
            <div className="space-y-2 mt-4">
                <div className="h-4 bg-slate-200 rounded w-full"></div>
                <div className="h-4 bg-slate-200 rounded w-3/4"></div>
            </div>
        </div>
    );

    // 空状态
    const EmptyState = () => (
        <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="p-4 bg-gradient-to-br from-purple-50 to-indigo-50 rounded-2xl mb-4">
                <Sparkles className="w-8 h-8 text-purple-500" />
            </div>
            <h4 className="text-sm font-medium text-slate-700 mb-2">
                暂无 AI 总结
            </h4>
            <p className="text-xs text-slate-500 mb-4">
                点击下方按钮，让 AI 为您生成今日活动总结
            </p>
            <button
                onClick={handleGenerateSummary}
                disabled={isLoading}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-indigo-500 text-white text-sm font-medium rounded-xl hover:from-purple-600 hover:to-indigo-600 transition-all duration-200 shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
                <Sparkles size={16} />
                生成 AI 总结
            </button>
        </div>
    );

    return (
        <div className={`bg-white rounded-2xl shadow-sm border border-gray-100 p-6 ${className}`}>
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-gradient-to-br from-purple-50 to-indigo-50 text-purple-500 rounded-xl">
                        <Sparkles size={18} />
                    </div>
                    <h3 className="text-base font-bold text-slate-800">{title}</h3>
                </div>

                {/* 重新生成按钮（有内容时显示） */}
                {content && !isLoading && (
                    <button
                        onClick={handleGenerateSummary}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-purple-600 hover:text-purple-700 hover:bg-purple-50 rounded-lg transition-colors"
                    >
                        <RefreshCw size={14} />
                        重新生成
                    </button>
                )}
            </div>

            {/* Content */}
            <div className="text-sm text-slate-600 leading-relaxed">
                {isLoading ? (
                    <LoadingSkeleton />
                ) : error ? (
                    <div className="flex flex-col items-center justify-center py-6 text-center">
                        <p className="text-sm text-red-500 mb-3">{error}</p>
                        <button
                            onClick={handleGenerateSummary}
                            className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                        >
                            <RefreshCw size={14} />
                            重试
                        </button>
                    </div>
                ) : content ? (
                    <>
                        <MarkdownRenderer content={content} />
                        {/* Token 使用量显示 */}
                        {tokensUsage && (
                            <div className="mt-4 pt-3 border-t border-slate-100">
                                <p className="text-xs text-slate-400">
                                    Token 使用量: {tokensUsage.totalTokens.toLocaleString()}
                                    <span className="mx-1">·</span>
                                    输入: {tokensUsage.inputTokens.toLocaleString()}
                                    <span className="mx-1">·</span>
                                    输出: {tokensUsage.outputTokens.toLocaleString()}
                                </p>
                            </div>
                        )}
                    </>
                ) : (
                    <EmptyState />
                )}
            </div>
        </div>
    );
};

export default AISummaryCard;
