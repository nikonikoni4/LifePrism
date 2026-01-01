/**
 * TaskPoolTree - 任务池树形组件
 * 
 * 提供类似IDE资源管理器的文件夹树结构，支持：
 * - 一级文件夹管理（添加、展开/折叠）
 * - 根级别和文件夹内的Todo创建
 * - 与周视图之间的拖拽交互
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    FolderPlus,
    FolderOpen,
    Folder,
    ChevronRight,
    Plus,
    Trash2,
    GripVertical,
    Circle,
    CheckCircle2
} from 'lucide-react';
import {
    useSortable,
    SortableContext,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useDroppable } from '@dnd-kit/core';
import { TodoItem, TaskFolder } from '../types';

// --- Animation Variants ---
const folderContentVariants = {
    open: {
        height: 'auto',
        opacity: 1,
        transition: {
            height: { duration: 0.25, ease: [0.4, 0, 0.2, 1] },
            opacity: { duration: 0.2, delay: 0.05 }
        }
    },
    closed: {
        height: 0,
        opacity: 0,
        transition: {
            height: { duration: 0.2, ease: [0.4, 0, 0.2, 1] },
            opacity: { duration: 0.1 }
        }
    }
};

const chevronVariants = {
    open: { rotate: 90 },
    closed: { rotate: 0 }
};

// --- Sortable Pool Item Component ---
interface SortablePoolTreeItemProps {
    task: TodoItem;
    isSelected: boolean;
    folderId: string | null;
    onClick: () => void;
    onDelete: () => void;
}

const SortablePoolTreeItem: React.FC<SortablePoolTreeItemProps> = ({ task, isSelected, folderId, onClick, onDelete }) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id: task.id, data: { type: 'pool-item', task, source: 'pool', folderId } });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
    };

    return (
        <div
            ref={setNodeRef}
            style={style}
            onClick={onClick}
            className={`group flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer transition-all ${isDragging ? 'opacity-50 shadow-lg ring-2 ring-blue-300' : ''
                } ${isSelected ? 'bg-blue-50 border border-blue-200' : 'hover:bg-slate-50 border border-transparent'}`}
        >
            {/* Drag Handle */}
            <div
                {...attributes}
                {...listeners}
                className="cursor-grab text-slate-300 hover:text-slate-500 transition-colors"
            >
                <GripVertical size={14} />
            </div>

            {/* Checkbox Circle */}
            {task.state === 'completed' ? (
                <CheckCircle2 size={16} className="text-green-500 flex-shrink-0" />
            ) : (
                <Circle size={16} className="text-slate-300 flex-shrink-0" />
            )}

            {/* Content */}
            <span className={`flex-1 text-sm truncate ${task.state === 'completed' ? 'text-slate-400 line-through' : 'text-slate-700'
                }`}>
                {task.content}
            </span>

            {/* Delete Button */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onDelete();
                }}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 text-slate-300 hover:text-red-500 transition-all"
            >
                <Trash2 size={12} />
            </button>
        </div>
    );
};

// --- Droppable Folder Container ---
interface DroppableFolderProps {
    folderId: string;
    children: React.ReactNode;
    isEmpty: boolean;
}

const DroppableFolder: React.FC<DroppableFolderProps> = ({ folderId, children, isEmpty }) => {
    const { setNodeRef, isOver } = useDroppable({
        id: `folder-${folderId}`,
        data: { type: 'folder', folderId }
    });

    return (
        <div
            ref={setNodeRef}
            className={`pl-6 py-1 min-h-[48px] transition-all duration-200 rounded-lg border-2 border-dashed ${isOver
                ? 'bg-blue-100 border-blue-400 shadow-inner'
                : 'border-transparent hover:border-slate-200'
                }`}
        >
            {children}
            {/* Drop zone indicator when hovering */}
            {isOver && (
                <div className="flex items-center justify-center py-2 text-xs text-blue-500 font-medium">
                    放置到此文件夹
                </div>
            )}
        </div>
    );
};

