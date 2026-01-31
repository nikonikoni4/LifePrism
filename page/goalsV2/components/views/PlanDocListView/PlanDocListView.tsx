import React, { useState, useEffect } from 'react';
import { useGoalPageContext } from '../../../context/GoalPageContext';
import { useGoalStore } from '../../../hooks/useGoalStore';
import { usePlanDocStore } from '../../../hooks/usePlanDocStore';
import { PlanDoc } from '../../../types';
import { Plus, ChevronDown, FileText, Target, MoreVertical, Trash2, Copy, Archive } from 'lucide-react';
import { PlanDocEditorView } from './components/PlanDocEditorView/PlanDocEditorView';
import { DropdownMenu, DropdownItem } from '../../shared/components/DropdownMenu';
import { viewBackground } from '../../shared/backgroundStyles';

export const PlanDocListView: React.FC = () => {
    const { selectedGoalId, setSelectedGoalId, selectedPlanDocId, setSelectedPlanDocId } = useGoalPageContext();
    const { goals } = useGoalStore();
    const { planDocs, addPlanDoc, updatePlanDoc, deletePlanDoc } = usePlanDocStore();

    // Local content state for editing to avoid laggy context updates on every keystroke
    const [localContent, setLocalContent] = useState('');

    // Derived
    const selectedGoal = goals.find(g => g.id === selectedGoalId) || null;
    const goalDocs = planDocs.filter(d => d.goalId === selectedGoalId);
    const selectedDoc = goalDocs.find(d => d.id === selectedPlanDocId) || null;

    // Effects
    // Select first doc when goal changes or if current selection invalid
    useEffect(() => {
        if (selectedGoalId && goalDocs.length > 0) {
            // If no doc selected, or selected doc is not in current goal list, select first
            if (!selectedPlanDocId || !goalDocs.find(d => d.id === selectedPlanDocId)) {
                setSelectedPlanDocId(goalDocs[0].id);
            }
        } else if (!selectedGoalId) {
            setSelectedPlanDocId(null);
        }
    }, [selectedGoalId, goalDocs, selectedPlanDocId, setSelectedPlanDocId]);

    // Sync local content when doc changes
    useEffect(() => {
        if (selectedDoc) {
            setLocalContent(selectedDoc.content);
        } else {
            setLocalContent('');
        }
    }, [selectedDoc?.id]); // Only when ID changes

    const handleContentChange = (newContent: string) => {
        setLocalContent(newContent);

        // Auto-save immediately to store for now
        if (selectedDoc) {
            updatePlanDoc({ ...selectedDoc, content: newContent, updatedAt: new Date().toISOString() });
        }
    };

    const handleCreateDoc = () => {
        if (!selectedGoalId) {
            alert("Please select a goal first.");
            return;
        }
        const newDoc: PlanDoc = {
            id: Date.now().toString(),
            goalId: selectedGoalId,
            title: `Untitled Plan ${goalDocs.length + 1}`,
            content: '# New Plan\n',
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            status: 'active'
        };
        addPlanDoc(newDoc);
        setSelectedPlanDocId(newDoc.id);
    };

    const handleDeleteDoc = () => {
        if (selectedPlanDocId) {
            if (confirm('Are you sure you want to delete this plan?')) {
                deletePlanDoc(selectedPlanDocId);
                setSelectedPlanDocId(null);
            }
        }
    };

    if (goals.length === 0) {
        return (
            <div className="flex-1 flex items-center justify-center text-slate-400">
                No goals available. Create a goal first.
            </div>
        );
    }

    // --- Dropdown Items Configuration ---

    const goalMenuItems: DropdownItem[] = goals.map(g => ({
        id: g.id,
        label: g.title,
        onClick: () => setSelectedGoalId(g.id)
    }));

    const planMenuItems: DropdownItem[] = goalDocs.length > 0
        ? goalDocs.map(d => ({
            id: d.id,
            label: d.title,
            onClick: () => setSelectedPlanDocId(d.id)
        }))
        : [{ id: 'empty', label: 'No plans yet', onClick: () => { }, disabled: true }];

    const actionMenuItems: DropdownItem[] = [
        {
            id: 'duplicate',
            label: 'Duplicate Plan',
            icon: <Copy size={14} />,
            onClick: () => console.log('Duplicate (Mock)'),
            disabled: !selectedPlanDocId
        },
        {
            id: 'archive',
            label: 'Archive Plan',
            icon: <Archive size={14} />,
            onClick: () => console.log('Archive (Mock)'),
            disabled: !selectedPlanDocId
        },
        {
            id: 'delete',
            label: 'Delete Plan',
            icon: <Trash2 size={14} />,
            variant: 'danger',
            divider: true,
            onClick: handleDeleteDoc,
            disabled: !selectedPlanDocId
        }
    ];

    return (
        <div className={`flex flex-col h-full backdrop-blur-sm relative ${viewBackground.className}`} style={viewBackground.style}>
            {/* Toolbar / Header */}
            <div className="h-16 flex items-center justify-between px-6 border-b border-white/60 bg-white/40 shrink-0 gap-4 relative z-20">
                <div className="flex items-center gap-4 flex-1 min-w-0">
                    {/* Goal Selector */}
                    <div className="relative group min-w-[140px] max-w-[240px] shrink-0">
                        <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-widest mb-1 pl-1">
                            <Target size={12} /> Target
                        </div>
                        <DropdownMenu
                            width="w-64"
                            trigger={
                                <div className="flex items-center justify-between w-full font-heading font-bold text-slate-700 text-sm py-1 pr-2 cursor-pointer hover:text-indigo-600 transition-colors bg-transparent">
                                    <span className="truncate">{selectedGoal?.title || 'Select Goal'}</span>
                                    <ChevronDown size={14} className="text-slate-400 ml-2 flex-shrink-0" />
                                </div>
                            }
                            items={goalMenuItems}
                        />
                    </div>

                    <div className="h-8 w-px bg-slate-200/50 mx-2 shrink-0"></div>

                    {/* Plan Selector */}
                    <div className="relative group flex-1 min-w-0">
                        <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-widest mb-1 pl-1">
                            <FileText size={12} /> Plan Doc
                        </div>
                        <DropdownMenu
                            width="w-72"
                            trigger={
                                <div className={`flex items-center justify-between w-full font-heading font-bold text-sm py-1 pr-2 cursor-pointer transition-colors ${selectedGoalId ? 'text-slate-700 hover:text-indigo-600' : 'text-slate-300'}`}>
                                    <span className="truncate">
                                        {selectedDoc?.title || (selectedGoalId ? (goalDocs.length === 0 ? 'No plans' : 'Select Plan') : 'Select Goal First')}
                                    </span>
                                    <ChevronDown size={14} className="text-slate-400 ml-2 flex-shrink-0" />
                                </div>
                            }
                            items={selectedGoalId ? planMenuItems : []}
                        />
                    </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                    <button
                        onClick={handleCreateDoc}
                        disabled={!selectedGoalId}
                        className="p-2 rounded-xl bg-white border border-slate-100 shadow-sm text-slate-400 hover:text-indigo-500 hover:border-indigo-100 hover:shadow-md transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        title="New Plan Doc"
                    >
                        <Plus size={18} />
                    </button>

                    <DropdownMenu
                        align="right"
                        width="w-48"
                        trigger={
                            <button className="p-2 rounded-xl bg-white border border-slate-100 shadow-sm text-slate-400 hover:text-slate-600 hover:shadow-md transition-all">
                                <MoreVertical size={18} />
                            </button>
                        }
                        items={actionMenuItems}
                    />
                </div>
            </div>

            {/* Editor Body */}
            <div className="flex-1 relative group overflow-hidden z-10">
                {selectedDoc ? (
                    <PlanDocEditorView
                        content={localContent}
                        onChange={handleContentChange}
                    />
                ) : (
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-300 p-8 text-center">
                        {selectedGoalId ? (
                            <>
                                <FileText size={48} strokeWidth={1} className="mb-4 opacity-50" />
                                <p className="max-w-xs">No plan selected. Create a new one or select from the list.</p>
                            </>
                        ) : (
                            <>
                                <Target size={48} strokeWidth={1} className="mb-4 opacity-50" />
                                <p className="max-w-xs">Select a goal to view its plans.</p>
                            </>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
