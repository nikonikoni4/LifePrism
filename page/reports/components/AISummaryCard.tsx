/**
 * AI Summary Card Component
 * 
 * AI 智能总结卡片组件
 */

import React from 'react';
import { Sparkles } from 'lucide-react';
import { MarkdownRenderer } from '../../common';

interface AISummaryCardProps {
    title?: string;
    content: string;
    className?: string;
}

const AISummaryCard: React.FC<AISummaryCardProps> = ({
    title = 'AI 智能总结',
    content,
    className = ''
}) => {
    return (
        <div className={`bg-white rounded-2xl shadow-sm border border-gray-100 p-6 ${className}`}>
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-gradient-to-br from-purple-50 to-indigo-50 text-purple-500 rounded-xl">
                    <Sparkles size={18} />
                </div>
                <h3 className="text-base font-bold text-slate-800">{title}</h3>
            </div>

            {/* Content using shared MarkdownRenderer */}
            <div className="text-sm text-slate-600 leading-relaxed">
                <MarkdownRenderer content={content} />
            </div>
        </div>
    );
};

export default AISummaryCard;
