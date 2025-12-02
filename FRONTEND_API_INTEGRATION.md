# Frontend API Integration Summary

## 已完成的工作

### 1. API Client Service
✅ **文件**: `frontend/services/categoryService.ts`
- 完整的 categoryPI 类，包含所有 7 个 CRUD 方法
- 与后端 API 完全对应
- 包含错误处理

### 2. CategorizationPage 需要的修改

由于文件较大(551行)，这里提供关键修改点：

#### 修改 1: 导入 API 服务和添加 useEffect
**位置**: 文件顶部 (第 1-13 行)
```tsx
import React, { useState, useEffect } from 'react';  // 添加 useEffect
import { categoryPI } from '../services/categoryService';  // 新增这一行
```

#### 修改 2: 替换状态初始化和添加加载逻辑
**位置**: CategorizationPage 组件内 (约第 52-56 行)

替换：
```tsx
const [categories, setCategories] = useState<CategoryDef[]>(MOCK_CATEGORIES);
```

为：
```tsx
const [categories, setCategories] = useState<CategoryDef[]>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

// Load categories from API on mount
useEffect(() => {
  loadCategories();
}, []);

const loadCategories = async () => {
  try {
    setLoading(true);
    setError(null);
    const data = await categoryPI.getAllCategories();
    setCategories(data);
  } catch (err) {
    console.error('Failed to load categories:', err);
    setError('Failed to load categories. Using fallback data.');
    setCategories(MOCK_CATEGORIES);  // Fallback
  } finally {
    setLoading(false);
  }
};
```

#### 修改 3-9: 更新 CategorySettingsTab 的 CRUD 函数

所有函数都需要改为 async 并调用 API。以下是修改列表：

**3. handleAddCategory** (约第 316 行)
```tsx
const handleAddCategory = async () => {
  const colors = ['#F87171', '#34D399', '#A78BFA', '#F472B6', '#60A5FA'];
  const randomColor = colors[Math.floor(Math.random() * colors.length)]
  
  try {
    const newCat = await categoryPI.createCategory('New Category', randomColor);
    setCategories([...categories, newCat]);
    setSelectedCatId(newCat.id);
    setEditingCatId(newCat.id);
    setEditCatName('New Category');
  } catch (error) {
    console.error('Failed to create category:', error);
    alert('Failed to create category. Please try again.');
  }
};
```

**4. handleDeleteCategory** (约第 335 行)
```tsx
const handleDeleteCategory = async (id: string, e: React.MouseEvent) => {
  e.stopPropagation();
  if (confirm('Are you sure? This will delete all sub-categories and associated rules.')) {
    try {
      await categoryPI.deleteCategory(id);
      const newCats = categories.filter(c => c.id !== id);
      setCategories(newCats);
      if (selectedCatId === id && newCats.length > 0) {
        setSelectedCatId(newCats[0].id);
      }
    } catch (error) {
      console.error('Failed to delete category:', error);
      alert('Failed to delete category. Please try again.');
    }
  }
};
```

**5. saveEditCategory** (约第 352 行)
```tsx
const saveEditCategory = async (e: React.MouseEvent) => {
  e.stopPropagation();
  if (!editingCatId) return;
  
  try {
    const updated = await categoryPI.updateCategory(editingCatId, { name: editCatName });
    setCategories(categories.map(c => 
      c.id === editingCatId ? updated : c
    ));
    setEditingCatId(null);
  } catch (error) {
    console.error('Failed to update category:', error);
    alert('Failed to update category. Please try again.');
  }
};
```

**6. handleAddSubCategory** (约第 366 行)
```tsx
const handleAddSubCategory = async () => {
  if (!newSubName.trim() || !activeCategory) return;
  
  try {
    const newSub = await categoryPI.createSubCategory(activeCategory.id, newSubName);
    setCategories(categories.map(c => {
      if (c.id === activeCategory.id) {
        return {
          ...c,
          subCategories: [...c.subCategories, newSub]
        };
      }
      return c;
    }));
    setNewSubName('');
  } catch (error) {
    console.error('Failed to create sub-category:', error);
    alert('Failed to create sub-category. Please try again.');
  }
};
```

**7. handleDeleteSubCategory** (约第 382 行)
```tsx
const handleDeleteSubCategory = async (subId: string) => {
  if (!activeCategory) return;
  
  try {
    await categoryPI.deleteSubCategory(activeCategory.id, subId);
    setCategories(categories.map(c => {
      if (c.id === activeCategory.id) {
        return {
          ...c,
          subCategories: c.subCategories.filter(s => s.id !== subId)
        };
      }
      return c;
    }));
  } catch (error) {
    console.error('Failed to delete sub-category:', error);
    alert('Failed to delete sub-category. Please try again.');
  }
};
```

**8. saveEditSub** (约第 399 行)
```tsx
const saveEditSub = async () => {
  if (!activeCategory || !editingSubId) return;
  
  try {
    const updated = await categoryPI.updateSubCategory(activeCategory.id, editingSubId, editSubName);
    setCategories(categories.map(c => {
      if (c.id === activeCategory.id) {
        return {
          ...c,
          subCategories: c.subCategories.map(s => 
            s.id === editingSubId ? updated : s
          )
        };
      }
      return c;
    }));
    setEditingSubId(null);
  } catch (error) {
    console.error('Failed to update sub-category:', error);
    alert('Failed to update sub-category. Please try again.');
  }
};
```

## 测试步骤

1. **启动后端服务器**:
   ```bash
   cd lifewatch/server
   uvicorn main:app --reload
   ```

2. **启动前端服务器**:
   ```bash
   cd frontend
   npm run dev
   ```

3. **测试功能**:
   - 页面加载时应该从 API 获取分类数据
   - 尝试添加新分类
   - 尝试编辑分类名称
   - 尝试添加/编辑/删除子分类
   - 尝试删除主分类

4. **检查浏览器控制台**:
   - 查看 Network 标签确认 API 调用
   - 查看 Console 标签查看任何错误

## 注意事项

- 所有 API 调用都包含错误处理
- 如果 API 失败，会显示 alert 提示用户
- 初始加载失败时会回退到 MOCK_CATEGORIES
- 所有修改都会立即反映到后端数据库

## 文件状态

✅ `frontend/services/categoryService.ts` - 已创建
⏳ `frontend/components/CategorizationPage.tsx` - 需要手动应用上述修改

由于文件较大(551行)，建议您手动应用上述修改，或者告诉我您希望我创建一个完整的新文件。
