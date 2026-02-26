import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useGoalPageContext } from '../../../context/GoalPageContext';
import { useGoalStore } from '../../../hooks/useGoalStore';
import { usePlanDocStore } from '../../../hooks/usePlanDocStore';
import { registerPlanDocSaveCallback, unregisterPlanDocSaveCallback, registerPlanDocRefreshCallback, unregisterPlanDocRefreshCallback } from '../../../hooks/usePlanDocSaveHook';
import { PlanDoc } from '../../../types';
import { planDocApi } from '../../../api';
import { Plus, ChevronDown, FileText, Target, MoreVertical, Trash2, Copy, Archive, Save, PenLine, RefreshCw } from 'lucide-react';
import { PlanDocEditorView } from './components/PlanDocEditorView/PlanDocEditorView';
import { DropdownMenu, DropdownItem } from '../../shared/components/DropdownMenu';
import { InputDialog } from '../../shared/components/InputDialog';
import { RefreshConflictDialog } from '../../shared/components/RefreshConflictDialog';
import { viewBackground } from '../../shared/backgroundStyles';
import { toast } from '../../../../../core/components';


export const PlanDocListView: React.FC = () => {
    const { selectedGoalId, setSelectedGoalId, selectedPlanDocId, setSelectedPlanDocId } = useGoalPageContext();
    const { goals } = useGoalStore();
    const { planDocs, addPlanDoc, removePlanDocLocal, updatePlanDoc, deletePlanDoc } = usePlanDocStore();

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

    // Dialog state for renaming
    const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
    const [renameDocName, setRenameDocName] = useState('');

    // Dialog state for refresh conflict
    const [isRefreshConflictDialogOpen, setIsRefreshConflictDialogOpen] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);

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

    // Auto-save when component unmounts (e.g. tab switch from plans → daily)
    // 确保编辑器内容在组件卸载前写入 MD 文件，避免切换标签页后丢失未保存内容
    useEffect(() => {
        return () => {
            if (prevDocIdRef.current && hasUnsavedChangesRef.current) {
                planDocApi.updatePlanDoc(prevDocIdRef.current, { content: prevContentRef.current })
                    .catch(err => console.error('Auto-save on unmount failed:', err));
            }
        };
    }, []);

    // 静默保存函数（供外部 hook 调用，不显示 toast）
    const silentSave = useCallback(async () => {
        if (!selectedDoc || !hasUnsavedChangesRef.current) return;
        try {
            await planDocApi.updatePlanDoc(selectedDoc.id, { content: prevContentRef.current });
            setHasUnsavedChanges(false);
            updatePlanDoc({ ...selectedDoc, content: prevContentRef.current, updatedAt: new Date().toISOString() });
        } catch (error) {
            console.error('Silent save failed:', error);
            // 静默保存失败不显示 toast，避免干扰用户操作
        }
    }, [selectedDoc, updatePlanDoc]);

    // 注册/注销 PlanDoc 保存回调
    useEffect(() => {
        if (selectedDoc?.id) {
            registerPlanDocSaveCallback(selectedDoc.id, silentSave);
            return () => {
                unregisterPlanDocSaveCallback(selectedDoc.id);
            };
        }
    }, [selectedDoc?.id, silentSave]);

    // 静默刷新函数（供外部 hook 调用，不显示 toast）
    const silentRefresh = useCallback(async () => {
        if (!selectedPlanDocId) return;
        try {
            const doc = await planDocApi.getPlanDocDetail(selectedPlanDocId);
            setLocalContent(doc.content);
            setHasUnsavedChanges(false);
            updatePlanDoc(doc);
        } catch (error) {
            console.error('Silent refresh failed:', error);
        }
    }, [selectedPlanDocId, updatePlanDoc]);

    // 注册/注销 PlanDoc 刷新回调
    useEffect(() => {
        if (selectedDoc?.id) {
            registerPlanDocRefreshCallback(selectedDoc.id, silentRefresh);
            return () => {
                unregisterPlanDocRefreshCallback(selectedDoc.id);
            };
        }
    }, [selectedDoc?.id, silentRefresh]);

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
        // 生成6位随机字符
        const randomSuffix = Math.random().toString(36).substring(2, 8);
        if (selectedGoalId && selectedGoal) {
            setDefaultDocName(`${selectedGoal.title}-planDoc-${randomSuffix}`);
        } else {
            setDefaultDocName(`temp-planDoc-${randomSuffix}`);
        }
        setIsCreateDialogOpen(true);
    };

    const handleCreateDoc = async (docId: string) => {
        // 检查本地 store 是否已存在同 ID（避免乐观更新覆盖）
        const existsLocally = planDocs.some(d => d.id === docId);
        if (existsLocally) {
            toast.error(`计划书 "${docId}" 已存在`);
            return;
        }

        const newDoc: PlanDoc = {
            id: docId,
            goalId: selectedGoalId,
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
            toast.success('计划书创建成功');
        } catch (error: any) {
            console.error('Failed to create plan doc:', error);
            // 失败时仅从本地 store 移除，不调用后端删除 API
            removePlanDocLocal(newDoc.id);
            // 显示错误信息
            const errorMsg = error?.response?.data?.detail || error?.message || '创建失败';
            toast.error(errorMsg);
        }
    };

    const handleOpenRenameDialog = () => {
        if (selectedDoc) {
            setRenameDocName(selectedDoc.id);
            setIsRenameDialogOpen(true);
        }
    };

    const handleRenameDoc = async (newId: string) => {
        if (!selectedDoc) return;

        try {
            await updatePlanDoc(selectedDoc, newId);
            toast.success('已重命名');
            // Store update handles state, but we might want to ensure selection follows rename
            setSelectedPlanDocId(newId);
        } catch (error) {
            console.error('Failed to rename doc:', error);
            toast.error('重命名失败');
        }
    };

    // Refresh handlers
    const handleRefreshClick = () => {
        if (!selectedPlanDocId) return;

        if (hasUnsavedChanges) {
            // Show conflict dialog
            setIsRefreshConflictDialogOpen(true);
        } else {
            // No conflict, refresh directly
            doRefresh();
        }
    };

    const doRefresh = async () => {
        if (!selectedPlanDocId) return;

        setIsRefreshing(true);
        try {
            const doc = await planDocApi.getPlanDocDetail(selectedPlanDocId);
            setLocalContent(doc.content);
            setHasUnsavedChanges(false);
            updatePlanDoc(doc);
            toast.success('已刷新');
        } catch (err) {
            console.error('Failed to refresh doc:', err);
            toast.error('刷新失败');
        } finally {
            setIsRefreshing(false);
        }
    };

    const handleUseEditedContent = () => {
        // User chose to keep local changes, just close dialog
        setIsRefreshConflictDialogOpen(false);
    };

    const handleUseLocalMdContent = () => {
        // User chose to use file content, discard local changes
        setIsRefreshConflictDialogOpen(false);
        doRefresh();
    };

    const handleDeleteDoc = async () => {
        if (selectedPlanDocId) {
            if (confirm('Are you sure you want to delete this plan?')) {
                try {
                    await deletePlanDoc(selectedPlanDocId);
                    setSelectedPlanDocId(null);
                    toast.success('删除成功');
                } catch (error) {
                    console.error('Failed to delete doc:', error);
                    toast.error('删除失败');
                }
            }
        }
    };

    // --- Dropdown Items Configuration ---

    const goalMenuItems: DropdownItem[] = goals.map(g => ({
        id: g.id,
        label: g.title, // Goal still has title
        onClick: () => setSelectedGoalId(g.id)
    }));

    const planMenuItems: DropdownItem[] = goalDocs.length > 0
        ? goalDocs.map(d => ({
            id: d.id,
            label: d.id,
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
            id: 'rename',
            label: 'Rename Plan',
            icon: <PenLine size={14} />,
            onClick: handleOpenRenameDialog,
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
                                        {selectedDoc?.id || (goalDocs.length === 0 ? 'No plans' : 'Select Plan')}
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
                        className={`p-2 rounded-xl border shadow-sm transition-all ${hasUnsavedChanges
                            ? 'bg-indigo-500 border-indigo-400 text-white hover:bg-indigo-600'
                            : 'bg-white border-slate-100 text-slate-300 cursor-not-allowed'
                            }`}
                        title={isSaving ? 'Saving...' : 'Save'}
                    >
                        <Save size={18} />
                    </button>

                    <button
                        onClick={handleRefreshClick}
                        disabled={!selectedPlanDocId || isRefreshing}
                        className={`p-2 rounded-xl border shadow-sm transition-all ${selectedPlanDocId && !isRefreshing
                            ? 'bg-white border-slate-100 text-slate-400 hover:text-indigo-500 hover:border-indigo-100 hover:shadow-md'
                            : 'bg-white border-slate-100 text-slate-300 cursor-not-allowed'
                            }`}
                        title="Refresh from file"
                    >
                        <RefreshCw size={18} className={isRefreshing ? 'animate-spin' : ''} />
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
            <div className="flex-1 relative group overflow-y-auto z-10 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden [&_*::-webkit-scrollbar]:hidden [&_*]:[-ms-overflow-style:none] [&_*]:[scrollbar-width:none]">
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
            {/* Rename Plan Doc Dialog */}
            <InputDialog
                isOpen={isRenameDialogOpen}
                onClose={() => setIsRenameDialogOpen(false)}
                onConfirm={handleRenameDoc}
                title="Rename Plan Doc"
                placeholder="Enter new plan name"
                defaultValue={renameDocName}
                confirmText="Rename"
                cancelText="Cancel"
            />
            {/* Refresh Conflict Dialog */}
            <RefreshConflictDialog
                isOpen={isRefreshConflictDialogOpen}
                onClose={() => setIsRefreshConflictDialogOpen(false)}
                onUseEditedContent={handleUseEditedContent}
                onUseLocalMdContent={handleUseLocalMdContent}
                docName={selectedDoc?.id || ''}
            />
        </div>
    );
};
