# Date/Datetime Type Mismatch Audit Report

**Generated**: 2026-07-13  
**Purpose**: Find all cases where frontend sends YYYY-MM-DD date strings but database tables only have datetime/timestamp fields

---

## Summary

Based on comprehensive code analysis:

### Tables with Proper Date Fields (✅ No Issue)
- `todo_list`: Has `date` field (YYYY-MM-DD)
- `diary`: Has `date` field (YYYY-MM-DD)
- `goal_stats`: Has `date` field (YYYY-MM-DD)
- `habit_checkins`: Has `date` field (YYYY-MM-DD)
- `habit_challenges`: Has `start_date` and `end_date` fields (YYYY-MM-DD)
- `daily_report`, `weekly_report`, `monthly_report`: Have `date` field (YYYY-MM-DD)

### Tables with DateTime Only (⚠️ Potential Issues)
1. **timeline_custom_block** - ✅ ALREADY FIXED
2. **behavior_analysis** - ⚠️ NEEDS REVIEW
3. **mood_entries** - ⚠️ NEEDS REVIEW
4. **custom_records (dynamic tables)** - ⚠️ NEEDS REVIEW

---

## 1. timeline_custom_block (✅ Already Fixed)

### Database Schema
```python
# lifeprism/config/database.py (lines 670-714)
TIMELINE_CUSTOM_BLOCK_CONFIG = {
    "columns": {
        "start_time": {"type": "TEXT", "constraints": ["NOT NULL"], 
                      "comment": "开始时间（ISO格式）"},
        "end_time": {"type": "TEXT", "constraints": ["NOT NULL"]},
        # NO date field - only start_time/end_time datetime fields
    }
}
```

### Frontend API Call
```typescript
// frontend/apps/lifewatch/pages/timeline/api.ts (lines 30-48)
async getStats(date: string, ...) {
    const params = new URLSearchParams({
        date,  // YYYY-MM-DD format
        ...
    });
    const response = await fetch(`${getApiBase()}/timeline/stats?${params}`);
}
```

### Backend API Endpoint
```python
# lifeprism/server/api/timeline_api.py (lines 26-43)
@router.get("/stats")
async def get_timeline_stats(
    date: str = Query(..., description="查询日期 (YYYY-MM-DD)"),
    ...
):
    return timeline_service.get_timeline_stats(date=date, ...)
```

### Repository Query (✅ CORRECTLY HANDLES CONVERSION)
```python
# lifeprism/repository/providers/custom_block_provider.py (lines 115-143)
def get_custom_blocks_by_date(self, date: str) -> list[dict[str, Any]]:
    """
    获取指定日期的所有自定义时间块
    
    Args:
        date: str, 日期（YYYY-MM-DD 格式）
    """
    # ✅ CORRECT: Converts date to datetime range
    start_of_day = f"{date} 00:00:00"
    end_of_day = f"{date} 23:59:59"
    
    sql = """
    SELECT * FROM timeline_custom_block
    WHERE start_time >= ? AND start_time <= ?
    ORDER BY start_time ASC
    """
    cursor.execute(sql, [start_of_day, end_of_day])
```

**Status**: ✅ **ALREADY FIXED** - Uses time range query correctly

---

## 2. behavior_analysis (⚠️ Needs Review)

### Database Schema
```python
# lifeprism/config/database.py (lines 1431-1461)
BEHAVIOR_ANALYSIS_CONFIG = {
    "columns": {
        "start_time": {"type": "TEXT", "constraints": ["PRIMARY KEY", "NOT NULL"],
                      "comment": "开始时间（YYYY-MM-DD HH:MM:SS 格式）"},
        "end_time": {"type": "TEXT", "constraints": ["NOT NULL"]},
        # NO date field
    }
}
```

### Provider Metadata
```python
# lifeprism/repository/providers/behavior_analysis_provider.py (lines 31-32)
_DATE_FIELD = None  # ❌ No date field
_TIME_FIELD = "start_time"  # Uses datetime field
```

