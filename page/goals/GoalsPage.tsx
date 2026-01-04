
import React, { useState, useEffect } from 'react';
import { Edit2 } from 'lucide-react';
import TodoTabView from './components/TodoTabView';
import PlanTabView from './components/PlanTabView';
import GoalTabView from './components/GoalTabView';
import GoalDetailView from './components/GoalDetailView';
import RewardTabView from './components/RewardTabView';
import BeingTabView from './components/BeingTabView';
import { UserGoal } from './types';

type TabType = 'todo' | 'plan' | 'goal' | 'reward' | 'being';

const GoalsPage: React.FC = () => {
    const [activeTab, setActiveTab] = useState<TabType>('todo');
    const [slogan, setSlogan] = useState("Build a life you don't need a vacation from.");
    const [isEditingSlogan, setIsEditingSlogan] = useState(false);
    const [greeting, setGreeting] = useState('');

    // State for handling Goal Detail View - now uses number ID
    const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);

    // State for navigating to TodoTabView with a specific date
    const [todoInitialDate, setTodoInitialDate] = useState<string | null>(null);

    useEffect(() => {
        const hour = new Date().getHours();
        if (hour < 12) setGreeting('Good Morning');
        else if (hour < 18) setGreeting('Good Afternoon');
        else setGreeting('Good Evening');
    }, []);

    // When switching tabs, clear the selected goal to reset view
    const handleTabChange = (tab: TabType) => {
        setActiveTab(tab);
        setSelectedGoalId(null);
        // Clear the initial date when manually switching tabs
        if (tab !== 'todo') {
            setTodoInitialDate(null);
        }
    };

    // Navigate to TodoTabView with a specific date
    const handleNavigateToTodoWithDate = (date: string) => {
        setTodoInitialDate(date);
        setActiveTab('todo');
    };

    const handleSaveGoal = (updatedGoal: UserGoal) => {
        console.log("Goal saved:", updatedGoal);
        setSelectedGoalId(null); // Return to list after save
    };

    const tabs = [
        { id: 'todo', label: 'To do list' },
        { id: 'plan', label: 'Plan' },
        { id: 'goal', label: 'Goal' },
        { id: 'reward', label: 'Reward' },
        { id: 'being', label: 'Being' },
    ];

    return (
        <div className="fixed inset-0 lg:left-64 flex flex-col animate-fade-in bg-[#F1F5F9] overflow-hidden">
            {/* 1. Top Header Section (White Desk Surface) */}
            <header className="bg-white border-b border-slate-200 px-10 pt-6 pb-0 z-20 shadow-sm shrink-0">
                <div className="mb-3 flex flex-col items-start gap-1">
                    <h1 className="text-3xl font-bold text-slate-800 tracking-tight">
                        {greeting}, Alex
                    </h1>
                    <div className="flex items-center gap-2 group min-h-[24px]">
                        {isEditingSlogan ? (
                            <input
                                autoFocus
                                type="text"
                                value={slogan}
                                onChange={(e) => setSlogan(e.target.value)}
                                onBlur={() => setIsEditingSlogan(false)}
                                onKeyDown={(e) => e.key === 'Enter' && setIsEditingSlogan(false)}
                                className="bg-transparent border-none focus:ring-0 text-slate-500 font-medium italic text-base p-0 placeholder-slate-300 w-full"
                            />
                        ) : (
                            <>
                                <p className="text-base text-slate-500 font-medium italic">
                                    "{slogan}"
                                </p>
                                <button
                                    onClick={() => setIsEditingSlogan(true)}
                                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-50 rounded-md transition-all"
                                >
                                    <Edit2 size={12} className="text-slate-400" />
                                </button>
                            </>
                        )}
                    </div>
                </div>

                {/* Minimal Tabs inside White Header */}
                <div className="flex gap-10">
                    {tabs.map((tab) => {
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => handleTabChange(tab.id as TabType)}
                                className={`py-2 text-xs font-bold uppercase tracking-widest transition-all relative ${isActive
                                    ? 'text-blue-600'
                                    : 'text-slate-400 hover:text-slate-600'
                                    }`}
                            >
                                {tab.label}
                                {isActive && (
                                    <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-blue-600 rounded-full animate-fade-in" />
                                )}
                            </button>
                        );
                    })}
                </div>
            </header>

            {/* 2. Main Body Content Area */}
            <main className="flex-1 flex min-h-0 overflow-hidden">
                {activeTab === 'todo' && (
                    <TodoTabView
                        initialDate={todoInitialDate}
                        onDateUsed={() => setTodoInitialDate(null)}
                    />
                )}
                {activeTab === 'plan' && (
                    <PlanTabView
                        onNavigateToTodo={handleNavigateToTodoWithDate}
                    />
                )}

                {/* Being Tab - Full width without container constraints */}
                {activeTab === 'being' && <BeingTabView />}

                {/* Other tabs with container constraints */}
                {activeTab !== 'todo' && activeTab !== 'plan' && activeTab !== 'being' && (
                    <div className="flex-1 overflow-y-auto p-0 no-scrollbar">
                        <div className="max-w-6xl mx-auto p-2 h-full">
                            {/* Goal Tab Logic: Toggle between List and Detail */}
                            {activeTab === 'goal' && (
                                selectedGoalId !== null ? (
                                    <GoalDetailView
                                        goalId={selectedGoalId}
                                        onBack={() => setSelectedGoalId(null)}
                                        onSave={handleSaveGoal}
                                    />
                                ) : (
                                    <GoalTabView onSelectGoal={setSelectedGoalId} />
                                )
                            )}

                            {activeTab === 'reward' && <RewardTabView />}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
};

export default GoalsPage;
