# Behavior Summary 显示功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Timeline 页面右侧新增 Behavior Summary 显示区域，展示基于截图分析的用户行为总结，支持点击查看详情

**Architecture:** 复用 CustomBlockLayer 的 UI 模式，创建 BehaviorBlockLayer（只读色块）和 BehaviorDetailPanel（滑出详情面板）两个新组件。后端提供 Mock 数据 API，前端通过 BehaviorAPI 调用并渲染。

**Tech Stack:** React, TypeScript, Tailwind CSS, FastAPI, Pydantic

---

## 文件结构

### 新增文件
- `frontend/apps/lifewatch/pages/timeline/components/BehaviorBlockLayer.tsx` - 右侧 behavior 色块层组件
- `frontend/apps/lifewatch/pages/timeline/components/BehaviorDetailPanel.tsx` - 详情面板组件

### 修改文件
- `lifeprism/server/schemas/timeline_schemas.py` - 添加 Behavior Schema
- `lifeprism/server/api/timeline_api.py` - 添加 behavior_summary API 端点
- `frontend/apps/lifewatch/pages/timeline/types.tsx` - 添加 Behavior 类型定义
- `frontend/apps/lifewatch/pages/timeline/api.ts` - 添加 BehaviorAPI
- `frontend/apps/lifewatch/pages/timeline/components/index.ts` - 导出新组件
- `frontend/apps/lifewatch/pages/timeline/Timeline.tsx` - 集成 Behavior 功能

---

### Task 1: 后端 Schema 定义

**Files:**
- Modify: `lifeprism/server/schemas/timeline_schemas.py`

- [ ] **Step 1: 在文件末尾添加 Behavior Schema**

```python
# ============================================================================
# Behavior Summary 相关 Schema
# ============================================================================

class BehaviorAnalysisItem(BaseModel):
    """单个行为分析项"""
    start_time: str = Field(..., description="开始时间，格式：YYYY-MM-DD HH:MM:SS")
    end_time: str = Field(..., description="结束时间，格式：YYYY-MM-DD HH:MM:SS")
    screen_count: int = Field(..., description="截图数量")
    behavior_summary: str = Field(..., description="总结性描述")
    behaviors: str = Field(..., description="分点行为（带序号的文本）")
    created_at: str = Field(..., description="创建时间")


class BehaviorAnalysisResponse(BaseModel):
    """行为分析响应"""
    behavior_list: list[BehaviorAnalysisItem] = Field(default_factory=list, description="行为分析列表")
```

- [ ] **Step 2: 验证 Schema 定义**

检查：
- 所有字段类型正确
- Field 描述清晰
- 导入 BaseModel 和 Field（文件顶部已有）

- [ ] **Step 3: Commit**

```bash
git add lifeprism/server/schemas/timeline_schemas.py
git commit -m "feat(schema): 添加 Behavior Summary Schema 定义"
```

---

### Task 2: 后端 API 端点（Mock 数据）

**Files:**
- Modify: `lifeprism/server/api/timeline_api.py`

- [ ] **Step 1: 在文件顶部导入新 Schema**

在现有导入语句后添加：

```python
from lifeprism.server.schemas.timeline_schemas import (
    # ... 现有导入
    BehaviorAnalysisResponse,
)
```

- [ ] **Step 2: 在文件末尾添加 behavior_summary 端点**

```python
@router.get("/behavior_summary", response_model=BehaviorAnalysisResponse)
async def get_behavior_summary(
    date: str = Query(..., description="查询日期 (YYYY-MM-DD)")
):
    """
    获取指定日期的行为分析数据（第一阶段：Mock 数据）
    
    - **date**: 查询日期，格式 YYYY-MM-DD
    """
    import json
    from pathlib import Path
    
    # 读取 mock 数据
    mock_file = Path(__file__).parent.parent.parent.parent / "test" / "explore" / "monitor_prompt" / "behavior_summary.json"
    
    try:
        with open(mock_file, "r", encoding="utf-8") as f:
            mock_data = json.load(f)
        return BehaviorAnalysisResponse(behavior_list=mock_data)
    except Exception as e:
        # 如果读取失败，返回空列表
        return BehaviorAnalysisResponse(behavior_list=[])
```

