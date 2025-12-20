/**
 * Goals Page
 * 
 * 目标管理页面（开发中）
 */

import React from 'react';
import { Target, Plus } from 'lucide-react';

const GoalsPage: React.FC = () => {
    return (
        <div className="max-w-7xl mx-auto animate-fade-in">
            {/* Page Header */}
            <header className="mb-8">
                <h1 className="text-3xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
                    <div className="p-2 bg-green-50 rounded-xl text-green-600">
                        <Target size={28} />
                    </div>
                    Goals
                </h1>
                <p className="text-slate-500 mt-2 font-medium">Set and track your productivity goals.</p>
            </header>

            {/* Coming Soon Card */}
            <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-12 text-center">
                <div className="w-20 h-20 mx-auto mb-6 rounded-3xl bg-gradient-to-br from-green-50 to-emerald-50 flex items-center justify-center">
                    <Target size={40} className="text-green-500" />
                </div>
                <h2 className="text-2xl font-bold text-slate-800 mb-3">Goals Module Coming Soon</h2>
                <p className="text-slate-500 max-w-md mx-auto mb-8">
                    Track your daily, weekly, and monthly productivity goals.
                    Link activities to goals and visualize your progress.
                </p>
                <div className="flex flex-wrap gap-4 justify-center">
                    <div className="px-4 py-2 bg-gray-50 rounded-xl border border-gray-100 text-sm text-slate-600">
                        📊 Goal Progress Tracking
                    </div>
                    <div className="px-4 py-2 bg-gray-50 rounded-xl border border-gray-100 text-sm text-slate-600">
                        🎯 Category-linked Goals
                    </div>
                    <div className="px-4 py-2 bg-gray-50 rounded-xl border border-gray-100 text-sm text-slate-600">
                        📅 Daily/Weekly/Monthly Views
                    </div>
                </div>
            </div>
        </div>
    );
};

export default GoalsPage;
