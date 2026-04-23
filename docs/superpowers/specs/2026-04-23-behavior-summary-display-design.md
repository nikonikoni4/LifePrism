# Behavior Summary 显示功能设计文档

## 文档信息

- **创建日期**：2026-04-23
- **设计阶段**：第一阶段 - 前端显示与 GET API 调用（Mock 数据）
- **相关草稿**：`docs/temp/monitor/monitor_analysis_display.md`

## 1. 功能概述

为 Timeline 页面新增 Behavior Summary 显示功能，展示基于截图分析得到的用户行为总结。用户可以查看每个时间段的行为摘要，点击后查看详细的行为分析内容。

### 1.1 核心目标

- 在 Timeline 右侧新增 Behavior 显示区域
- 复用 CustomBlockLayer 的 UI 模式，保持交互一致性
- 实现点击查看详情的交互流程
- 第一阶段使用 Mock 数据，不连接数据库

### 1.2 用户价值

- 快速了解某个时间段的主要活动
- 通过 AI 分析获得更高层次的行为总结
- 补充 Timeline 原有的细粒度活动记录

## 2. 整体架构设计

### 2.1 组件结构

```
Timeline.tsx (主页面)
├── CustomBlockLayer (左侧，现有)
├── BehaviorBlockLayer (右侧，新增)
│   ├── 色块渲染层
│   ├── 标签区域
│   └── 详情面板触发
└── BehaviorDetailPanel (右侧详情面板，新增)
    ├── behavior_summary 显示
    └── behaviors 文本显示
```

### 2.2 数据流

```
Timeline.tsx
  ↓ 调用 API
BehaviorAPI.getBehaviorSummary(date)
  ↓ 返回 mock 数据
BehaviorBlockLayer (渲染色块)
  ↓ 用户点击
BehaviorDetailPanel (显示详情)
```

### 2.3 布局调整

**当前布局**：
```
[时间刻度 64px] [CustomBlock 80px] [Timeline主体] [ActivityDetail面板]
```

**新布局**：
```
[时间刻度 64px] [CustomBlock 80px] [Timeline主体] [Behavior 100px] [DetailPanel]
```

**调整说明**：
- Timeline 主体宽度缩小，为 Behavior 区域腾出 100px 空间
- Behavior 区域略宽于 CustomBlock（100px vs 80px），因为文本可能更长
- DetailPanel 点击后从右侧滑出，覆盖在页面上

## 3. API 设计

### 3.1 后端 API

**端点**：`GET /api/v2/timeline/behavior_summary`

**文件位置**：`lifeprism/server/api/timeline_api.py`

**请求参数**：
```python
date: str  # YYYY-MM-DD 格式，查询日期
```

**响应 Schema**：
```python
class BehaviorAnalysisItem(BaseModel):
    start_time: str          # "2026-04-19 11:00:00"
    end_time: str            # "2026-04-19 12:10:00"
    screen_count: int        # 截图数量
    behavior_summary: str    # 总结性描述
    behaviors: str           # 分点行为（带序号的文本）
    created_at: str          # 创建时间

class BehaviorAnalysisResponse(BaseModel):
    behavior_list: list[BehaviorAnalysisItem]
```

**第一阶段实现**：
- 直接读取 `test/explore/monitor_prompt/behavior_summary.json`
- 不连接数据库
- 不做任何数据处理，原样返回 mock 数据

### 3.2 前端 API 封装

**文件位置**：`frontend/apps/lifewatch/pages/timeline/api.ts`

**新增代码**：
```typescript
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

## 4. 前端组件设计

### 4.1 BehaviorBlockLayer 组件

**文件位置**：`frontend/apps/lifewatch/pages/timeline/components/BehaviorBlockLayer.tsx`

**设计原则**：
- 复用 CustomBlockLayer 的代码结构
- 移除编辑/创建/删除功能（只读显示）
- 调整定位和样式

**Props 接口**：
```typescript
interface BehaviorBlockLayerProps {
  behaviors: BehaviorAnalysisItem[];  // behavior数据列表
  hourHeight: number;                 // 每小时像素高度
  onBehaviorClick: (item: BehaviorAnalysisItem) => void;  // 点击回调
  isLoading?: boolean;                // 加载状态
}
```

**核心功能**：
1. **色块渲染**：
   - 根据 `start_time` 和 `end_time` 计算位置和高度
   - 使用浅蓝色半透明背景（区别于 custom_block 的绿色）
   - 左侧 3px 蓝色边框
   - 支持跨小时显示

2. **标签显示**：
   - 显示时间范围（如 "11:00~12:10"）
   - 垂直居中显示在色块内
   - 文字大小：10px

3. **交互**：
   - 点击色块或标签触发 `onBehaviorClick`
   - 悬停时 opacity 变化（0.8）
   - 无编辑功能

**定位样式**：
```typescript
// 色块层
className="absolute right-0 w-[100px] top-0"
style={{ height: `${24 * hourHeight}px`, zIndex: 0 }}