- [ ] **Step 3: 测试 API 端点**

启动后端服务，访问：
```
http://localhost:8000/api/v2/timeline/behavior_summary?date=2026-04-19
```

预期：返回 JSON 数据，包含 behavior_list 数组

- [ ] **Step 4: Commit**

```bash
git add lifeprism/server/api/timeline_api.py
git commit -m "feat(api): 添加 behavior_summary API 端点（Mock 数据）"
```

---

### Task 3: 前端类型定义

**Files:**
- Modify: `frontend/apps/lifewatch/pages/timeline/types.tsx`

- [ ] **Step 1: 在文件末尾添加 Behavior 类型**

```typescript
// ============================================================================
// Behavior Summary 相关类型
// ============================================================================

/** 单个行为分析项 */
export interface BehaviorAnalysisItem {
  start_time: string;       // 开始时间，格式：YYYY-MM-DD HH:MM:SS
  end_time: string;         // 结束时间，格式：YYYY-MM-DD HH:MM:SS
  screen_count: number;     // 截图数量
  behavior_summary: string; // 总结性描述
  behaviors: string;        // 分点行为（带序号的文本）
  created_at: string;       // 创建时间
}

/** 行为分析响应 */
export interface BehaviorAnalysisResponse {
  behavior_list: BehaviorAnalysisItem[];
}
```

- [ ] **Step 2: 验证类型定义**

检查：
- 字段名与后端 Schema 一致（snake_case）
- 注释清晰
- 导出语句正确

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/lifewatch/pages/timeline/types.tsx
git commit -m "feat(types): 添加 Behavior Summary 类型定义"
```

---

### Task 4: 前端 API 封装

**Files:**
- Modify: `frontend/apps/lifewatch/pages/timeline/api.ts`

- [ ] **Step 1: 在文件顶部导入新类型**

在现有导入语句后添加：

```typescript
import {
    TimelineStatsResponse,
    TimelineTimeOverviewResponse,
    BehaviorAnalysisResponse,  // 新增
} from './types';
```

- [ ] **Step 2: 在文件末尾添加 BehaviorAPI**

```typescript
// ============================================================================
// Behavior Summary API
// ============================================================================

export const BehaviorAPI = {
    /**
     * 获取指定日期的行为分析数据
     * 
     * @param date 查询日期 (YYYY-MM-DD)
     * @returns 行为分析列表
     */
    async getBehaviorSummary(date: string): Promise<BehaviorAnalysisResponse> {
        const params = new URLSearchParams({ date });
        const response = await fetch(
            `${getApiBase()}/timeline/behavior_summary?${params.toString()}`
        );
        
        if (!response.ok) {
            throw new Error(`Failed to fetch behavior summary: ${response.statusText}`);
        }
        
        return response.json();
    }
};
```

- [ ] **Step 3: 验证 API 封装**

检查：
- 导入路径正确
- API 端点路径正确（/timeline/behavior_summary）
- 错误处理完整

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/lifewatch/pages/timeline/api.ts
git commit -m "feat(api): 添加 BehaviorAPI 封装"
```

---

### Task 5: BehaviorBlockLayer 组件（第1部分：基础结构）

**Files:**
- Create: `frontend/apps/lifewatch/pages/timeline/components/BehaviorBlockLayer.tsx`

- [ ] **Step 1: 创建文件并添加导入和类型定义**

