from __future__ import annotations

from datetime import date
from typing import Any


def _is_completed(todo: dict[str, Any]) -> bool:
    """判断 todo 是否已完成。

    Args:
        todo: 待办事项字典，包含 status 字段

    Returns:
        bool: 是否已完成
    """
    return todo.get("status") == "completed"


def _is_overdue(todo: dict[str, Any], reference_date: str) -> bool:
    """判断 todo 是否逾期（未完成且截止日期早于参考日期，不包括参考日期当天）。

    Args:
        todo: 待办事项字典，包含 status, due_date 字段
        reference_date: 参考日期（ISO 格式，如 "2026-04-04"）

    Returns:
        bool: 是否逾期
    """
    if _is_completed(todo):
        return False
    due_date = todo.get("due_date")
    if not due_date:
        return False
    # 只有截止日期严格早于参考日期才算逾期（不包括参考日期当天）
    return due_date < reference_date


def build_todo_execution_context(
    todos: list[dict[str, Any]],
    reference_date: str,
    max_items: int = 10,
) -> dict[str, Any]:
    """构建 todo 执行上下文，统计完成情况和逾期情况。

    Args:
        todos: 待办事项列表，每项包含 id, title, status, due_date
        reference_date: 参考日期（ISO 格式），用于判断逾期
        max_items: 返回的已完成和逾期项目的最大数量

    Returns:
        dict: 包含以下键的字典：
            - total: 总数
            - completed: 已完成数
            - incomplete: 未完成数
            - overdue: 逾期数
            - completion_rate: 完成率（0.0-1.0）
            - completed_items: 已完成项目列表（最多 max_items 项）
            - overdue_items: 逾期项目列表（最多 max_items 项）
    """

    total = len(todos)
    completed_list = [t for t in todos if _is_completed(t)]
    overdue_list = [t for t in todos if _is_overdue(t, reference_date)]
    incomplete = total - len(completed_list)

    completion_rate = 0.0 if total == 0 else round(len(completed_list) / total, 4)

    return {
        "total": total,
        "completed": len(completed_list),
        "incomplete": incomplete,
        "overdue": len(overdue_list),
        "completion_rate": completion_rate,
        "completed_items": [
            {"todo_id": t["id"], "title": t["title"]}
            for t in completed_list[:max_items]
        ],
        "overdue_items": [
            {"todo_id": t["id"], "title": t["title"]}
            for t in overdue_list[:max_items]
        ],
    }


def build_habit_execution_context(
    habits: list[dict[str, Any]],
    habit_checkins: list[dict[str, Any]],
    start_date: str,
    end_date: str,
    max_items: int = 10,
) -> dict[str, Any]:
    """构建 habit 执行上下文，统计打卡完成情况。

    假设每个习惯在日期范围内每天都应该打卡，计算实际打卡数和遗漏数。

    Args:
        habits: 习惯列表，每项包含 id, name
        habit_checkins: 习惯打卡记录列表，每项包含 habit_id, checkin_date
        start_date: 开始日期（ISO 格式）
        end_date: 结束日期（ISO 格式）
        max_items: 返回的已完成和遗漏项目的最大数量

    Returns:
        dict: 包含以下键的字典：
            - tracked: 追踪的习惯数量
            - completed_checkins: 完成的打卡总数
            - missed_checkins: 遗漏的打卡总数
            - completion_rate: 完成率（0.0-1.0）
            - completed_items: 有打卡记录的习惯列表（最多 max_items 项）
            - missed_items: 有遗漏打卡的习惯列表（最多 max_items 项）
    """

    if not habits:
        return {
            "tracked": 0,
            "completed_checkins": 0,
            "missed_checkins": 0,
            "completion_rate": 0.0,
            "completed_items": [],
            "missed_items": [],
        }

    # 计算日期范围内的天数
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    days_count = (end - start).days + 1

    # 构建 habit_id -> checkin 日期集合的映射
    checkin_by_habit: dict[str, set[str]] = {}
    for checkin in habit_checkins:
        habit_id = checkin["habit_id"]
        checkin_date = checkin["date"]  # 字段名是 date 而不是 checkin_date
        if habit_id not in checkin_by_habit:
            checkin_by_habit[habit_id] = set()
        checkin_by_habit[habit_id].add(checkin_date)

    # 计算每个 habit 的完成情况
    completed_items: list[dict[str, str]] = []
    missed_items: list[dict[str, str]] = []
    total_expected = 0
    total_completed = 0

    for habit in habits:
        habit_id = habit["id"]
        habit_name = habit["name"]
        checkin_dates = checkin_by_habit.get(habit_id, set())

        # 简化逻辑：假设每个 habit 在范围内每天都应该打卡
        expected = days_count
        completed = len(checkin_dates)
        missed = expected - completed

        total_expected += expected
        total_completed += completed

        if completed > 0:
            completed_items.append({"habit_id": habit_id, "name": habit_name})

        if missed > 0:
            missed_items.append({"habit_id": habit_id, "name": habit_name})

    completion_rate = 0.0 if total_expected == 0 else round(total_completed / total_expected, 4)

    return {
        "tracked": len(habits),
        "completed_checkins": total_completed,
        "missed_checkins": total_expected - total_completed,
        "completion_rate": completion_rate,
        "completed_items": completed_items[:max_items],
        "missed_items": missed_items[:max_items],
    }


def build_execution_context(
    todos: list[dict[str, Any]],
    habits: list[dict[str, Any]],
    habit_checkins: list[dict[str, Any]],
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """构建执行上下文（todo + habit），聚合待办和习惯的执行情况。

    这是执行数据聚合的主入口函数，用于 AI 总结时理解用户的任务完成情况。

    Args:
        todos: 待办事项列表
        habits: 习惯列表
        habit_checkins: 习惯打卡记录列表
        start_date: 开始日期（ISO 格式）
        end_date: 结束日期（ISO 格式）

    Returns:
        dict: 包含以下键的字典：
            - todos: todo 执行上下文
            - habits: habit 执行上下文
    """

    return {
        "todos": build_todo_execution_context(todos, end_date),
        "habits": build_habit_execution_context(habits, habit_checkins, start_date, end_date),
    }
