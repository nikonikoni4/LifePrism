# Frontend Time Usage Report

**Generated:** 2026-07-12

**Purpose:** Comprehensive audit of all time-related code in the frontend to identify violations of `dateUtils.ts` rules and timezone-related bugs.

---

## Part 1: dateUtils.ts Rules Summary

**Location:** `frontend/core/utils/dateUtils.ts`

### Core Principle
All Date → string conversions in frontend MUST use **local timezone methods** (`getFullYear`, `getMonth`, `getDate`). **NEVER use `toISOString()`** because it returns UTC time.

### The Problem
`toISOString()` returns UTC time, causing timezone offset bugs in UTC+ timezones:
- Example: Local `2026-03-03 00:00` (UTC+8) → `toISOString()` → `"2026-03-02T16:00:00.000Z"` (date becomes previous day)

### Available Utility Functions

#### 1. `toLocalDateString(date: Date): string`
- **Output:** `YYYY-MM-DD` (e.g., `2026-03-03`)
- **Use for:** Date-only fields, UI display, database date fields
- **Forbidden alternative:** `date.toISOString().split('T')[0]` ❌

#### 2. `toLocalDateTimeString(date: Date): string`
- **Output:** `YYYY-MM-DDTHH:MM:SS` (e.g., `2026-03-03T14:30:00`)
- **Use for:** DateTime fields when saving to database (backend performs date range queries using local time strings)
- **Forbidden alternative:** `date.toISOString()` ❌

### Key Rule: "带T的时间" (Time with T)
When saving datetime fields to database, use `toLocalDateTimeString()` to produce `YYYY-MM-DDTHH:MM:SS` format in **local timezone**, not UTC.

---

## Part 2: Time Generation Inventory

### 2.1 Database Write Operations (High Risk)

| File:Line | Code Context | Current Method | Output Format | Violation? | Should Use | Risk |
|-----------|--------------|----------------|---------------|------------|------------|------|
| `frontend/apps/addons/components/ExpandDirManager.tsx:49` | Create new expand directory, set `created_at` field | `new Date().toISOString()` | UTC with Z suffix | ✅ YES | `toLocalDateTimeString(new Date())` | **P0** |
| `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx:137` | Update plan doc `updatedAt` on auto-save | `new Date().toISOString()` | UTC with Z suffix | ✅ YES | `toLocalDateTimeString(new Date())` | **P0** |
| `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx:185` | Update plan doc `updatedAt` on manual save | `new Date().toISOString()` | UTC with Z suffix | ✅ YES | `toLocalDateTimeString(new Date())` | **P0** |
| `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx:225` | Create new plan doc `createdAt` | `new Date().toISOString()` | UTC with Z suffix | ✅ YES | `toLocalDateTimeString(new Date())` | **P0** |
| `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx:226` | Create new plan doc `updatedAt` | `new Date().toISOString()` | UTC with Z suffix | ✅ YES | `toLocalDateTimeString(new Date())` | **P0** |
| `frontend/my-ui-kit/ui-kit/todoItem/TodoItemDetailed.tsx:195` | Mark todo as completed, set `actualFinishAt` | `new Date().toISOString().split('T')[0]` | Date only (YYYY-MM-DD) in UTC | ✅ YES | `toLocalDateString(new Date())` | **P1** |
| `frontend/my-ui-kit/ui-kit/todoItem/TodoItem.tsx:199` | Mark todo as completed, set `actualFinishAt` | `new Date().toISOString().split('T')[0]` | Date only (YYYY-MM-DD) in UTC | ✅ YES | `toLocalDateString(new Date())` | **P1** |
| `frontend/apps/goals/hooks/useGoalStore.ts:204` | Complete milestone, set `finishTime` | `new Date().toISOString().split('T')[0]` | Date only (YYYY-MM-DD) in UTC | ✅ YES | `toLocalDateString(new Date())` | **P1** |
| `frontend/apps/goals/components/views/GoalListView/components/JournalEntryModal.tsx:22` | Get today's date for journal entry | `new Date().toISOString().split('T')[0]` | Date only (YYYY-MM-DD) in UTC | ✅ YES | `toLocalDateString(new Date())` | **P1** |
| `frontend/apps/goals/components/views/GoalListView/components/AddGoalModal.tsx:21` | Get today's date for new goal | `new Date().toISOString().split('T')[0]` | Date only (YYYY-MM-DD) in UTC | ✅ YES | `toLocalDateString(new Date())` | **P1** |
| `frontend/apps/lifewatch/pages/usage/UsagePage.tsx:28` | Get today's date for usage page | `new Date().toISOString().split('T')[0]` | Date only (YYYY-MM-DD) in UTC | ✅ YES | `toLocalDateString(new Date())` | **P1** |
| `frontend/core/services/reportCacheService.ts:290` | Generate adjacent date strings for cache | `adjacentDate.toISOString().split('T')[0]` | Date only (YYYY-MM-DD) in UTC | ✅ YES | `toLocalDateString(adjacentDate)` | **P1** |