```typescript
/**
 * BehaviorBlockLayer 组件
 * 
 * 行为分析色块渲染层（只读）
 * 
 * 设计规范：
 * - 作为半透明背景层显示在 Timeline 右侧
 * - 使用浅蓝色（区别于 CustomBlock 的绿色）
 * - 左侧 3px 蓝色边框
 * - 只读显示，点击打开详情面板
 */

import React from 'react';
import { BehaviorAnalysisItem } from '../types';

interface BehaviorBlockLayerProps {
    behaviors: BehaviorAnalysisItem[];
    hourHeight: number;
    onBehaviorClick: (item: BehaviorAnalysisItem) => void;
    isLoading?: boolean;
}

/**
 * 将时间字符串转换为小时浮点数
 */
function timeToHour(timeStr: string): number {
    const timePart = timeStr.includes('T') 
        ? timeStr.split('T')[1] 
        : timeStr.split(' ')[1] || timeStr;
    const [hours, minutes] = timePart.split(':').map(Number);
    return hours + minutes / 60;
}

/**
 * 格式化 HH:MM
 */
function formatHHMM(hour: number): string {
    const h = Math.floor(hour);
    const m = Math.round((hour - h) * 60);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}
```

- [ ] **Step 2: 验证文件创建**

检查：
- 文件路径正确
- 导入语句无错误
- 工具函数定义完整

---

### Task 6: BehaviorBlockLayer 组件（第2部分：渲染逻辑）

**Files:**
- Modify: `frontend/apps/lifewatch/pages/timeline/components/BehaviorBlockLayer.tsx`

- [ ] **Step 1: 添加组件主体和渲染函数**

在文件末尾添加：

```typescript
const BehaviorBlockLayer: React.FC<BehaviorBlockLayerProps> = ({
    behaviors,
    hourHeight,
    onBehaviorClick,
    isLoading = false,
}) => {
    // 渲染单个色块
    const renderBlock = (behavior: BehaviorAnalysisItem) => {
        const startHour = timeToHour(behavior.start_time);
        const endHour = timeToHour(behavior.end_time);
        const top = startHour * hourHeight;
        const height = (endHour - startHour) * hourHeight;

        return (
            <div
                key={`block-${behavior.start_time}-${behavior.end_time}`}
                className="absolute w-full rounded-sm cursor-pointer
                           hover:opacity-80 transition-opacity duration-150"
                style={{
                    left: 0,
                    right: 0,
                    top: `${top}px`,
                    height: `${height}px`,
                    backgroundColor: 'rgba(191, 219, 254, 0.5)',
                    borderLeft: '3px solid #3b82f6',
                }}
                onClick={() => onBehaviorClick(behavior)}
            />
        );
    };

    // 渲染标签
    const renderLabel = (behavior: BehaviorAnalysisItem) => {
        const startHour = timeToHour(behavior.start_time);
        const endHour = timeToHour(behavior.end_time);
        const top = startHour * hourHeight;
        const height = (endHour - startHour) * hourHeight;
        
        const startTime = formatHHMM(startHour);
        const endTime = formatHHMM(endHour);

        return (
            <div
                key={`label-${behavior.start_time}-${behavior.end_time}`}
                className="absolute left-0 right-0 flex items-center justify-center
                           px-1.5 cursor-pointer overflow-hidden
                           transition-opacity duration-150 hover:opacity-80"
                style={{
                    top: `${top}px`,
                    height: `${height}px`,
                }}
                onClick={() => onBehaviorClick(behavior)}
            >
                <span className="text-[10px] font-medium text-gray-700 text-center leading-tight">
                    {startTime}~{endTime}
                </span>
            </div>
        );
    };

    return (
        <>
            {/* 背景色块层 */}
            <div
                className="absolute right-0 w-[100px] top-0"
                style={{ height: `${24 * hourHeight}px`, zIndex: 0 }}
            >
                {behaviors.map(renderBlock)}
            </div>

            {/* 标签区域 */}
            <div className="absolute right-0 w-[100px] top-0 bottom-0 z-[3]">
                <div className="relative h-full">
                    {behaviors.map(renderLabel)}
                </div>
            </div>

            {/* 空状态提示 */}
            {behaviors.length === 0 && !isLoading && (
                <div className="absolute right-0 w-[100px] h-full 
                                flex items-center justify-center 
                                pointer-events-none z-[2]">
                    <div className="flex flex-col items-center gap-1 text-gray-300">
                        <span className="text-[10px] font-medium text-center leading-tight">
                            暂无行为分析
                        </span>
                    </div>
                </div>
            )}
        </>
    );
};

export default BehaviorBlockLayer;
```

- [ ] **Step 2: 验证组件完整性**

