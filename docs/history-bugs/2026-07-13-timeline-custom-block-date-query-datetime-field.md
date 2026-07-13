# Timeline Custom Block 时区处理三个方向全面缺失

## 元信息

- **发生时间**: 2026-07-13
- **修复状态**: ✅ 已修复
- **影响范围**: Timeline Custom Block 全生命周期（创建→存储→展示→查询）
- **bug 类型**: 前端与后端之间 UTC/本地时间的双向转换全面缺失
- **严重程度**: 高（数据写入错误 + 显示错误 + 查询失败）

## 触发规则

在以下场景时阅读此文档：
- 前端传日期参数（`date=YYYY-MM-DD`）查询，但数据库表只有 datetime 字段
- 查询结果不完整或时区错乱
- SQLite 字符串比较导致时间范围查询失败
- 用户输入本地时间后，数据库存储的时间与实际期望不一致
- 前端显示时间比用户实际记录的提前/延后 N 小时
- **前端与后端之间 UTC/本地时间双向转换的任意方向缺失**

## 问题描述

Timeline Custom Block 的时区处理存在 **三个方向** 的全面缺失：

### Bug 1: 查询方向 — 日期传参不匹配（文档原记录）

**用户现象**：用户新增 timeline_custom_block 记录后，查询指定日期的数据时：
- 部分记录查不到
- 跨日期边界的记录丢失

**请求数据示例**：

```json
// 用户在前端创建（北京时间 2026-07-13 05:20 ~ 08:37）
POST /api/v2/timeline/custom-blocks
{
  "start_time": "...",  // Bug 2 决定这里实际传了什么
  "end_time": "...",
  "content": "测试4",
  "color": "#fecaca"
}

// 数据库实际存储（UTC）
{
  "start_time": "2026-07-12T21:20:00.000Z",  // UTC-8
  "end_time": "2026-07-13T00:37:00.000Z"
}

// 前端查询（本地日期）
GET /api/v2/timeline/custom-blocks?date=2026-07-13

// 查询失败：找不到记录
```

### Bug 2: 创建/编辑方向 — 用户输入本地时间未转换为 UTC（文档新增）

**用户现象**：
- 用户在北京时间 05:20 创建记录，数据库中存储的也是 `"2026-07-13T05:20:00"`（本地时间字符串，未挂时区标记）
- 不同时区用户看到的同一时间块显示时间不一致
- 前端"就近转换"规则完全未执行

**错误代码**（`CustomBlockLayer.tsx:handleSavePopover`）：

```typescript
// 修改前：直接拼接本地时间字符串提交
const startTimeStr = `${currentDate}T${data.startTime}:00`;
// → "2026-07-13T05:20:00"（无时区标记，语义模糊）
const endTimeStr = `${currentDate}T${data.endTime}:00`;
```

**根因**：前端在将用户输入的本地时间提交给后端之前，**完全没有调用 `toISOStringUTC()` 进行 UTC 转换**。时间字符串直接按本地字面量发给后端，后端也未经处理直接存入数据库。

### Bug 3: 展示方向 — UTC 时间直接当本地时间显示（文档新增）

**用户现象**：
- Timeline 上的时间块位置偏移 N 小时（如 UTC+8 用户看到的块比实际偏移了 8 小时）
- 编辑弹框中显示的时间是 UTC 时间而非用户本地时间

**错误代码**（`CustomBlockLabel.tsx:timeToHour`, `CustomBlockPopover.tsx:extractTime`, `BehaviorBlockLayer.tsx:timeToHour`, `BehaviorDetailPanel.tsx:formatTime/formatDate`）：

```typescript
// 修改前：字符串截取 UTC ISO 时间的时间部分，直接当本地时间
function timeToHour(timeStr: string): number {
    const timePart = timeStr.includes('T')
        ? timeStr.split('T')[1]    // "21:20:00.000Z"
        : timeStr.split(' ')[1] || timeStr;
    const [hours, minutes] = timePart.split(':').map(Number);
    return hours + minutes / 60;   // 返回 21.333...（UTC 时间），而非 5.333...（本地时间）
}

function extractTime(timeStr: string): string {
    const timePart = timeStr.includes('T')
        ? timeStr.split('T')[1]
        : timeStr.split(' ')[1] || timeStr;
    return timePart.slice(0, 5);   // 返回 "21:20"（UTC），而非 "05:20"（本地）
}
```

