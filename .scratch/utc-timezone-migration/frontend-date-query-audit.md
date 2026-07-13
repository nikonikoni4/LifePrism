# Frontend Date Query Audit Report

**目的**: 找出前端所有"传日期查询 datetime 字段表"的场景（类似 Custom Block 问题）

**问题模式**: 前端传 `date: "YYYY-MM-DD"` → 后端查询只有 datetime 字段的表 → 查询失败或返回空

---

## 1. 已知正确场景（✅ 无需修改）

### 1.1 Custom Block API
- **文件**: `frontend/apps/lifewatch/pages/timeline/components/customBlockApi.ts`
- **方法**: `getByDate(date: string)`
- **实现**: ✅ **已修复** - 前端将日期转换为 UTC 时间范围
  ```typescript
  const startOfDay = new Date(`${date}T00:00:00`);
  const endOfDay = new Date(`${date}T23:59:59.999`);
  const start_time = toISOStringUTC(startOfDay);
  const end_time = toISOStringUTC(endOfDay);
  ```
- **后端表**: `timeline_custom_block` (只有 `start_time`, `end_time` datetime 字段)
- **状态**: ✅ 已修复

### 1.2 Todo API
- **文件**: `frontend/apps/goals/apis/todoApi.ts`
- **API**: GET/POST/PUT `/api/v2/todos`
- **后端表**: `todo_list` (有 `date` 字段，也有 `created_at`, `updated_at` datetime)
- **参数**: `date: string | null` (YYYY-MM-DD)
- **状态**: ✅ 正确 - 表有 date 字段

### 1.3 Diary API
- **文件**: `frontend/apps/mindspace/components/journal/diaryApi.ts`
- **API**: GET/POST/PATCH `/api/v2/diary/entries/:date`
- **后端表**: `diary` (有 `date` 字段)
- **参数**: `date: string` (YYYY-MM-DD)
- **状态**: ✅ 正确 - 表有 date 字段

### 1.4 Habit Check-in API
- **文件**: `frontend/apps/habits/apis/checkin.ts`
- **API**: DELETE `/api/v2/habit/habits/:habitId/checkins/:date`
- **后端表**: `habit_check_in_records` (有 `date` 字段)
- **参数**: `date: string` (YYYY-MM-DD)
- **状态**: ✅ 正确 - 表有 date 字段

---

## 2. 聚合 API（✅ 后端处理日期转换）

### 2.1 Activity Stats API
- **文件**: `frontend/apps/lifewatch/pages/home/api.ts`
- **方法**: `ActivityAPI.getStats({ date: string })`
- **API**: GET `/api/v2/activity/stats?date=YYYY-MM-DD`
- **后端表**: `user_app_behavior_log` (只有 `start_time`, `end_time` datetime)
- **实现**: ✅ **后端处理** - 后端将 date 转换为时间范围查询
- **状态**: ✅ 正确 - 后端负责转换

### 2.2 Timeline Stats API
- **文件**: `frontend/apps/lifewatch/pages/timeline/api.ts`
- **方法**: `TimelineAPIV2.getStats(date: string)`
- **API**: GET `/api/v2/timeline/stats?date=YYYY-MM-DD`
- **后端表**: `user_app_behavior_log` (只有 datetime)
- **实现**: ✅ **后端处理** - 后端将 date 转换为时间范围
- **状态**: ✅ 正确 - 后端负责转换

### 2.3 Timeline Overview API
- **文件**: `frontend/apps/lifewatch/pages/timeline/api.ts`
- **方法**: `TimelineAPIV2.getOverview(date: string, startHour, endHour)`
- **API**: GET `/api/v2/timeline/overview?date=YYYY-MM-DD&start_hour=0&end_hour=24`
- **后端表**: `user_app_behavior_log` (只有 datetime)
- **实现**: ✅ **后端处理** - 后端将 date + hour 转换为时间范围
- **状态**: ✅ 正确 - 后端负责转换

### 2.4 Behavior Summary API
- **文件**: `frontend/apps/lifewatch/pages/timeline/api.ts`
- **方法**: `BehaviorAPI.getBehaviorSummary(date: string)`
- **API**: GET `/api/v2/timeline/behavior_summary?date=YYYY-MM-DD`
- **后端表**: `user_app_behavior_log` (只有 datetime)
- **实现**: ✅ **后端处理** - 后端将 date 转换为时间范围
- **状态**: ✅ 正确 - 后端负责转换