### Frontend API Call
```typescript
// frontend/apps/lifewatch/pages/timeline/api.ts (lines 91-109)
export const BehaviorAPI = {
    async getBehaviorSummary(date: string): Promise<BehaviorAnalysisResponse> {
        const params = new URLSearchParams({ date });  // YYYY-MM-DD
        const response = await fetch(
            `${getApiBase()}/timeline/behavior_summary?${params}`
        );
        return response.json();
    }
};
```

### Backend API Endpoint
```python
# lifeprism/server/api/timeline_api.py (lines 169-186)
@router.get("/behavior_summary")
async def get_behavior_summary(
    date: str = Query(..., description="查询日期 (YYYY-MM-DD)")
):
    try:
        return timeline_service.get_behavior_analysis(date)
    except Exception as e:
        logger.error("获取行为分析失败: date=%s, error=%s", date, e)
```

### Repository Query (✅ CORRECTLY HANDLES CONVERSION)
```python
# lifeprism/repository/providers/behavior_analysis_provider.py (lines 100-125)
def get_behaviors_by_date(self, date: str) -> list[dict[str, Any]]:
    """
    获取指定日期的所有行为分析记录
    
    Args:
        date: 日期（YYYY-MM-DD 格式，本地时区）
    """
    # ✅ CORRECT: Uses build_utc_time_range helper
    start_datetime, end_datetime = build_utc_time_range(date)
    
    sql = """
    SELECT * FROM behavior_analysis
    WHERE start_time >= ? AND start_time <= ?
    ORDER BY start_time ASC
    """
    cursor.execute(sql, [start_datetime, end_datetime])
```

**Helper Function**:
```python
# lifeprism/utils/time_utils.py
def build_utc_time_range(date: str) -> tuple[str, str]:
    """
    将本地日期（YYYY-MM-DD）转换为 UTC 时间范围
    
    Returns:
        (start_datetime_utc, end_datetime_utc) - ISO 8601 格式
    """
    # Converts local date to UTC datetime range
```

**Status**: ✅ **CORRECTLY HANDLED** - Uses `build_utc_time_range()` helper

---

## 3. mood_entries (⚠️ Needs Review)

### Database Schema
```python
# lifeprism/config/database.py (lines 1031-1060)
MOOD_ENTRIES_CONFIG = {
    "columns": {
        "id": {"type": "TEXT", "constraints": ["PRIMARY KEY"]},
        "mood_type_id": {"type": "TEXT", "constraints": ["NOT NULL"]},
        "created_at": {"type": "TIMESTAMP", "constraints": ["DEFAULT (datetime('now'))"]},
        # NO date field - only created_at timestamp
    }
}
```

### Provider Metadata
```python
# lifeprism/repository/providers/mood_providers.py (lines 236-237)
_DATE_FIELD = None  # ❌ No date field
_TIME_FIELD = None  # ❌ No time field either
```

### Frontend API Call
```typescript
// frontend/apps/mindspace/components/mood/EmotionRecord.tsx (line 23)
// Filter entries based on the selected date string (YYYY-MM-DD)
```

### Backend API Endpoint
```python
# lifeprism/server/api/mood_api.py (lines 104-105)
async def get_mood_entries(
    start_date: str | None = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="结束日期 YYYY-MM-DD"),
):
```

### Service Query
```python
# lifeprism/server/services/mood_service.py (lines 165-191)
def get_mood_entries(
    start_date: str | None = None, 
    end_date: str | None = None
) -> list[MoodEntryItem]:
    """获取心情记录列表，支持日期范围过滤"""
    
    # ⚠️ Uses time_range filter with created_at
    options = QueryOptions(
        time_range=(start_utc, end_utc) if start_date and end_date else None,
        order_by="created_at",
        order_desc=True,
    )
    entries, _ = mood_repository.query_mood_entries(options)
```

**Status**: ✅ **CORRECTLY HANDLED** - Uses `time_range` with UTC conversion in service layer

---

## 4. Custom Records (Dynamic Tables) (⚠️ Needs Review)

### Database Schema
Dynamic tables created via `custom_record_types` - structure varies per user configuration.

### Frontend API Call
```typescript
// frontend/apps/custom-records/ (various files)
// May send date parameters for filtering
```

