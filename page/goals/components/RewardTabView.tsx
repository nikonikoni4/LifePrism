
import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Trophy, Plus, Gift, Target, X, Edit2 } from 'lucide-react';
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer
} from 'recharts';
import { MOCK_REWARDS, MOCK_GOALS_LIST } from '../api';
import { RewardRecord } from '../types';

interface RewardFormModalProps {
    isOpen: boolean;
    mode: 'add' | 'edit';
    initialData?: { goalId: string; content: string };
    goals: typeof MOCK_GOALS_LIST;
    onClose: () => void;
    onSave: (data: { goalId: string; content: string }) => void;
}

const RewardFormModal: React.FC<RewardFormModalProps> = ({
    isOpen,
    mode,
    initialData,
    goals,
    onClose,
    onSave
}) => {
    const [goalId, setGoalId] = useState('');
    const [content, setContent] = useState('');

    useEffect(() => {
        if (isOpen) {
            setGoalId(initialData?.goalId || '');
            setContent(initialData?.content || '');
        }
    }, [isOpen, initialData]);

    if (!isOpen) return null;

    return createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-md transition-opacity" onClick={onClose} />
            <div className="relative w-full max-w-2xl bg-white rounded-[2rem] shadow-2xl border border-white/50 p-8 md:p-10 animate-in zoom-in-95 duration-200">
                <div className="absolute top-6 right-6">
                    <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full text-slate-400 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <h3 className="text-xl font-bold text-slate-800 mb-8 flex items-center gap-2">
                    {mode === 'add' ? <Plus size={20} className="text-blue-500" /> : <Edit2 size={20} className="text-blue-500" />}
                    {mode === 'add' ? 'New Reward' : 'Edit Reward'}
                </h3>

                <div className="space-y-8">
                    <div>
                        <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">I want to treat myself to...</label>
                        <input
                            autoFocus
                            type="text"
                            value={content}
                            onChange={(e) => setContent(e.target.value)}
                            placeholder="e.g. A weekend trip to Kyoto"
                            className="w-full text-2xl md:text-3xl font-black text-slate-800 placeholder-slate-200 border-none outline-none bg-transparent border-b border-slate-100 pb-2 focus:border-blue-200 transition-colors"
                        />
                    </div>

                    <div>
                        <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">When I complete...</label>
                        <div className="relative">
                            <select
                                value={goalId}
                                onChange={(e) => setGoalId(e.target.value)}
                                className="w-full appearance-none bg-slate-50 border border-slate-200 text-slate-700 font-bold text-sm rounded-xl px-4 py-4 outline-none focus:ring-2 focus:ring-blue-100 cursor-pointer transition-all hover:bg-white hover:border-blue-200"
                            >
                                <option value="" disabled>Select a Goal</option>
                                {goals.map(g => (
                                    <option key={g.id} value={g.id}>{g.abstract || g.name}</option>
                                ))}
                            </select>
                            <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                                <Target size={16} />
                            </div>
                        </div>
                    </div>

                    <div className="flex justify-end pt-4">
                        <button
                            onClick={() => onSave({ goalId, content })}
                            disabled={!goalId || !content}
                            className="w-full md:w-auto px-10 py-4 bg-blue-600 text-white rounded-xl font-bold text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xl shadow-blue-200 hover:shadow-2xl hover:scale-[1.02] active:scale-95"
                        >
                            {mode === 'add' ? 'Create Reward' : 'Save Changes'}
                        </button>
                    </div>
                </div>
            </div>
        </div>,
        document.body
    );
};