// 标签区域
className="absolute right-0 w-[100px] top-0 bottom-0 z-[3]"
```

### 4.2 BehaviorDetailPanel 组件

**文件位置**：`frontend/apps/lifewatch/pages/timeline/components/BehaviorDetailPanel.tsx`

**Props 接口**：
```typescript
interface BehaviorDetailPanelProps {
  behavior: BehaviorAnalysisItem | null;  // 选中的behavior
  isOpen: boolean;                        // 是否打开
  onClose: () => void;                    // 关闭回调
}
```

**布局结构**：
```
┌─────────────────────────────────┐
│ [X] 行为分析详情                 │  <- 标题栏（固定）
├─────────────────────────────────┤
│ 📅 2026-04-19                   │
│ ⏰ 11:00 ~ 12:10 (1h 10m)       │
│ 📸 23 张截图                    │
├─────────────────────────────────┤
│ 总结：                          │
│ [behavior_summary 文本]         │  <- 可滚动区域
│                                 │
├─────────────────────────────────┤
│ 详细行为：                      │
│ [behaviors 文本]                │  <- 保留换行和序号
│ 1. xxx                          │
│ 2. xxx                          │
│ ...                             │
└─────────────────────────────────┘
```

**样式规范**：
- 面板宽度：400px
- 从右侧滑入动画（transition: transform 300ms）
- 背景：白色，带阴影
- 遮罩层：半透明黑色（bg-black/30）
- 标题栏：灰色背景，带关闭按钮
- 内容区域：可滚动，padding: 16px

**交互行为**：
- 点击遮罩层关闭面板
- 点击关闭按钮（X）关闭面板
- ESC 键关闭面板（可选）

**文本显示**：
- `behavior_summary`：普通段落，保留换行
- `behaviors`：使用 `white-space: pre-wrap` 保留原始格式
- 字体大小：14px
- 行高：1.6

### 4.3 类型定义

**文件位置**：`frontend/apps/lifewatch/pages/timeline/types.tsx`

**新增类型**：
```typescript
/** 单个行为分析项 */
export interface BehaviorAnalysisItem {
  start_time: string;       // 开始时间
  end_time: string;         // 结束时间
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

## 5. Timeline.tsx 集成

### 5.1 状态管理

**新增状态**：
```typescript
// Behavior 相关状态
const [behaviors, setBehaviors] = useState<BehaviorAnalysisItem[]>([]);
const [selectedBehavior, setSelectedBehavior] = useState<BehaviorAnalysisItem | null>(null);
const [isBehaviorPanelOpen, setIsBehaviorPanelOpen] = useState(false);
const [isBehaviorsLoading, setIsBehaviorsLoading] = useState(false);
```

### 5.2 数据加载

**在现有的 useEffect 中新增**：
```typescript
useEffect(() => {
  // ... 现有的加载逻辑
  
  // 新增：加载 behavior 数据
  const loadBehaviors = async () => {
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
  };
  
  loadBehaviors();
}, [currentDate]);
```

### 5.3 布局调整

**修改主容器结构**：
```tsx
<div className="relative flex-1 overflow-hidden">
  {/* CustomBlockLayer - 左侧 */}
  <CustomBlockLayer
    currentDate={currentDate}
    blocks={customBlocks}
    hourHeight={hourHeight}
    categories={categories}
    todos={todos}
    onUpdate={loadCustomBlocks}
    isLoading={isCustomBlocksLoading}
  />
  
  {/* Timeline主体 - 中间（调整宽度） */}
  <div className="absolute left-[96px] right-[100px] top-0 bottom-0">
    {/* 现有的 timeline 渲染逻辑 */}
  </div>
  
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
  
  {/* BehaviorDetailPanel - 滑出面板 */}
  <BehaviorDetailPanel
    behavior={selectedBehavior}
    isOpen={isBehaviorPanelOpen}
    onClose={() => setIsBehaviorPanelOpen(false)}
  />
</div>
```

**关键调整点**：
- Timeline 主体从 `left-[96px] right-0` 改为 `left-[96px] right-[100px]`
- 为 Behavior 区域预留 100px 宽度

## 6. 实现细节

### 6.1 时间计算复用

从 CustomBlockLayer 复用以下工具函数：

```typescript
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

### 6.2 色块渲染逻辑

```typescript
const renderBlock = (behavior: BehaviorAnalysisItem) => {
  const startHour = timeToHour(behavior.start_time);
  const endHour = timeToHour(behavior.end_time);
  const top = startHour * hourHeight;
  const height = (endHour - startHour) * hourHeight;

  return (
    <div
      key={`${behavior.start_time}-${behavior.end_time}`}
      className="absolute w-full rounded-sm cursor-pointer
                 hover:opacity-80 transition-opacity duration-150"
      style={{
        left: 0,
        right: 0,
        top: `${top}px`,
        height: `${height}px`,
        backgroundColor: 'rgba(191, 219, 254, 0.5)', // blue-200 with 50% opacity
        borderLeft: '3px solid #3b82f6', // blue-500
      }}
      onClick={() => onBehaviorClick(behavior)}
    />
  );
};
```

### 6.3 标签渲染逻辑

```typescript
const renderLabel = (behavior: BehaviorAnalysisItem) => {
  const startHour = timeToHour(behavior.start_time);
  const endHour = timeToHour(behavior.end_time);
  const top = startHour * hourHeight;
  const height = (endHour - startHour) * hourHeight;
  
  const startTime = formatHHMM(startHour);
  const endTime = formatHHMM(endHour);

  return (
    <div
      key={`label-${behavior.start_time}`}
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
```

### 6.4 空状态处理

```typescript
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
```

## 7. 错误处理

### 7.1 API 错误

- 网络错误：显示空状态，console.error 记录
- 数据格式错误：显示空状态，console.error 记录
- 不阻塞 Timeline 主功能的加载

### 7.2 数据异常

- `behavior_list` 为空：显示"暂无行为分析"
- 时间格式错误：跳过该条数据，console.warn 记录
- 缺少必填字段：跳过该条数据，console.warn 记录

## 8. 测试要点

### 8.1 功能测试

- [ ] 页面加载时正确调用 API
- [ ] Mock 数据正确渲染为色块
- [ ] 色块位置和高度与时间范围匹配
- [ ] 点击色块打开详情面板
- [ ] 详情面板显示完整信息
- [ ] 关闭详情面板功能正常
- [ ] 切换日期时重新加载数据

### 8.2 UI 测试

- [ ] Behavior 区域宽度为 100px
- [ ] Timeline 主体宽度正确缩小
- [ ] 色块颜色为浅蓝色（区别于 custom_block）
- [ ] 标签文字清晰可读
- [ ] 悬停效果正常
- [ ] 详情面板滑入动画流畅

### 8.3 边界测试

- [ ] 跨小时的 behavior 正确显示
- [ ] 空数据时显示空状态
- [ ] API 错误时不影响主功能
- [ ] 多个 behavior 重叠时标签不遮挡

## 9. 后续扩展（第二阶段）

第一阶段完成后，第二阶段将实现：

1. **数据库集成**：
   - 创建 `behavior_analysis` 表
   - 实现数据持久化
   - 实现增量更新逻辑

2. **数据生成**：
   - 接入截图分析服务
   - 实现 LLM 语义合并
   - 实现定时/手动触发分析

3. **交互增强**：
   - 支持手动编辑 behavior
   - 支持删除/重新生成
   - 支持导出分析报告

## 10. 技术决策记录

### 10.1 为什么复用 CustomBlockLayer？

**决策**：创建新组件 BehaviorBlockLayer，复制 CustomBlockLayer 代码结构

**理由**：
- UI 一致性：用户已熟悉 custom_block 的交互模式
- 快速交付：第一阶段重点是验证功能，复用代码最快
- 低风险：不改动现有代码，只新增组件
- 易扩展：如果后续需要编辑功能，代码已准备好

**替代方案**：
- 抽象共享组件：过度设计，增加复杂度
- 独立实现：UI 可能不一致，重复工作

### 10.2 为什么使用滑出面板而非内联展开？

**决策**：使用从右侧滑出的独立面板

**理由**：
- 不影响 Timeline 主体布局
- 可以显示更多内容（400px 宽度）
- 符合现有的 ActivityDetail 面板交互模式
- 关闭后不留痕迹，视觉更清爽

### 10.3 为什么第一阶段使用 Mock 数据？

**决策**：第一阶段只实现前端显示和 API 调用，使用 Mock 数据

**理由**：
- 快速验证 UI 和交互设计
- 前后端可以并行开发
- 降低初期复杂度，聚焦核心功能
- Mock 数据已准备好，可直接使用

## 11. 文件清单

### 11.1 新增文件

- `frontend/apps/lifewatch/pages/timeline/components/BehaviorBlockLayer.tsx`
- `frontend/apps/lifewatch/pages/timeline/components/BehaviorDetailPanel.tsx`

### 11.2 修改文件

- `frontend/apps/lifewatch/pages/timeline/Timeline.tsx`
- `frontend/apps/lifewatch/pages/timeline/types.tsx`
- `frontend/apps/lifewatch/pages/timeline/api.ts`
- `frontend/apps/lifewatch/pages/timeline/components/index.ts`
- `lifeprism/server/api/timeline_api.py`
- `lifeprism/server/schemas/timeline_schemas.py`

### 11.3 依赖文件

- `test/explore/monitor_prompt/behavior_summary.json` (Mock 数据源)

## 12. 实现顺序建议

1. **后端 API**（最简单）
   - 在 `timeline_api.py` 添加端点
   - 在 `timeline_schemas.py` 添加 Schema
   - 读取 mock 数据并返回

2. **前端类型和 API**
   - 在 `types.tsx` 添加类型定义
   - 在 `api.ts` 添加 API 封装

3. **BehaviorBlockLayer 组件**
   - 复制 CustomBlockLayer 代码
   - 移除编辑功能
   - 调整样式和定位

4. **BehaviorDetailPanel 组件**
   - 实现滑出面板
   - 实现内容显示

5. **Timeline.tsx 集成**
   - 添加状态管理
   - 添加数据加载
   - 调整布局
   - 集成组件

6. **测试和调优**
   - 功能测试
   - UI 调优
   - 边界测试
