#!/usr/bin/env python3
"""
Web-Demo 每日数据刷新脚本（每天 12:00 执行）

生成"今天"的模拟数据，使演示环境看起来有持续的新数据。
覆盖：数据库表（9 张）+ 日记文件 + behavior.md 追加

用法：
    python scripts/demo/refresh_daily_data.py [--data-path PATH] [--force]

    --data-path  数据目录路径（默认: localData）
    --force      强制刷新（即使今天已有数据）
"""

import argparse
import random
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ==================== 配置模板（与 generate_demo_data.py 共享） ====================

FEATURE_NAMES = ["用户认证", "数据同步", "消息推送", "文件上传", "搜索优化",
                 "API 接口", "前端组件", "数据可视化", "性能优化", "错误处理"]
COMPONENT_NAMES = ["core", "api", "frontend", "database", "auth", "notification", "storage"]
TOPIC_NAMES = ["React Hooks", "FastAPI 中间件", "SQLite 优化", "Docker 部署",
               "Redis 缓存", "WebSocket", "GraphQL", "RESTful API 设计"]

DEMO_APPS = [
    ("Code.exe", "Visual Studio Code", "cat-work", "subcat-work-other"),
    ("codebuddy.exe", "CodeBuddy - Project", "cat-work", "subcat-work-other"),
    ("chrome.exe", "GitHub - repository", "cat-work", "subcat-work-other"),
    ("chrome.exe", "Stack Overflow", "cat-work", "subcat-work-other"),
    ("chrome.exe", "Documentation", "cat-study", "subcat-study-other"),
    ("chrome.exe", "YouTube - Tutorial", "cat-study", "subcat-study-other"),
    ("chrome.exe", "Bilibili", "cat-entertainment", "subcat-entertainment-other"),
    ("terminal.exe", "Terminal", "cat-work", "subcat-work-other"),
    ("spotify.exe", "Spotify", "cat-entertainment", "subcat-entertainment-other"),
    ("wechat.exe", "微信", "cat-other", "subcat-other-other"),
    ("notion.exe", "Notion", "cat-work", "subcat-work-other"),
    ("obsidian.exe", "Obsidian", "cat-study", "subcat-study-other"),
]

MOOD_TEMPLATES = [
    {"mood_type_id": "joy", "score": 90, "content": "今天的开发进展很顺利，解决了一个关键问题"},
    {"mood_type_id": "calm", "score": 70, "content": "按计划推进工作，节奏刚好，心情平稳"},
    {"mood_type_id": "pensive", "score": 50, "content": "在思考下一步的方向，有一些需要理清的地方"},
    {"mood_type_id": "calm", "score": 70, "content": "下午运动后状态不错，完成了计划中的任务"},
]

DIARY_TODAY_TEMPLATES = [
    {
        "mood": "calm", "importance": "normal",
        "morning": "今天状态不错，按计划推进项目。上午主要处理了一些遗留的代码审查问题。",
        "evening": "今天的效率令人满意，完成了大部分计划。傍晚散了会儿步。\n\n### 今天最有价值的一件事情\n\n重建了部分核心模块的代码结构，为后续扩展做好了准备。\n\n### 今天发生的好事情\n\n收到了用户对之前功能的正向反馈。",
    },
    {
        "mood": "joy", "importance": "important",
        "morning": "精神很好，今天的重点是完成当前迭代的最后几个任务。",
        "evening": "迭代顺利收尾！比预期提前完成了所有任务。\n\n### 今天最有价值的一件事情\n\n优化后的查询性能提升了 40%，超过了预期目标。\n\n### 今天发生的好事情\n\n下午和同事进行了一次高效的方案讨论。",
    },
    {
        "mood": "pensive", "importance": "important",
        "morning": "今天主要是技术调研和方案评审，为下一个迭代做准备。",
        "evening": "调研了三个候选方案，各有优劣，需要进一步评估后再做决定。\n\n### 今天最有价值的一件事情\n\n梳理清楚了技术选型的决策依据，对后续方向有了更清晰的认识。\n\n### 今天发生的好事情\n\n学习了一个新的设计模式，可以用在接下来的开发中。",
    },
]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


