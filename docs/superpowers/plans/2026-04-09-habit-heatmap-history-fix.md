# Habit Heatmap History Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复习惯热力图历史计算，使分母按“当天应计入的唯一 habit”计算、分子按唯一 `(habit_id, date)` 计算，不再被当前 `active` 状态、新增 habit、暂停状态或重复打卡污染。

**Architecture:** 保持修复范围收敛在 `habit_stats_service`，不新增表。热力图改为读取当前仍存在的所有 habit，再结合 challenge 历史区间推导某天是否应计入基数；同一天命中多个 challenge 时按 `habit_id` 去重。已知限制是历史频率仍沿用当前 habit 的 frequency 解释，此限制需要在代码注释与变更说明里明确。

**Tech Stack:** Python 3.13, FastAPI service layer, provider singletons, pytest, monkeypatch

---

### Task 1: 写热力图回归测试

**Files:**
- Create: `test/server/services/test_habit_stats_service.py`
- Modify: none
- Test: `test/server/services/test_habit_stats_service.py`

- [ ] **Step 1: 写失败测试文件**

```python
from datetime import date

from lifeprism.server.services import habit_stats_service


def _habit(
    habit_id: str,
    *,
    created_at: str,
    status: str = "active",
    frequency_type: str = "daily",
    frequency_config: str | None = None,
) -> dict:
    return {
        "id": habit_id,
        "name": habit_id,
        "status": status,
        "created_at": created_at,
        "frequency_type": frequency_type,
        "frequency_config": frequency_config,
    }


def _challenge(
    challenge_id: str,
    habit_id: str,
    *,
    start_date: str,
    end_date: str,
    status: str,
    finished_at: str | None = None,
) -> dict:
    return {
        "id": challenge_id,
        "habit_id": habit_id,
        "start_date": start_date,
        "end_date": end_date,
        "status": status,
        "finished_at": finished_at,
    }


def _checkin(habit_id: str, challenge_id: str, checkin_date: str) -> dict:
    return {
        "id": f"checkin-{habit_id}-{checkin_date}",
        "habit_id": habit_id,
        "challenge_id": challenge_id,
        "date": checkin_date,
    }


def _install_provider_stubs(monkeypatch, habits, challenges_by_habit, checkins):
    def fake_get_habits(status=None):
        if status is None:
            return list(habits)
        return [habit for habit in habits if habit["status"] == status]

    monkeypatch.setattr(habit_stats_service.habit_provider, "get_habits", fake_get_habits)
    monkeypatch.setattr(
        habit_stats_service.habit_challenge_provider,
        "get_challenges_by_habit",
        lambda habit_id: list(challenges_by_habit.get(habit_id, [])),
    )
    monkeypatch.setattr(
        habit_stats_service.habit_checkin_provider,
        "get_checkins_in_date_range",
        lambda start_date, end_date, habit_ids: [
            row for row in checkins
            if start_date <= row["date"] <= end_date and row["habit_id"] in habit_ids
        ],
    )


def test_heatmap_excludes_future_created_habit_from_past_denominator(monkeypatch):
    habits = [
        _habit("habit-1", created_at="2026-04-01 09:00:00"),
        _habit("habit-2", created_at="2026-04-10 09:00:00"),
    ]
    challenges_by_habit = {
        "habit-1": [_challenge("challenge-1", "habit-1", start_date="2026-04-01", end_date="2026-04-30", status="in_progress")],
        "habit-2": [_challenge("challenge-2", "habit-2", start_date="2026-04-10", end_date="2026-05-09", status="in_progress")],
    }
    checkins = [_checkin("habit-1", "challenge-1", "2026-04-09")]
    _install_provider_stubs(monkeypatch, habits, challenges_by_habit, checkins)

    rows = habit_stats_service.get_heatmap(date(2026, 4, 10), 2)

    assert rows[0]["date"] == "2026-04-09"
    assert rows[0]["totalHabits"] == 1
    assert rows[0]["completedHabits"] == 1
    assert rows[0]["completionRate"] == 1.0


def test_heatmap_counts_pause_day_but_excludes_days_after_pause(monkeypatch):
    habits = [_habit("habit-1", created_at="2026-04-01 09:00:00", status="paused")]
    challenges_by_habit = {
        "habit-1": [
            _challenge(
                "challenge-1",
                "habit-1",
                start_date="2026-04-01",
                end_date="2026-04-23",
                status="cancelled",
                finished_at="2026-04-09T15:50:44",
            )
        ]
    }
    checkins = [_checkin("habit-1", "challenge-1", "2026-04-09")]
    _install_provider_stubs(monkeypatch, habits, challenges_by_habit, checkins)

    rows = habit_stats_service.get_heatmap(date(2026, 4, 10), 2)

    assert rows[0]["date"] == "2026-04-09"
    assert rows[0]["totalHabits"] == 1
    assert rows[0]["completedHabits"] == 1
    assert rows[1]["date"] == "2026-04-10"
    assert rows[1]["totalHabits"] == 0
    assert rows[1]["completedHabits"] == 0


def test_heatmap_dedupes_overlapping_challenges_for_same_habit(monkeypatch):
    habits = [_habit("habit-1", created_at="2026-04-01 09:00:00")]
    challenges_by_habit = {
        "habit-1": [
            _challenge(
                "challenge-old",
                "habit-1",
                start_date="2026-04-01",
                end_date="2026-04-23",
                status="cancelled",
                finished_at="2026-04-09T15:50:44",
            ),
            _challenge(
                "challenge-new",
                "habit-1",
                start_date="2026-04-09",
                end_date="2026-05-07",
                status="in_progress",
            ),
        ]
    }
    checkins = [_checkin("habit-1", "challenge-new", "2026-04-09")]
    _install_provider_stubs(monkeypatch, habits, challenges_by_habit, checkins)

    rows = habit_stats_service.get_heatmap(date(2026, 4, 9), 1)

    assert rows[0]["totalHabits"] == 1
    assert rows[0]["completedHabits"] == 1


def test_heatmap_dedupes_duplicate_checkins_by_habit_and_date(monkeypatch):
    habits = [
        _habit("habit-1", created_at="2026-04-01 09:00:00"),
        _habit("habit-2", created_at="2026-04-01 09:00:00"),
    ]
    challenges_by_habit = {
        "habit-1": [_challenge("challenge-1", "habit-1", start_date="2026-04-01", end_date="2026-04-30", status="in_progress")],
        "habit-2": [_challenge("challenge-2", "habit-2", start_date="2026-04-01", end_date="2026-04-30", status="in_progress")],
    }
    checkins = [
        _checkin("habit-1", "challenge-1", "2026-04-09"),
        _checkin("habit-1", "challenge-overlap", "2026-04-09"),
        _checkin("habit-2", "challenge-2", "2026-04-09"),
    ]
    _install_provider_stubs(monkeypatch, habits, challenges_by_habit, checkins)

    rows = habit_stats_service.get_heatmap(date(2026, 4, 9), 1)

    assert rows[0]["totalHabits"] == 2
    assert rows[0]["completedHabits"] == 2
    assert rows[0]["completionRate"] == 1.0
```