### 2.2 UI Display & Component State (Medium Risk)

| File:Line | Code Context | Current Method | Output Format | Violation? | Should Use | Risk |
|-----------|--------------|----------------|---------------|------------|------------|------|
| `frontend/apps/goals/components/views/CalendarView/components/DateGrid.tsx:21` | Generate date string for calendar grid | `current.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(current)` | **P2** |
| `frontend/apps/goals/components/views/CalendarView/components/DateGrid.tsx:66` | Check if date is today | `today.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(today)` | **P2** |
| `frontend/apps/goals/components/views/CalendarView/components/DateGrid.tsx:89` | Check if date is selected | `selectedDate.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(selectedDate)` | **P2** |
| `frontend/apps/goals/components/views/DailyTaskView/DailyTaskView.tsx:329` | Get selected date string | `selectedDate.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(selectedDate)` | **P2** |
| `frontend/apps/lifewatch/pages/reports/components/DailyReviewTab.tsx:38` | Get today's date string | `today.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(today)` | **P2** |
| `frontend/apps/lifewatch/pages/reports/components/DailyReviewTab.tsx:119` | Get previous date string | `prevDate.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(prevDate)` | **P2** |
| `frontend/apps/lifewatch/pages/reports/components/DailyReviewTab.tsx:168` | Set selected date from calendar | `date.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(date)` | **P2** |
| `frontend/apps/lifewatch/pages/reports/components/DailyReviewTab.tsx:187` | Set selected date from navigation | `date.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(date)` | **P2** |
| `frontend/apps/lifewatch/pages/reports/components/WeeklyReviewTab.tsx:36` | Get week start date | `monday.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(monday)` | **P2** |
| `frontend/apps/lifewatch/pages/reports/components/WeeklyReviewTab.tsx:37` | Get week end date | `sunday.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(sunday)` | **P2** |
| `frontend/apps/lifewatch/pages/reports/components/WeeklyReviewTab.tsx:118` | Get previous week start | `prevStartDate.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(prevStartDate)` | **P2** |
| `frontend/apps/lifewatch/pages/reports/components/WeeklyReviewTab.tsx:122` | Get previous week end | `prevEndDate.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(prevEndDate)` | **P2** |
| `frontend/apps/lifewatch/pages/reports/mockData.ts:66` | Generate mock data date strings | `date.toISOString().split('T')[0]` | Date only in UTC | ✅ YES | `toLocalDateString(date)` | **P2** |
| `frontend/my-ui-kit/ui-kit/calendar/calendar.tsx:79` | Calendar cell key generation | `date.toISOString()` | Full ISO string as React key | ⚠️ MAYBE | Keep (React key only) or use `date.getTime()` | **P2** |
| `frontend/apps/mindspace/components/journal/journal.tsx:64` | Active date for logging | `activeDate.toISOString()` | Full ISO string | ⚠️ MAYBE | Depends on usage context | **P2** |
| `frontend/apps/mindspace/components/journal/journal.tsx:87` | Debug log for active date | `activeDate.toISOString()` | Full ISO string | ❌ NO | OK for logging | **P3** |
| `frontend/apps/mindspace/components/journal/journal.tsx:244` | Debug log for date clicked | `currentDate.toISOString()` | Full ISO string | ❌ NO | OK for logging | **P3** |
| `frontend/apps/mindspace/components/journal/journal.tsx:291` | Month block React key | `m.toISOString()` | Full ISO string as React key | ⚠️ MAYBE | Keep (React key only) or use `m.getTime()` | **P2** |
| `frontend/apps/mindspace/components/journal/useCalendarScroll.ts:25` | Active date for debugging | `activeDate.toISOString()` | Full ISO string | ❌ NO | OK for logging | **P3** |