// --- Droppable Folder Header ---
// Makes the folder header itself a drop target with visual feedback
interface DroppableFolderHeaderProps {
    folderId: string;
    children: React.ReactNode;
}

const DroppableFolderHeader: React.FC<DroppableFolderHeaderProps> = ({ folderId, children }) => {
    const { setNodeRef, isOver } = useDroppable({
        id: `folder-header-${folderId}`,
        data: { type: 'folder', folderId }
    });

    return (
        <div
            ref={setNodeRef}
            className={`group flex items-center gap-1 px-2 py-1.5 rounded-lg transition-all duration-200 ${isOver
                ? 'bg-blue-100 ring-2 ring-blue-400 shadow-md'
                : 'hover:bg-slate-50'
                }`}
        >
            {children}
            {/* Drop indicator badge */}
            {isOver && (
                <span className="ml-auto text-[10px] text-blue-600 bg-blue-200 px-2 py-0.5 rounded-full font-medium animate-pulse">
                    放入
                </span>
            )}
        </div>
    );
};

// --- Droppable Root Container ---
interface DroppableRootProps {
    children: React.ReactNode;
}

const DroppableRoot: React.FC<DroppableRootProps> = ({ children }) => {
    const { setNodeRef, isOver } = useDroppable({
        id: 'pool-root',
        data: { type: 'pool-root' }
    });

    return (
        <div
            ref={setNodeRef}
            className={`min-h-[60px] transition-all duration-200 rounded-lg border-2 border-dashed mt-2 ${isOver
                ? 'bg-emerald-100 border-emerald-400 shadow-inner'
                : 'border-transparent'
                }`}
        >
            {children}
            {/* Drop zone indicator when hovering */}
            {isOver && (
                <div className="flex items-center justify-center py-2 text-xs text-emerald-600 font-medium">
                    放置到根目录
                </div>
            )}
        </div>
    );
};

// --- Main Component Props ---
interface TaskPoolTreeProps {
    folders: TaskFolder[];
    rootTodoIds: number[];
    allTasks: TodoItem[];
    selectedTaskId: number | null;
    onSelectTask: (task: TodoItem | null) => void;
    onCreateFolder: (name: string) => void;
    onToggleFolder: (folderId: string) => void;
    onDeleteFolder: (folderId: string) => void;
    onCreateTask: (content: string, folderId: string | null) => void;
    onDeleteTask: (taskId: number) => void;
}

