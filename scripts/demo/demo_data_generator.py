"""
Web-Demo 演示数据生成器

每次 web-demo 启动时全量重建过去 N 天的模拟数据。覆盖：
- 数据库表：21 张表
- 文件数据：diary MD 文件、behavior.md、recent_state.md

时间格式（2026-07-13 更新）：
- 所有时间戳字段（created_at/updated_at/start_time/end_time/event_time）使用 UTC ISO 8601 格式
- 日期字段（date）仍使用 YYYY-MM-DD 格式
- mood_entries 和 custom_records 使用 event_time 字段替代 created_at 进行查询
"""

from __future__ import annotations

import random
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lifeprism.config.settings_manager import settings
from lifeprism.utils import get_logger
from lifeprism.utils.time_utils import get_utc_now_iso
from scripts.demo.demo_data_config import (
    BEHAVIOR_TEMPLATES,
    COMPONENT_NAMES,
    DAILY_FOCUS_TEMPLATES,
    DEMO_APPS,
    DEMO_COMMITMENTS,
    DEMO_CUSTOM_RECORDS,
    DEMO_HABITS,
    DEMO_VALUES,
    DIARY_TEMPLATES,
    FEATURE_NAMES,
    GOAL_JOURNAL_TEMPLATES,
    MOOD_TEMPLATES,
    TIME_PARADOX_ENTRIES,
    TIMELINE_BLOCK_TEMPLATES,
    TODO_TEMPLATES,
    TOPIC_NAMES,
    WORK_BLOCKS,
)

LOGGER = get_logger(__name__)

# ==================== 工具函数 ====================


def _now_str() -> str:
    """当前时间的 UTC ISO 8601 字符串"""
    return get_utc_now_iso()


