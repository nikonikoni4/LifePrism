
import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Trophy, Plus, Gift, Target, X, Edit2, Trash2, Loader2, Calendar, Clock } from 'lucide-react';
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Line,
    ComposedChart,
    Bar
} from 'recharts';
import { rewardApi, goalApi } from '../api';
import { RewardItem, RewardStatsResponse, RewardHistoryPoint, ActiveGoalNamesResponse } from '../types';

interface ActiveGoalItem {
    id: string;
    name: string;
}

interface RewardFormModalProps {
    isOpen: boolean;
    mode: 'add' | 'edit';
    initialData?: { goalId: string; name: string; startTime: string; targetHours: number };
    goals: ActiveGoalItem[];
    onClose: () => void;
    onSave: (data: { goalId: string; name: string; startTime: string; targetHours: number }) => void;
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
    const [name, setName] = useState('');
    const [startTime, setStartTime] = useState('');
    const [targetHours, setTargetHours] = useState(0);

    useEffect(() => {
        if (isOpen) {
            setGoalId(initialData?.goalId || '');
            setName(initialData?.name || '');
            setStartTime(initialData?.startTime || new Date().toISOString().split('T')[0]);
            setTargetHours(initialData?.targetHours || 0);
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

                <div className="space-y-6">
                    <div>
                        <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">I want to treat myself to...</label>
                        <input
                            autoFocus
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
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
                                    <option key={g.id} value={g.id}>{g.name}</option>
                                ))}
                            </select>
                            <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                                <Target size={16} />
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                                <Calendar size={12} />
                                Start Date
                            </label>
                            <input
                                type="date"
                                value={startTime}
                                onChange={(e) => setStartTime(e.target.value)}
                                className="w-full bg-slate-50 border border-slate-200 text-slate-700 font-bold text-sm rounded-xl px-4 py-4 outline-none focus:ring-2 focus:ring-blue-100 transition-all hover:bg-white hover:border-blue-200"
                            />
                        </div>
                        <div>
                            <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                                <Clock size={12} />
                                Target Hours
                            </label>
                            <input
                                type="number"
                                min="0"
                                value={targetHours}
                                onChange={(e) => setTargetHours(parseInt(e.target.value) || 0)}
                                placeholder="e.g. 100"
                                className="w-full bg-slate-50 border border-slate-200 text-slate-700 font-bold text-sm rounded-xl px-4 py-4 outline-none focus:ring-2 focus:ring-blue-100 transition-all hover:bg-white hover:border-blue-200"
                            />
                        </div>
                    </div>

                    <div className="flex justify-end pt-4">
                        <button
                            onClick={() => onSave({ goalId, name, startTime, targetHours })}
                            disabled={!goalId || !name || !startTime}
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
    // State
    const [rewards, setRewards] = useState<RewardItem[]>([]);
    const [goals, setGoals] = useState<ActiveGoalItem[]>([]);
    const [selectedRewardId, setSelectedRewardId] = useState<number | null>(null);
    const [selectedStats, setSelectedStats] = useState<RewardStatsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [statsLoading, setStatsLoading] = useState(false);

    // Form state
    const [formMode, setFormMode] = useState<'idle' | 'add' | 'edit'>('idle');
    const [editingReward, setEditingReward] = useState<RewardItem | null>(null);
    const [initialFormData, setInitialFormData] = useState<{ goalId: string; name: string; startTime: string; targetHours: number }>({ goalId: '', name: '', startTime: '', targetHours: 0 });

    // Load rewards and goals
    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            const [rewardsData, goalsResponse] = await Promise.all([
                rewardApi.getRewards(),
                goalApi.getActiveGoalNames()
            ]);
            setRewards(rewardsData);
            setGoals(goalsResponse.items || []);