检查：
- renderBlock 和 renderLabel 函数完整
- 样式类名正确（Tailwind CSS）
- 定位样式正确（right-0, w-[100px]）
- 导出语句存在

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/lifewatch/pages/timeline/components/BehaviorBlockLayer.tsx
git commit -m "feat(component): 添加 BehaviorBlockLayer 组件"
```

---

### Task 7: BehaviorDetailPanel 组件（第1部分：基础结构）

**Files:**
- Create: `frontend/apps/lifewatch/pages/timeline/components/BehaviorDetailPanel.tsx`

- [ ] **Step 1: 创建文件并添加导入和类型定义**

```typescript
/**
 * BehaviorDetailPanel 组件
 * 
 * 行为分析详情面板
 * 
 * 设计规范：
 * - 从右侧滑入的独立面板
 * - 宽度 400px
 * - 显示 behavior_summary 和 behaviors
 * - 点击遮罩层或关闭按钮关闭
 */

import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { BehaviorAnalysisItem } from '../types';

interface BehaviorDetailPanelProps {
    behavior: BehaviorAnalysisItem | null;
    isOpen: boolean;
    onClose: () => void;
}

/**
 * 格式化持续时长
 */
function formatDuration(startTime: string, endTime: string): string {
    const start = new Date(startTime.replace(' ', 'T'));
    const end = new Date(endTime.replace(' ', 'T'));
    const diffMs = end.getTime() - start.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);
    
    const hours = Math.floor(diffMinutes / 60);
    const minutes = diffMinutes % 60;
    
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
}

/**
 * 格式化时间为 HH:MM
 */
function formatTime(timeStr: string): string {
    const timePart = timeStr.includes('T') 
        ? timeStr.split('T')[1] 
        : timeStr.split(' ')[1] || timeStr;
    return timePart.substring(0, 5);
}

/**
 * 格式化日期为 YYYY-MM-DD
 */
function formatDate(timeStr: string): string {
    const datePart = timeStr.includes('T') 
        ? timeStr.split('T')[0] 
        : timeStr.split(' ')[0] || timeStr;
    return datePart;
}
```

- [ ] **Step 2: 验证文件创建**

检查：
- 文件路径正确
- 导入语句无错误
- 工具函数定义完整

---

### Task 8: BehaviorDetailPanel 组件（第2部分：面板UI）

**Files:**
- Modify: `frontend/apps/lifewatch/pages/timeline/components/BehaviorDetailPanel.tsx`

- [ ] **Step 1: 添加组件主体**

在文件末尾添加：

```typescript
const BehaviorDetailPanel: React.FC<BehaviorDetailPanelProps> = ({
    behavior,
    isOpen,
    onClose,
}) => {
    // ESC 键关闭面板
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isOpen) {
                onClose();
            }
        };
        window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [isOpen, onClose]);

    if (!isOpen || !behavior) {
        return null;
    }

    const date = formatDate(behavior.start_time);
    const startTime = formatTime(behavior.start_time);
    const endTime = formatTime(behavior.end_time);
    const duration = formatDuration(behavior.start_time, behavior.end_time);

    return (
        <>
            {/* 遮罩层 */}
            <div
                className="fixed inset-0 bg-black/30 z-40"
                onClick={onClose}
            />

            {/* 面板 */}
            <div
                className="fixed top-0 right-0 bottom-0 w-[400px] bg-white shadow-2xl z-50
                           flex flex-col animate-slide-in-right"
            >
                {/* 标题栏 */}
                <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b">
                    <h3 className="text-base font-semibold text-gray-800">行为分析详情</h3>
                    <button
                        onClick={onClose}
                        className="p-1 hover:bg-gray-200 rounded transition-colors"
                    >
                        <X size={20} className="text-gray-600" />
                    </button>
                </div>

                {/* 内容区域 */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                    {/* 基本信息 */}
                    <div className="space-y-2 text-sm">
                        <div className="flex items-center gap-2 text-gray-600">
                            <span>📅</span>
                            <span>{date}</span>
                        </div>
                        <div className="flex items-center gap-2 text-gray-600">
                            <span>⏰</span>
                            <span>{startTime} ~ {endTime} ({duration})</span>
                        </div>
                        <div className="flex items-center gap-2 text-gray-600">
                            <span>📸</span>
                            <span>{behavior.screen_count} 张截图</span>
                        </div>
                    </div>

                    {/* 分隔线 */}
                    <div className="border-t" />

                    {/* 总结 */}
                    <div>
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">总结：</h4>
                        <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                            {behavior.behavior_summary}
                        </p>
                    </div>

                    {/* 分隔线 */}
                    <div className="border-t" />

                    {/* 详细行为 */}
                    <div>
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">详细行为：</h4>
                        <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                            {behavior.behaviors}
                        </p>
                    </div>
                </div>
            </div>
        </>
    );
};