def _uid(prefix: str = "") -> str:
    """生成简短唯一 ID"""
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _format_time(dt: datetime) -> str:
    """datetime → UTC ISO 8601 格式"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ==================== 非重叠时间槽生成 ====================


def _generate_non_overlapping_slots(
    date: datetime,
    num_entries: int,
    min_duration_min: int,
    max_duration_min: int,
    day_start_hour: int = 8,
    day_end_hour: int = 23,
    day_end_min: int = 30,
) -> list[tuple[datetime, datetime, int]]:
    """
    为某一天生成 N 个不重叠的时间槽。

    算法：
    1. 计算可用总分钟数
    2. 限制 max_duration 使条目能放入时间窗口
    3. 随机生成时长，剩余时间作为间隙
    4. 用 stick-breaking 法随机分配间隙
    5. 依次构建时间段

    Returns:
        [(start_dt, end_dt, duration_seconds), ...] 按 start_dt 升序排列
    """
    total_available_min = (day_end_hour - day_start_hour) * 60 + day_end_min

    # 限制最大时长，确保所有条目能放入窗口
    capped_max = min(max_duration_min, total_available_min // num_entries)
    if capped_max < min_duration_min:
        capped_max = min_duration_min

    # 随机生成时长
    durations_min = [random.randint(min_duration_min, capped_max) for _ in range(num_entries)]
    total_dur = sum(durations_min)

    # 剩余时间作为间隙
    total_gap = max(0, total_available_min - total_dur)
    gaps = _distribute_gaps(num_entries + 1, total_gap)

    # 构建时间槽
    slots: list[tuple[datetime, datetime, int]] = []
    base = date.replace(hour=day_start_hour, minute=0, second=0, microsecond=0)
    cursor_min = 0
    for i in range(num_entries):
        cursor_min += gaps[i]
        start_dt = base + timedelta(minutes=cursor_min)
        end_dt = start_dt + timedelta(minutes=durations_min[i])
        slots.append((start_dt, end_dt, durations_min[i] * 60))
        cursor_min += durations_min[i]

    return slots


def _distribute_gaps(num_gaps: int, total_gap_min: int) -> list[int]:
    """
    Stick-breaking 法：将 total_gap_min 分钟随机分为 num_gaps 份。
    """
    if total_gap_min <= 0:
        return [0] * num_gaps
    if num_gaps <= 1:
        return [total_gap_min]

    cuts = sorted(random.randint(0, total_gap_min) for _ in range(num_gaps - 1))
    cuts = [0] + cuts + [total_gap_min]
    return [cuts[i + 1] - cuts[i] for i in range(num_gaps)]


# ==================== 生成器主类 ====================


class DemoDataGenerator:
    """演示数据生成器"""

    def __init__(self, data_path: Path, days: int = 7):
        self.data_path = data_path.resolve()
        self.days = days
        self.db_path = self.data_path / "dataset" / "lifewatch_ai.db"
        self.today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        self.start_date = self.today - timedelta(days=days - 1)

    # ==================== 入口 ====================

    def run(self) -> None:
        """执行所有数据生成（先清理，再重建）"""
        if not self.db_path.exists():
            LOGGER.error("数据库不存在: %s，请先启动 web-demo 初始化数据库", self.db_path)
            return

        date_start = self.start_date.strftime("%Y-%m-%d")
        date_end = self.today.strftime("%Y-%m-%d")
        LOGGER.info(
            "开始生成演示数据: 时间范围=%s ~ %s (%d 天), 数据目录=%s",
            date_start,
            date_end,
            self.days,
            self.data_path,
        )

        # 1. 清理已有演示数据
        self._cleanup_demo_data()

        # 2. 生成数据库数据
        self._generate_db_data()

        # 3. 生成文件数据
        self._generate_file_data()

        LOGGER.info("演示数据生成完成: %d 天数据已就绪", self.days)

    # ==================== 数据清理 ====================

    def _cleanup_demo_data(self) -> None:
        """清理已有演示数据（每次启动全量重建）"""
        conn = sqlite3.connect(str(self.db_path))

        date_start = self.start_date.strftime("%Y-%m-%d")
        date_end = self.today.strftime("%Y-%m-%d")

        # 日期范围表：删除时间窗口内的数据
        # date 列存储 YYYY-MM-DD，timestamp 列存储 UTC ISO 8601
        date_range_tables: list[tuple[str, str, str]] = [
            ("user_app_behavior_log", "start_time", "timestamp"),
            ("behavior_analysis", "start_time", "timestamp"),
            ("raw_behavior_analysis", "start_time", "timestamp"),
            ("diary", "date", "date"),
            ("daily_focus", "date", "date"),
            ("goal_stats", "date", "date"),
            ("goal_journal", "date", "date"),
            ("timeline_custom_block", "start_time", "timestamp"),
            ("habit_checkins", "date", "date"),
            ("mood_entries", "event_time", "timestamp"),
        ]
        for table, col, col_type in date_range_tables:
            if col_type == "date":
                conn.execute(
                    f"DELETE FROM {table} WHERE {col} >= ? AND {col} <= ?",
                    (date_start, date_end),
                )
            else:
                # ISO 8601 格式，用 T 分隔
                conn.execute(
                    f"DELETE FROM {table} WHERE {col} >= ? AND {col} <= ?",
                    (f"{date_start}T00:00:00+00:00", f"{date_end}T23:59:59+00:00"),
                )

        # ID 前缀表：删除 demo 前缀的
        conn.execute("DELETE FROM todo_list WHERE id LIKE 't-demo-%'")

        prefix_tables = {
            "habits": "hab-demo-%",
            "habit_challenges": "chall-demo-%",
            "user_values": "val-demo-%",
            "commitments": "cmt-demo-%",
        }
        for table, prefix in prefix_tables.items():
            conn.execute(f"DELETE FROM {table} WHERE id LIKE '{prefix}'")

        # tokens_usage_log 主键是 session_id
        conn.execute("DELETE FROM tokens_usage_log WHERE session_id LIKE 'session-demo-%'")

        # 整表清理（无 demo 标记）
        no_marker_tables = [
            "habit_chains",
            "habit_chain_nodes",
            "time_paradoxes",
            "weekly_focus",
            "category_map_cache",
            "multi_purpose_map_cache",
            "single_purpose_map_cache",
        ]
        for table in no_marker_tables:
            conn.execute(f"DELETE FROM {table}")

        # 自定义记录：清理 demo 数据表
        for record_def in DEMO_CUSTOM_RECORDS:
            slug = record_def["slug"]
            conn.execute(f"DROP TABLE IF EXISTS custom_{slug}")
        conn.execute("DELETE FROM custom_record_fields WHERE id LIKE 'crf-demo-%'")
        conn.execute("DELETE FROM custom_record_types WHERE id LIKE 'crt-demo-%'")

        conn.commit()
        conn.close()
        LOGGER.info("已清理旧演示数据")

    # ==================== 数据库数据生成 ====================

    def _generate_db_data(self) -> None:
        conn = sqlite3.connect(str(self.db_path))

        self._gen_app_cache(conn)
        self._gen_behavior_logs(conn)
        self._gen_behavior_analysis(conn)
        self._gen_raw_behavior_analysis(conn)
        self._gen_mood_entries(conn)
        self._gen_diary(conn)
        self._gen_todos(conn)
        self._gen_goal_journals(conn)
        self._gen_daily_focus(conn)
        self._gen_weekly_focus(conn)
        self._gen_habits(conn)
        self._gen_habit_challenges(conn)
        self._gen_habit_checkins(conn)
        self._gen_habit_chain(conn)
        self._gen_user_values(conn)
        self._gen_commitments(conn)
        self._gen_time_paradoxes(conn)
        self._gen_timeline_custom_blocks(conn)
        self._gen_goal_stats(conn)
        self._gen_tokens_usage(conn)
        self._gen_custom_records(conn)

        conn.commit()
        conn.close()
        LOGGER.info("数据库演示数据生成完成")

    # --- 日期迭代 ---

    def _date_range(self):
        """生成日期列表"""
        for i in range(self.days):
            yield self.start_date + timedelta(days=i)

    # --- 各表生成 ---

    def _gen_app_cache(self, conn: sqlite3.Connection) -> None:
        """生成应用分类缓存数据"""
        seen: set[tuple[str, str]] = set()
        total = 0
        for app, title, cat_id, sub_id, is_mp in DEMO_APPS:
            key = (app, title)
            if key in seen:
                continue
            seen.add(key)

            conn.execute(
                """INSERT INTO category_map_cache
                   (app, title, is_multipurpose_app, app_description, title_analysis,
                    category_id, sub_category_id, state, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    app,
                    title,
                    is_mp,
                    f"{title} 应用程序",
                    f"{title} 的标题分析",
                    cat_id,
                    sub_id,
                    _now_str(),
                    _now_str(),
                ),
            )
            total += 1

        # multi/single purpose cache
        for app, title, cat_id, sub_id, is_mp in DEMO_APPS:
            if is_mp:
                conn.execute(
                    """INSERT INTO multi_purpose_map_cache
                       (id, app, title, category_id, sub_category_id, state, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                    (
                        f"m-{uuid.uuid4().hex[:8]}",
                        app,
                        title,
                        cat_id,
                        sub_id,
                        _now_str(),
                        _now_str(),
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO single_purpose_map_cache
                       (id, app, title, category_id, sub_category_id, state, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                    (
                        f"s-{uuid.uuid4().hex[:8]}",
                        app,
                        title,
                        cat_id,
                        sub_id,
                        _now_str(),
                        _now_str(),
                    ),
                )

        LOGGER.info("  [ok] 缓存数据: %d 条", total)

    # ---- Bug 2 修复: user_app_behavior_log 使用非重叠时间槽 ----

    def _gen_behavior_logs(self, conn: sqlite3.Connection) -> None:
        """生成过去 N 天的应用使用日志（不重叠时间槽）"""
        total = 0
        seen_pairs: set[tuple[str, str]] = set()

        for day in self._date_range():
            num_entries = random.randint(25, 35)
            slots = _generate_non_overlapping_slots(
                date=day,
                num_entries=num_entries,
                min_duration_min=3,
                max_duration_min=90,
                day_start_hour=8,
                day_end_hour=23,
                day_end_min=30,
            )

            for start_dt, end_dt, duration_sec in slots:
                hour = start_dt.hour
                # 确定时段偏好
                ratio = 0.5
                for bh_start, bh_end, work_ratio in WORK_BLOCKS:
                    if bh_start <= hour < bh_end:
                        ratio = work_ratio
                        break

                if random.random() < ratio:
                    pool = [a for a in DEMO_APPS if a[2] in ("cat-work", "cat-study")]
                else:
                    pool = DEMO_APPS

                app, title, cat_id, sub_id, _ = random.choice(pool)

                start_str = _format_time(start_dt)
                end_str = _format_time(end_dt)

                # 处理 UNIQUE(app, start_time) 约束：微调秒数避开冲突
                pair = (app, start_str)
                adj_sec = 0
                while pair in seen_pairs:
                    adj_sec += 1
                    adj_start = start_dt + timedelta(seconds=adj_sec)
                    pair = (app, _format_time(adj_start))

                if adj_sec > 0:
                    adj_start = start_dt + timedelta(seconds=adj_sec)
                    adj_end = end_dt + timedelta(seconds=adj_sec)
                    start_str = _format_time(adj_start)
                    end_str = _format_time(adj_end)

                seen_pairs.add(pair)

                conn.execute(
                    """INSERT INTO user_app_behavior_log
                       (start_time, end_time, duration, app, title, is_multipurpose_app,
                        category_id, sub_category_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
                    (
                        start_str,
                        end_str,
                        duration_sec,
                        app,
                        title,
                        cat_id,
                        sub_id,
                        _now_str(),
                        _now_str(),
                    ),
                )
                total += 1

        LOGGER.info("  [ok] user_app_behavior_log: %d 条 (非重叠)", total)

    # ---- Bug 3 修复: behavior_analysis 使用非重叠时间槽 ----

    def _gen_behavior_analysis(self, conn: sqlite3.Connection) -> None:
        """生成行为分析数据（不重叠时间槽）"""
        total = 0

        for day in self._date_range():
            num_entries = random.randint(7, 12)
            slots = _generate_non_overlapping_slots(
                date=day,
                num_entries=num_entries,
                min_duration_min=10,
                max_duration_min=120,
                day_start_hour=8,
                day_end_hour=22,
                day_end_min=0,
            )

            for i, (start_dt, end_dt, _duration_sec) in enumerate(slots):
                start_str = _format_time(start_dt)
                end_str = _format_time(end_dt)

                template = random.choice(BEHAVIOR_TEMPLATES)
                behavior_detail = template.format(
                    feature=random.choice(FEATURE_NAMES),
                    component=random.choice(COMPONENT_NAMES),
                    topic=random.choice(TOPIC_NAMES),
                    module=random.choice(COMPONENT_NAMES),
                )

                # start_time 是 PRIMARY KEY，非重叠槽已保证唯一性
                conn.execute(
                    """INSERT OR IGNORE INTO behavior_analysis
                       (start_time, end_time, behavior, behavior_summary, title,
                        screen_count, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        start_str,
                        end_str,
                        behavior_detail,
                        behavior_detail[:50],
                        f"行为片段 {i + 1}",
                        random.randint(3, 15),
                        _now_str(),
                        _now_str(),
                    ),
                )
                total += 1

        LOGGER.info("  [ok] behavior_analysis: %d 条 (非重叠)", total)

    def _gen_raw_behavior_analysis(self, conn: sqlite3.Connection) -> None:
        """生成原始行为分析（不重叠时间槽）"""
        total = 0
        behaviors = ["开发编码", "查阅文档", "沟通协作", "休闲娱乐", "学习阅读", "其他活动"]

        for day in self._date_range():
            num_entries = random.randint(5, 8)
            slots = _generate_non_overlapping_slots(
                date=day,
                num_entries=num_entries,
                min_duration_min=10,
                max_duration_min=120,
                day_start_hour=8,
                day_end_hour=22,
                day_end_min=0,
            )

            for start_dt, end_dt, _duration_sec in slots:
                start_str = _format_time(start_dt)
                end_str = _format_time(end_dt)

                conn.execute(
                    """INSERT INTO raw_behavior_analysis
                       (start_time, end_time, behavior, screen_count, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        start_str,
                        end_str,
                        random.choice(behaviors),
                        random.randint(1, 10),
                        _now_str(),
                    ),
                )
                total += 1

        LOGGER.info("  [ok] raw_behavior_analysis: %d 条 (非重叠)", total)

    def _gen_mood_entries(self, conn: sqlite3.Connection) -> None:
        """生成心情记录"""
        total = 0
        for day in self._date_range():
            for _ in range(random.randint(1, 2)):
                template = random.choice(MOOD_TEMPLATES)
                factors_json = '["工作","健康","学习"]'
                event_time = _format_time(
                    day.replace(hour=random.randint(8, 22), minute=random.randint(0, 59))
                )
                conn.execute(
                    """INSERT INTO mood_entries
                       (id, mood_type_id, score, content, factors, event_time, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"mood-{uuid.uuid4().hex[:8]}",
                        template["mood_type_id"],
                        template["score"],
                        template["content"],
                        factors_json,
                        event_time,
                        _now_str(),
                        _now_str(),
                    ),
                )
                total += 1
        LOGGER.info("  [ok] mood_entries: %d 条", total)

    def _gen_diary(self, conn: sqlite3.Connection) -> None:
        """生成日记元数据"""
        total = 0
        for i, day in enumerate(self._date_range()):
            template = DIARY_TEMPLATES[i % len(DIARY_TEMPLATES)]
            conn.execute(
                """INSERT INTO diary
                   (date, mood, importance, custom_tags, word_count,
                    ai_summary, diary_source_hash, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    day.strftime("%Y-%m-%d"),
                    template["mood"],
                    template["importance"],
                    '["日常"]',
                    random.randint(200, 800),
                    f"{template['morning'][:50]}... {template['evening'][:50]}...",
                    _uid("hash-"),
                    _now_str(),
                    _now_str(),
                ),
            )
            total += 1
        LOGGER.info("  [ok] diary: %d 条", total)

    def _gen_todos(self, conn: sqlite3.Connection) -> None:
        """生成待办事项"""
        total = 0
        # scheduled (过去几天 + 今天)
        for day in self._date_range():
            num_todos = random.randint(2, 4)
            scheduled_templates = [
                t for t in TODO_TEMPLATES if t["state"] in ("completed", "scheduled")
            ]
            templates = random.sample(scheduled_templates, min(num_todos, len(scheduled_templates)))
            for idx, tmpl in enumerate(templates):
                todo_id = f"t-demo-{day.strftime('%m%d')}-{idx}"
                content = tmpl["content"].format(
                    feature=random.choice(FEATURE_NAMES),
                    component=random.choice(COMPONENT_NAMES),
                    topic=random.choice(TOPIC_NAMES),
                )
                state = tmpl["state"]
                actual_finished = day.strftime("%Y-%m-%d") if state == "completed" else None

                conn.execute(
                    """INSERT INTO todo_list
                       (id, order_index, content, color, state, link_to_goal_id,
                        date, actual_finished_at, cross_day, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                    (
                        todo_id,
                        idx,
                        content,
                        random.choice(["#FFFFFF", "#E0F2FE", "#DCFCE7", "#FEF3C7", "#FAE8FF"]),
                        state,
                        tmpl["link_to_goal_id"],
                        day.strftime("%Y-%m-%d"),
                        actual_finished,
                        _now_str(),
                        _now_str(),
                    ),
                )
                total += 1

        # pool tasks
        pool_templates = [t for t in TODO_TEMPLATES if t["state"] == "pool"]
        for idx, tmpl in enumerate(pool_templates):
            content = tmpl["content"].format(
                feature=random.choice(FEATURE_NAMES),
                component=random.choice(COMPONENT_NAMES),
                topic=random.choice(TOPIC_NAMES),
            )
            conn.execute(
                """INSERT INTO todo_list
                   (id, pool_order_index, content, color, state, link_to_goal_id,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"t-demo-pool-{idx}",
                    idx,
                    content,
                    "#FFFFFF",
                    "pool",
                    tmpl["link_to_goal_id"],
                    _now_str(),
                    _now_str(),
                ),
            )
            total += 1

        # shelved
        shelved_templates = [t for t in TODO_TEMPLATES if t["state"] == "shelved"]
        for idx, tmpl in enumerate(shelved_templates):
            conn.execute(
                """INSERT INTO todo_list
                   (id, order_index, content, color, state, created_at, updated_at)
                   VALUES (?, 0, ?, ?, 'shelved', ?, ?)""",
                (f"t-demo-shelved-{idx}", tmpl["content"], "#F3F4F6", _now_str(), _now_str()),
            )
            total += 1

        LOGGER.info("  [ok] todo_list: %d 条", total)

    def _gen_goal_journals(self, conn: sqlite3.Connection) -> None:
        """生成目标日志"""
        total = 0
        for day in self._date_range():
            if random.random() < 0.4:
                continue
            tmpl = random.choice(GOAL_JOURNAL_TEMPLATES)
            conn.execute(
                """INSERT INTO goal_journal
                   (id, goal_id, date, time, content, mood, duration, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"journal-demo-{uuid.uuid4().hex[:8]}",
                    tmpl["goal_id"],
                    day.strftime("%Y-%m-%d"),
                    f"{random.randint(8, 22):02d}:{random.randint(0, 59):02d}",
                    tmpl["content"],
                    tmpl["mood"],
                    tmpl["duration"],
                    _now_str(),
                    _now_str(),
                ),
            )
            total += 1
        LOGGER.info("  [ok] goal_journal: %d 条", total)

    def _gen_daily_focus(self, conn: sqlite3.Connection) -> None:
        """生成日焦点"""
        for day in self._date_range():
            tmpl = random.choice(DAILY_FOCUS_TEMPLATES)
            content = tmpl.format(
                feature=random.choice(FEATURE_NAMES),
                component=random.choice(COMPONENT_NAMES),
                topic=random.choice(TOPIC_NAMES),
            )
            conn.execute(
                """INSERT INTO daily_focus (date, content, created_at, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (day.strftime("%Y-%m-%d"), content, _now_str(), _now_str()),
            )
        LOGGER.info("  [ok] daily_focus: %d 条", self.days)

    def _gen_weekly_focus(self, conn: sqlite3.Connection) -> None:
        """生成周焦点"""
        today = self.today
        for week_offset in range(4):
            week_start = today - timedelta(weeks=week_offset, days=today.weekday())
            conn.execute(
                """INSERT INTO weekly_focus
                   (year, month, week_num, content, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    week_start.year,
                    week_start.month,
                    (week_start.day - 1) // 7 + 1,
                    f"第 {4 - week_offset} 周重点：推进核心功能开发与代码质量提升",
                    _now_str(),
                    _now_str(),
                ),
            )
        LOGGER.info("  [ok] weekly_focus: 4 条")

    def _gen_habits(self, conn: sqlite3.Connection) -> None:
        """生成习惯定义"""
        for h in DEMO_HABITS:
            conn.execute(
                """INSERT INTO habits
                   (id, name, description, frequency_type, frequency_config,
                    current_level, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, '{}', ?, 'active', ?, ?)""",
                (
                    h["id"],
                    h["name"],
                    h["description"],
                    h["frequency_type"],
                    h["current_level"],
                    _now_str(),
                    _now_str(),
                ),
            )
        LOGGER.info("  [ok] habits: %d 条", len(DEMO_HABITS))

    def _gen_habit_challenges(self, conn: sqlite3.Connection) -> None:
        """生成习惯挑战"""
        for i, h in enumerate(DEMO_HABITS):
            challenge_start = self.start_date
            challenge_end = self.today + timedelta(days=7)
            conn.execute(
                """INSERT INTO habit_challenges
                   (id, habit_id, challenge_weeks, required_completions,
                    from_level, to_level, start_date, end_date,
                    completed_count, streak_base, status, created_at, updated_at)
                   VALUES (?, ?, 4, ?, ?, ?, ?, ?, ?, 0, 'in_progress', ?, ?)""",
                (
                    f"chall-demo-{i:03d}",
                    h["id"],
                    random.randint(20, 25),
                    h["current_level"],
                    h["current_level"] + 1,
                    challenge_start.strftime("%Y-%m-%d"),
                    challenge_end.strftime("%Y-%m-%d"),
                    random.randint(5, 18),
                    _now_str(),
                    _now_str(),
                ),
            )
        LOGGER.info("  [ok] habit_challenges: %d 条", len(DEMO_HABITS))

    def _gen_habit_checkins(self, conn: sqlite3.Connection) -> None:
        """生成习惯打卡"""
        total = 0
        for day in self._date_range():
            if day >= self.today:
                continue
            for i, h in enumerate(DEMO_HABITS):
                if random.random() < 0.7:
                    time_str = _format_time(
                        day.replace(hour=random.randint(7, 22), minute=random.randint(0, 59))
                    )
                    conn.execute(
                        """INSERT INTO habit_checkins
                           (id, habit_id, challenge_id, date, completed_at, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            f"checkin-demo-{uuid.uuid4().hex[:8]}",
                            h["id"],
                            f"chall-demo-{i:03d}",
                            day.strftime("%Y-%m-%d"),
                            time_str,
                            _now_str(),
                        ),
                    )
                    total += 1
        LOGGER.info("  [ok] habit_checkins: %d 条", total)

    def _gen_habit_chain(self, conn: sqlite3.Connection) -> None:
        """生成习惯链"""
        conn.execute(
            """INSERT INTO habit_chains (name, description, show_in_timeline, created_at, updated_at)
               VALUES ('晨间例行', '每天早上的习惯链条', 1, ?, ?)""",
            (_now_str(), _now_str()),
        )
        chain_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        nodes = [
            ("起床洗漱", None, "07:00"),
            ("冥想练习", "hab-demo-003", "07:20"),
            ("晨间阅读", "hab-demo-001", "07:40"),
            ("写日记", "hab-demo-004", "22:00"),
        ]
        for idx, (name, habit_id, trigger_time) in enumerate(nodes):
            conn.execute(
                """INSERT INTO habit_chain_nodes
                   (chain_id, sort_order, name, habit_id, trigger_time, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (chain_id, idx + 1, name, habit_id, trigger_time, _now_str(), _now_str()),
            )
        LOGGER.info("  [ok] habit_chain: 1 条链 + 4 个节点")

    def _gen_user_values(self, conn: sqlite3.Connection) -> None:
        """生成价值观"""
        for idx, v in enumerate(DEMO_VALUES):
            conn.execute(
                """INSERT INTO user_values
                   (id, keywords, content_positive, content_negative, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    v["id"],
                    v["keywords"],
                    v["content_positive"],
                    v["content_negative"],
                    len(DEMO_VALUES) - idx,
                    _now_str(),
                    _now_str(),
                ),
            )
        LOGGER.info("  [ok] user_values: %d 条", len(DEMO_VALUES))

    def _gen_commitments(self, conn: sqlite3.Connection) -> None:
        """生成承诺"""
        for c in DEMO_COMMITMENTS:
            conn.execute(
                """INSERT INTO commitments
                   (id, content, value_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (c["id"], c["content"], c["value_id"], c["status"], _now_str(), _now_str()),
            )
        LOGGER.info("  [ok] commitments: %d 条", len(DEMO_COMMITMENTS))

    def _gen_time_paradoxes(self, conn: sqlite3.Connection) -> None:
        """生成时间悖论测试"""
        for idx, entry in enumerate(TIME_PARADOX_ENTRIES, start=1):
            conn.execute(
                """INSERT INTO time_paradoxes
                   (id, user_id, version, mode, content, ai_abstract, created_at, updated_at)
                   VALUES (?, 1, 1, ?, ?, ?, ?, ?)""",
                (
                    idx,
                    entry["mode"],
                    entry["content"],
                    entry["ai_abstract"],
                    _now_str(),
                    _now_str(),
                ),
            )
        LOGGER.info("  [ok] time_paradoxes: %d 条", len(TIME_PARADOX_ENTRIES))

    def _gen_timeline_custom_blocks(self, conn: sqlite3.Connection) -> None:
        """生成手动时间块"""
        total = 0
        for day in self._date_range():
            num_blocks = random.randint(2, 4)
            slots = _generate_non_overlapping_slots(
                date=day,
                num_entries=num_blocks,
                min_duration_min=20,
                max_duration_min=90,
                day_start_hour=8,
                day_end_hour=22,
                day_end_min=0,
            )

            for start_dt, end_dt, duration_sec in slots:
                content, cat_id, sub_id, color = random.choice(TIMELINE_BLOCK_TEMPLATES)
                start_str = _format_time(start_dt)
                end_str = _format_time(end_dt)

                conn.execute(
                    """INSERT OR IGNORE INTO timeline_custom_block
                       (start_time, end_time, duration, content, color,
                        category_id, sub_category_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        start_str,
                        end_str,
                        duration_sec // 60,
                        content,
                        color,
                        cat_id,
                        sub_id,
                        _now_str(),
                        _now_str(),
                    ),
                )
                total += 1

        LOGGER.info("  [ok] timeline_custom_block: %d 条", total)

    def _gen_goal_stats(self, conn: sqlite3.Connection) -> None:
        """生成目标统计数据"""
        for day in self._date_range():
            for goal_id in ["goal-daily", "goal-example"]:
                conn.execute(
                    """INSERT INTO goal_stats
                       (goal_id, date, time_spent, completed_todo_count, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        goal_id,
                        day.strftime("%Y-%m-%d"),
                        random.randint(30, 300),
                        random.randint(0, 3),
                        _now_str(),
                    ),
                )
        LOGGER.info("  [ok] goal_stats: %d 条", self.days * 2)

    def _gen_tokens_usage(self, conn: sqlite3.Connection) -> None:
        """生成 token 使用统计"""
        total = 0
        for i, day in enumerate(self._date_range()):
            if i % 2 != 0:
                continue
            conn.execute(
                """INSERT INTO tokens_usage_log
                   (session_id, input_tokens, output_tokens, total_tokens,
                    search_count, result_items_count, mode, created_at)
                   VALUES (?, ?, ?, ?, 0, 0, 'chatbot', ?)""",
                (
                    f"session-demo-{uuid.uuid4().hex[:8]}",
                    random.randint(500, 5000),
                    random.randint(200, 3000),
                    random.randint(700, 8000),
                    _format_time(day.replace(hour=random.randint(8, 22))),
                ),
            )
            total += 1
        LOGGER.info("  [ok] tokens_usage_log: %d 条", total)

    def _gen_custom_records(self, conn: sqlite3.Connection) -> None:
        """生成自定义记录数据（读书、锻炼等）"""
        total_types = 0
        total_entries = 0
        now = _now_str()

        for record_def in DEMO_CUSTOM_RECORDS:
            type_id = record_def["type_id"]
            slug = record_def["slug"]
            data_table = f"custom_{slug}"

            # 1. 写入类型元数据
            conn.execute(
                """INSERT INTO custom_record_types
                   (id, name, slug, description, card_template, icon, accent_color, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    type_id,
                    record_def["name"],
                    slug,
                    record_def["description"],
                    "clean",
                    record_def["icon"],
                    record_def["accent_color"],
                    now,
                    now,
                ),
            )
            total_types += 1

            # 2. 写入字段定义
            for f in record_def["fields"]:
                conn.execute(
                    """INSERT INTO custom_record_fields
                       (id, type_id, field_name, field_key, field_type, sort_order, display_role, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f["id"],
                        type_id,
                        f["field_name"],
                        f["field_key"],
                        f["field_type"],
                        f["sort_order"],
                        f["display_role"],
                        now,
                    ),
                )

            # 3. 创建数据表
            column_defs = ["id TEXT PRIMARY KEY"]
            for f in record_def["fields"]:
                column_defs.append(f"{f['field_key']} TEXT")
            column_defs.append("event_time TEXT")
            column_defs.append("created_at TEXT")
            column_defs.append("updated_at TEXT")
            ddl = f"CREATE TABLE IF NOT EXISTS {data_table} ({', '.join(column_defs)})"
            conn.execute(ddl)

            # 4. 插入过去 N 天的记录（每天随机 0~2 条）
            entry_templates = record_def["entries"]
            for day in self._date_range():
                num_entries = random.randint(1, 2)
                for _ in range(num_entries):
                    tmpl = random.choice(entry_templates)
                    entry_id = f"cre-demo-{uuid.uuid4().hex[:8]}"
                    entry_time = _format_time(
                        day.replace(hour=random.randint(8, 22), minute=random.randint(0, 59))
                    )

                    field_keys = [f["field_key"] for f in record_def["fields"]]
                    values = [tmpl[k] for k in field_keys]

                    columns = ["id"] + field_keys + ["event_time", "created_at", "updated_at"]
                    placeholders = ["?"] * len(columns)
                    params = [entry_id] + values + [entry_time, now, now]

                    conn.execute(
                        f"INSERT INTO {data_table} ({', '.join(columns)}) "
                        f"VALUES ({', '.join(placeholders)})",
                        params,
                    )
                    total_entries += 1

        LOGGER.info("  [ok] custom_records: %d 类型, %d 条记录", total_types, total_entries)

    # ==================== 文件数据生成 ====================

    def _generate_file_data(self) -> None:
        """生成文件类演示数据"""
        self._generate_diary_files()
        self._generate_behavior_md()
        self._generate_recent_state()
        LOGGER.info("文件演示数据生成完成")

    def _generate_diary_files(self) -> None:
        """生成日记 MD 文件"""
        diary_dir = self.data_path / "diary"
        total = 0
        for i, day in enumerate(self._date_range()):
            date_str = day.strftime("%Y-%m-%d")
            year_str = day.strftime("%Y")
            month_str = day.strftime("%m")
            file_path = diary_dir / year_str / month_str / f"{date_str}.md"

            file_path.parent.mkdir(parents=True, exist_ok=True)

            template = DIARY_TEMPLATES[i % len(DIARY_TEMPLATES)]
            feature = random.choice(FEATURE_NAMES)
            component = random.choice(COMPONENT_NAMES)

            morning = template["morning"].format(feature=feature, component=component)
            evening = template["evening"].format(feature=feature, component=component)

            content = f"## Morning Page\n\n{morning}\n\n## Evening Page\n\n{evening}\n"
            file_path.write_text(content, encoding="utf-8")
            total += 1

        LOGGER.info("  [ok] diary 文件: %d 个", total)

    def _generate_behavior_md(self) -> None:
        """生成 behavior.md"""
        daily_data_dir = self.data_path / "user" / "daily_data"
        daily_data_dir.mkdir(parents=True, exist_ok=True)
        file_path = daily_data_dir / "behavior.md"

        lines: list[str] = []
        for i, day in enumerate(self._date_range()):
            if day >= self.today:
                continue
            date_str = day.strftime("%Y-%m-%d")
            template = DIARY_TEMPLATES[i % len(DIARY_TEMPLATES)]

            work_hours = random.uniform(4, 8)
            entertainment_hours = random.uniform(1, 4)
            lines.append(f"## {date_str}")
            lines.append("### 行为总结")
            lines.append(
                "1. 今日概览：当天主要进行软件开发工作，辅以学习和休闲活动。电脑使用集中在上午和下午时段。"
            )
            lines.append(
                f"2. 电脑使用总览：工作/学习约 {work_hours:.1f} 小时，娱乐约 {entertainment_hours:.1f} 小时。"
            )
            lines.append("3. 高频使用时段：")
            lines.append("   - 08:30~12:00：以工作/学习为主")
            lines.append("   - 13:30~18:00：以工作/学习为主，伴有短暂休息")
            lines.append("   - 20:00~22:30：娱乐与学习交替")
            lines.append("")

            lines.append("### 日记总结")
            mood_label = {
                "joy": "有点开心",
                "calm": "平静",
                "pensive": "沉思",
                "melancholy": "不太好",
                "anger": "不太好",
            }.get(template["mood"], "平静")
            lines.append(f"用户输入标签： 心情：{mood_label} 重要程度: {template['importance']}")
            lines.append("1. 客观事实与反应：")
            lines.append(f"   [{date_str}]")
            lines.append(f"   1. [上午] {template['morning'][:80]}...")
            lines.append("   2. [下午] 继续推进开发工作，处理代码审查反馈。")
            lines.append(f"   3. [晚上] {template['evening'][:80]}...")
            lines.append("2. 日记总结：记录了当天的开发工作进展和个人状态反思。")
            lines.append(f"3. 整体状态：心情{mood_label}，当天完成了计划中的主要任务。")
            lines.append("")

        file_path.write_text("\n".join(lines), encoding="utf-8")
        LOGGER.info("  [ok] behavior.md: %d 天数据", self.days - 1)

    def _generate_recent_state(self) -> None:
        """生成 recent_state.md"""
        output_dir = self.data_path / "user" / "daily_data"
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / "recent_state.md"

        end_date = self.today - timedelta(days=1)
        start_date = self.start_date

        content = (
            f"## 近期事件\n"
            f"[{start_date.strftime('%Y-%m-%d')}~{end_date.strftime('%Y-%m-%d')}]："
            f"近期主要进行软件项目开发工作，包括功能迭代、代码优化和文档完善。"
            f"日常保持阅读和运动的习惯，整体状态稳定。\n\n"
            f"[当前仅描述最近发生的用户有较为强烈的情绪波动事件、关键事件，"
            f"忽略部分不重要事件，但不代表也不能就此断章取义推测用户情绪容易波动]\n\n"
            f"## 心理状态和生理状态\n"
            f"1. 心理状态：\n"
            f"[缺少数据说明]：当前由于近7天体现心理状态的数据为演示数据，"
            f"以下内容仅代表部分时间段的心理状态。"
            f"近期心情以平静为主，偶尔因项目进度压力感到焦虑，"
            f"但通过运动和自我调节能够恢复。对技术成长和个人发展持积极态度。\n\n"
            f"2. 生理状态：\n"
            f"[缺少数据说明]：当前由于体现生理状态的数据为演示数据，"
            f"以下内容仅代表部分时间段的生理状态。"
            f"近期睡眠基本规律，偶有晚睡。"
            f"通过每日运动和散步保持基本活动量。饮食以自己做饭为主。\n\n"
            f"## 时间花费与目标\n"
            f"电脑使用总览：{start_date.strftime('%Y-%m-%d')}至{end_date.strftime('%Y-%m-%d')}期间，"
            f"电脑使用以工作/学习为主（约70%），娱乐为辅（约25%），其他占5%。\n"
            f"电脑使用趋势：白天以密集开发工作为主，晚上适当放松。周末使用强度略有下降。\n"
            f"目标总结：持续进行技术开发工作，保持学习与工作平衡。\n\n"
            f"## 旧版本总结\n"
            f"（暂无历史数据 — 演示环境）\n"
        )
        file_path.write_text(content, encoding="utf-8")
        LOGGER.info("  [ok] recent_state.md")


# ==================== 便捷函数 ====================


def generate_demo_data(data_path: Path | None = None, days: int = 7) -> None:
    """
    Web-Demo 演示数据自动生成入口。

    在 lifespan 中调用，每次启动时全量重建演示数据。

    Args:
        data_path: 数据目录路径，None 时自动从 settings.lifeprism_data_path 解析
        days: 生成过去多少天的数据（默认 7 天）
    """
    if data_path is None:
        data_path = settings.lifeprism_data_path

    random.seed(datetime.now().strftime("%Y%m%d"))

    generator = DemoDataGenerator(data_path, days)
    generator.run()
