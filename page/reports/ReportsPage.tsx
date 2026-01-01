/**
 * Reports Page
 * 
 * 报告统计页面 - 提供每日、每周、每月总结
 */

import React, { useState } from 'react';
import { FileBarChart } from 'lucide-react';
import DailyReviewTab from './components/DailyReviewTab';
import WeeklyReviewTab from './components/WeeklyReviewTab';
import MonthlyReviewTab from './components/MonthlyReviewTab';
import { ReportTabType } from './types';

const ReportsPage: React.FC = () => {
    const [activeTab, setActiveTab] = useState<ReportTabType>('daily');

    const tabs = [
        { id: 'daily' as ReportTabType, label: '每日总结', emoji: '📅' },
        { id: 'weekly' as ReportTabType, label: '每周总结', emoji: '📊' },
        { id: 'monthly' as ReportTabType, label: '每月总结', emoji: '📈' },
    ];

    return (
        <div className="fixed inset-0 lg:left-64 flex flex-col animate-fade-in bg-[#F1F5F9] overflow-hidden">
            {/* Header */}
            <header className="bg-white border-b border-slate-200 px-10 pt-6 pb-0 z-20 shadow-sm shrink-0">
                <div className="mb-3 flex items-center gap-4">
                    <div className="p-2.5 bg-gradient-to-br from-purple-50 to-indigo-50 rounded-xl text-purple-600">
                        <FileBarChart size={28} />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                            Reports
                        </h1>
                        <p className="text-slate-500 text-sm font-medium">
                            回顾你的时间投资，发现效率规律
                        </p>
                    </div>
                </div>

                {/* Tab Navigation */}
                <div className="flex gap-10">
                    {tabs.map((tab) => {
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`py-2 text-xs font-bold uppercase tracking-widest transition-all relative flex items-center gap-2 ${isActive
                                        ? 'text-purple-600'
                                        : 'text-slate-400 hover:text-slate-600'
                                    }`}
                            >
                                <span>{tab.emoji}</span>
                                {tab.label}
                                {isActive && (
                                    <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-purple-600 rounded-full animate-fade-in" />
                                )}
                            </button>
                        );
                    })}
                </div>
            </header>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto p-6 no-scrollbar">
                <div className="max-w-7xl mx-auto">
                    {activeTab === 'daily' && <DailyReviewTab />}
                    {activeTab === 'weekly' && <WeeklyReviewTab />}
                    {activeTab === 'monthly' && <MonthlyReviewTab />}
                </div>
            </main>
        </div>
    );
};

export default ReportsPage;