export default BehaviorDetailPanel;
```

- [ ] **Step 2: 添加滑入动画到全局样式**

在 `frontend/apps/lifewatch/src/index.css` 或相应的全局样式文件中添加：

```css
@keyframes slide-in-right {
  from {
    transform: translateX(100%);
  }
  to {
    transform: translateX(0);
  }
}

.animate-slide-in-right {
  animation: slide-in-right 300ms ease-out;
}
```

- [ ] **Step 3: 验证组件完整性**

检查：
- ESC 键监听正确
- 遮罩层点击关闭功能
- 面板布局完整
- 文本格式保留（whitespace-pre-wrap）

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/lifewatch/pages/timeline/components/BehaviorDetailPanel.tsx
git add frontend/apps/lifewatch/src/index.css
git commit -m "feat(component): 添加 BehaviorDetailPanel 组件"
```

---

### Task 9: 导出新组件

**Files:**
- Modify: `frontend/apps/lifewatch/pages/timeline/components/index.ts`

- [ ] **Step 1: 添加新组件导出**

在文件末尾添加：

```typescript
export { default as BehaviorBlockLayer } from './BehaviorBlockLayer';
export { default as BehaviorDetailPanel } from './BehaviorDetailPanel';
```

- [ ] **Step 2: 验证导出**

检查：
- 导出语句语法正确
- 组件名称与文件名一致

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/lifewatch/pages/timeline/components/index.ts
git commit -m "feat(export): 导出 Behavior 相关组件"
```

---

### Task 10: Timeline.tsx 集成（第1部分：导入和状态）

**Files:**
- Modify: `frontend/apps/lifewatch/pages/timeline/Timeline.tsx`

- [ ] **Step 1: 添加新的导入语句**

在文件顶部的导入区域，找到现有的组件导入，添加：

```typescript
// 在现有的 CustomBlockLayer 导入附近添加
import { 
    CustomBlockLayer, 
    CustomBlockAPI, 
    UserCustomBlock, 
    TodoSelectItem,
    BehaviorBlockLayer,      // 新增
    BehaviorDetailPanel,     // 新增
} from './components';
```

在类型导入中添加：

```typescript
import {
    // ... 现有类型导入
    BehaviorAnalysisItem,    // 新增
} from './types';
```

在 API 导入中添加：

```typescript
import { 
    TimelineAPIV2, 
    ActivityLogsAPI, 
    CategoryAPI,
    BehaviorAPI,             // 新增
} from './api';
```

- [ ] **Step 2: 添加 Behavior 相关状态**

在组件内部，找到现有的状态定义区域（如 customBlocks 相关状态），在附近添加：

```typescript
// Behavior 相关状态
const [behaviors, setBehaviors] = useState<BehaviorAnalysisItem[]>([]);
const [selectedBehavior, setSelectedBehavior] = useState<BehaviorAnalysisItem | null>(null);
const [isBehaviorPanelOpen, setIsBehaviorPanelOpen] = useState(false);
const [isBehaviorsLoading, setIsBehaviorsLoading] = useState(false);
```

- [ ] **Step 3: 验证导入和状态**

检查：
- 所有导入路径正确
- 状态类型正确
- 没有重复导入

---

### Task 11: Timeline.tsx 集成（第2部分：数据加载）

**Files:**
- Modify: `frontend/apps/lifewatch/pages/timeline/Timeline.tsx`

- [ ] **Step 1: 添加 loadBehaviors 函数**

在组件内部，找到现有的数据加载函数（如 loadCustomBlocks），在附近添加：

```typescript
// 加载 behavior 数据
const loadBehaviors = useCallback(async () => {
    setIsBehaviorsLoading(true);
    try {
        const response = await BehaviorAPI.getBehaviorSummary(currentDate);
        setBehaviors(response.behavior_list);
    } catch (error) {
        console.error('Failed to load behaviors:', error);
        setBehaviors([]);
    } finally {
        setIsBehaviorsLoading(false);
    }
}, [currentDate]);
```

- [ ] **Step 2: 在 useEffect 中调用 loadBehaviors**

找到现有的 useEffect（监听 currentDate 变化的那个），在其中添加 loadBehaviors 调用：

```typescript
useEffect(() => {
    // ... 现有的加载逻辑（如 loadCustomBlocks）
    
    // 新增：加载 behavior 数据
    loadBehaviors();
}, [currentDate, /* 其他依赖 */, loadBehaviors]);
```

- [ ] **Step 3: 验证数据加载逻辑**

检查：
- useCallback 依赖项正确
- useEffect 依赖项包含 loadBehaviors
- 错误处理完整

---

### Task 12: Timeline.tsx 集成（第3部分：布局调整和组件渲染）

**Files:**
- Modify: `frontend/apps/lifewatch/pages/timeline/Timeline.tsx`

- [ ] **Step 1: 调整 Timeline 主体宽度**

找到 Timeline 主体的容器 div（通常包含 `left-[96px]` 的那个），修改其样式：

```typescript
// 原来：
<div className="absolute left-[96px] right-0 top-0 bottom-0">

