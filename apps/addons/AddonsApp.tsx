import React from 'react';

export const AddonsApp: React.FC = () => {
    return (
        <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-emerald-50 to-teal-100">
            <div className="text-center">
                <div className="w-24 h-24 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-2xl shadow-emerald-500/30">
                    <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" className="w-12 h-12">
                        <rect x="3" y="3" width="7" height="7" rx="1" />
                        <rect x="14" y="3" width="7" height="7" rx="1" />
                        <rect x="3" y="14" width="7" height="7" rx="1" />
                        <path d="M17.5 14v7" />
                        <path d="M14 17.5h7" />
                    </svg>
                </div>
                <h1 className="text-4xl font-bold text-emerald-900 mb-3">Add-ons</h1>
                <p className="text-emerald-600/70 text-lg">扩展插件中心</p>
                <p className="text-emerald-500/50 text-sm mt-4">即将推出...</p>
            </div>
        </main>
    );
};