### 2.3 Test Files & Mock Data (Low Risk)

| File:Line | Code Context | Current Method | Risk |
|-----------|--------------|----------------|------|
| `frontend/apps/settings/components/SyncStatusSection.test.tsx:363-399` | Test fixture timestamps (7 occurrences) | `new Date(...).toISOString()` | **P3** |
| `frontend/my-ui-kit/test/src/test_component/DragDropTestPage.tsx:263-267` | Mock date strings (5 occurrences) | `new Date().toISOString().split('T')[0]` | **P3** |
| `frontend/my-ui-kit/test/src/test_component/DragDropTestPage.tsx:132` | Check if today | `new Date().toISOString().split('T')[0]` | **P3** |
| `frontend/my-ui-kit/test/src/test_component/DragDropTestPage.tsx:466` | Get today string | `new Date().toISOString().split('T')[0]` | **P3** |
| `frontend/my-ui-kit/test/src/test_component/DragDropTestPage.tsx:734` | Check if today | `new Date().toISOString().split('T')[0]` | **P3** |
| `frontend/my-ui-kit/test/src/test_component/TodoItemTest.tsx:10-11` | Mock timestamps | `new Date().toISOString()` | **P3** |
| `frontend/my-ui-kit/ui-kit/dragDrop/examples/TaskPoolCalendarExample.tsx:246` | Example date format | `date.toISOString().split('T')[0]` | **P3** |
| `frontend/electron/preload.cjs:5` | Logging timestamp | `new Date().toISOString()` | **P3** |

### 2.4 Correct Usage (Already Following Rules) ✅

| File:Line | Code Context | Method Used |
|-----------|--------------|-------------|
| `frontend/floating/what-am-i-doing/utils/formatTime.ts:14` | Get today's date string | `toLocalDateString(new Date())` ✅ |
| `frontend/apps/mindspace/components/journal/useDiaryData.ts:27` | Format date for diary API | `toLocalDateString(date)` ✅ |
| `frontend/apps/mindspace/components/journal/journal.tsx:79` | Format date function | `toLocalDateString` ✅ |
| `frontend/apps/mindspace/components/journal/RangeSummaryModal.tsx:39-40` | Format start/end dates | `toLocalDateString(start/end)` ✅ |
| `frontend/apps/mindspace/components/journal/RangeSummaryModal.tsx:85-92` | Input value binding | `toLocalDateString(start/end)` ✅ |

---

## Part 3: Violation Summary

### Critical Violations (P0) - 5 occurrences

**Database writes using `.toISOString()` directly (returns UTC time with Z suffix)**

1. `frontend/apps/addons/components/ExpandDirManager.tsx:49`
   - **Field:** `created_at`
   - **Current:** `new Date().toISOString()`
   - **Fix:** `toLocalDateTimeString(new Date())`

2. `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx:137`
   - **Field:** `updatedAt` (auto-save)
   - **Current:** `new Date().toISOString()`
   - **Fix:** `toLocalDateTimeString(new Date())`

3. `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx:185`
   - **Field:** `updatedAt` (manual save)
   - **Current:** `new Date().toISOString()`
   - **Fix:** `toLocalDateTimeString(new Date())`

4. `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx:225`
   - **Field:** `createdAt` (new doc)
   - **Current:** `new Date().toISOString()`
   - **Fix:** `toLocalDateTimeString(new Date())`

5. `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx:226`
   - **Field:** `updatedAt` (new doc)
   - **Current:** `new Date().toISOString()`
   - **Fix:** `toLocalDateTimeString(new Date())`

### High-Priority Violations (P1) - 8 occurrences

**Date-only fields using `.toISOString().split('T')[0]` (returns UTC date, may be off by one day)**

1. `frontend/my-ui-kit/ui-kit/todoItem/TodoItemDetailed.tsx:195`
   - **Field:** `actualFinishAt`
   - **Current:** `new Date().toISOString().split('T')[0]`
   - **Fix:** `toLocalDateString(new Date())`