// 修改为：
<div className="absolute left-[96px] right-[100px] top-0 bottom-0">
```

- [ ] **Step 2: 添加 BehaviorBlockLayer 组件**

在 Timeline 主体容器的同级位置（CustomBlockLayer 附近），添加：

```typescript
{/* BehaviorBlockLayer - 右侧 */}
<BehaviorBlockLayer
    behaviors={behaviors}
    hourHeight={hourHeight}
    onBehaviorClick={(item) => {
        setSelectedBehavior(item);
        setIsBehaviorPanelOpen(true);
    }}
    isLoading={isBehaviorsLoading}
/>
```

- [ ] **Step 3: 添加 BehaviorDetailPanel 组件**

在组件的返回 JSX 末尾（通常在最外层容器内），添加：

```typescript
{/* BehaviorDetailPanel - 滑出面板 */}
<BehaviorDetailPanel
    behavior={selectedBehavior}
    isOpen={isBehaviorPanelOpen}
    onClose={() => setIsBehaviorPanelOpen(false)}
/>
```

- [ ] **Step 4: 验证布局和组件集成**

检查：
- Timeline 主体宽度调整正确（right-[100px]）
- BehaviorBlockLayer 位置正确（在 Timeline 主体右侧）
- BehaviorDetailPanel 在最外层（不被其他元素遮挡）
- 所有 props 传递正确

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/lifewatch/pages/timeline/Timeline.tsx
git commit -m "feat(timeline): 集成 Behavior Summary 功能"
```

---

### Task 13: 功能测试

**Files:**
- Test: 整个功能

- [ ] **Step 1: 启动前后端服务**

```bash
# 启动后端
cd lifeprism
python -m lifeprism.server.main

# 启动前端（新终端）
cd frontend
npm run dev
```

- [ ] **Step 2: 测试 API 端点**

在浏览器访问：
```
http://localhost:8000/api/v2/timeline/behavior_summary?date=2026-04-19
```

预期：返回包含 behavior_list 的 JSON 数据

- [ ] **Step 3: 测试前端显示**

1. 打开 Timeline 页面
2. 检查右侧是否显示 Behavior 色块
3. 检查色块位置是否与时间范围匹配
4. 检查标签显示是否正确（时间范围）

- [ ] **Step 4: 测试交互功能**