**根因**：从后端取回的 `start_time`/`end_time` 是 UTC ISO 8601 格式（如 `"2026-07-12T21:20:00.000Z"`），前端直接用字符串操作截取时分秒部分，**完全没有调用 `parseISOString()` 转为本地时间**。

### 数据库表结构

```sql
CREATE TABLE timeline_custom_block (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT,      -- UTC ISO 8601: "2026-07-12T21:20:00.000Z"
    end_time TEXT,
    content TEXT,
    color TEXT,
    created_at TEXT,
    updated_at TEXT
);
```

**关键**：表中**没有 `date` 字段**，只有 `start_time/end_time` datetime 字段（UTC 格式）。

## 根本原因（总览）

三个 bug 共享同一个根本原因：**UTC/本地时间双向转换规则完全没有落实**。

| 方向 | 应该做什么 | 实际做了什么 | 违反规则 |
|------|-----------|-------------|---------|
| Create/Update | 用户本地时间 → `toISOStringUTC()` → UTC ISO 发给后端 | 直接拼本地时间字符串 | "就近转换"原则 |
| Query | 用户本地日期 → `toISOStringUTC()` → UTC 时间范围发给后端 | 直接传 `date=YYYY-MM-DD` | "就近转换"原则 |
| Display | UTC ISO → `parseISOString()` → 计算本地 hours/minutes | 字符串截取 UTC 时间部分 | "就近转换"原则 |

### 为什么三个方向的转换全部缺失

根本原因只有一个：**代码中对时间字符串的处理采用的是字符串操作（split/slice/拼接），而非语义化时间转换（Date/parseISOString/toISOStringUTC）**。

这是同一模式在不同方向上的重复表现：
- **写出方向**：`\`${currentDate}T${data.startTime}:00\``  — 字符串拼接
- **读入方向**：`start_of_day = f"{date} 00:00:00"` / `timeStr.split('T')[1]` — 字符串截取
- **展示方向**：`timePart.slice(0, 5)` — 字符串截取

所有操作都绕过了 `Date` 对象，因此浏览器/Node.js 的自动时区转换能力完全没有被利用。

## 修复方案

### 修复原则："就近转换"

**前端负责双向转换，后端只处理 UTC**：

| 方向 | 规则 |
|------|------|
| 前端→后端（Create/Query） | 前端用 `toISOStringUTC()` 将本地时间转为 UTC ISO 再提交 |
| 后端→前端（Display） | 后端返回 UTC ISO，前端用 `parseISOString()` 转为本地时间再显示 |
| 后端内部 | 全程 UTC，不做时区转换 |

### 修改文件清单（完整版）

#### 方向 1: 查询（Bug 1）

| 文件 | 修改内容 |
|------|---------|
| `frontend/.../customBlockApi.ts` | `getByDate()`: `date` → `start_time/end_time`，前端用 `toISOStringUTC()` 转换 |
| `lifeprism/server/api/timeline_api.py` | 参数从 `date: str` 改为 `start_time: str, end_time: str` |
| `lifeprism/server/services/timeline_service.py` | `get_custom_blocks_by_date()` → `get_custom_blocks_by_time_range()` |
| `lifeprism/repository/providers/custom_block_provider.py` | 删除 `f"{date} 00:00:00"` 字符串拼接，直接使用 UTC 时间范围 |
| `test/core/services/test_timeline_service_snapshot.py` | 更新测试用例 |

#### 方向 2: 创建/编辑（Bug 2）

| 文件 | 修改内容 |
|------|---------|
| `frontend/.../CustomBlockLayer.tsx` | `handleSavePopover()`: 用户输入的本地时间构造 `Date` 后调用 `toISOStringUTC()` 再提交 |

```typescript
// 修改后：就近转换
const localStartDate = new Date(`${currentDate}T${data.startTime}:00`);
const localEndDate = new Date(`${currentDate}T${data.endTime}:00`);
const startTimeStr = toISOStringUTC(localStartDate);  // → "2026-07-12T21:20:00.000Z"
const endTimeStr = toISOStringUTC(localEndDate);
```

#### 方向 3: 展示（Bug 3）

