/**
 * Settings Page
 * 
 * 设置页面（开发中）
 */

import React from 'react';
import { Settings, Bell, Palette, Database, Shield } from 'lucide-react';

const SettingsPage: React.FC = () => {
    return (
        <div className="max-w-7xl mx-auto animate-fade-in">
            {/* Page Header */}
            <header className="mb-8">
                <h1 className="text-3xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
                    <div className="p-2 bg-slate-100 rounded-xl text-slate-600">
                        <Settings size={28} />
                    </div>
                    Settings
                </h1>
                <p className="text-slate-500 mt-2 font-medium">Configure your LifeWatch AI preferences.</p>
            </header>

            {/* Coming Soon Card */}
            <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-12 text-center">
                <div className="w-20 h-20 mx-auto mb-6 rounded-3xl bg-gradient-to-br from-slate-50 to-gray-100 flex items-center justify-center">
                    <Settings size={40} className="text-slate-500" />
                </div>
                <h2 className="text-2xl font-bold text-slate-800 mb-3">Settings Module Coming Soon</h2>
                <p className="text-slate-500 max-w-md mx-auto mb-8">
                    Customize your experience with theme options, notification preferences,
                    data management, and API configuration.
                </p>
                <div className="flex flex-wrap gap-4 justify-center">
                    <div className="px-4 py-2 bg-gray-50 rounded-xl border border-gray-100 text-sm text-slate-600 flex items-center gap-2">
                        <Palette size={14} />
                        Theme & Display
                    </div>
                    <div className="px-4 py-2 bg-gray-50 rounded-xl border border-gray-100 text-sm text-slate-600 flex items-center gap-2">
                        <Bell size={14} />
                        Notifications
                    </div>
                    <div className="px-4 py-2 bg-gray-50 rounded-xl border border-gray-100 text-sm text-slate-600 flex items-center gap-2">
                        <Database size={14} />
                        Data & Sync
                    </div>
                    <div className="px-4 py-2 bg-gray-50 rounded-xl border border-gray-100 text-sm text-slate-600 flex items-center gap-2">
                        <Shield size={14} />
                        Privacy
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SettingsPage;