### 2.5 Reports API (日报/周报/月报)
- **文件**: `frontend/apps/lifewatch/pages/reports/api.ts`
- **方法**: 
  - `ReportsAPI.getDailyReport(date: string)`
  - `ReportsAPI.getWeeklyReport(weekStartDate: string)`
  - `ReportsAPI.getMonthlyReport(month: string)`
- **API**: 
  - GET `/api/v2/report/daily?date=YYYY-MM-DD`
  - GET `/api/v2/report/weekly?week_start_date=YYYY-MM-DD`
  - GET `/api/v2/report/monthly?month=YYYY-MM`
- **后端表**: 多个表聚合（behavior, todo, goal, diary）
- **实现**: ✅ **后端处理** - 后端聚合多表数据
- **状态**: ✅ 正确 - 后端负责转换

### 2.6 Usage Stats API
- **文件**: `frontend/apps/lifewatch/pages/usage/api.ts`
- **方法**: `UsageAPI.getUsageStats(date: string)`
- **API**: GET `/api/v2/usage/stats?date=YYYY-MM-DD`
- **后端表**: `llm_usage_log` (只有 `created_at` datetime)
- **实现**: ✅ **后端处理** - 后端将 date 转换为时间范围
- **状态**: ✅ 正确 - 后端负责转换

---

## 3. 需要检查的场景（⚠️ 可能有问题）

### 3.1 Mood Entries API
- **文件**: `frontend/apps/mindspace/components/mood/moodApi.ts`
- **方法**: `MoodAPI.getEntries(startDate?: string, endDate?: string)`
- **API**: GET `/api/v2/mood/entries?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- **后端表**: `mood_entries` (只有 `created_at` datetime，**无 date 字段**)
- **实现**: ⚠️ **前端传日期，后端表只有 datetime**
  ```typescript
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  ```
- **问题**: 类似 Custom Block，前端传日期，后端需要转换为时间范围
- **建议**: 
  - **方案1**: 前端改为传时间范围（类似 Custom Block）
  - **方案2**: 后端改为接受日期参数并转换（类似聚合 API）
- **优先级**: ⚠️ **中等** - 取决于使用频率

### 3.2 Custom Records Entries API
- **文件**: `frontend/apps/custom-records/api.ts`
- **方法**: `CustomRecordsAPI.getEntries(typeId, { start_date, end_date })`
- **API**: GET `/api/v2/custom-records/:typeId/entries?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- **后端表**: `custom_records` (只有 `created_at`, `updated_at` datetime，**无 date 字段**)
- **实现**: ⚠️ **前端传日期，后端表只有 datetime**
  ```typescript
  if (params?.start_date) query.set('start_date', params.start_date);
  if (params?.end_date) query.set('end_date', params.end_date);
  ```
- **问题**: 类似 Custom Block，前端传日期，后端需要转换为时间范围
- **建议**: 
  - **方案1**: 前端改为传时间范围
  - **方案2**: 后端改为接受日期参数并转换
- **优先级**: ⚠️ **中等** - 取决于使用频率