const TaskPoolTree: React.FC<TaskPoolTreeProps> = ({
    folders,
    rootTodoIds,
    allTasks,
    selectedTaskId,
    onSelectTask,
    onCreateFolder,
    onToggleFolder,
    onDeleteFolder,
    onCreateTask,
    onDeleteTask,
}) => {
    const [newFolderName, setNewFolderName] = useState('');
    const [isAddingFolder, setIsAddingFolder] = useState(false);
    const [rootInput, setRootInput] = useState('');
    const [folderInputs, setFolderInputs] = useState<Record<string, string>>({});
    const [activeFolderInput, setActiveFolderInput] = useState<string | null>(null);

    // Get task by ID
    const getTaskById = (id: number): TodoItem | undefined => {
        return allTasks.find(t => t.id === id);
    };

    // Get tasks for folder
    const getFolderTasks = (folder: TaskFolder): TodoItem[] => {
        return folder.todoIds.map(id => getTaskById(id)).filter((t): t is TodoItem => t !== undefined);
    };

    // Get root tasks
    const getRootTasks = (): TodoItem[] => {
        return rootTodoIds.map(id => getTaskById(id)).filter((t): t is TodoItem => t !== undefined);
    };

    // Handle folder creation
    const handleCreateFolder = () => {
        if (newFolderName.trim()) {
            onCreateFolder(newFolderName.trim());
            setNewFolderName('');
            setIsAddingFolder(false);
        }
    };

    // Handle root task creation
    const handleCreateRootTask = () => {
        if (rootInput.trim()) {
            onCreateTask(rootInput.trim(), null);
            setRootInput('');
        }
    };

    // Handle folder task creation
    const handleCreateFolderTask = (folderId: string) => {
        const input = folderInputs[folderId];
        if (input?.trim()) {
            onCreateTask(input.trim(), folderId);
            setFolderInputs(prev => ({ ...prev, [folderId]: '' }));
            setActiveFolderInput(null);
        }
    };

    return (
        <div className="flex-1 flex flex-col overflow-hidden">
            {/* Add Folder Button */}
            <div className="px-4 py-2 border-b border-slate-100">
                {isAddingFolder ? (
                    <div className="flex items-center gap-2">
                        <input
                            type="text"
                            value={newFolderName}
                            onChange={(e) => setNewFolderName(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') handleCreateFolder();
                                if (e.key === 'Escape') {
                                    setIsAddingFolder(false);
                                    setNewFolderName('');
                                }
                            }}
                            placeholder="文件夹名称..."
                            autoFocus
                            className="flex-1 px-2 py-1.5 text-sm border border-slate-200 rounded-lg outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50"
                        />
                        <button
                            onClick={handleCreateFolder}
                            className="px-2 py-1.5 bg-blue-500 text-white text-xs font-bold rounded-lg hover:bg-blue-600 transition-colors"
                        >
                            添加
                        </button>
                        <button
                            onClick={() => {
                                setIsAddingFolder(false);
                                setNewFolderName('');
                            }}
                            className="px-2 py-1.5 text-slate-500 text-xs font-bold rounded-lg hover:bg-slate-100 transition-colors"
                        >
                            取消
                        </button>
                    </div>
                ) : (
                    <button
                        onClick={() => setIsAddingFolder(true)}
                        className="flex items-center gap-2 px-3 py-2 w-full text-sm text-slate-600 hover:bg-slate-50 rounded-lg transition-colors"
                    >
                        <FolderPlus size={16} className="text-slate-400" />
                        <span>添加文件夹</span>
                    </button>
                )}
            </div>

            {/* Root Task Input */}
            <div className="px-4 py-2 border-b border-slate-100">
                <div className="relative">
                    <input
                        type="text"
                        value={rootInput}
                        onChange={(e) => setRootInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') handleCreateRootTask();
                        }}
                        placeholder="+ Type to create a task..."
                        className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 pl-8 text-sm outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50 transition-all placeholder:text-slate-400 shadow-sm"
                    />
                    <Plus size={16} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                </div>
            </div>

            {/* Tree Content - Scrollable */}
            <div className="flex-1 overflow-y-auto px-2 py-2">
                {/* Folders */}
                {folders.map(folder => {
                    const folderTasks = getFolderTasks(folder);
                    const isExpanded = folder.isExpanded;

                    return (
                        <div key={folder.id} className="mb-1">
                            {/* Folder Header - Now a droppable zone */}
                            <DroppableFolderHeader folderId={folder.id}>
                                {/* Expand/Collapse */}
                                <button
                                    onClick={() => onToggleFolder(folder.id)}
                                    className="p-0.5"
                                >
                                    <motion.div
                                        variants={chevronVariants}
                                        animate={isExpanded ? 'open' : 'closed'}
                                        transition={{ duration: 0.15 }}
                                    >
                                        <ChevronRight size={14} className="text-slate-400" />
                                    </motion.div>
                                </button>

                                {/* Folder Icon */}
                                {isExpanded ? (
                                    <FolderOpen size={16} className="text-amber-500" />
                                ) : (
                                    <Folder size={16} className="text-amber-400" />
                                )}

                                {/* Folder Name */}
                                <span className="flex-1 text-sm font-medium text-slate-700 truncate">
                                    {folder.name}
                                </span>

                                {/* Task Count */}
                                <span className="text-[10px] text-slate-400 px-1.5 py-0.5 bg-slate-100 rounded">
                                    {folderTasks.length}
                                </span>

                                {/* Add Task to Folder Button */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setActiveFolderInput(folder.id);
                                        if (!isExpanded) onToggleFolder(folder.id);
                                    }}
                                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-blue-50 text-slate-400 hover:text-blue-500 transition-all"
                                >
                                    <Plus size={14} />
                                </button>

                                {/* Delete Folder Button */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onDeleteFolder(folder.id);
                                    }}
                                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 text-slate-400 hover:text-red-500 transition-all"
                                >
                                    <Trash2 size={12} />
                                </button>
                            </DroppableFolderHeader>

                            {/* Folder Content */}
                            <AnimatePresence initial={false}>
                                {isExpanded && (
                                    <motion.div
                                        variants={folderContentVariants}
                                        initial="closed"
                                        animate="open"
                                        exit="closed"
                                        className="overflow-hidden"
                                    >
                                        <DroppableFolder folderId={folder.id} isEmpty={folderTasks.length === 0}>
                                            {/* Folder Input */}
                                            {activeFolderInput === folder.id && (
                                                <div className="mb-2">
                                                    <input
                                                        type="text"
                                                        value={folderInputs[folder.id] || ''}
                                                        onChange={(e) => setFolderInputs(prev => ({ ...prev, [folder.id]: e.target.value }))}
                                                        onKeyDown={(e) => {
                                                            if (e.key === 'Enter') handleCreateFolderTask(folder.id);
                                                            if (e.key === 'Escape') setActiveFolderInput(null);
                                                        }}
                                                        onBlur={() => {
                                                            if (!folderInputs[folder.id]?.trim()) {
                                                                setActiveFolderInput(null);
                                                            }
                                                        }}
                                                        placeholder="输入任务内容..."
                                                        autoFocus
                                                        className="w-full px-2 py-1.5 text-sm border border-slate-200 rounded-lg outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50"
                                                    />
                                                </div>
                                            )}

                                            {/* Folder Tasks */}
                                            <SortableContext items={folderTasks.map(t => t.id)} strategy={verticalListSortingStrategy}>
                                                <div className="space-y-0.5">
                                                    {folderTasks.map(task => (
                                                        <SortablePoolTreeItem
                                                            key={task.id}
                                                            task={task}
                                                            folderId={folder.id}
                                                            isSelected={selectedTaskId === task.id}
                                                            onClick={() => onSelectTask(task)}
                                                            onDelete={() => onDeleteTask(task.id)}
                                                        />
                                                    ))}
                                                </div>
                                            </SortableContext>

                                            {folderTasks.length === 0 && activeFolderInput !== folder.id && (
                                                <div className="text-xs text-slate-400 italic py-2 pl-2">
                                                    文件夹为空
                                                </div>
                                            )}
                                        </DroppableFolder>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    );
                })}

                {/* Root Tasks */}
                <DroppableRoot>
                    <SortableContext items={getRootTasks().map(t => t.id)} strategy={verticalListSortingStrategy}>
                        <div className="space-y-0.5">
                            {getRootTasks().map(task => (
                                <SortablePoolTreeItem
                                    key={task.id}
                                    task={task}
                                    folderId={null}
                                    isSelected={selectedTaskId === task.id}
                                    onClick={() => onSelectTask(task)}
                                    onDelete={() => onDeleteTask(task.id)}
                                />
                            ))}
                        </div>
                    </SortableContext>

                    {getRootTasks().length === 0 && folders.length === 0 && (
                        <div className="text-center py-8 text-slate-400 text-sm">
                            任务池为空，拖拽任务到这里
                        </div>
                    )}
                </DroppableRoot>
            </div>
        </div>
    );
};

export default TaskPoolTree;
