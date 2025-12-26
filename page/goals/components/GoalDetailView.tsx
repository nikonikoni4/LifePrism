
import React, { useState, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight, Save, Clock, Calendar, AlignLeft, Folder, ChevronDown, Palette, Check, Activity, Loader2, Edit3, Eye } from 'lucide-react';
import { UserGoal, CategoryTreeItem, UpdateGoalRequest } from '../types';
import { categoryApi, goalApi } from '../api';
import CategorySelectionModal from './CategorySelectionModal';
import { MarkdownRenderer } from '../../common';

interface GoalDetailViewProps {
  goalId: string;
  onBack: () => void;
  onSave: (updatedGoal: UserGoal) => void;
}

const GOAL_COLORS = [
  '#FFFFFF', // White
  '#E0F2FE', // Blue
  '#DCFCE7', // Green
  '#FEF3C7', // Amber
  '#FAE8FF', // Purple
  '#FEE2E2', // Red
  '#F3F4F6'  // Grey
];

const GoalDetailView: React.FC<GoalDetailViewProps> = ({ goalId, onBack, onSave }) => {
  const [formData, setFormData] = useState<UserGoal | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [categories, setCategories] = useState<CategoryTreeItem[]>([]);
  const [isEditingContent, setIsEditingContent] = useState(false);
  const [isMetadataExpanded, setIsMetadataExpanded] = useState(false);

  // Track selected category/subcategory IDs for the modal
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
  const [selectedSubCategoryId, setSelectedSubCategoryId] = useState<string | null>(null);

  // Load goal details and categories on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [goal, categoriesResponse] = await Promise.all([
          goalApi.getGoalDetail(goalId),
          categoryApi.getCategoryTree(2)
        ]);
        setFormData(goal);
        setCategories(categoriesResponse.data);

        // Find and set category IDs from names
        if (goal.linkToCategory) {
          const cat = categoriesResponse.data.find(c => c.name === goal.linkToCategory);
          if (cat) {
            setSelectedCategoryId(cat.id);
            if (goal.linkToSubCategory && cat.subcategories) {
              const sub = cat.subcategories.find(s => s.name === goal.linkToSubCategory);
              if (sub) setSelectedSubCategoryId(sub.id);
            }
          }
        }
      } catch (err) {
        console.error('Failed to load goal:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [goalId]);

  const handleChange = (field: keyof UserGoal, value: any) => {
    if (!formData) return;
    setFormData(prev => prev ? { ...prev, [field]: value } : null);
  };

  const handleCategoryApply = (categoryId: string | null, subCategoryId: string | null) => {
    setSelectedCategoryId(categoryId);
    setSelectedSubCategoryId(subCategoryId);
    setShowCategoryModal(false);
  };

  // Save goal data, optionally silent (no callback to parent)
  const handleSave = async (options?: { silent?: boolean }) => {
    if (!formData) return;

    try {
      setSaving(true);
      setSaveMessage(null);
      const updateData: UpdateGoalRequest = {
        name: formData.name,
        abstract: formData.abstract,
        content: formData.content,
        color: formData.color,
        expectedFinishedAt: formData.expectedFinishedAt,
        expectedHours: formData.expectedHours,
        linkToCategoryId: selectedCategoryId || undefined,
        linkToSubCategoryId: selectedSubCategoryId || undefined,
        status: formData.status
      };

      const updatedGoal = await goalApi.updateGoal(formData.id, updateData);

      if (options?.silent) {
        // Show success message for silent save (Ctrl+S)
        setSaveMessage({ type: 'success', text: '保存成功' });
        // Auto-hide message after 2 seconds
        setTimeout(() => setSaveMessage(null), 2000);
      } else {
        // Trigger parent callback (for button save)
        onSave(updatedGoal);
      }
    } catch (err) {
      console.error('Failed to save goal:', err);
      setSaveMessage({ type: 'error', text: '保存失败' });
      setTimeout(() => setSaveMessage(null), 3000);
    } finally {
      setSaving(false);
    }
  };

  // Handle back with auto-save
  const handleBackWithSave = useCallback(async () => {
    if (formData && !saving) {
      await handleSave(); // Non-silent, will trigger onSave callback
    }
    onBack();
  }, [formData, saving, selectedCategoryId, selectedSubCategoryId]);

  // Ctrl+S keyboard shortcut to save (silent mode)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (!saving) {
          handleSave({ silent: true });
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [formData, saving, selectedCategoryId, selectedSubCategoryId]);

  const handleStatusToggle = () => {
    if (!formData) return;
    const newStatus = formData.status === 'completed' ? 'active' : 'completed';
    handleChange('status', newStatus);
  };

  // Get active category/subcategory info from IDs
  const activeCategory = categories.find(c => c.id === selectedCategoryId);
  const activeSubCategory = activeCategory?.subcategories?.find(s => s.id === selectedSubCategoryId);

  // Format expected hours for display
  const formatHoursForInput = (hours: number | undefined) => {
    if (!hours) return '';
    return hours.toString();
  };

  const parseHoursFromInput = (value: string) => {
    const parsed = parseInt(value, 10);
    return isNaN(parsed) ? undefined : parsed;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-140px)] bg-white rounded-[2.5rem]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!formData) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-140px)] bg-white rounded-[2.5rem] text-red-500">
        Failed to load goal
      </div>
    );
  }

  const isCompleted = formData.status === 'completed';

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] bg-white rounded-[2.5rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden animate-fade-in relative">

      {/* Decorative Background Blob */}
      <div
        className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-blue-50/50 to-purple-50/50 rounded-full blur-3xl -z-10 translate-x-1/3 -translate-y-1/3 pointer-events-none transition-colors duration-500"
        style={formData.color && formData.color !== '#FFFFFF' ? { backgroundColor: formData.color, opacity: 0.3 } : {}}
      />

      {/* Header Toolbar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-slate-100 bg-white/80 backdrop-blur-md sticky top-0 z-20">
        <button
          onClick={handleBackWithSave}
          className="flex items-center gap-1.5 text-slate-400 hover:text-slate-800 transition-all group"
        >
          <div className="p-1.5 rounded-lg bg-slate-50 group-hover:bg-slate-100 transition-colors">
            <ChevronLeft size={16} />
          </div>
          <span className="font-medium text-xs uppercase tracking-wider">返回</span>
        </button>

        {/* Save Message Toast */}
        {saveMessage && (
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all animate-fade-in ${saveMessage.type === 'success'
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-red-50 text-red-700 border border-red-200'
              }`}
          >
            {saveMessage.type === 'success' ? (
              <Check size={14} className="text-green-500" />
            ) : (
              <span className="text-red-500">✕</span>
            )}
            {saveMessage.text}
          </div>
        )}

        <button
          onClick={() => handleSave({ silent: true })}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 text-white rounded-lg font-medium text-xs uppercase tracking-wider hover:bg-blue-600 hover:shadow-md hover:shadow-blue-500/20 transition-all transform active:scale-95 disabled:opacity-50"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          保存
        </button>
      </div>

      {/* Main Content Scrollable Area */}
      <div className="flex-1 overflow-y-auto no-scrollbar p-6 md:p-8 w-full max-w-4xl mx-auto">

        {/* Title Input (Smaller, more compact) */}
        <div className="mb-2 animate-fade-in" style={{ animationDelay: '100ms' }}>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => handleChange('name', e.target.value)}
            placeholder="Enter Goal Title..."
            className="w-full text-2xl md:text-3xl font-bold text-slate-800 bg-transparent border-none outline-none placeholder-slate-300 leading-tight"
          />
        </div>

        {/* Abstract/Summary Input */}
        <div className="mb-4 animate-fade-in" style={{ animationDelay: '120ms' }}>
          <input
            type="text"
            value={formData.abstract || ''}
            onChange={(e) => handleChange('abstract', e.target.value)}
            placeholder="Add a brief summary..."
            className="w-full text-base text-slate-500 bg-transparent border-none outline-none placeholder-slate-300 leading-relaxed"
          />
        </div>

        {/* Collapsible Metadata Section */}
        <div className="mb-6 animate-fade-in" style={{ animationDelay: '150ms' }}>
          {/* Toggle Button */}
          <button
            onClick={() => setIsMetadataExpanded(!isMetadataExpanded)}
            className="flex items-center gap-2 text-slate-400 hover:text-slate-600 transition-colors py-2 group"
          >
            <ChevronRight
              size={14}
              className={`transition-transform duration-200 ${isMetadataExpanded ? 'rotate-90' : ''}`}
            />
            <span className="text-xs font-medium uppercase tracking-wider">信息</span>
            {!isMetadataExpanded && (
              <span className="text-xs text-slate-300 ml-2">
                {formData.expectedFinishedAt && `📅 ${formData.expectedFinishedAt}`}
                {formData.expectedHours && ` • ⏱️ ${formData.expectedHours}h`}
                {activeCategory && ` • 📁 ${activeCategory.name}`}
              </span>
            )}
          </button>

          {/* Expandable Metadata Content */}
          <div
            className={`overflow-hidden transition-all duration-300 ease-in-out ${isMetadataExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
              }`}
          >
            <div className="flex flex-wrap items-center gap-4 py-4 pl-6 border-l-2 border-slate-100">
              {/* Date Picker */}
              <div className="flex items-center gap-2 bg-slate-50 px-3 py-2 rounded-lg border border-slate-100 hover:border-slate-200 transition-colors">
                <Calendar size={14} className="text-slate-400" />
                <div className="flex flex-col">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">目标日期</span>
                  <input
                    type="date"
                    value={formData.expectedFinishedAt || ''}
                    onChange={(e) => handleChange('expectedFinishedAt', e.target.value)}
                    className="bg-transparent text-slate-700 font-medium text-xs focus:outline-none p-0 w-28 cursor-pointer"
                  />
                </div>
              </div>

              {/* Estimate Input */}
              <div className="flex items-center gap-2 bg-slate-50 px-3 py-2 rounded-lg border border-slate-100 hover:border-slate-200 transition-colors">
                <Clock size={14} className="text-slate-400" />
                <div className="flex flex-col">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">预计时长</span>
                  <input
                    type="number"
                    value={formatHoursForInput(formData.expectedHours)}
                    onChange={(e) => handleChange('expectedHours', parseHoursFromInput(e.target.value))}
                    className="bg-transparent text-slate-700 font-medium text-xs w-16 focus:outline-none placeholder-slate-300"
                    placeholder="60"
                    min={0}
                  />
                </div>
              </div>

              {/* Color Picker */}
              <div className="flex items-center gap-2 bg-slate-50 px-3 py-2 rounded-lg border border-slate-100 hover:border-slate-200 transition-colors">
                <Palette size={14} className="text-slate-400" />
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">颜色</span>
                  <div className="flex gap-1.5">
                    {GOAL_COLORS.slice(0, 5).map(c => (
                      <button
                        key={c}
                        onClick={() => handleChange('color', c)}
                        className={`w-3.5 h-3.5 rounded-full border border-slate-200 shadow-sm transition-transform hover:scale-110 ${(formData.color || '#FFFFFF') === c ? 'ring-2 ring-slate-400 scale-110' : ''
                          }`}
                        style={{ backgroundColor: c }}
                      />
                    ))}
                  </div>
                </div>
              </div>

              {/* Status Toggle */}
              <button
                onClick={handleStatusToggle}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all ${isCompleted
                  ? 'bg-green-50 border-green-200 hover:bg-green-100'
                  : 'bg-slate-50 border-slate-100 hover:border-slate-200'
                  }`}
              >
                <div className={`w-6 h-6 rounded-md flex items-center justify-center border transition-colors ${isCompleted
                  ? 'bg-green-500 border-green-500 text-white'
                  : 'bg-white border-slate-200 text-slate-300'
                  }`}>
                  {isCompleted ? <Check size={12} strokeWidth={3} /> : <Activity size={12} />}
                </div>
                <div className="flex flex-col items-start">
                  <span className={`text-[10px] font-medium uppercase tracking-wider ${isCompleted ? 'text-green-600' : 'text-slate-400'}`}>状态</span>
                  <span className={`text-xs font-medium ${isCompleted ? 'text-green-700' : 'text-slate-700'}`}>
                    {isCompleted ? '已完成' : '进行中'}
                  </span>
                </div>
              </button>

              {/* Category Selector */}
              <button
                onClick={() => setShowCategoryModal(true)}
                className="flex items-center gap-2 bg-slate-50 px-3 py-2 rounded-lg border border-slate-100 hover:border-slate-200 transition-all text-left"
              >
                <Folder size={14} className="text-slate-400" />
                <div className="flex flex-col">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">分类</span>
                  <div className="flex items-center gap-1.5">
                    {activeCategory ? (
                      <>
                        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: activeCategory.color }}></div>
                        <span className="text-slate-700 font-medium text-xs whitespace-nowrap">
                          {activeCategory.name}
                          {activeSubCategory && <span className="opacity-50"> / {activeSubCategory.name}</span>}
                        </span>
                      </>
                    ) : (
                      <span className="text-slate-700 font-medium text-xs">未分类</span>
                    )}
                    <ChevronDown size={10} className="text-slate-400" />
                  </div>
                </div>
              </button>
            </div>
          </div>

          {/* Divider */}
          <div className="border-b border-slate-100 mt-2"></div>
        </div>

        {/* Main Description Area - Edit/Preview Toggle */}
        <div className="min-h-[400px] animate-fade-in relative" style={{ animationDelay: '200ms' }}>
          {/* Right-top Tab Buttons */}
          <div className="absolute right-0 -top-2 flex items-center gap-1 bg-white rounded-lg shadow-sm border border-slate-100 p-1 z-10">
            <button
              onClick={() => setIsEditingContent(true)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${isEditingContent
                ? 'bg-slate-900 text-white'
                : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                }`}
            >
              <span className="flex items-center gap-1.5">
                <Edit3 size={12} />
                编辑
              </span>
            </button>
            <button
              onClick={() => setIsEditingContent(false)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${!isEditingContent
                ? 'bg-slate-900 text-white'
                : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                }`}
            >
              <span className="flex items-center gap-1.5">
                <Eye size={12} />
                预览
              </span>
            </button>
          </div>

          {/* Content Area */}
          <div className="pt-8">
            {isEditingContent ? (
              <textarea
                value={formData.content}
                onChange={(e) => handleChange('content', e.target.value)}
                placeholder="在此描述你的目标、里程碑和动机... (支持 Markdown 格式)"
                className="w-full min-h-[500px] resize-none outline-none text-lg text-slate-600 font-mono leading-relaxed bg-slate-50 rounded-xl p-4 border border-slate-200 focus:border-blue-300 focus:ring-2 focus:ring-blue-100 transition-all"
                autoFocus
              />
            ) : (
              <div
                className="min-h-[300px] text-lg text-slate-600 leading-relaxed rounded-xl p-4 transition-colors border border-transparent hover:border-slate-200 hover:bg-slate-50/50 cursor-pointer group"
                onDoubleClick={() => setIsEditingContent(true)}
                title="双击编辑"
              >
                {formData.content ? (
                  <MarkdownRenderer content={formData.content} />
                ) : (
                  <div className="flex flex-col items-center justify-center h-[200px] text-slate-300">
                    <AlignLeft size={32} className="mb-3 opacity-50" />
                    <p className="italic">双击此处编辑目标描述...</p>
                    <p className="text-xs mt-1 opacity-70">支持 Markdown 格式</p>
                  </div>
                )}
                {/* Double-click hint on hover */}
                <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity text-xs text-slate-400 bg-white px-2 py-1 rounded shadow-sm">
                  双击编辑
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Category Modal */}
        <CategorySelectionModal
          isOpen={showCategoryModal}
          onClose={() => setShowCategoryModal(false)}
          categories={categories.map(c => ({
            id: c.id,
            name: c.name,
            color: c.color,
            subCategories: c.subcategories?.map(s => ({ id: s.id, name: s.name })) || []
          }))}
          initialCategoryId={selectedCategoryId}
          initialSubCategoryId={selectedSubCategoryId}
          onApply={handleCategoryApply}
        />
      </div>
    </div>
  );
};

export default GoalDetailView;