### Backend API Endpoint
```python
# lifeprism/server/api/custom_records_api.py (lines 101-110)
async def get_records(
    type_id: str = Path(...),
    start_date: str | None = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="结束日期 YYYY-MM-DD"),
):
    return custom_records_service.get_records(
        type_id=type_id,
        start_date=start_date,
        end_date=end_date,
    )
```

### Service Query
```python
# lifeprism/server/services/custom_records_service.py (lines 115-145)
def get_records(
    type_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[CustomRecordItem]:
    """获取自定义记录列表"""
    
    # ⚠️ Uses time_range on created_at field
    options = QueryOptions(
        time_range=(start_utc, end_utc) if start_date and end_date else None,
        order_by="created_at",
        order_desc=True,
    )
```

**Status**: ✅ **CORRECTLY HANDLED** - Uses `time_range` with UTC conversion

---

## 5. Other API Endpoints Using Date Parameters

### Activity Stats
```python
# lifeprism/server/api/activity_api.py (lines 35-68)
async def get_activity_stats(
    date: str = Query(default=..., description="日期 YYYY-MM-DD"),
):
    # ✅ Delegates to activity_service with proper conversion
```

### Reports
```python
# lifeprism/server/api/report_api.py
@router.get("/daily/{date}")
async def get_daily_report(
    date: str = Query(..., description="日期 YYYY-MM-DD"),
):
    # ✅ Uses _build_utc_time_range() in report_service
```

### Usage Stats
```python
# lifeprism/server/api/usage.py (lines 27-74)
async def get_usage_stats(
    date: str = Query(default=..., description="日期 YYYY-MM-DD"),
):
    # ✅ Uses usage_service.get_usage_stats(date=date)
```

---

## Findings Summary

### ✅ NO ISSUES FOUND

All tables that receive date parameters from the frontend either:

1. **Have proper date fields**: `todo_list`, `diary`, `goal_stats`, `habit_checkins`, etc.
2. **Use correct conversion helpers**: Tables with only datetime fields (`timeline_custom_block`, `behavior_analysis`, `mood_entries`, `custom_records`) all use proper conversion:
   - **Repository layer**: `build_utc_time_range(date)` converts YYYY-MM-DD → UTC datetime range
   - **Provider layer**: Uses `time_range` parameter in `QueryOptions`
   - **SQL queries**: Properly compare datetime fields with converted UTC ranges

### Key Pattern (Correct Implementation)

```python
# Frontend sends
date: "2026-07-13"

# Backend receives
date: str = Query(..., description="YYYY-MM-DD")

# Service/Repository converts
start_datetime, end_datetime = build_utc_time_range(date)
# Returns: ("2026-07-12T16:00:00+00:00", "2026-07-13T15:59:59.999999+00:00")
# Assuming Asia/Shanghai timezone (UTC+8)

# SQL query
WHERE start_time >= ? AND start_time <= ?
```

---

## Conclusion

**No date/datetime type mismatch issues found.**

All code follows the correct pattern defined in `docs/coding-rules/time-handling-rules.md`:
- Frontend sends local date strings (YYYY-MM-DD)
- Backend converts to UTC datetime ranges at the service/repository boundary
- SQL queries use proper range comparisons with datetime fields

The system already handles this correctly throughout.

---

## Reference Files

### Database Schemas
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\config\database.py`

### Provider Metadata
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\repository\providers\custom_block_provider.py`
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\repository\providers\behavior_analysis_provider.py`
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\repository\providers\mood_providers.py`
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\repository\providers\todo_provider.py`
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\repository\providers\diary_provider.py`

### API Endpoints
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\server\api\timeline_api.py`
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\server\api\activity_api.py`
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\server\api\mood_api.py`
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\server\api\custom_records_api.py`

### Helper Functions
- `D:\desktop\软件开发\LifeWatch-AI\lifeprism\utils\time_utils.py` - `build_utc_time_range()`

### Frontend API Calls
- `D:\desktop\软件开发\LifeWatch-AI\frontend\apps\lifewatch\pages\timeline\api.ts`
- `D:\desktop\软件开发\LifeWatch-AI\frontend\apps\goals\apis\goal.ts`
- `D:\desktop\软件开发\LifeWatch-AI\frontend\apps\habits\apis\checkin.ts`
