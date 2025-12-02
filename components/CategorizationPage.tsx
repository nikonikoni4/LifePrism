
import React, { useState } from 'react';
import { 
  Search, 
  Filter, 
  Trash2, 
  Edit2, 
  Plus, 
  Check, 
  X as XIcon,
  MoreHorizontal 
} from 'lucide-react';
import { MOCK_CATEGORIES, MOCK_ACTIVITY_RECORDS } from '../constants';
import { CategoryDef, ActivityRecord } from '../types';

/* 
  === BACKEND API DATA REQUIREMENTS ===

  1. GET /api/categories
     - Description: Fetch the full hierarchy of categorization rules.
     - Response: CategoryDef[]
  
  2. POST /api/categories
     - Description: Create a new Level 1 Main Category.
     - Body: { name: string, color: string }
     - Response: { id: string, name: string, color: string, subCategories: [] }

  3. PUT /api/categories/:id
     - Description: Update a Main Category (Rename or Change Color).
     - Body: { name?: string, color?: string }
     - Response: Updated Category Object

  4. DELETE /api/categories/:id
     - Description: Delete a Main Category. 
     - Warning: Backend should handle reassigning orphaned records to 'Uncategorized' or delete cascadingly.

  5. POST /api/categories/:parentId/sub
     - Description: Add a Level 2 Sub-category to a parent.
     - Body: { name: string }
     - Response: { id: string, name: string }

  6. PUT /api/categories/:parentId/sub/:subId
     - Description: Rename a Sub-category.
     - Body: { name: string }

  7. DELETE /api/categories/:parentId/sub/:subId
     - Description: Delete a Sub-category.
*/

type Tab = 'settings' | 'review';

const CategorizationPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('settings');
  // Lifted state to manage categories globally for the page
  const [categories, setCategories] = useState<CategoryDef[]>(MOCK_CATEGORIES);

  return (
    <div className="max-w-7xl mx-auto h-[calc(100vh-100px)] flex flex-col">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4 flex-shrink-0">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Categorization</h1>
          <p className="text-slate-500 mt-1 font-medium">Manage activity data and classification rules.</p>
        </div>

        {/* Segmented Control */}
        <div className="bg-gray-100 p-1.5 rounded-xl inline-flex font-semibold text-sm">
           <button
            onClick={() => setActiveTab('settings')}
            className={`px-6 py-2 rounded-lg transition-all ${
              activeTab === 'settings'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Category Settings
          </button>
          <button
            onClick={() => setActiveTab('review')}
            className={`px-6 py-2 rounded-lg transition-all ${
              activeTab === 'review'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Data Review
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 min-h-0 bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
        {activeTab === 'review' ? (
            <DataReviewTab categories={categories} />
        ) : (
            <CategorySettingsTab categories={categories} setCategories={setCategories} />
        )}
      </div>
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/*                               Data Review Tab                              */
/* -------------------------------------------------------------------------- */

interface DataReviewTabProps {
    categories: CategoryDef[];
}

const DataReviewTab: React.FC<DataReviewTabProps> = ({ categories }) => {
  const [showUncategorized, setShowUncategorized] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [records, setRecords] = useState<ActivityRecord[]>(MOCK_ACTIVITY_RECORDS);
  const [dateRange, setDateRange] = useState({ start: '2023-10-25', end: '2023-10-26' });

  const filteredRecords = records.filter(record => {
    const matchesSearch = 
      record.appName.toLowerCase().includes(searchTerm.toLowerCase()) || 
      record.windowTitle.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesUncategorized = showUncategorized 
      ? (record.categoryId === 'other' && record.subCategoryId === 'untracked') 
      : true;

    return matchesSearch && matchesUncategorized;
  });

  const getCategoryColor = (catId: string) => {
    const cat = categories.find(c => c.id === catId);
    return cat ? cat.color : '#CBD5E1';
  };

  return (
    <div className="flex flex-col h-full">
      {/* Filter Bar */}
      <div className="p-6 border-b border-gray-100 flex flex-col xl:flex-row gap-4 justify-between items-center bg-gray-50/50">
        <div className="flex items-center gap-4 w-full xl:w-auto">
          {/* Date Picker Range */}
          <div className="flex items-center bg-white border border-gray-200 rounded-xl px-2 py-1.5 text-sm font-medium text-slate-600 shadow-sm gap-2">
            <input 
                type="date" 
                value={dateRange.start}
                onChange={(e) => setDateRange(prev => ({...prev, start: e.target.value}))}
                className="bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-100 rounded-lg p-1 text-slate-600 text-xs font-bold font-mono cursor-pointer hover:bg-gray-50 transition-colors"
            />
            <span className="text-gray-300">→</span>
            <input 
                type="date" 
                value={dateRange.end}
                onChange={(e) => setDateRange(prev => ({...prev, end: e.target.value}))}
                className="bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-100 rounded-lg p-1 text-slate-600 text-xs font-bold font-mono cursor-pointer hover:bg-gray-50 transition-colors"
            />
          </div>
          
          {/* Search */}
          <div className="relative flex-1 xl:w-64">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input 
              type="text" 
              placeholder="Search App or Title..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300"
            />
          </div>
        </div>

        {/* Toggles */}
        <div className="flex items-center gap-6 w-full xl:w-auto justify-end">
           <div className="flex items-center gap-3 cursor-pointer" onClick={() => setShowUncategorized(!showUncategorized)}>
              <span className="text-sm font-semibold text-slate-600">Show Uncategorized Only</span>
              <div className={`w-11 h-6 rounded-full p-1 transition-colors ${showUncategorized ? 'bg-indigo-600' : 'bg-gray-200'}`}>
                  <div className={`w-4 h-4 bg-white rounded-full shadow-sm transform transition-transform ${showUncategorized ? 'translate-x-5' : 'translate-x-0'}`} />
              </div>
           </div>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-gray-50 sticky top-0 z-10">
            <tr>
              <th className="py-4 px-6 w-12 border-b border-gray-100">
                <input type="checkbox" className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
              </th>
              <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100">App Info</th>
              <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100">Window Title</th>
              <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-48">Category (L1)</th>
              <th className="py-4 px-6 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-gray-100 w-48">Sub-category (L2)</th>
              <th className="py-4 px-6 w-20 border-b border-gray-100"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {filteredRecords.map((record) => (
              <tr key={record.id} className="hover:bg-slate-50/80 transition-colors group">
                <td className="py-4 px-6">
                  <input type="checkbox" className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                </td>
                <td className="py-4 px-6">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center text-slate-600 font-bold text-sm border border-gray-200">
                      {record.appName.charAt(0)}
                    </div>
                    <div>
                      <div className="text-sm font-bold text-slate-900">{record.appName}</div>
                      <div className="text-xs text-slate-400 mt-0.5 font-medium">{record.aiDescription}</div>
                    </div>
                  </div>
                </td>
                <td className="py-4 px-6">
                  <div className="text-sm text-slate-600 font-medium truncate max-w-xs" title={record.windowTitle}>
                    {record.windowTitle}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">{record.timestamp} • {record.duration}</div>
                </td>
                <td className="py-4 px-6">
                  <div className="relative">
                    <select 
                      className="appearance-none w-full pl-3 pr-8 py-1.5 bg-white border border-gray-200 rounded-lg text-sm font-semibold text-slate-700 focus:outline-none focus:border-blue-400 cursor-pointer hover:bg-gray-50"
                      defaultValue={record.categoryId}
                    >
                      {categories.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))}
                    </select>
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getCategoryColor(record.categoryId) }}></div>
                    </div>
                  </div>
                </td>
                <td className="py-4 px-6">
                  <div className="relative">
                     <select 
                      className="appearance-none w-full px-3 py-1.5 bg-gray-50 border border-transparent hover:border-gray-200 rounded-lg text-sm text-slate-600 focus:outline-none focus:bg-white focus:border-blue-400 cursor-pointer"
                      defaultValue={record.subCategoryId}
                    >
                      {categories.find(c => c.id === record.categoryId)?.subCategories.map(sub => (
                        <option key={sub.id} value={sub.id}>{sub.name}</option>
                      ))}
                    </select>
                  </div>
                </td>
                <td className="py-4 px-6 text-right">
                  <button className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100">
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        
        {filteredRecords.length === 0 && (
          <div className="p-12 text-center text-slate-400">
             <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4">
               <Filter size={24} className="text-gray-300" />
             </div>
             <p className="font-medium">No records found matching your filters.</p>
          </div>
        )}
      </div>
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/*                            Category Settings Tab                           */
/* -------------------------------------------------------------------------- */

interface CategorySettingsTabProps {
    categories: CategoryDef[];
    setCategories: React.Dispatch<React.SetStateAction<CategoryDef[]>>;
}

const CategorySettingsTab: React.FC<CategorySettingsTabProps> = ({ categories, setCategories }) => {
  const [selectedCatId, setSelectedCatId] = useState<string>(categories[0]?.id || '');
  
  // Edit State for L1 Category
  const [editingCatId, setEditingCatId] = useState<string | null>(null);
  const [editCatName, setEditCatName] = useState('');

  // Edit State for L2 Sub-category
  const [editingSubId, setEditingSubId] = useState<string | null>(null);
  const [editSubName, setEditSubName] = useState('');

  // Add State
  const [newSubName, setNewSubName] = useState('');

  const activeCategory = categories.find(c => c.id === selectedCatId) || categories[0];

  // --- L1 Logic ---

  const handleAddCategory = () => {
    const newId = `cat-${Date.now()}`;
    const colors = ['#F87171', '#34D399', '#A78BFA', '#F472B6', '#60A5FA'];
    const randomColor = colors[Math.floor(Math.random() * colors.length)];
    
    const newCat: CategoryDef = {
        id: newId,
        name: 'New Category',
        color: randomColor,
        subCategories: []
    };

    setCategories([...categories, newCat]);
    setSelectedCatId(newId);
    // Auto start editing
    setEditingCatId(newId);
    setEditCatName('New Category');
  };

  const handleDeleteCategory = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Are you sure? This will delete all sub-categories and associated rules.')) {
        const newCats = categories.filter(c => c.id !== id);
        setCategories(newCats);
        if (selectedCatId === id && newCats.length > 0) {
            setSelectedCatId(newCats[0].id);
        }
    }
  };

  const startEditCategory = (id: string, name: string, e: React.MouseEvent) => {
      e.stopPropagation();
      setEditingCatId(id);
      setEditCatName(name);
  };

  const saveEditCategory = (e: React.MouseEvent) => {
      e.stopPropagation();
      setCategories(categories.map(c => 
          c.id === editingCatId ? { ...c, name: editCatName } : c
      ));
      setEditingCatId(null);
  };

  const cancelEditCategory = (e: React.MouseEvent) => {
      e.stopPropagation();
      setEditingCatId(null);
  };

  // --- L2 Logic ---

  const handleAddSubCategory = () => {
      if (!newSubName.trim()) return;
      const newSubId = `sub-${Date.now()}`;
      
      setCategories(categories.map(c => {
          if (c.id === activeCategory.id) {
              return {
                  ...c,
                  subCategories: [...c.subCategories, { id: newSubId, name: newSubName }]
              };
          }
          return c;
      }));
      setNewSubName('');
  };

  const handleDeleteSubCategory = (subId: string) => {
    setCategories(categories.map(c => {
        if (c.id === activeCategory.id) {
            return {
                ...c,
                subCategories: c.subCategories.filter(s => s.id !== subId)
            };
        }
        return c;
    }));
  };

  const startEditSub = (subId: string, name: string) => {
      setEditingSubId(subId);
      setEditSubName(name);
  };

  const saveEditSub = () => {
    setCategories(categories.map(c => {
        if (c.id === activeCategory.id) {
            return {
                ...c,
                subCategories: c.subCategories.map(s => 
                    s.id === editingSubId ? { ...s, name: editSubName } : s
                )
            };
        }
        return c;
    }));
    setEditingSubId(null);
  };

  return (
    <div className="flex h-full divide-x divide-gray-100">
      
      {/* Left Column: L1 Categories */}
      <div className="w-1/3 min-w-[250px] bg-gray-50/50 flex flex-col p-6">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4 px-2">Main Categories</h3>
        
        <div className="flex-1 space-y-2 overflow-y-auto">
          {categories.map((cat) => {
            const isEditing = editingCatId === cat.id;
            const isSelected = selectedCatId === cat.id;

            return (
                <div 
                    key={cat.id}
                    onClick={() => !isEditing && setSelectedCatId(cat.id)}
                    className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer border transition-all ${
                        isSelected 
                        ? 'bg-white border-blue-200 shadow-sm ring-1 ring-blue-100' 
                        : 'bg-transparent border-transparent hover:bg-white hover:border-gray-200'
                    }`}
                >
                    {isEditing ? (
                        <div className="flex items-center gap-2 w-full" onClick={e => e.stopPropagation()}>
                            <input 
                                value={editCatName}
                                onChange={(e) => setEditCatName(e.target.value)}
                                className="w-full bg-white border border-blue-300 rounded px-2 py-1 text-sm focus:outline-none"
                                autoFocus
                            />
                            <button onClick={saveEditCategory} className="p-1 text-green-600 hover:bg-green-50 rounded"><Check size={14} /></button>
                            <button onClick={cancelEditCategory} className="p-1 text-gray-400 hover:bg-gray-100 rounded"><XIcon size={14} /></button>
                        </div>
                    ) : (
                        <>
                            <div className="flex items-center gap-3">
                                <div 
                                className="w-5 h-5 rounded-full border border-black/10 shadow-inner flex-shrink-0" 
                                style={{ backgroundColor: cat.color }}
                                />
                                <span className={`font-semibold ${isSelected ? 'text-slate-900' : 'text-slate-600'}`}>
                                {cat.name}
                                </span>
                            </div>
                            <div className={`flex items-center gap-1 opacity-0 ${isSelected ? 'opacity-100' : 'group-hover:opacity-100'} transition-opacity`}>
                                <button onClick={(e) => startEditCategory(cat.id, cat.name, e)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg">
                                    <Edit2 size={14} />
                                </button>
                                <button onClick={(e) => handleDeleteCategory(cat.id, e)} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg">
                                    <Trash2 size={14} />
                                </button>
                            </div>
                        </>
                    )}
                </div>
            );
          })}
        </div>

        <button 
            onClick={handleAddCategory}
            className="mt-4 flex items-center justify-center gap-2 w-full py-3 bg-white border border-dashed border-gray-300 rounded-xl text-slate-500 font-bold text-sm hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-all"
        >
          <Plus size={16} />
          Add New Category
        </button>
      </div>

      {/* Right Column: L2 Sub-categories */}
      <div className="flex-1 p-8 flex flex-col bg-white">
        {activeCategory ? (
            <>
                <div className="flex justify-between items-end mb-8 border-b border-gray-100 pb-6">
                <div>
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Sub-categories for</span>
                    <div className="flex items-center gap-3 mt-1">
                    <h2 className="text-2xl font-bold text-slate-900" style={{ color: activeCategory.color }}>
                        {activeCategory.name}
                    </h2>
                    <span className="bg-gray-100 text-gray-500 text-xs font-bold px-2 py-1 rounded-md">
                        {activeCategory.subCategories.length} items
                    </span>
                    </div>
                </div>
                </div>

                <div className="space-y-3 flex-1 overflow-y-auto pr-2">
                {activeCategory.subCategories.map((sub) => {
                    const isEditing = editingSubId === sub.id;
                    return (
                        <div key={sub.id} className="flex items-center justify-between p-4 rounded-xl border border-gray-100 hover:border-gray-300 hover:shadow-sm transition-all group">
                            {isEditing ? (
                                <div className="flex items-center gap-2 w-full">
                                    <input 
                                        value={editSubName}
                                        onChange={(e) => setEditSubName(e.target.value)}
                                        className="flex-1 bg-gray-50 border border-blue-300 rounded px-2 py-1 text-sm font-semibold focus:outline-none"
                                        autoFocus
                                    />
                                    <button onClick={saveEditSub} className="p-2 text-green-600 hover:bg-green-50 rounded"><Check size={16} /></button>
                                    <button onClick={() => setEditingSubId(null)} className="p-2 text-gray-400 hover:bg-gray-100 rounded"><XIcon size={16} /></button>
                                </div>
                            ) : (
                                <>
                                    <span className="font-semibold text-slate-700">{sub.name}</span>
                                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button onClick={() => startEditSub(sub.id, sub.name)} className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg">
                                            <Edit2 size={16} />
                                        </button>
                                        <button onClick={() => handleDeleteSubCategory(sub.id)} className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg">
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </>
                            )}
                        </div>
                    );
                })}
                {activeCategory.subCategories.length === 0 && (
                    <div className="text-center py-12 text-slate-400 italic">
                        No sub-categories defined. Add one below.
                    </div>
                )}
                </div>

                <div className="mt-6 pt-6 border-t border-gray-100">
                <label className="block text-xs font-bold text-slate-500 mb-2 uppercase">Create new sub-category</label>
                <div className="flex gap-3">
                    <input 
                    type="text" 
                    value={newSubName}
                    onChange={(e) => setNewSubName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAddSubCategory()}
                    placeholder={`Add to ${activeCategory.name}...`}
                    className="flex-1 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300 transition-all"
                    />
                    <button 
                        onClick={handleAddSubCategory}
                        className="px-6 bg-slate-900 text-white rounded-xl font-bold text-sm hover:bg-slate-800 transition-colors shadow-lg shadow-slate-200"
                    >
                    Add
                    </button>
                </div>
                </div>
            </>
        ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
                Select a category to manage details
            </div>
        )}
      </div>

    </div>
  );
};

export default CategorizationPage;