1. 点击 Behavior 色块
2. 检查详情面板是否从右侧滑入
3. 检查详情面板内容是否完整（日期、时间、截图数、总结、详细行为）
4. 点击遮罩层，检查面板是否关闭
5. 再次打开面板，按 ESC 键，检查面板是否关闭

- [ ] **Step 5: 测试边界情况**

1. 切换到没有数据的日期，检查是否显示"暂无行为分析"
2. 检查跨小时的 behavior 是否正确显示
3. 检查 Timeline 主体宽度是否正确缩小

- [ ] **Step 6: 记录测试结果**

如果发现问题，记录到 `docs/temp/behavior-summary-test-issues.md`

---

### Task 14: UI 调优和最终提交

**Files:**
- Modify: 根据测试结果调整

- [ ] **Step 1: 检查视觉效果**

1. 色块颜色是否与设计一致（浅蓝色，区别于 CustomBlock）
2. 标签文字是否清晰可读
3. 悬停效果是否流畅
4. 详情面板滑入动画是否流畅

- [ ] **Step 2: 检查响应式布局**

1. 不同窗口大小下布局是否正常
2. Behavior 区域是否始终保持 100px 宽度
3. Timeline 主体是否正确缩小

- [ ] **Step 3: 性能检查**

1. 打开浏览器开发者工具 Network 面板
2. 检查 API 请求是否正常
3. 检查是否有重复请求
4. 检查控制台是否有错误或警告

- [ ] **Step 4: 代码审查**

1. 检查是否有 console.log 需要清理
2. 检查是否有未使用的导入
3. 检查代码格式是否一致

- [ ] **Step 5: 最终提交**

```bash
git add -A
git commit -m "feat(timeline): 完成 Behavior Summary 显示功能

- 添加后端 API 端点（Mock 数据）
- 添加 BehaviorBlockLayer 和 BehaviorDetailPanel 组件
- 集成到 Timeline 页面
- 调整布局，右侧新增 100px behavior 区域
- 支持点击查看详情，滑出面板显示完整信息"
```

- [ ] **Step 6: 更新文档**

在 `docs/temp/monitor/monitor_analysis_display.md` 中标记第一阶段已完成

---

## 实现完成检查清单

### 后端
- [ ] Schema 定义完整（BehaviorAnalysisItem, BehaviorAnalysisResponse）
- [ ] API 端点正常工作（/api/v2/timeline/behavior_summary）
- [ ] Mock 数据正确返回

### 前端
- [ ] 类型定义完整（types.tsx）
- [ ] API 封装正常（api.ts）
- [ ] BehaviorBlockLayer 组件完整且正常渲染
- [ ] BehaviorDetailPanel 组件完整且交互正常
- [ ] Timeline.tsx 集成完成
- [ ] 布局调整正确（Timeline 主体宽度缩小）

### 功能
- [ ] 页面加载时正确调用 API
- [ ] Mock 数据正确渲染为色块
- [ ] 色块位置和高度与时间范围匹配
- [ ] 点击色块打开详情面板
- [ ] 详情面板显示完整信息
- [ ] 关闭详情面板功能正常（遮罩层、关闭按钮、ESC 键）
- [ ] 切换日期时重新加载数据
- [ ] 空数据时显示空状态
- [ ] 跨小时的 behavior 正确显示

### UI
- [ ] Behavior 区域宽度为 100px
- [ ] Timeline 主体宽度正确缩小
- [ ] 色块颜色为浅蓝色（区别于 custom_block）
- [ ] 标签文字清晰可读
- [ ] 悬停效果正常
- [ ] 详情面板滑入动画流畅

---

## 后续工作（第二阶段）

第一阶段完成后，第二阶段需要实现：

1. **数据库集成**
   - 创建 `behavior_analysis` 表
   - 实现数据持久化
   - 实现增量更新逻辑

2. **数据生成**
   - 接入截图分析服务
   - 实现 LLM 语义合并
   - 实现定时/手动触发分析

3. **交互增强**
   - 支持手动编辑 behavior
   - 支持删除/重新生成
   - 支持导出分析报告

