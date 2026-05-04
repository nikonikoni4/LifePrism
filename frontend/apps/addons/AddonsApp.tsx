import React from 'react';
import { ExpandDirManager } from './components/ExpandDirManager';

interface AddonCard {
    id: string;
    name: string;
    description: string;
    icon: React.ReactNode;
}

const ADDON_CARDS: AddonCard[] = [
    {
        id: 'what-am-i-doing',
        name: 'What Am I Doing?',
        description: '桌面浮窗，随时查看当前活动状态',
        icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
            </svg>
        ),
    },
];

export const AddonsApp: React.FC = () => {
    const isElectron = !!window.electronAPI;

    const handleCardClick = (addonId: string) => {
        if (!isElectron) return;
        window.electronAPI!.openFloatingWindow(addonId);
    };

    return (
        <main className="min-h-screen bg-gradient-to-br from-emerald-50 to-teal-100 pt-20 px-6 pb-6">
            <div className="max-w-4xl mx-auto space-y-8">
                <div>
                    <h1 className="text-2xl font-bold text-emerald-900 mb-2">Add-ons</h1>
                    <p className="text-emerald-600/70 mb-8">扩展插件中心</p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {ADDON_CARDS.map((addon) => (
                            <button
                                key={addon.id}
                                onClick={() => handleCardClick(addon.id)}
                                disabled={!isElectron}
                                className={`
                                    group relative p-5 rounded-xl text-left transition-all duration-200
                                    ${isElectron
                                        ? 'bg-white hover:bg-emerald-50 hover:shadow-lg hover:shadow-emerald-500/10 cursor-pointer border border-emerald-100 hover:border-emerald-300'
                                        : 'bg-white/50 cursor-not-allowed border border-slate-200 opacity-60'
                                    }
                                `}
                            >
                                <div className={`w-12 h-12 rounded-lg flex items-center justify-center mb-3 ${
                                    isElectron
                                        ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white'
                                        : 'bg-slate-300 text-slate-500'
                                }`}>
                                    {addon.icon}
                                </div>
                                <h3 className={`font-semibold mb-1 ${isElectron ? 'text-slate-800' : 'text-slate-500'}`}>
                                    {addon.name}
                                </h3>
                                <p className={`text-sm ${isElectron ? 'text-slate-500' : 'text-slate-400'}`}>
                                    {addon.description}
                                </p>
                                {!isElectron && (
                                    <span className="absolute top-3 right-3 text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
                                        仅桌面版可用
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                </div>

                {/* 扩展数据文件夹管理 */}
                <ExpandDirManager />
            </div>
        </main>
    );
};