- [ ] **Step 2: 运行测试并确认当前实现失败**

Run:

```bash
pytest test/server/services/test_habit_stats_service.py -v
```

Expected:
- `test_heatmap_excludes_future_created_habit_from_past_denominator` 失败，当前实现会把 `habit-2` 算进 `2026-04-09` 的分母
- `test_heatmap_counts_pause_day_but_excludes_days_after_pause` 失败，当前实现只取当前 `active` habit
- `test_heatmap_dedupes_duplicate_checkins_by_habit_and_date` 失败，当前实现直接按 `date` 累加原始打卡行

- [ ] **Step 3: 提交测试骨架**

```bash
git add test/server/services/test_habit_stats_service.py
git commit -m "test: add habit heatmap history regression coverage"
```

### Task 2: 在服务层按历史 challenge 区间重算热力图

**Files:**
- Modify: `lifeprism/server/services/habit_stats_service.py`
- Test: `test/server/services/test_habit_stats_service.py`

- [ ] **Step 1: 为 challenge 历史口径添加辅助函数**

在 `lifeprism/server/services/habit_stats_service.py` 中新增以下辅助函数，放在 `get_heatmap()` 之前：

```python
def _parse_datetime_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _get_habit_created_date(habit_row: Dict[str, Any]) -> date:
    created_at = habit_row.get("created_at")
    if not created_at:
        raise ValidationError("习惯缺少 created_at，无法计算热力图历史区间")
    return _parse_datetime_date(created_at)


def _get_challenge_effective_end(challenge: Dict[str, Any]) -> date:
    end_date = date.fromisoformat(challenge["end_date"])
    finished_date = _parse_datetime_date(challenge.get("finished_at"))
    if finished_date is None:
        return end_date
    return min(end_date, finished_date)


def _is_habit_active_on_day(
    habit_row: Dict[str, Any],
    challenges: List[Dict[str, Any]],
    day_obj: date,
) -> bool:
    if day_obj < _get_habit_created_date(habit_row):
        return False

    for challenge in challenges:
        challenge_start = date.fromisoformat(challenge["start_date"])
        challenge_end = _get_challenge_effective_end(challenge)
        if challenge_start <= day_obj <= challenge_end:
            return True
    return False
```

- [ ] **Step 2: 用“所有现存 habit + challenge 历史 + 去重分子”重写 `get_heatmap()`**

将 `get_heatmap()` 的核心逻辑改为下面这个结构：

