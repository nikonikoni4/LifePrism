import React, { useState, useEffect, useRef } from 'react';
import { useGoalPageContext } from '../../../context/GoalPageContext';
import { useGoalStore } from '../../../hooks/useGoalStore';
import { usePlanDocStore } from '../../../hooks/usePlanDocStore';
import { PlanDoc } from '../../../types';
import { planDocApi } from '../../../api';
import { Plus, ChevronDown, FileText, Target, MoreVertical, Trash2, Copy, Archive, Save } from 'lucide-react';
import { PlanDocEditorView } from './components/PlanDocEditorView/PlanDocEditorView';
import { DropdownMenu, DropdownItem } from '../../shared/components/DropdownMenu';
import { InputDialog } from '../../shared/components/InputDialog';
import { viewBackground } from '../../shared/backgroundStyles';
import { toast } from '../../../../common';


export const PlanDocListView: React.FC = () => {
    const { selectedGoalId, setSelectedGoalId, selectedPlanDocId, setSelectedPlanDocId } = useGoalPageContext();
    const { goals } = useGoalStore();
    const { planDocs, addPlanDoc, updatePlanDoc, deletePlanDoc } = usePlanDocStore();

    // Local content state for editing to avoid laggy context updates on every keystroke
    const [localContent, setLocalContent] = useState('');
    const [isLoadingContent, setIsLoadingContent] = useState(false);

    // Save state
    const [isSaving, setIsSaving] = useState(false);
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

    // Refs for auto-save on doc switch
    const prevDocIdRef = useRef<string | null>(null);
    const prevContentRef = useRef<string>('');
    const hasUnsavedChangesRef = useRef(false);

    // Dialog state for creating new plan doc
    const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
    const [defaultDocName, setDefaultDocName] = useState('');

    // Derived
    const selectedGoal = goals.find(g => g.id === selectedGoalId) || null;
    // Show docs for selected goal, or temp docs (goalId === null) when no goal selected
    const goalDocs = selectedGoalId
        ? planDocs.filter(d => d.goalId === selectedGoalId)
        : planDocs.filter(d => d.goalId === null);
    const selectedDoc = goalDocs.find(d => d.id === selectedPlanDocId) || null;

    // Effects
    // Select first doc when goal changes or if current selection invalid
    useEffect(() => {
        if (goalDocs.length > 0) {
            // If no doc selected, or selected doc is not in current goal list, select first
            if (!selectedPlanDocId || !goalDocs.find(d => d.id === selectedPlanDocId)) {
                setSelectedPlanDocId(goalDocs[0].id);
            }
        } else {
            setSelectedPlanDocId(null);
        }
    }, [selectedGoalId, goalDocs.length, selectedPlanDocId, setSelectedPlanDocId]);

    // Fetch full content from API when doc changes
    useEffect(() => {
        if (!selectedPlanDocId) {
            setLocalContent('');
            setHasUnsavedChanges(false);
            return;
        }

        // Fetch full content from API
        setIsLoadingContent(true);
        planDocApi.getPlanDocDetail(selectedPlanDocId)
            .then(doc => {
                setLocalContent(doc.content);
                setHasUnsavedChanges(false);
                // Update store with full content
                updatePlanDoc(doc);
            })
            .catch(err => {
                console.error('Failed to load doc content:', err);
                setLocalContent('');
            })
            .finally(() => {
                setIsLoadingContent(false);
            });
    }, [selectedPlanDocId]); // Only when ID changes

    // Keep refs in sync
    useEffect(() => {
        hasUnsavedChangesRef.current = hasUnsavedChanges;
        prevContentRef.current = localContent;
    }, [hasUnsavedChanges, localContent]);

    // Auto-save when switching documents
    useEffect(() => {
        const prevId = prevDocIdRef.current;
        const currentId = selectedDoc?.id || null;

        // If switching from a doc that had unsaved changes, save it
        if (prevId && prevId !== currentId && hasUnsavedChangesRef.current) {
            planDocApi.updatePlanDoc(prevId, { content: prevContentRef.current })
                .then(() => {
                    toast.success('文档已自动保存');
                })
                .catch(err => {
                    console.error('Auto-save on doc switch failed:', err);
                    toast.error('自动保存失败');
                });
        }

        prevDocIdRef.current = currentId;
    }, [selectedDoc?.id]);

    // Note: beforeunload auto-save removed because sendBeacon only supports POST
    // but backend uses PATCH. Auto-save on doc switch handles most cases.

    // Save handler
    const handleSave = async () => {
        if (!selectedDoc || !hasUnsavedChanges) return;
        setIsSaving(true);
        try {
            await planDocApi.updatePlanDoc(selectedDoc.id, { content: localContent });
            setHasUnsavedChanges(false);
            // Update store after successful save
            updatePlanDoc({ ...selectedDoc, content: localContent, updatedAt: new Date().toISOString() });
            toast.success('文档已保存');
        } catch (error) {
            console.error('Save failed:', error);
            toast.error('保存失败');
        } finally {
            setIsSaving(false);
        }
    };

    const handleContentChange = (newContent: string) => {
        setLocalContent(newContent);
        setHasUnsavedChanges(true);
        // Note: Don't update store on every keystroke to avoid re-renders
        // Store will be updated when save completes
    };

    const handleOpenCreateDialog = () => {
        if (selectedGoalId && selectedGoal) {
            setDefaultDocName(`planDoc-${selectedGoal.title}`);
        } else {
            setDefaultDocName(`planDoc-temp`);
        }
        setIsCreateDialogOpen(true);
    };

    const handleCreateDoc = async (title: string) => {
        const newDoc: PlanDoc = {
            id: title,  // 使用 title 作为 id
            goalId: selectedGoalId,
            title: title,
            content: '# New Plan\n',
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            status: 'active'
        };

        // 先添加到内存 store（乐观更新）
        addPlanDoc(newDoc);
        setSelectedPlanDocId(newDoc.id);

        // 调用后端 API 创建（会同时创建 md 文件）
        try {
            await planDocApi.createPlanDoc(newDoc);
        } catch (error) {
            console.error('Failed to create plan doc:', error);
            // 可选：失败时从 store 中移除
            deletePlanDoc(newDoc.id);
        }
    };

    const handleDeleteDoc = () => {
        if (selectedPlanDocId) {
            if (confirm('Are you sure you want to delete this plan?')) {
                deletePlanDoc(selectedPlanDocId);
                setSelectedPlanDocId(null);
            }
        }
    };

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
                                <div className="flex items-center justify-between w-full font-heading font-bold text-sm py-1 pr-2 cursor-pointer transition-colors text-slate-700 hover:text-indigo-600">
                                    <span className="truncate">
                                        {selectedDoc?.title || (goalDocs.length === 0 ? 'No plans' : 'Select Plan')}
                                    </span>
                                    <ChevronDown size={14} className="text-slate-400 ml-2 flex-shrink-0" />
                                </div>
                            }
                            items={planMenuItems}
                        />
                    </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                    <button
                        onClick={handleSave}
                        disabled={!hasUnsavedChanges || isSaving}
                        className={`p-2 rounded-xl border shadow-sm transition-all ${
                            hasUnsavedChanges
                                ? 'bg-indigo-500 border-indigo-400 text-white hover:bg-indigo-600'
                                : 'bg-white border-slate-100 text-slate-300 cursor-not-allowed'
                        }`}
                        title={isSaving ? 'Saving...' : 'Save'}
                    >
                        <Save size={18} />
                    </button>

                    <button
                        onClick={handleOpenCreateDialog}
                        className="p-2 rounded-xl bg-white border border-slate-100 shadow-sm text-slate-400 hover:text-indigo-500 hover:border-indigo-100 hover:shadow-md transition-all"
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
                {isLoadingContent ? (
                    <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
                    </div>
                ) : selectedDoc ? (
                    <PlanDocEditorView
                        content={localContent}
                        onChange={handleContentChange}
                    />
                ) : (
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-300 p-8 text-center">
                        <FileText size={48} strokeWidth={1} className="mb-4 opacity-50" />
                        <p className="max-w-xs">No plan selected. Create a new one or select from the list.</p>
                    </div>
                )}
            </div>

            {/* Create Plan Doc Dialog */}
            <InputDialog
                isOpen={isCreateDialogOpen}
                onClose={() => setIsCreateDialogOpen(false)}
                onConfirm={handleCreateDoc}
                title="Create New Plan Doc"
                placeholder="Enter plan doc name"
                defaultValue={defaultDocName}
                confirmText="Create"
                cancelText="Cancel"
            />
        </div>
    );
};
