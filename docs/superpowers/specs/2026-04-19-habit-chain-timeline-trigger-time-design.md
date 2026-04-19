# Habit Chain Timeline 节点时间计算设计

**日期**: 2026-04-19
**状态**: 已确认
**类型**: 设计方案

---

## 1. 背景与目标

### 1.1 当前问题

前端在计算锚点节点时间时存在逻辑错误：当相邻锚点间距小于 `MIN_ANCHOR_GAP(80px)` 时，前端会推挤 Y 坐标但未同步更新对应的分钟数，导致锚点显示时间与实际位置不一致。

### 1.2 解决方案

将时间计算逻辑从**前端**移至**后端**，后端负责：
- 根据用户设置的显式时间计算所有节点的 trigger_time
- 验证时间间隔是否符合规则（相邻节点 ≥ 10min）
- 不通过验证则 raise 错误

### 1.3 前端 Timeline 放大

**问题**：当前前端 1px = 1分钟，导致时间密度过高，两个相邻节点（10min 间隔）在 timeline 上仅相距 10px，内容无法正常显示。

**解决方案**：将 `PIXELS_PER_MINUTE` 从 1 改为 4，即 1分钟 = 4px。

**放大倍数**：4倍

| 常量 | 原值 | 新值 |
|------|------|------|
| PIXELS_PER_MINUTE | 1 | 4 |
| HOUR_HEIGHT | 60px | 240px |
| MIN_ANCHOR_GAP | 80px | 320px |
| MIN_NODE_HEIGHT | 48px | 保持48px（已是最小值） |

**放大原因**：10分钟的内容按原比例仅占10px，放大4倍后占40px，可以正常显示。

---

## 2. 时间计算规则

### 2.1 基本参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 默认时长 | 30min | 节点到下一节点的默认间距 |
| 最小时长 | 10min | 相邻节点最小间距（验证规则） |
| 最大时长 | 无限制 | 不设置上限 |

### 2.2 计算逻辑

**情况A**：该时间节点后面的节点没有显式设置的时间

```
例：5个节点，第一个节点为8:00，后面节点都按默认时长计算
节点1: 8:00
节点2: 8:30  (8:00 + 30min)
节点3: 9:00  (8:30 + 30min)
节点4: 9:30  (9:00 + 30min)
节点5: 10:00 (9:30 + 30min)
```

**情况B**：该时间节点后面有显式设置时长

```
例：第一个节点是8:00，第四个节点设置9:00
- 8:00到9:00共60min
- 中间有2个隐式节点（节点2、3）
- 每段时长 = 60min / 3 = 20min

节点1: 8:00   (显式)
节点2: 8:20   (隐式, 20min间隔)
节点3: 8:40   (隐式, 20min间隔)
节点4: 9:00   (显式)
节点5: 9:30   (隐式, 使用默认30min)
```

### 2.3 验证规则

**后端验证**：相邻节点的 trigger_time 间距必须 ≥ 10min

```
节点1: 8:00
节点2: 8:05  → 间距5min < 10min → 验证失败，raise 错误
```

---

## 3. 数据模型

### 3.1 habit_chain_nodes 表

`trigger_time` 字段保持可选，仅存储用户**显式设置**的时间。

### 3.2 计算结果

**不存库**。计算的 trigger_time 作为 API 响应返回，不写入数据库。

原因：
- 计算结果是动态的，取决于锚点设置
- 避免数据冗余和同步问题
- 前端每次获取链条时由后端实时计算

---

## 4. API 契约

### 4.1 请求格式

`PATCH /habit-chains/{chain_id}` 或创建时传入节点数组：

```json
{
  "nodes": [
    { "id": 1, "node_name": "节点1", "trigger_time": "08:00" },
    { "id": 2, "node_name": "节点2", "trigger_time": null },
    { "id": 3, "node_name": "节点3", "trigger_time": null },
    { "id": 4, "node_name": "节点4", "trigger_time": "09:00" },
    { "id": 5, "node_name": "节点5", "trigger_time": null }
  ]
}
```

### 4.2 响应格式

```json
{
  "id": "chain-xxxxxxxx",
  "name": "早晨习惯链",
  "nodes": [
    { "id": 1, "node_name": "节点1", "trigger_time": "08:00", "calculated_time": "08:00" },
    { "id": 2, "node_name": "节点2", "trigger_time": null, "calculated_time": "08:20" },
    { "id": 3, "node_name": "节点3", "trigger_time": null, "calculated_time": "08:40" },
    { "id": 4, "node_name": "节点4", "trigger_time": "09:00", "calculated_time": "09:00" },
    { "id": 5, "node_name": "节点5", "trigger_time": null, "calculated_time": "09:30" }
  ]
}
```

### 4.3 错误响应

验证失败时返回 400：

```json
{
  "error": "VALIDATION_ERROR",
  "message": "节点2(08:05)与节点1(08:00)间距不足10min",
  "details": {
    "node_id": 2,
    "expected_min_gap": "10min",
    "actual_gap": "5min"
  }
}
```

---

## 5. 后端计算流程

### 5.1 get_timeline() 伪代码

```
1. 获取链条所有节点（按 sequence_order 排序）
2. 找出所有有显式 trigger_time 的锚点
3. 对每对相邻锚点之间：
   a. 计算总时长 = 锚点2.time - 锚点1.time
   b. 计算中间隐式节点数量 N
   c. 每段时长 = 总时长 / (N + 1)
   d. 填充中间节点的 calculated_time
4. 锚点之后若无显式时间节点，按默认30min递推
5. 验证所有相邻节点间距 >= 10min
6. 返回完整 nodes（含 calculated_time）
```

---

## 6. 前端改动

### 6.1 常量调整

| 常量 | 原值 | 新值 |
|------|------|------|
| PIXELS_PER_MINUTE | 1 | 4 |
| HOUR_HEIGHT | 60 | 240 |
| MIN_ANCHOR_GAP | 80 | 320 |

### 6.2 显示逻辑调整

- 使用后端返回的 `calculated_time` 显示，不再本地计算
- Y 坐标计算：`y = minutes * PIXELS_PER_MINUTE`
- 节点间距检查不再需要（后端已验证）

---

## 7. 影响范围

| 文件 | 改动 |
|------|------|
| `lifeprism/server/services/habit_chain_service.py` | 新增时间计算逻辑 |
| `lifeprism/server/api/habit_api.py` | 新增验证错误响应 |
| `frontend/apps/habits/constants.ts` | 调整布局常量 |
| `frontend/apps/habits/hooks/useTimelineStore.ts` | 简化，移除错误的时间计算逻辑 |
| `frontend/apps/habits/components/views/timeline/TimelineView.tsx` | 容器高度调整 |
