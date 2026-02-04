import React from 'react';

export const MindSpaceApp: React.FC = () => {
    return (
        <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
            <div className="text-center">
                <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-pink-500 to-purple-600 flex items-center justify-center shadow-2xl shadow-purple-500/30">
                    <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" className="w-12 h-12">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" />
                        <path d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4z" />
                    </svg>
                </div>
                <h1 className="text-4xl font-bold text-white mb-3">MindSpace</h1>
                <p className="text-purple-200/70 text-lg">心理与情绪空间</p>
                <p className="text-purple-300/50 text-sm mt-4">即将推出...</p>
            </div>
        </main>
    );
};