| 文件 | 修改内容 |
|------|---------|
| `frontend/.../CustomBlockLabel.tsx` | `timeToHour()`: 字符串截取 → `parseISOString()` + `getHours()` |
| `frontend/.../CustomBlockPopover.tsx` | `extractTime()`: 字符串截取 → `new Date()` + `getHours()/getMinutes()` |
| `frontend/.../BehaviorBlockLayer.tsx` | `timeToHour()`: 字符串截取 → `parseISOString()` + `getHours()` |
| `frontend/.../BehaviorDetailPanel.tsx` | `formatTime()`/`formatDate()`/`formatDuration()`: 字符串截取/替换 → `parseISOString()` + `toLocalDateString()` |

```typescript
// 修改后：UTC → 本地
function timeToHour(timeStr: string): number {
    const date = parseISOString(timeStr);
    return date.getHours() + date.getMinutes() / 60;  // 浏览器自动转为本地时间
}

function extractTime(timeStr: string): string {
    const date = new Date(timeStr);
    const hours = date.getHours();
    const minutes = date.getMinutes();
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}
```

#### 附带修复

| 文件 | 修改内容 |
|------|---------|
| `lifeprism/utils/time_utils.py` | `local_to_utc_iso()`: 增加 DST `NonExistentTimeError` / `AmbiguousTimeError` 异常处理 |

### 修改前后对比

**方向 1: 查询**

```typescript
// 修改前
const params = { date: "2026-07-13" };
```
```python
# 修改前
start_of_day = f"{date} 00:00:00"  # 字符串拼接，无时区转换
```

```typescript
// 修改后
const startOfDay = new Date(`${date}T00:00:00`);
const endOfDay = new Date(`${date}T23:59:59.999`);
const params = {
  start_time: toISOStringUTC(startOfDay),  // "2026-07-12T16:00:00.000Z"
  end_time: toISOStringUTC(endOfDay)       // "2026-07-13T15:59:59.999Z"
};
```
```python
# 修改后
def get_custom_blocks_by_time_range(self, start_time: str, end_time: str):
    cursor.execute(sql, [start_time, end_time])  # 直接使用 UTC 时间范围
```

**方向 2: 创建/编辑**

```typescript
// 修改前：字符串拼接，无 UTC 转换
const startTimeStr = `${currentDate}T${data.startTime}:00`;  // "2026-07-13T05:20:00"

// 修改后：构造 Date → toISOStringUTC
const localStartDate = new Date(`${currentDate}T${data.startTime}:00`);
const startTimeStr = toISOStringUTC(localStartDate);  // "2026-07-12T21:20:00.000Z"
```

**方向 3: 展示**

```typescript
// 修改前：字符串截取 UTC 时间，直接当本地时间
function timeToHour(timeStr: string): number {
    const timePart = timeStr.split('T')[1];  // "21:20:00.000Z"
    const [hours, minutes] = timePart.split(':').map(Number);
    return hours + minutes / 60;  // 21.33（错误！应该是 5.33）
}

// 修改后：parseISOString → getHours（浏览器自动转本地）
function timeToHour(timeStr: string): number {
    const date = parseISOString(timeStr);
    return date.getHours() + date.getMinutes() / 60;  // 5.33（正确）
}
```

## 验证方法

### 1. 三个方向的完整性检查清单

| 方向 | 检查项 | 验证方式 |
|------|--------|---------|
| Create | 用户输入本地时间 → 数据库存储 UTC 时间 | 检查数据库中 `start_time` 是否带 `Z` 后缀且比本地时间少 8 小时 |
| Query | 选择本地日期 → 能查到该日期的所有记录 | 创建一条跨 UTC 日期边界的记录，验证能查到 |
| Display | 数据库 UTC 时间 → 页面显示本地时间 | 确认 Timeline 上时间块位置和编辑框时间均为本地时间 |

### 2. 单元测试

```python
def test_get_custom_blocks_by_time_range_utc():
    provider.create_custom_block({
        "start_time": "2026-07-12T21:20:00.000Z",  # 北京时间 07-13 05:20
        "end_time": "2026-07-13T00:37:00.000Z",
        "content": "测试"
    })

    results = provider.get_custom_blocks_by_time_range(
        start_time="2026-07-12T16:00:00.000Z",  # 北京 07-13 00:00
        end_time="2026-07-13T15:59:59.999Z"     # 北京 07-13 23:59
    )

    assert len(results) == 1
    assert results[0]["content"] == "测试"
```

