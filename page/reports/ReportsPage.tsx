/**
 * Reports Page
 * 
 * 报告统计页面（开发中）
 */

import React from 'react';
import { FileBarChart, Download } from 'lucide-react';

const ReportsPage: React.FC = () => {
    return (
        <div className="max-w-7xl mx-auto animate-fade-in">
            {/* Page Header */}
            <header className="mb-8">
                <h1 className="text-3xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
                    <div className="p-2 bg-purple-50 rounded-xl text-purple-600">
                        <FileBarChart size={28} />
                    </div>
                    Reports
                </h1>
                <p className="text-slate-500 mt-2 font-medium">Generate and export detailed productivity reports.</p>
            </header>

            {/* Coming Soon Card */}
            <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-12 text-center">
                <div className="w-20 h-20 mx-auto mb-6 rounded-3xl bg-gradient-to-br from-purple-50 to-indigo-50 flex items-center justify-center">
                    <FileBarChart size={40} className="text-purple-500" />
                </div>
                <h2 className="text-2xl font-bold text-slate-800 mb-3">Reports Module Coming Soon</h2>
                <p className="text-slate-500 max-w-md mx-auto mb-8">
                    Generate comprehensive reports on your productivity patterns.
                    Export data in various formats for further analysis.
                </p>
                <div className="flex flex-wrap gap-4 justify-center">
                    <div className="px-4 py-2 bg-gray-50 rounded-xl border border-gray-100 text-sm text-slate-600">
                        📈 Weekly/Monthly Reports
                    </div>
                    <div className="px-4 py-2 bg-gray-50 rounded-xl border border-gray-100 text-sm text-slate-600">
                        📊 Category Analytics
                    </div>
                    <div className="px-4 py-2 bg-gray-50 rounded-xl border border-gray-100 text-sm text-slate-600">
                        💾 Export to PDF/CSV
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ReportsPage;