```python
def get_heatmap(today: date, days: int) -> List[Dict[str, Any]]:
    """获取过去 days 天热力图数据。"""
    habits = habit_provider.get_habits()
    if not habits:
        result = []
        for i in range(days):
            d = (today - timedelta(days=days - 1 - i)).isoformat()
            result.append({
                "date": d,
                "totalHabits": 0,
                "completedHabits": 0,
                "completionRate": None,
                "isRestDay": True,
            })
        return result

    parsed_habits = {
        habit["id"]: {
            "row": habit,
            "freq": _parse_freq_from_row(habit),
            "challenges": habit_challenge_provider.get_challenges_by_habit(habit["id"]),
        }
        for habit in habits
    }

    habit_ids = list(parsed_habits.keys())
    start = (today - timedelta(days=days - 1)).isoformat()
    end = today.isoformat()
    raw_checkins = habit_checkin_provider.get_checkins_in_date_range(start, end, habit_ids)

    completed_habits_by_date: Dict[str, set[str]] = defaultdict(set)
    for row in raw_checkins:
        completed_habits_by_date[row["date"]].add(row["habit_id"])

    result = []
    for i in range(days):
        day_obj = today - timedelta(days=days - 1 - i)
        date_str = day_obj.isoformat()

        scheduled_habit_ids = set()
        for habit_id, payload in parsed_habits.items():
            if not _is_habit_active_on_day(payload["row"], payload["challenges"], day_obj):
                continue
            if not is_scheduled_day(day_obj, payload["freq"]):
                continue
            scheduled_habit_ids.add(habit_id)

        total_habits = len(scheduled_habit_ids)
        completed_habits = len(completed_habits_by_date.get(date_str, set()) & scheduled_habit_ids)
        completion_rate = None if total_habits == 0 else round(min(completed_habits / total_habits, 1.0), 4)

        result.append({
            "date": date_str,
            "totalHabits": total_habits,
            "completedHabits": completed_habits,
            "completionRate": completion_rate,
            "isRestDay": total_habits == 0,
        })
    return result
```

实现时保留两条明确注释：

```python
# 已知限制：历史计划日仍按当前 habit frequency 解释；频率变更历史不回放。
# challenge 允许同日重叠，但热力图分母始终按唯一 habit_id 去重。
```

- [ ] **Step 3: 运行聚焦测试并确认通过**

Run:

```bash
pytest test/server/services/test_habit_stats_service.py -v
```

Expected:
- 4 个回归测试全部通过
- `totalHabits` 在创建日之前不受未来 habit 影响
- `completedHabits` 不会被同一天重复打卡记录抬高

- [ ] **Step 4: 提交服务修复**

```bash
git add lifeprism/server/services/habit_stats_service.py test/server/services/test_habit_stats_service.py
git commit -m "fix: correct habit heatmap historical denominator"
```

### Task 3: 做接口级验证并记录已知限制

**Files:**
- Modify: `docs/superpowers/plans/2026-04-09-habit-heatmap-history-fix.md`
- Test: `test/server/services/test_habit_stats_service.py`

- [ ] **Step 1: 运行一次最小接口冒烟**

如果本地服务已可启动，运行：

```bash
pytest test/server/services/test_habit_stats_service.py -v
```

然后人工调用或通过现有前端页面确认：
- 新增 habit 后，新增日前的历史热力图不变
- pause 当天仍有基数，次日开始不再计入
- 当天改频率导致旧 challenge cancelled、新 challenge in_progress 并存时，分母仍只算 1 个 habit

- [ ] **Step 2: 在交付说明中明确两个风险点**

交付说明必须包含以下文字含义：

```text
1. 热力图历史口径已改为 challenge 区间 + habit 去重，不再依赖当前 active 状态。
2. 已知限制：历史频率仍按当前 habit frequency 解释；若用户过去修改过 frequency，历史计划日可能存在轻微失真。
```

- [ ] **Step 3: 提交最终验证结果**

```bash
git add lifeprism/server/services/habit_stats_service.py test/server/services/test_habit_stats_service.py docs/superpowers/plans/2026-04-09-habit-heatmap-history-fix.md
git commit -m "docs: record habit heatmap history fix plan"
```

---

## Self-Review

### Spec coverage

- “新增 habit 不应污染新增日前历史分母” 已由 Task 1 / Test 1 覆盖。
- “pause 当天算，后续不算” 已由 Task 1 / Test 2 覆盖。
- “cancelled 正常算上，challenge 重叠无所谓，但要按 habit 去重” 已由 Task 1 / Test 3 与 Task 2 的 `scheduled_habit_ids` 去重覆盖。
- “分子需要对重复打卡去重” 已由 Task 1 / Test 4 与 Task 2 的 `completed_habits_by_date` 去重覆盖。
- “已删除 habit 不参与统计” 由 Task 2 中 `habit_provider.get_habits()` 只读取当前现存 habit 满足，前提是删除链路保持删除 `habits` 主表记录。

### Placeholder scan

- 无 `TODO` / `TBD`
- 每个代码变更步骤都给了明确文件与代码块
- 每个验证步骤都给了具体命令

### Type consistency

- 所有辅助函数都使用 `Dict[str, Any]` / `List[Dict[str, Any]]` / `Optional[str]`
- `completed_habits_by_date` 的去重单位是 `set[str]`
- `get_heatmap()` 对外返回结构保持不变，不影响现有 API 形状

Plan complete and saved to `docs/superpowers/plans/2026-04-09-habit-heatmap-history-fix.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
