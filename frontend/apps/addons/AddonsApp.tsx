import React, { useState } from 'react';
import { ExpandDirManager } from './components/ExpandDirManager';
import { FolderOpen } from 'lucide-react';

interface AddonCard {
    id: string;
    name: string;
    description: string;
    icon: React.ReactNode;
    type: 'floating-window' | 'modal';
}

const ADDON_CARDS: AddonCard[] = [
    {
        id: 'what-am-i-doing',
        name: 'What Am I Doing?',
        description: '桌面浮窗，随时查看当前活动状态',
        type: 'floating-window',
        icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
            </svg>
        ),
    },
    {
        id: 'expand-dir-manager',
        name: '扩展数据文件夹',
        description: '管理额外的数据文件夹，用于 AI 索引',
        type: 'modal',
        icon: <FolderOpen className="w-8 h-8" />,
    },
];

export const AddonsApp: React.FC = () => {
    const isElectron = !!window.electronAPI;
    const [showExpandDirModal, setShowExpandDirModal] = useState(false);

    const handleCardClick = (addon: AddonCard) => {
        if (addon.type === 'floating-window') {
            if (!isElectron) return;
            window.electronAPI!.openFloatingWindow(addon.id);
        } else if (addon.type === 'modal') {
            if (addon.id === 'expand-dir-manager') {
                setShowExpandDirModal(true);
            }
        }
    };

    return (
        <main className="min-h-screen bg-gradient-to-br from-emerald-50 to-teal-100 pt-20 px-6 pb-6">
            <div className="max-w-4xl mx-auto space-y-8">
                <div>
                    <h1 className="text-2xl font-bold text-emerald-900 mb-2">Add-ons</h1>
                    <p className="text-emerald-600/70 mb-8">扩展插件中心</p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {ADDON_CARDS.map((addon) => {
                            const isDisabled = addon.type === 'floating-window' && !isElectron;
                            return (
                                <button
                                    key={addon.id}
                                    onClick={() => handleCardClick(addon)}
                                    disabled={isDisabled}
                                    className={`
                                        group relative p-5 rounded-xl text-left transition-all duration-200
                                        ${!isDisabled
                                            ? 'bg-white hover:bg-emerald-50 hover:shadow-lg hover:shadow-emerald-500/10 cursor-pointer border border-emerald-100 hover:border-emerald-300'
                                            : 'bg-white/50 cursor-not-allowed border border-slate-200 opacity-60'
                                        }
                                    `}
                                >
                                    <div className={`w-12 h-12 rounded-lg flex items-center justify-center mb-3 ${
                                        !isDisabled
                                            ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white'
                                            : 'bg-slate-300 text-slate-500'
                                    }`}>
                                        {addon.icon}
                                    </div>
                                    <h3 className={`font-semibold mb-1 ${!isDisabled ? 'text-slate-800' : 'text-slate-500'}`}>
                                        {addon.name}
                                    </h3>
                                    <p className={`text-sm ${!isDisabled ? 'text-slate-500' : 'text-slate-400'}`}>
                                        {addon.description}
                                    </p>
                                    {isDisabled && (
                                        <span className="absolute top-3 right-3 text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
                                            仅桌面版可用
                                        </span>
                                    )}
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* 扩展数据文件夹管理弹窗 */}
                {showExpandDirModal && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                        <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
                            <div className="flex items-center justify-between p-6 border-b border-gray-100">
                                <h2 className="text-xl font-bold text-slate-800">扩展数据文件夹管理</h2>
                                <button
                                    onClick={() => setShowExpandDirModal(false)}
                                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                                >
                                    <svg className="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                            <div className="flex-1 overflow-y-auto p-6">
                                <ExpandDirManager />
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </main>
    );
};
