
import React, { useState, useEffect } from 'react';
import { ChevronLeft, Save, Clock, Calendar, AlignLeft, Folder, ChevronDown, Palette, Check, Activity, Loader2, Edit3, Eye } from 'lucide-react';
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
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [categories, setCategories] = useState<CategoryTreeItem[]>([]);
  const [isEditingContent, setIsEditingContent] = useState(false);

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

  const handleSave = async () => {
    if (!formData) return;

    try {
      setSaving(true);
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
      onSave(updatedGoal);
    } catch (err) {
      console.error('Failed to save goal:', err);
    } finally {
      setSaving(false);
    }
  };

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
      <div className="flex items-center justify-between px-8 py-6 border-b border-slate-50 bg-white/80 backdrop-blur-md sticky top-0 z-20">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-slate-800 transition-all group"
        >
          <div className="p-2.5 rounded-2xl bg-slate-50 group-hover:bg-slate-100 transition-colors">
            <ChevronLeft size={20} />
          </div>
          <span className="font-bold text-xs uppercase tracking-widest">Back to Goals</span>
        </button>

        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-3 bg-slate-900 text-white rounded-xl font-bold text-xs uppercase tracking-wider hover:bg-blue-600 hover:shadow-lg hover:shadow-blue-500/20 transition-all transform active:scale-95 disabled:opacity-50"
        >
          {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          Save Changes
        </button>
      </div>

      {/* Main Content Scrollable Area */}
      <div className="flex-1 overflow-y-auto no-scrollbar p-8 md:p-12 w-full max-w-5xl mx-auto">

        {/* Title Input (Huge) */}
        <div className="mb-4 animate-fade-in" style={{ animationDelay: '100ms' }}>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => handleChange('name', e.target.value)}
            placeholder="Enter Goal Title..."
            className="w-full text-4xl md:text-6xl font-black text-slate-800 bg-transparent border-none outline-none placeholder-slate-200 leading-tight tracking-tight"
          />
        </div>

        {/* Abstract/Summary Input */}
        <div className="mb-10 animate-fade-in" style={{ animationDelay: '120ms' }}>
          <input
            type="text"
            value={formData.abstract || ''}
            onChange={(e) => handleChange('abstract', e.target.value)}
            placeholder="Add a brief summary or alias for this goal..."
            className="w-full text-lg md:text-xl font-medium text-slate-500 bg-transparent border-none outline-none placeholder-slate-300 leading-relaxed"
          />
        </div>

        {/* Metadata Row */}
        <div className="flex flex-wrap items-center gap-6 mb-12 text-slate-400 font-medium text-sm border-y border-dashed border-slate-100 py-6 animate-fade-in" style={{ animationDelay: '150ms' }}>
          {/* Date Picker */}
          <div className="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-xl border border-slate-100">
            <Calendar size={16} className="text-slate-400" />
            <div className="flex flex-col">
              <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Target Date</span>
              <input
                type="date"
                value={formData.expectedFinishedAt || ''}
                onChange={(e) => handleChange('expectedFinishedAt', e.target.value)}
                className="bg-transparent text-slate-700 font-bold font-mono text-xs focus:outline-none p-0 w-28 cursor-pointer"
              />
            </div>
          </div>

          {/* Estimate Input */}
          <div className="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-xl border border-slate-100">
            <Clock size={16} className="text-slate-400" />
            <div className="flex flex-col">
              <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Hours</span>
              <input
                type="number"
                value={formatHoursForInput(formData.expectedHours)}
                onChange={(e) => handleChange('expectedHours', parseHoursFromInput(e.target.value))}
                className="bg-transparent text-slate-700 font-bold font-mono text-xs w-16 focus:outline-none placeholder-slate-300"
                placeholder="60"
                min={0}
              />
            </div>
          </div>

          {/* Color Picker */}
          <div className="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-xl border border-slate-100 hover:bg-white hover:border-blue-200 transition-all group min-w-[140px]">
            <Palette size={16} className="text-slate-400 group-hover:text-purple-500 transition-colors" />
            <div className="flex flex-col gap-1">
              <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Color</span>
              <div className="flex gap-1.5 mt-0.5">
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
            className={`flex items-center gap-3 px-4 py-2 rounded-xl border transition-all min-w-[140px] group ${isCompleted
              ? 'bg-green-50 border-green-200 hover:bg-green-100'
              : 'bg-slate-50 border-slate-100 hover:bg-white hover:border-blue-200'
              }`}
          >
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center border transition-colors ${isCompleted
              ? 'bg-green-500 border-green-500 text-white'
              : 'bg-white border-slate-200 text-slate-300'
              }`}>
              {isCompleted ? <Check size={16} strokeWidth={3} /> : <Activity size={16} />}
            </div>
            <div className="flex flex-col items-start">
              <span className={`text-[9px] font-bold uppercase tracking-wider ${isCompleted ? 'text-green-600' : 'text-slate-400'}`}>Status</span>
              <span className={`text-xs font-bold ${isCompleted ? 'text-green-700' : 'text-slate-700'}`}>
                {isCompleted ? 'Completed' : 'In Progress'}
              </span>
            </div>
          </button>

          {/* Category Selector (Button Trigger) */}
          <button
            onClick={() => setShowCategoryModal(true)}
            className="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-xl border border-slate-100 hover:border-blue-200 hover:bg-white hover:shadow-sm transition-all text-left group min-w-[140px]"
          >
            <Folder size={16} className="text-slate-400 group-hover:text-blue-500 transition-colors" />
            <div className="flex flex-col flex-1">
              <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Category</span>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  {activeCategory ? (
                    <>
                      <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: activeCategory.color }}></div>
                      <span className="text-slate-700 font-bold text-xs whitespace-nowrap">
                        {activeCategory.name}
                        {activeSubCategory && <span className="opacity-50"> / {activeSubCategory.name}</span>}
                      </span>
                    </>
                  ) : (
                    <span className="text-slate-700 font-bold text-xs">Uncategorized</span>
                  )}
                </div>
                <ChevronDown size={12} className="text-slate-400" />
              </div>
            </div>
          </button>
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