2. `frontend/my-ui-kit/ui-kit/todoItem/TodoItem.tsx:199`
   - **Field:** `actualFinishAt`
   - **Current:** `new Date().toISOString().split('T')[0]`
   - **Fix:** `toLocalDateString(new Date())`

3. `frontend/apps/goals/hooks/useGoalStore.ts:204`
   - **Field:** `finishTime`
   - **Current:** `new Date().toISOString().split('T')[0]`
   - **Fix:** `toLocalDateString(new Date())`

4. `frontend/apps/goals/components/views/GoalListView/components/JournalEntryModal.tsx:22`
   - **Usage:** Default date for journal entry
   - **Current:** `new Date().toISOString().split('T')[0]`
   - **Fix:** `toLocalDateString(new Date())`

5. `frontend/apps/goals/components/views/GoalListView/components/AddGoalModal.tsx:21`
   - **Usage:** Default date for new goal
   - **Current:** `new Date().toISOString().split('T')[0]`
   - **Fix:** `toLocalDateString(new Date())`

6. `frontend/apps/lifewatch/pages/usage/UsagePage.tsx:28`
   - **Usage:** Default selected date
   - **Current:** `new Date().toISOString().split('T')[0]`
   - **Fix:** `toLocalDateString(new Date())`

7. `frontend/core/services/reportCacheService.ts:290`
   - **Usage:** Generate adjacent date strings for cache
   - **Current:** `adjacentDate.toISOString().split('T')[0]`
   - **Fix:** `toLocalDateString(adjacentDate)`

### Medium-Priority (P2) - 15 occurrences

**UI display and component state (may cause visual inconsistencies but not data corruption)**

All occurrences in:
- Calendar components (DateGrid.tsx, DailyTaskView.tsx)
- Report pages (DailyReviewTab.tsx, WeeklyReviewTab.tsx)
- Mock data generation

**Pattern:** `someDate.toISOString().split('T')[0]`
**Fix:** `toLocalDateString(someDate)`

Detailed list in section 2.2 above.

### Low-Priority (P3) - Test files

Test files and mock data can be fixed opportunistically but are not critical since they don't affect production data.

---

## Part 4: Fix Priority

### Priority 1: Critical (P0) - Fix Immediately ⚠️

**5 violations** in database write operations that store UTC time instead of local time.

**Files to fix:**
1. `frontend/apps/addons/components/ExpandDirManager.tsx` (line 49)
2. `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx` (lines 137, 185, 225, 226)

**Impact:** These bugs cause incorrect datetime values to be stored in the database, leading to:
- Wrong timestamps displayed to users
- Potential date range query failures
- Data integrity issues

**Required change:**
```typescript
// BEFORE (❌ Wrong - UTC time)
created_at: new Date().toISOString()

// AFTER (✅ Correct - Local time)
import { toLocalDateTimeString } from 'path/to/dateUtils';
created_at: toLocalDateTimeString(new Date())
```

### Priority 2: High (P1) - Fix Soon 🔴

**7 violations** in date-only fields that may show wrong date (off by one day in certain timezones).

**Files to fix:**
1. `frontend/my-ui-kit/ui-kit/todoItem/TodoItemDetailed.tsx` (line 195)
2. `frontend/my-ui-kit/ui-kit/todoItem/TodoItem.tsx` (line 199)
3. `frontend/apps/goals/hooks/useGoalStore.ts` (line 204)
4. `frontend/apps/goals/components/views/GoalListView/components/JournalEntryModal.tsx` (line 22)
5. `frontend/apps/goals/components/views/GoalListView/components/AddGoalModal.tsx` (line 21)
6. `frontend/apps/lifewatch/pages/usage/UsagePage.tsx` (line 28)
7. `frontend/core/services/reportCacheService.ts` (line 290)

**Impact:** Wrong date displayed/stored, especially problematic around midnight in UTC+ timezones.

**Required change:**
```typescript
// BEFORE (❌ Wrong - UTC date, may be off by one day)
actualFinishAt: new Date().toISOString().split('T')[0]

// AFTER (✅ Correct - Local date)
import { toLocalDateString } from 'path/to/dateUtils';
actualFinishAt: toLocalDateString(new Date())
```

### Priority 3: Medium (P2) - Fix When Convenient 🟡