class DailyDataRefresher:
    """每日数据刷新器"""

    def __init__(self, data_path: Path, force: bool = False):
        self.data_path = data_path.resolve()
        self.force = force
        self.db_path = self.data_path / "dataset" / "lifewatch_ai.db"
        self.today = datetime.now()
        self.today_str = self.today.strftime("%Y-%m-%d")

    def run(self):
        if not self.db_path.exists():
            print(f"[ERROR] 数据库不存在: {self.db_path}")
            sys.exit(1)

        print(f"[INFO] 数据目录: {self.data_path}")
        print(f"[INFO] 今天日期: {self.today_str}")

        if not self.force and self._today_data_exists():
            print("[INFO] 今天的数据已存在，跳过刷新（使用 --force 强制刷新）")
            return

        print("\n[1/3] 刷新数据库今天的数据...")
        self._refresh_db()

        print("\n[2/3] 生成今天的日记文件...")
        self._generate_today_diary()

        print("\n[3/3] 追加今天的行为总结...")
        self._append_behavior_md()

        print(f"\n[DONE] {self.today_str} 数据刷新完成！")

    def _today_data_exists(self) -> bool:
        """检查今天是否已有数据（通过 behavior_analysis 表判断）"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute(
                "SELECT COUNT(*) FROM user_app_behavior_log WHERE start_time LIKE ?",
                (f"{self.today_str}%",)
            )
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception:
            return False

    # ==================== 数据库刷新 ====================

    def _refresh_db(self):
        conn = sqlite3.connect(str(self.db_path))

        self._refresh_behavior_logs(conn)
        self._refresh_behavior_analysis(conn)
        self._refresh_raw_behavior(conn)
        self._refresh_mood_entries(conn)
        self._refresh_daily_focus(conn)
        self._refresh_timeline_blocks(conn)
        self._refresh_goal_stats(conn)
        self._refresh_habit_checkins(conn)
        self._refresh_todo_status(conn)

        conn.commit()
        conn.close()
        print("  数据库刷新完成")

    def _today_exists(self, conn: sqlite3.Connection, table: str, date_column: str = "start_time") -> bool:
        """检查表中是否已有今天的数据"""
        if not self.force:
            try:
                cursor = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {date_column} LIKE ?",
                    (f"{self.today_str}%",)
                )
                return cursor.fetchone()[0] > 0
            except Exception:
                return False
        return False

    def _refresh_behavior_logs(self, conn):
        """生成今天的应用使用日志"""
        if self._today_exists(conn, "user_app_behavior_log", "start_time"):
            print("  [skip] user_app_behavior_log 今天已有数据")
            return

        now = datetime.now()
        start_hour = 8
        current_hour = now.hour
        if current_hour < start_hour:
            current_hour = start_hour + 1

        total = 0
        # 模拟从 8:00 到当前时间的应用使用
        for hour in range(start_hour, min(current_hour + 1, 24)):
            if hour > current_hour:
                break
            num_entries = random.randint(2, 5)

            for _ in range(num_entries):
                app, title, cat_id, sub_id = random.choice(DEMO_APPS)
                minute = random.randint(0, 59)
                start_time_str = self.today.replace(hour=hour, minute=minute, second=0).strftime("%Y-%m-%d %H:%M:%S")
                duration = random.randint(3, 60) * 60  # 3-60 分钟
                end_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S") + timedelta(seconds=duration)
                end_time_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

                conn.execute(
                    """INSERT INTO user_app_behavior_log
                       (start_time, end_time, duration, app, title, is_multipurpose_app,
                        category_id, sub_category_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
                    (start_time_str, end_time_str, duration, app, title,
                     cat_id, sub_id, iso_now(), iso_now())
                )
                total += 1

        print(f"  [ok] user_app_behavior_log: {total} 条 (8:00 ~ {current_hour}:00)")

    def _refresh_behavior_analysis(self, conn):
        """生成今天的行为分析"""
        if self._today_exists(conn, "behavior_analysis", "start_time"):
            print("  [skip] behavior_analysis 今天已有数据")
            return

        total = 0
        now_hour = datetime.now().hour
        for hour in range(8, min(now_hour + 1, 23), 2):
            start_time_str = self.today.replace(hour=hour, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
            end_time_str = self.today.replace(hour=hour + 1, minute=30, second=0).strftime("%Y-%m-%d %H:%M:%S")

            behavior_texts = [
                f"编写 {random.choice(FEATURE_NAMES)} 相关代码",
                f"查阅 {random.choice(TOPIC_NAMES)} 技术文档",
                "进行代码审查与优化",
                "处理日常开发任务",
                "参与团队沟通与协作",
            ]
            behavior = random.choice(behavior_texts)

            conn.execute(
                """INSERT INTO behavior_analysis
                   (start_time, end_time, behavior, behavior_summary, title,
                    screen_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (start_time_str, end_time_str, behavior, behavior[:50],
                 f"上午时段分析 {hour}", random.randint(5, 15), iso_now(), iso_now())
            )
            total += 1
        print(f"  [ok] behavior_analysis: {total} 条")

    def _refresh_raw_behavior(self, conn):
        """生成今天的原始行为分析"""
        if self._today_exists(conn, "raw_behavior_analysis", "start_time"):
            print("  [skip] raw_behavior_analysis 今天已有数据")
            return

        total = 0
        now_hour = datetime.now().hour
        for hour in range(8, min(now_hour + 1, 23), 3):
            start_time_str = self.today.replace(hour=hour, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
            end_time_str = self.today.replace(hour=hour + 2, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")

            behaviors = ["开发编码", "查阅文档", "沟通协作"]
            conn.execute(
                """INSERT INTO raw_behavior_analysis
                   (start_time, end_time, behavior, screen_count, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (start_time_str, end_time_str, random.choice(behaviors),
                 random.randint(3, 10), iso_now())
            )
            total += 1
        print(f"  [ok] raw_behavior_analysis: {total} 条")

    def _refresh_mood_entries(self, conn):
        """生成今天的心情记录"""
        if self._today_exists(conn, "mood_entries", "created_at"):
            print("  [skip] mood_entries 今天已有数据")
            return

        total = 0
        for _ in range(random.randint(1, 2)):
            tmpl = random.choice(MOOD_TEMPLATES)
            conn.execute(
                """INSERT INTO mood_entries
                   (id, mood_type_id, score, content, factors, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (f"mood-{uuid.uuid4().hex[:8]}",
                 tmpl["mood_type_id"], tmpl["score"], tmpl["content"],
                 '["工作","健康"]', iso_now(), iso_now())
            )
            total += 1
        print(f"  [ok] mood_entries: {total} 条")

    def _refresh_daily_focus(self, conn):
        """生成今天的日焦点"""
        if self._today_exists(conn, "daily_focus", "date"):
            print("  [skip] daily_focus 今天已有数据")
            return

        focus_options = [
            f"完成 {random.choice(FEATURE_NAMES)} 功能开发",
            f"推进 {random.choice(COMPONENT_NAMES)} 模块优化",
            f"学习 {random.choice(TOPIC_NAMES)} 并实践",
            "整理本周工作内容，规划下周任务",
        ]
        conn.execute(
            """INSERT INTO daily_focus (date, content, created_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            (self.today_str, random.choice(focus_options), iso_now(), iso_now())
        )
        print("  [ok] daily_focus: 1 条")

    def _refresh_timeline_blocks(self, conn):
        """生成今天的时间块"""
        if self._today_exists(conn, "timeline_custom_block", "start_time"):
            print("  [skip] timeline_custom_block 今天已有数据")
            return

        total = 0
        now_hour = datetime.now().hour
        blocks = [
            ("专注开发", "cat-work", "subcat-work-other", "#5B8FF9", 9, 60),
            ("阅读时间", "cat-study", "subcat-study-other", "#5AD8A6", 13, 30),
            ("午休", "cat-other", "subcat-other-other", "#cbd5e1", 12, 30),
            ("散步", "cat-other", "subcat-other-other", "#5AD8A6", 17, 30),
        ]

        for content, cat_id, sub_id, color, hour, duration_min in blocks:
            if hour > now_hour:
                continue
            if hour == now_hour and datetime.now().minute < duration_min:
                continue

            start_time_str = self.today.replace(hour=hour, minute=random.randint(0, 30)).strftime("%Y-%m-%dT%H:%M:%S")
            end_time_str = (datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S") +
                            timedelta(minutes=duration_min)).strftime("%Y-%m-%dT%H:%M:%S")

            conn.execute(
                """INSERT INTO timeline_custom_block
                   (start_time, end_time, duration, content, color,
                    category_id, sub_category_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (start_time_str, end_time_str, duration_min,
                 content, color, cat_id, sub_id, iso_now(), iso_now())
            )
            total += 1
        print(f"  [ok] timeline_custom_block: {total} 条")

    def _refresh_goal_stats(self, conn):
        """生成今天的目标统计"""
        if self._today_exists(conn, "goal_stats", "date"):
            print("  [skip] goal_stats 今天已有数据")
            return

        for goal_id in ["goal-daily", "goal-example"]:
            conn.execute(
                """INSERT INTO goal_stats
                   (goal_id, date, time_spent, completed_todo_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (goal_id, self.today_str,
                 random.randint(20, 180), random.randint(0, 2),
                 iso_now(), iso_now())
            )
        print("  [ok] goal_stats: 2 条")

    def _refresh_habit_checkins(self, conn):
        """生成今天的习惯打卡"""
        if self._today_exists(conn, "habit_checkins", "date"):
            print("  [skip] habit_checkins 今天已有数据")
            return

        # 查询所有活跃习惯
        cursor = conn.execute("SELECT id FROM habits WHERE status='active'")
        habits = [row[0] for row in cursor.fetchall()]

        # 查询每个习惯的活跃挑战
        total = 0
        for habit_id in habits:
            cursor = conn.execute(
                "SELECT id FROM habit_challenges WHERE habit_id=? AND status='in_progress'",
                (habit_id,)
            )
            challenges = [row[0] for row in cursor.fetchall()]
            if not challenges:
                continue  # 没有活跃挑战，跳过打卡
            challenge_id = challenges[0]

            # 根据当前时间随机决定是否打卡（上午 ~80% 完成，下午 ~50%）
            current_hour = datetime.now().hour
            if current_hour < 12 and random.random() < 0.8:
                will_checkin = True
            elif current_hour >= 12 and random.random() < 0.5:
                will_checkin = True
            else:
                will_checkin = False

            if will_checkin:
                conn.execute(
                    """INSERT INTO habit_checkins
                       (id, habit_id, challenge_id, date, completed_at, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"checkin-demo-{uuid.uuid4().hex[:8]}",
                     habit_id, challenge_id, self.today_str,
                     iso_now(), iso_now())
                )
                total += 1

        print(f"  [ok] habit_checkins: {total} 条")

    def _refresh_todo_status(self, conn):
        """随机将今天 scheduled 的部分 todo 标记为 completed"""
        now = datetime.now()
        if now.hour < 15:
            print("  [skip] todo 状态更新（15:00 后才执行）")
            return

        cursor = conn.execute(
            "SELECT id, content FROM todo_list WHERE date=? AND state='scheduled'",
            (self.today_str,)
        )
        today_todos = cursor.fetchall()

        if not today_todos:
            print("  [info] 今天没有 scheduled 的 todo")
            return

        # 随机完成 30%-70%
        completed = 0
        for todo_id, _ in today_todos:
            if random.random() < 0.5:
                conn.execute(
                    "UPDATE todo_list SET state='completed', actual_finished_at=?, updated_at=? WHERE id=?",
                    (self.today_str, iso_now(), todo_id)
                )
                completed += 1

        print(f"  [ok] todo 状态: {completed}/{len(today_todos)} 标记为已完成")

    # ==================== 文件刷新 ====================

    def _generate_today_diary(self):
        """生成今天的日记文件"""
        diary_dir = self.data_path / "diary"
        year_str = self.today.strftime("%Y")
        month_str = self.today.strftime("%m")
        file_path = diary_dir / year_str / month_str / f"{self.today_str}.md"

        if file_path.exists() and not self.force:
            print("  [skip] 今天的日记文件已存在")
            return

        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmpl = random.choice(DIARY_TODAY_TEMPLATES)
        content = f"## Morning Page\n\n{tmpl['morning']}\n\n## Evening Page\n\n{tmpl['evening']}\n"
        file_path.write_text(content, encoding="utf-8")
        print(f"  [ok] 日记文件: {file_path}")

    def _append_behavior_md(self):
        """追加今天的行为总结到 behavior.md"""
        daily_data_dir = self.data_path / "user" / "daily_data"
        file_path = daily_data_dir / "behavior.md"

        if not file_path.exists():
            print("  [warn] behavior.md 不存在，跳过追加（请先运行 generate_demo_data.py）")
            return

        content = file_path.read_text(encoding="utf-8")

        # 检查今天是否已经追加过
        if f"## {self.today_str}" in content and not self.force:
            print("  [skip] behavior.md 今天已追加")
            return

        tmpl = random.choice(DIARY_TODAY_TEMPLATES)
        now = datetime.now()
        work_hours = max(1, (now.hour - 8) * random.uniform(0.4, 0.7))
        ent_hours = max(0, (now.hour - 8) * random.uniform(0.1, 0.3))

        today_entry = f"""
## {self.today_str}
### 行为总结
1. 今日概览：当天进行软件开发工作，推进了项目进度。截至当前时间，电脑使用以工作/学习为主。
2. 电脑使用总览：工作/学习约 {work_hours:.1f} 小时，娱乐约 {ent_hours:.1f} 小时。
3. 高频使用时段：
   - 08:30~12:00：以工作/学习为主，主要编写代码和文档
   - 13:30~{now.hour:02d}:00：工作/学习与短暂休息交替

### 日记总结
用户输入标签： 心情：{tmpl['mood']} 重要程度: {tmpl['importance']}
1. 客观事实与反应：
   [{self.today_str}]
   1. [上午] {tmpl['morning'][:80]}...
   2. [下午] 继续推进项目开发任务。
2. 日记总结：记录了今天的开发工作进展和个人状态。
3. 整体状态：心情平稳，当天计划推进中。
"""

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(today_entry)
        print("  [ok] behavior.md 已追加今天条目")


# ==================== 主入口 ====================

def main():
    parser = argparse.ArgumentParser(description="Web-Demo 每日数据刷新脚本")
    parser.add_argument("--data-path", default="localData",
                        help="数据目录路径（默认: localData）")
    parser.add_argument("--force", action="store_true",
                        help="强制刷新（即使今天已有数据）")
    args = parser.parse_args()

    data_path = Path(args.data_path).resolve()
    if not data_path.exists():
        print(f"[ERROR] 数据目录不存在: {data_path}")
        sys.exit(1)

    random.seed(datetime.now().strftime("%Y%m%d"))

    refresher = DailyDataRefresher(data_path, args.force)
    refresher.run()


if __name__ == "__main__":
    main()