            // Auto-select first reward
            if (rewardsData.length > 0 && !selectedRewardId) {
                setSelectedRewardId(rewardsData[0].id);
            }
        } catch (error) {
            console.error('Failed to load rewards:', error);
        } finally {
            setLoading(false);
        }
    }, [selectedRewardId]);

    // Load stats when selected reward changes
    const loadStats = useCallback(async (rewardId: number) => {
        setStatsLoading(true);
        try {
            const stats = await rewardApi.getRewardStats(rewardId);
            setSelectedStats(stats);
        } catch (error) {
            console.error('Failed to load reward stats:', error);
            setSelectedStats(null);
        } finally {
            setStatsLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
    }, []);

    useEffect(() => {
        if (selectedRewardId) {
            loadStats(selectedRewardId);
        }
    }, [selectedRewardId, loadStats]);

    // Handlers
    const handleAddNew = () => {
        setFormMode('add');
        setEditingReward(null);
        setInitialFormData({ goalId: '', name: '', startTime: new Date().toISOString().split('T')[0], targetHours: 0 });
    };

    const handleEdit = (reward: RewardItem, e: React.MouseEvent) => {
        e.stopPropagation();
        setFormMode('edit');
        setEditingReward(reward);
        setInitialFormData({
            goalId: reward.goalId,
            name: reward.name,
            startTime: reward.startTime,
            targetHours: reward.targetHours
        });
    };

    const handleDelete = async (reward: RewardItem, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm(`Delete reward "${reward.name}"?`)) return;

        try {
            await rewardApi.deleteReward(reward.id);
            setRewards(prev => prev.filter(r => r.id !== reward.id));
            if (selectedRewardId === reward.id) {
                setSelectedRewardId(null);
                setSelectedStats(null);
            }
        } catch (error) {
            console.error('Failed to delete reward:', error);
        }
    };

    const handleSave = async (data: { goalId: string; name: string; startTime: string; targetHours: number }) => {
        try {
            if (formMode === 'add') {
                const newReward = await rewardApi.createReward({
                    goalId: data.goalId,
                    name: data.name,
                    startTime: data.startTime,
                    targetHours: data.targetHours
                });
                setRewards(prev => [...prev, newReward]);
                setSelectedRewardId(newReward.id);
            } else if (formMode === 'edit' && editingReward) {
                const updated = await rewardApi.updateReward(editingReward.id, {
                    goalId: data.goalId,
                    name: data.name,
                    startTime: data.startTime,
                    targetHours: data.targetHours
                });
                setRewards(prev => prev.map(r => r.id === updated.id ? updated : r));
            }
        } catch (error) {
            console.error('Failed to save reward:', error);
        }

        setFormMode('idle');
        setEditingReward(null);
    };

    const handleCloseForm = () => {
        setFormMode('idle');
        setEditingReward(null);
    };

    const selectedReward = rewards.find(r => r.id === selectedRewardId);
    const selectedGoal = goals.find(g => g.id === selectedReward?.goalId);

    // Prepare chart data (convert minutes to hours)
    const chartData = selectedStats?.history.map(point => ({
        date: point.date,
        timeSpent: +(point.cumulativeTimeSpent / 60).toFixed(1),  // Convert to hours
        todoCount: point.cumulativeTodoCount
    })) || [];

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
        );
    }

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
                goals={goals}
                onClose={handleCloseForm}
                onSave={handleSave}
            />

            {/* Empty State */}
            {rewards.length === 0 && (
                <div className="text-center py-16">
                    <Gift size={48} className="mx-auto text-slate-300 mb-4" />
                    <h4 className="text-lg font-bold text-slate-600 mb-2">No rewards yet</h4>
                    <p className="text-slate-400">Create a reward to motivate yourself!</p>
                </div>
            )}

            {/* Reward Cards List */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {rewards.map((reward) => {
                    const goal = goals.find(g => g.id === reward.goalId);
                    const isSelected = selectedRewardId === reward.id;

                    return (
                        <div
                            key={reward.id}
                            onClick={() => setSelectedRewardId(reward.id)}
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

                                {/* Right aligned actions: Badge and Edit/Delete Buttons */}
                                <div className="flex items-center gap-2">
                                    {isSelected && <div className="px-3 py-1 bg-blue-200 text-blue-700 rounded-full text-[10px] font-bold uppercase tracking-wider">Active</div>}

                                    <button
                                        onClick={(e) => handleEdit(reward, e)}
                                        className={`p-2 rounded-full transition-all ${isSelected
                                            ? 'text-blue-400 hover:bg-white hover:text-blue-600'
                                            : 'text-slate-300 hover:bg-slate-100 hover:text-slate-600 opacity-0 group-hover:opacity-100'
                                            }`}
                                    >
                                        <Edit2 size={16} />
                                    </button>
                                    <button
                                        onClick={(e) => handleDelete(reward, e)}
                                        className={`p-2 rounded-full transition-all ${isSelected
                                            ? 'text-red-400 hover:bg-white hover:text-red-600'
                                            : 'text-slate-300 hover:bg-slate-100 hover:text-red-500 opacity-0 group-hover:opacity-100'
                                            }`}
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </div>
                            </div>

                            <h4 className={`text-lg font-bold mb-2 leading-tight ${isSelected ? 'text-blue-900' : 'text-slate-800'}`}>
                                {reward.name}
                            </h4>
                            <div className={`flex items-center gap-2 text-xs font-medium ${isSelected ? 'text-blue-500' : 'text-slate-500'}`}>
                                <Target size={14} />
                                <span>{goal?.name || 'Unknown Goal'}</span>
                            </div>

                            {/* Start Time and Target Hours Display */}
                            <div className={`mt-4 pt-4 border-t ${isSelected ? 'border-blue-200' : 'border-slate-100'} flex flex-wrap gap-4`}>
                                <div className={`flex items-center gap-1.5 text-xs ${isSelected ? 'text-blue-500' : 'text-slate-400'}`}>
                                    <Calendar size={12} />
                                    <span>{reward.startTime}</span>
                                </div>
                                {reward.targetHours > 0 && (
                                    <div className={`flex items-center gap-1.5 text-xs ${isSelected ? 'text-blue-500' : 'text-slate-400'}`}>
                                        <Clock size={12} />
                                        <span>{reward.targetHours}h target</span>
                                    </div>
                                )}
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
                                {selectedReward.name}
                                <span className="text-slate-300">/</span>
                                <span className="text-blue-600 flex items-center gap-2">
                                    <Trophy size={20} />
                                    {selectedStats?.goalName || selectedGoal?.name}
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

                    {statsLoading ? (
                        <div className="flex items-center justify-center h-[300px]">
                            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                        </div>
                    ) : chartData.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-[300px] text-slate-400">
                            <Target size={48} className="mb-4 opacity-50" />
                            <p className="font-medium">No tracking data yet</p>
                            <p className="text-sm">Complete tasks linked to this goal to see progress</p>
                        </div>
                    ) : (
                        <div className="h-[300px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <ComposedChart data={chartData}>
                                    <defs>
                                        <linearGradient id="colorTimeSpent" x1="0" y1="0" x2="0" y2="1">
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
                                        yAxisId="left"
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fill: '#94A3B8', fontSize: 11, fontWeight: 600 }}
                                        label={{ value: 'Hours', angle: -90, position: 'insideLeft', fill: '#94A3B8', fontSize: 10 }}
                                    />
                                    <YAxis
                                        yAxisId="right"
                                        orientation="right"
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fill: '#10B981', fontSize: 11, fontWeight: 600 }}
                                        label={{ value: 'Todos', angle: 90, position: 'insideRight', fill: '#10B981', fontSize: 10 }}
                                    />
                                    <Tooltip
                                        contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)', backgroundColor: '#FFFFFF' }}
                                        itemStyle={{ fontWeight: 600, fontSize: '13px' }}
                                        formatter={(value: number, name: string) => {
                                            if (name === 'timeSpent') return [`${value}h`, 'Time Spent'];
                                            if (name === 'todoCount') return [value, 'Todos Completed'];
                                            return [value, name];
                                        }}
                                    />
                                    <Area
                                        yAxisId="left"
                                        type="monotone"
                                        dataKey="timeSpent"
                                        name="timeSpent"
                                        stroke="#3B82F6"
                                        strokeWidth={3}
                                        fillOpacity={1}
                                        fill="url(#colorTimeSpent)"
                                    />
                                    <Line
                                        yAxisId="right"
                                        type="monotone"
                                        dataKey="todoCount"
                                        name="todoCount"
                                        stroke="#10B981"
                                        strokeWidth={2}
                                        dot={{ fill: '#10B981', strokeWidth: 2, r: 4 }}
                                    />
                                </ComposedChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default RewardTabView;