**15 violations** in UI display and component state.

**Files to fix:**
- `frontend/apps/goals/components/views/CalendarView/components/DateGrid.tsx` (lines 21, 66, 89)
- `frontend/apps/goals/components/views/DailyTaskView/DailyTaskView.tsx` (line 329)
- `frontend/apps/lifewatch/pages/reports/components/DailyReviewTab.tsx` (lines 38, 119, 168, 187)
- `frontend/apps/lifewatch/pages/reports/components/WeeklyReviewTab.tsx` (lines 36, 37, 118, 122)
- `frontend/apps/lifewatch/pages/reports/mockData.ts` (line 66)

**Impact:** Visual inconsistencies, wrong date highlights in UI components.

### Priority 4: Low (P3) - Optional Cleanup 🟢

**Test files and mock data** - Fix opportunistically during related work.

---

## Part 5: Statistics

- **Total time-related code locations scanned:** 268
- **Violations found:** 28
  - **P0 (Critical - Database writes):** 5
  - **P1 (High - Date-only fields):** 7
  - **P2 (Medium - UI display):** 15
  - **P3 (Low - Test files):** ~15 (estimated)
- **Already using dateUtils correctly:** 5+ locations
- **Safe usage (parsing, display only with toLocaleDateString/toLocaleString):** ~200+ locations

### Violation Rate by Category

| Category | Total Locations | Violations | Rate |
|----------|----------------|------------|------|
| Database writes | ~10 | 5 | 50% |
| Date-only fields | ~25 | 7 | 28% |
| UI display | ~30 | 15 | 50% |
| Test files | ~20 | ~15 | 75% |
| **Production code** | **~65** | **27** | **42%** |

---

## Part 6: Recommendations

### Immediate Actions

1. **Fix all P0 violations immediately** - These are data corruption bugs affecting database integrity.

2. **Add ESLint rule** - Create a custom ESLint rule to prevent `.toISOString()` usage:
   ```json
   {
     "no-restricted-syntax": [
       "error",
       {
         "selector": "CallExpression[callee.property.name='toISOString']",
         "message": "Do not use toISOString(). Use toLocalDateString() or toLocalDateTimeString() from dateUtils instead."
       }
     ]
   }
   ```

3. **Fix P1 violations before next release** - These affect user-facing features.

### Long-term Improvements

1. **Centralize date formatting** - Consider creating a date formatting service that enforces timezone-aware operations.

2. **Update documentation** - Add timezone handling guidelines to coding standards.

3. **Add runtime checks** - Consider adding development-mode warnings when ISO strings are used inappropriately.

4. **Backend verification** - Verify that backend correctly handles the local datetime format (`YYYY-MM-DDTHH:MM:SS` without Z suffix).

---

## Part 7: Example Bug Scenario

**Scenario:** User in UTC+8 timezone marks a todo as completed at 2026-07-11 23:30 (11:30 PM local time).

**Current buggy code:**
```typescript
actualFinishAt: new Date().toISOString().split('T')[0]
// Returns: "2026-07-11" (looks correct but actually derived from UTC time)
```

**What actually happens:**
- Local time: `2026-07-11 23:30`
- `.toISOString()` converts to UTC: `"2026-07-11T15:30:00.000Z"`
- `.split('T')[0]` extracts: `"2026-07-11"` ✅ (works in this case)

**But if user completes at 00:30 AM (just after midnight):**
- Local time: `2026-07-12 00:30`
- `.toISOString()` converts to UTC: `"2026-07-11T16:30:00.000Z"`
- `.split('T')[0]` extracts: `"2026-07-11"` ❌ (wrong date! Should be 2026-07-12)

**Correct code:**
```typescript
actualFinishAt: toLocalDateString(new Date())
// Always returns correct local date: "2026-07-12"
```

---

## Appendix: Search Patterns Used

- `new Date()`
- `.toISOString()`
- `.toLocaleDateString()` / `.toLocaleString()`
- `toLocalDateString` / `toLocalDateTimeString` (from dateUtils)
- Time field names: `updated_at`, `created_at`, `updatedAt`, `createdAt`, `timestamp`
- Database write operations (POST/PUT/PATCH in API files)

**Total files scanned:** ~150 TypeScript/JavaScript files in frontend directory