### 3.3 Category Map Cache API (update logs by cache)
- **文件**: `frontend/apps/lifewatch/pages/category/api.ts`
- **方法**: `CategoryMapCacheAPI.updateLogsByCache({ start_date, end_date })`
- **API**: POST `/api/v2/activity/manage/logs/update-by-cache?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- **后端表**: `user_app_behavior_log` (只有 datetime)
- **实现**: ⚠️ **前端传日期，后端表只有 datetime**
  ```typescript
  if (params.start_date) searchParams.set('start_date', params.start_date);
  if (params.end_date) searchParams.set('end_date', params.end_date);
  ```
- **问题**: 批量更新日志时，前端传日期范围，后端需要转换
- **建议**: 
  - **方案1**: 前端改为传时间范围
  - **方案2**: 后端改为接受日期参数并转换
- **优先级**: ⚠️ **中等** - 批量操作场景

### 3.4 Goal API (start_date, expected_finished_at)
- **文件**: `frontend/apps/goals/apis/goal.ts`
- **方法**: `goalsV2Api.createGoal()`, `goalsV2Api.updateGoal()`
- **API**: POST/PATCH `/api/v2/goal/goals`
- **后端表**: `goal` (有 `start_date`, `expected_finished_at` date 字段)
- **实现**: ✅ 正确 - 表有 date 字段
  ```typescript
  start_date: formatDateForApi(frontend.startDate || ''),
  expected_finished_at: formatDateForApi(frontend.endDate || ''),
  ```
- **状态**: ✅ 正确 - 表有 date 字段

---

## 4. 总结

### 4.1 问题统计

| 场景 | API 端点 | 后端表 | 是否有 date 字段 | 状态 |
|------|---------|--------|-----------------|------|
| Custom Block | GET `/timeline/custom-blocks` | `timeline_custom_block` | ❌ 只有 datetime | ✅ 已修复 |
| Mood Entries | GET `/mood/entries` | `mood_entries` | ❌ 只有 datetime | ⚠️ 需要检查 |
| Custom Records | GET `/custom-records/:id/entries` | `custom_records` | ❌ 只有 datetime | ⚠️ 需要检查 |
| Category Map Update | POST `/activity/manage/logs/update-by-cache` | `user_app_behavior_log` | ❌ 只有 datetime | ⚠️ 需要检查 |
| Todo | GET `/todos` | `todo_list` | ✅ 有 date 字段 | ✅ 正确 |
| Diary | GET `/diary/entries/:date` | `diary` | ✅ 有 date 字段 | ✅ 正确 |
| Habit | DELETE `/habit/habits/:id/checkins/:date` | `habit_check_in_records` | ✅ 有 date 字段 | ✅ 正确 |
| Goal | POST `/goal/goals` | `goal` | ✅ 有 date 字段 | ✅ 正确 |
| Activity Stats | GET `/activity/stats` | `user_app_behavior_log` | ❌ 只有 datetime | ✅ 后端处理 |
| Timeline Stats | GET `/timeline/stats` | `user_app_behavior_log` | ❌ 只有 datetime | ✅ 后端处理 |
| Reports | GET `/report/daily` | 多表聚合 | - | ✅ 后端处理 |
| Usage | GET `/usage/stats` | `llm_usage_log` | ❌ 只有 datetime | ✅ 后端处理 |

### 4.2 修改建议

**需要修改的场景（3个）**:

1. **Mood Entries API** (`mood_entries` 表)
   - 前端文件: `frontend/apps/mindspace/components/mood/moodApi.ts`
   - 修改方式: 类似 Custom Block，前端传时间范围

2. **Custom Records Entries API** (`custom_records` 表)
   - 前端文件: `frontend/apps/custom-records/api.ts`
   - 修改方式: 类似 Custom Block，前端传时间范围

3. **Category Map Update Logs API** (`user_app_behavior_log` 表)
   - 前端文件: `frontend/apps/lifewatch/pages/category/api.ts`
   - 修改方式: 类似 Custom Block，前端传时间范围

### 4.3 修改优先级

根据使用频率和影响范围：

1. **高优先级**: 
   - ✅ Custom Block（已修复）

2. **中等优先级**:
   - ⚠️ Mood Entries（心情记录，日常使用）
   - ⚠️ Custom Records（自定义记录，取决于用户使用）
   - ⚠️ Category Map Update（批量操作，不常用）

3. **低优先级**:
   - 聚合 API（后端已处理，无需修改）

### 4.4 修改方案

**统一修改方案**（类似 Custom Block）：

```typescript
// 前端将日期转换为 UTC 时间范围
const startOfDay = new Date(`${date}T00:00:00`);
const endOfDay = new Date(`${date}T23:59:59.999`);
const start_time = toISOStringUTC(startOfDay);
const end_time = toISOStringUTC(endOfDay);

const params = new URLSearchParams({ start_time, end_time });
```

**优点**:
- 前端控制时区转换逻辑
- 后端只处理时间范围查询（统一逻辑）
- 避免后端多处转换逻辑

---

## 5. 下一步行动

### 5.1 验证问题场景

1. **验证 Mood Entries API** 是否有查询问题
   - 测试：创建心情记录，按日期查询，检查返回结果

2. **验证 Custom Records API** 是否有查询问题
   - 测试：创建自定义记录，按日期查询，检查返回结果

3. **验证 Category Map Update** 是否有问题
   - 测试：批量更新日志，检查是否正确匹配时间范围

### 5.2 批量修改（如果需要）

如果验证发现问题，按以下顺序修改：

1. Mood Entries API
2. Custom Records API
3. Category Map Update API

每个修改：
- 前端：改为传时间范围（类似 Custom Block）
- 测试：验证查询结果正确
- 文档：更新 API 文档

---

## 6. 参考

- ✅ Custom Block 修复示例: `frontend/apps/lifewatch/pages/timeline/components/customBlockApi.ts`
- 📖 时间工具函数: `frontend/core/utils/dateUtils.ts` (`toISOStringUTC`)
