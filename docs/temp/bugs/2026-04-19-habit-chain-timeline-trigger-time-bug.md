# 习惯链条 Timeline 节点时间计算 Bug

**日期**: 2026-04-19
**状态**: 仅记录，未修复
**类型**: 前端逻辑 bug

---

## Bug 描述

当习惯链条的多个锚点节点（设置了 `trigger_time`）间距小于 `MIN_ANCHOR_GAP(80px)` 时，前端会推挤下一个锚点的 **Y 坐标**，但未同步更新其对应的 **分钟数（minutes）**，导致锚点显示的时间与实际垂直位置不一致。

---

## 完整链条时间计算流程

### 后端部分

| 步骤 | 文件 | 位置 | 说明 |
|------|------|------|------|
| 1 | `lifeprism/server/providers/habit_chain_provider.py` | 第153-169行 `get_nodes_by_chain()` | 从数据库查询节点，返回原始 `trigger_time` |
| 2 | `lifeprism/server/services/habit_chain_service.py` | 第187-207行 `get_timeline()` | 组装 `TimelineNodeItem`，直接用 `n.get("trigger_time")` 不做任何计算 |
| 3 | `lifeprism/server/api/habit_api.py` | API端点 | 返回给前端的数据就是数据库原始值 |

**结论**：后端**不做任何时间计算**，只做验证（`_validate_chain_timeline_rules`），直接透传数据库值。

---

### 前端部分

| 步骤 | 文件 | 位置 | 说明 |
|------|------|------|------|
| 1 | `frontend/apps/habits/hooks/useChainStore.ts` | `useChainStore` | 调用API获取链条数据 |
| 2 | `frontend/apps/habits/hooks/useTimelineStore.ts` | 第41-178行 `timelineEvents useMemo` | **核心计算逻辑**，见下方详细拆解 |
| 3 | `frontend/apps/habits/constants.ts` | 第1-5行 | 布局常量定义 |
| 4 | `frontend/apps/habits/components/views/timeline/TimelineView.tsx` | 第34行 | 容器高度 `24 * HOUR_HEIGHT` |
| 5 | `frontend/apps/habits/components/views/timeline/TimelineNode.tsx` | 第15-20行 | 根据 `top` / `height` 渲染节点位置 |

#### 前端布局常量 (`constants.ts`)

```typescript
export const PIXELS_PER_MINUTE = 1;    // 每分钟 = 1px
export const HOUR_HEIGHT = 60;          // 1小时 = 60px
export const MIN_NODE_HEIGHT = 48;      // 节点最小高度 48px
export const MIN_ANCHOR_GAP = 80;       // 锚点最小间距 80px
```

#### 前端时间计算核心逻辑 (`useTimelineStore.ts`)

##### Step 1: 收集锚点 (第51-62行)

```typescript
nodes.forEach((node, idx) => {
    if (node.triggerTime) {
        anchors.push({
            index: idx,
            minutes: parseTimeToMinutes(node.triggerTime),  // 例: "08:20" → 500
            y: parseTimeToMinutes(node.triggerTime) * PIXELS_PER_MINUTE  // y = 500
        });
    }
});
```

##### Step 2: 锚点间距检查 (第64-71行)

```typescript
for (let i = 1; i < anchors.length; i++) {
    const prev = anchors[i - 1];
    const curr = anchors[i];
    if (curr.y - prev.y < MIN_ANCHOR_GAP) {
        curr.y = prev.y + MIN_ANCHOR_GAP;  // ← 只更新了 y，未更新 minutes！
    }
}
```

##### Step 3: 锚点间节点分布 (第105-143行)

```typescript
for (let a = 0; a < anchors.length - 1; a++) {
    const currAnchor = anchors[a];
    const nextAnchor = anchors[a + 1];
    // ...
    if (currentY > nextAnchor.y) {
        nextAnchor.y = currentY;  // ← 又只更新了 y
        // not strictly updating minutes here, just visual Y
    }
}
```

##### Step 4: 尾随节点 (第145-158行)

```typescript
for (let i = lastAnchor.index; i < nodes.length; i++) {
    nodeLayouts[i] = {
        y: currentY,
        height: MIN_NODE_HEIGHT,
        endTimeMinutes: currentMins + (MIN_NODE_HEIGHT / PIXELS_PER_MINUTE)
    };
    currentY += MIN_NODE_HEIGHT;
    currentMins += (MIN_NODE_HEIGHT / PIXELS_PER_MINUTE);
}
```

##### Step 5: 组装 TimelineEvent (第161-174行)

```typescript
nodes.forEach((node, idx) => {
    const layout = nodeLayouts[idx];
    const startTimeMinutes = layout.y / PIXELS_PER_MINUTE;  // ← 用 Y 反推时间（不准确）
    events.push({
        id: `${chain.id}_${node.id}`,
        title: node.name,
        startTime: formatMinutesToTime(startTimeMinutes),  // ← 显示时间可能与 triggerTime 不符
        endTime: formatMinutesToTime(layout.endTimeMinutes),
        associatedHabitId: node.habitId,
        height: layout.height,
        top: layout.y
    });
});
```

---

## Bug 复现场景

**输入**: 5个节点，第1节点 trigger_time=08:00，第3节点 trigger_time=08:20

**锚点收集后**:
```
锚点0: index=0, minutes=480, y=480
锚点1: index=2, minutes=500, y=500
```

**Step 2 间距检查后** (y被推挤但minutes未更新):
```
锚点0: index=0, minutes=480, y=480
锚点1: index=2, minutes=500, y=560  ← y从500推挤到560，但minutes仍为500
```

**结果**: 节点3的Y坐标在560px（对应09:20时间），但显示的startTime是从Y反推的560/1=560分钟=09:20，与数据库中存储的08:20不一致。

---

## 相关代码文件

| 文件 | 说明 |
|-----|------|
| `lifeprism/server/providers/habit_chain_provider.py` | 数据库查询节点原始数据 |
| `lifeprism/server/services/habit_chain_service.py` | 后端Timeline组装 + 验证逻辑 |
| `frontend/apps/habits/hooks/useTimelineStore.ts` | **前端核心布局计算（bug所在）** |
| `frontend/apps/habits/constants.ts` | 布局常量 |
| `frontend/apps/habits/components/views/timeline/TimelineView.tsx` | Timeline容器组件 |
| `frontend/apps/habits/components/views/timeline/TimelineNode.tsx` | 单个节点渲染组件 |
| `frontend/apps/habits/hooks/useChainStore.ts` | 链条数据获取 |
| `docs/specs/2026-04-15-habit-system.md` | 习惯系统spec（Timeline布局规则不在其中） |

---

## Spec 是否涉及此逻辑

**否**。`2026-04-15-habit-system.md` spec 中：
- 数据模型定义了 `trigger_time` 字段
- 验证规则定义了递增性检查
- **完全没有规定 Timeline UI 如何渲染节点、时间如何计算、锚点间距如何处理**

Timeline 布局规则属于前端实现细节，不在后端 spec 约束范围内。

---

## 修复方向（待确认）

1. **方案A**: Step 2/3 推挤Y时，同步按比例更新 minutes
   - 例：y从500→560，增量60px对应60分钟，minutes也应500→560
2. **方案B**: Step 5 不再用Y反推时间，直接用节点的原始 triggerTime
   - 但需要处理无 triggerTime 的节点
3. **方案C**: 前端认为当前行为是正确的（锚点被推挤后显示时间就是新的位置时间）
   - 需要和产品确认交互意图