### 3. 集成测试

```bash
# 创建记录（前端已转 UTC：北京时间 05:20 → UTC 21:20）
curl -X POST http://localhost:5050/api/v2/timeline/custom-blocks \
  -H "Content-Type: application/json" \
  -d '{
    "start_time": "2026-07-12T21:20:00.000Z",
    "end_time": "2026-07-13T00:37:00.000Z",
    "content": "测试"
  }'

# 查询北京时间 2026-07-13 范围
curl "http://localhost:5050/api/v2/timeline/custom-blocks?start_time=2026-07-12T16:00:00.000Z&end_time=2026-07-13T15:59:59.999Z"
# 预期：返回刚创建的记录
```

### 4. 前端测试

1. 打开 Timeline 页面
2. 创建时间块（选择本地时间 05:20 - 08:37）
3. 刷新页面 → Timeline 上时间块应显示在 05:20 位置
4. 点击编辑 → 弹框中时间应为 05:20（而非 21:20）
5. 切换到其他日期再切回 → 记录仍在

## 相关文档

- 时区处理规则：`docs/coding-rules/time-handling-rules.md`
- UTC 迁移指南：`docs/guides/utc-migration-guide.md`
- 前端时间工具：`frontend/core/utils/dateUtils.ts`（`parseISOString`, `toISOStringUTC`, `toLocalDateString`）
- 后端时间工具：`lifeprism/utils/time_utils.py`

## 经验教训

### 为什么三个方向同时缺失

**根本原因只有一个**：项目统一用 UTC 存储后，前端代码没有同步改造。开发者习惯性地用字符串操作（split/slice/拼接）处理时间，而非用 `Date` 对象 + `dateUtils` 工具函数进行语义化转换。

字符串操作绕过了浏览器内置的时区转换能力，导致：
- 写出时：本地时间字面量原样存入数据库
- 读入时：UTC 时间字面量原样显示在页面上

### 如何预防

1. **代码审查检查点**：任何对时间字符串做 `split('T')`、`slice(0,5)`、字符串拼接的操作都应标记为可疑
2. **"就近转换"原则必须落实到代码**：
   - 前端发出的时间 → 必须是 UTC ISO（`toISOStringUTC()`）
   - 前端接收的时间 → 必须先转换再显示（`parseISOString()`）
3. **类型约束**：API 参数名明确体现含义（`start_time` 而非 `time`，ISO 8601 UTC 格式）
4. **全生命周期检查**：每涉及一个时间字段，必须检查 Create/Read/Update/Query 四个方向是否都正确处理了转换

## 相关问题

排查发现以下类似问题：
1. **Timeline Stats API**：✅ 已修复（2026-07-13）
   - 修改文件：`frontend/apps/lifewatch/pages/timeline/api.ts`、`lifeprism/server/api/timeline_api.py`、`lifeprism/server/services/timeline_service.py`、`lifeprism/server/services/timeline_builder.py`
   - 前端：组件内转换 date → UTC 时间范围
   - 后端：参数改为 `start_time/end_time`，删除字符串拼接
2. **Timeline Overview API**：✅ 已修复（2026-07-13）
   - 同上，参数改为 `start_time/end_time`
3. **Mood Entries API**：❌ 待修复 - `mood_entries` 表只有 `created_at`，但查询用 `start_date/end_date`
4. **Custom Records API**：❌ 待修复 - `custom_records` 表只有 datetime，但查询用日期
5. **Category Update Logs API**：❌ 待修复 - `user_app_behavior_log` 表只有 datetime，但查询用日期

参考此文档的修复方案进行修复。

## 标准模板说明

此文档作为"前端传日期查询 datetime 字段表"类型问题的标准模板，包含：
1. **问题识别**：前端传日期，后端表只有 datetime
2. **根因分析**：类型不匹配 + 时区未转换 + 字符串比较失败
3. **修复方案**：前端传 UTC 时间范围，后端直接使用
4. **验证方法**：单元测试 + 集成测试 + 前端测试
5. **预防措施**：规则明确 + 类型约束 + 测试覆盖