const RewardTabView: React.FC = () => {
    const [rewards, setRewards] = useState<RewardRecord[]>(MOCK_REWARDS);
    const [formMode, setFormMode] = useState<'idle' | 'add' | 'edit'>('idle');
    const [editingIndex, setEditingIndex] = useState<number | null>(null);
    const [selectedRewardIndex, setSelectedRewardIndex] = useState(0);
    const [initialFormData, setInitialFormData] = useState<{ goalId: string; content: string }>({ goalId: '', content: '' });

    const handleAddNew = () => {
        setFormMode('add');
        setInitialFormData({ goalId: '', content: '' });
    };

    const handleEdit = (index: number, e: React.MouseEvent) => {
        e.stopPropagation();
        setFormMode('edit');
        setEditingIndex(index);
        setInitialFormData({
            goalId: rewards[index].goalId,
            content: rewards[index].rewardContent
        });
        setSelectedRewardIndex(index);
    };

    const handleSave = (data: { goalId: string; content: string }) => {
        if (formMode === 'add') {
            const mockHistory = [
                { date: 'Start', timeSpent: 0, todoCount: 0 },
                { date: 'Day 1', timeSpent: 30, todoCount: 1 },
                { date: 'Day 2', timeSpent: 45, todoCount: 2 },
                { date: 'Day 3', timeSpent: 120, todoCount: 5 },
            ];

            const newReward: RewardRecord = {
                goalId: data.goalId,
                rewardContent: data.content,
                history: mockHistory
            };

            setRewards([...rewards, newReward]);
            setSelectedRewardIndex(rewards.length);
        } else if (formMode === 'edit' && editingIndex !== null) {
            const updated = [...rewards];
            updated[editingIndex] = {
                ...updated[editingIndex],
                goalId: data.goalId,
                rewardContent: data.content
            };
            setRewards(updated);
        }

        setFormMode('idle');
        setEditingIndex(null);
    };

    const handleCloseForm = () => {
        setFormMode('idle');
        setEditingIndex(null);
    };

    const selectedReward = rewards[selectedRewardIndex];
    const selectedGoal = MOCK_GOALS_LIST.find(g => g.id === selectedReward?.goalId);

    return (
        <div className="space-y-8 animate-fade-in pb-20">
            {/* Header & Add Button */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
                <div>
                    <h3 className="text-3xl font-bold text-slate-800 tracking-tight">Rewards</h3>
                    <p className="text-slate-500 font-medium mt-1">Incentivize your progress.</p>
                </div>
                <button
                    onClick={handleAddNew}
                    className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-bold text-xs uppercase tracking-widest hover:bg-blue-700 transition-all shadow-lg shadow-blue-200 hover:shadow-blue-300"
                >
                    <Plus size={16} /> Add Reward
                </button>
            </div>

            {/* Extracted Modal Component */}
            <RewardFormModal
                isOpen={formMode !== 'idle'}
                mode={formMode === 'add' ? 'add' : 'edit'}
                initialData={initialFormData}
                goals={MOCK_GOALS_LIST}
                onClose={handleCloseForm}
                onSave={handleSave}
            />

            {/* Reward Cards List */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {rewards.map((reward, idx) => {
                    const goal = MOCK_GOALS_LIST.find(g => g.id === reward.goalId);
                    const isSelected = selectedRewardIndex === idx;

                    return (
                        <div
                            key={idx}
                            onClick={() => setSelectedRewardIndex(idx)}
                            className={`group relative p-6 rounded-[2rem] border cursor-pointer transition-all duration-300 ${isSelected
                                ? 'bg-[#EBF6FF] border-blue-200 shadow-xl scale-[1.02]'
                                : 'bg-white border-slate-200 hover:border-blue-200 hover:shadow-lg'
                                }`}
                        >
                            <div className="flex justify-between items-start mb-6">
                                <div className={`w-12 h-12 rounded-2xl flex items-center justify-center text-xl shadow-sm transition-colors ${isSelected ? 'bg-white text-blue-600' : 'bg-orange-50 text-orange-500'
                                    }`}>
                                    <Gift size={24} />
                                </div>

                                {/* Right aligned actions: Badge and Edit Button */}
                                <div className="flex items-center gap-2">
                                    {isSelected && <div className="px-3 py-1 bg-blue-200 text-blue-700 rounded-full text-[10px] font-bold uppercase tracking-wider">Active</div>}

                                    <button
                                        onClick={(e) => handleEdit(idx, e)}
                                        className={`p-2 rounded-full transition-all ${isSelected
                                            ? 'text-blue-400 hover:bg-white hover:text-blue-600'
                                            : 'text-slate-300 hover:bg-slate-100 hover:text-slate-600 opacity-0 group-hover:opacity-100'
                                            }`}
                                    >
                                        <Edit2 size={16} />
                                    </button>
                                </div>
                            </div>

                            <h4 className={`text-lg font-bold mb-2 leading-tight ${isSelected ? 'text-blue-900' : 'text-slate-800'}`}>
                                {reward.rewardContent}
                            </h4>
                            <div className={`flex items-center gap-2 text-xs font-medium ${isSelected ? 'text-blue-500' : 'text-slate-500'}`}>
                                <Target size={14} />
                                <span>{goal?.abstract || goal?.name || 'Unknown Goal'}</span>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Detail View (Chart) for Selected Reward */}
            {selectedReward && (
                <div className="mt-8 bg-white rounded-[2.5rem] p-8 md:p-12 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-8 gap-4">
                        <div>
                            <div className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-2">Momentum Tracker</div>
                            <h3 className="text-2xl font-bold text-slate-800 flex flex-wrap items-center gap-2">
                                {selectedReward.rewardContent}
                                <span className="text-slate-300">/</span>
                                <span className="text-blue-600 flex items-center gap-2">
                                    <Trophy size={20} />
                                    {selectedGoal?.name}
                                </span>
                            </h3>
                        </div>
                        <div className="flex items-center gap-3">
                            <div className="px-4 py-2 bg-green-50 text-green-700 rounded-xl font-bold text-xs border border-green-100 flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                                Tracking Active
                            </div>
                        </div>
                    </div>

                    <div className="h-[300px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={selectedReward.history}>
                                <defs>
                                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.2} />
                                        <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                                <XAxis
                                    dataKey="date"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: '#94A3B8', fontSize: 11, fontWeight: 600 }}
                                    dy={10}
                                />
                                <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: '#94A3B8', fontSize: 11, fontWeight: 600 }}
                                />
                                <Tooltip
                                    contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)', backgroundColor: '#FFFFFF' }}
                                    itemStyle={{ fontWeight: 600, fontSize: '13px', color: '#1E293B' }}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="timeSpent"
                                    name="Effort (min)"
                                    stroke="#3B82F6"
                                    strokeWidth={3}
                                    fillOpacity={1}
                                    fill="url(#colorValue)"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}
        </div>
    );
};

export default RewardTabView;
