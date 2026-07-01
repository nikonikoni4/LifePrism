/**
 * AI Summary Card Component
 * 
 * AI 总结卡片组件，支持日报/周报/月报的 AI 总结生成
 */

import React, { useState, useEffect } from 'react';
import { Sparkles } from 'lucide-react';
import { MarkdownRenderer } from '../../../../../core/components';

// 报告类型
type ReportType = 'daily' | 'weekly' | 'monthly';

interface AISummaryCardProps {
    title?: string;
    content?: string;
    reportType: ReportType;
    className?: string;
}

const AISummaryCard: React.FC<AISummaryCardProps> = ({
    title = 'AI 总结',
    content: initialContent = '',
    reportType,
    className = '',
}) => {
    const [content, setContent] = useState(initialContent);

    // 当外部传入的 content 变化时，同步更新内部状态
    useEffect(() => {
        setContent(initialContent);
    }, [initialContent]);

    // 空状态
    const EmptyState = () => (
        <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="p-4 bg-gradient-to-br from-purple-50 to-indigo-50 rounded-2xl mb-4">
                <Sparkles className="w-8 h-8 text-purple-500" />
            </div>
            <h4 className="text-sm font-medium text-slate-700 mb-2">
                暂无 AI 总结
            </h4>
            <p className="text-xs text-slate-500">
                {reportType === 'daily'
                    ? 'AI 总结每天 10:00 自动更新，请稍后查看'
                    : '暂无 AI 总结数据'}
            </p>
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

                {/* 有内容时显示更新提示 */}
                {content && (
                    <span className="text-xs text-slate-400">
                        每天 10:00 自动更新
                    </span>
                )}
            </div>

            {/* Content */}
            <div className="text-sm text-slate-600 leading-relaxed">
                {content ? (
                    <MarkdownRenderer content={content} />
                ) : (
                    <EmptyState />
                )}
            </div>
        </div>
    );
};

export default AISummaryCard;

