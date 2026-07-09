#!/usr/bin/env python3
"""
Web-Demo 演示数据生成脚本（一次性运行）

生成过去 7 天的模拟用户数据，包括：
- 数据库表：应用使用日志、行为分析、心情、日记、待办、习惯等（21 张表）
- 文件数据：diary MD 文件、behavior.md、recent_state.md

用法：
    python scripts/demo/generate_demo_data.py [--data-path PATH] [--days 7] [--force]

    --data-path  数据目录路径（默认: localData）
    --days       生成多少天的数据（默认: 7）
    --force      强制重新生成（覆盖已有数据）
"""

import argparse
import random
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ==================== 配置 ====================

# 演示用户使用的应用列表（无个人信息）
DEMO_APPS = [
    # (app, title, category_id, sub_category_id, is_multipurpose)
    ("Code.exe", "Visual Studio Code", "cat-work", "subcat-work-other", 1),
    ("codebuddy.exe", "CodeBuddy - Project Alpha", "cat-work", "subcat-work-other", 1),
    ("chrome.exe", "GitHub - repository", "cat-work", "subcat-work-other", 1),
    ("chrome.exe", "Stack Overflow - Question", "cat-work", "subcat-work-other", 1),
    ("chrome.exe", "Documentation - API Reference", "cat-study", "subcat-study-other", 1),
    ("chrome.exe", "YouTube - Tutorial", "cat-study", "subcat-study-other", 1),
    ("chrome.exe", "Bilibili - 影视", "cat-entertainment", "subcat-entertainment-other", 1),
    ("chrome.exe", "知乎 - 浏览", "cat-entertainment", "subcat-entertainment-other", 1),
    ("chrome.exe", "Gmail - Inbox", "cat-other", "subcat-other-other", 1),
    ("terminal.exe", "Terminal", "cat-work", "subcat-work-other", 0),
    ("spotify.exe", "Spotify", "cat-entertainment", "subcat-entertainment-other", 0),
    ("wechat.exe", "微信", "cat-other", "subcat-other-other", 0),
    ("notion.exe", "Notion - Notes", "cat-work", "subcat-work-other", 1),
    ("obsidian.exe", "Obsidian - Knowledge Base", "cat-study", "subcat-study-other", 0),
    ("steam.exe", "Steam", "cat-entertainment", "subcat-entertainment-other", 0),
    ("figma.exe", "Figma - Design", "cat-work", "subcat-work-other", 0),
]

# 行为分析模板
BEHAVIOR_TEMPLATES = [
    "编写代码，处理 {feature} 功能",
    "调试 {component} 模块的 bug",
    "查阅 {topic} 相关技术文档",
    "参加项目进度同步会议",
    "代码审查，review {module} 模块",
    "编写单元测试，覆盖 {feature} 场景",
    "重构 {component} 代码结构",
    "学习 {topic} 新技术框架",
    "浏览技术社区，了解行业动态",
    "整理项目文档和笔记",
    "回复消息、处理日常沟通",
    "规划设计 {feature} 的架构方案",
]

FEATURE_NAMES = ["用户认证", "数据同步", "消息推送", "文件上传", "搜索优化",
                 "API 接口", "前端组件", "数据可视化", "性能优化", "错误处理"]
COMPONENT_NAMES = ["core", "api", "frontend", "database", "auth", "notification", "storage"]
TOPIC_NAMES = ["React Hooks", "FastAPI 中间件", "SQLite 优化", "Docker 部署",
               "Redis 缓存", "WebSocket", "GraphQL", "RESTful API 设计"]

# 心情条目模板
MOOD_TEMPLATES = [
    {"mood_type_id": "joy", "score": 90, "content": "今天完成了计划中的功能开发，代码运行顺利，感觉很有成就感"},
    {"mood_type_id": "calm", "score": 70, "content": "按部就班地推进项目，节奏稳定，心情平静"},
    {"mood_type_id": "calm", "score": 70, "content": "今天在阳台看了会儿书，阳光很好，感觉很舒适"},
    {"mood_type_id": "pensive", "score": 50, "content": "思考项目的下一步方向，有一些不确定性需要梳理"},
    {"mood_type_id": "pensive", "score": 50, "content": "看了一篇关于技术趋势的文章，引发对未来规划的思考"},
    {"mood_type_id": "melancholy", "score": 30, "content": "今天效率不高，感觉有些疲倦，需要调整节奏"},
    {"mood_type_id": "joy", "score": 90, "content": "运动后精神状态很好，感觉身体在慢慢恢复"},
    {"mood_type_id": "calm", "score": 70, "content": "散步时看到晚霞很美，记录下了这个瞬间"},
]

# 日焦点模板
DAILY_FOCUS_TEMPLATES = [
    "完成 {feature} 功能开发",
    "推进 {component} 模块重构",
    "学习 {topic} 并做笔记",
    "整理项目文档，补充 README",
    "修复已知 bug，提升代码质量",
    "设计 {feature} 方案并评审",
    "完成本周的代码审查工作",
]

# 习惯定义
DEMO_HABITS = [
    {"id": "hab-demo-001", "name": "晨间阅读", "description": "每天早上阅读至少 30 分钟",
     "frequency_type": "daily", "current_level": 2},
    {"id": "hab-demo-002", "name": "每日运动", "description": "每天进行至少 20 分钟的运动",
     "frequency_type": "daily", "current_level": 1},
    {"id": "hab-demo-003", "name": "冥想练习", "description": "每天冥想 10 分钟，培养正念",
     "frequency_type": "daily", "current_level": 1},
    {"id": "hab-demo-004", "name": "写日记", "description": "每天记录当天的思考和感悟",
     "frequency_type": "daily", "current_level": 3},
]

# 价值观
DEMO_VALUES = [
    {"id": "val-demo-001", "keywords": "持续成长;终身学习",
     "content_positive": "保持好奇心，不断学习新知识、新技能，在专业领域持续深耕",
     "content_negative": "不满足于现状，拒绝停滞和固步自封"},
    {"id": "val-demo-002", "keywords": "身心健康;自律",
     "content_positive": "关注身体和心理健康，通过规律运动、健康饮食和充足睡眠维持良好状态",
     "content_negative": "不因工作压力忽视身体信号，不长期透支健康"},
    {"id": "val-demo-003", "keywords": "创造价值;影响力",
     "content_positive": "通过技术能力创造对他人有用的产品，解决实际问题",
     "content_negative": "不做无意义的重复劳动，不满足于表面完成"},
    {"id": "val-demo-004", "keywords": "真实;自我接纳",
     "content_positive": "诚实地面对自己的感受和局限，接纳不完美的自己，同时努力改善",
     "content_negative": "不为了迎合他人而伪装，不过度自我批判"},
]

# 承诺
DEMO_COMMITMENTS = [
    {"id": "cmt-demo-001", "content": "每天阅读技术书籍或文章至少 30 分钟", "value_id": "val-demo-001", "status": "active"},
    {"id": "cmt-demo-002", "content": "每周完成至少 3 次运动训练", "value_id": "val-demo-002", "status": "active"},
    {"id": "cmt-demo-003", "content": "每天 23:00 前放下手机准备入睡", "value_id": "val-demo-002", "status": "active"},
    {"id": "cmt-demo-004", "content": "每季度发布一个开源项目或技术文章", "value_id": "val-demo-003", "status": "active"},
    {"id": "cmt-demo-005", "content": "每天写日记记录思考和感悟", "value_id": "val-demo-004", "status": "active"},
    {"id": "cmt-demo-006", "content": "每周回顾个人目标和进展", "value_id": "val-demo-001", "status": "active"},
]

# 日记模板 — Morning Page / Evening Page
DIARY_TEMPLATES = [
    {
        "mood": "calm", "importance": "normal",
        "morning": "今天天气不错，早上起来后做了简单的拉伸。计划今天主要推进 {feature} 的开发工作。",
        "evening": "今天进展顺利，完成了大部分计划内容。下午抽空看了会儿书。\n\n### 今天最有价值的一件事情\n\n成功调试了一个困扰了两天的 bug，找到了根本原因。\n\n### 今天发生的好事情\n\n傍晚散步时看到了很美的夕阳。",
    },
    {
        "mood": "joy", "importance": "important",
        "morning": "昨晚睡眠质量不错，精神很好。今天计划完成 {feature} 的上线部署。",
        "evening": "今天效率很高！不仅完成了部署，还顺便优化了一些性能瓶颈。\n\n### 今天最有价值的一件事情\n\n发现了一个长期存在的性能问题并成功修复，响应时间降低了 60%。\n\n### 今天发生的好事情\n\n同事对我的代码重构方案表示认可，团队协作很顺畅。",
    },
    {
        "mood": "pensive", "importance": "important",
        "morning": "醒得比较早，想了很久关于项目下一步方向的事情。今天主要做技术调研。",
        "evening": "花了一天时间调研技术方案，有几个不错的选择需要进一步评估。\n\n### 今天最有价值的一件事情\n\n梳理清楚了技术选型的决策矩阵，后续方向更明确了。\n\n### 今天发生的好事情\n\n看了几篇高质量的技术文章，收获颇丰。",
    },
    {
        "mood": "calm", "importance": "normal",
        "morning": "今天状态一般，昨晚有点晚睡。准备从简单的任务开始，逐步进入状态。",
        "evening": "虽然开始有些困难，但逐渐进入状态后还是完成了不少工作。\n\n### 今天最有价值的一件事情\n\n重构了 {component} 模块的代码，可读性和可维护性都有提升。\n\n### 今天发生的好事情\n\n自己做了一顿简单的饭，味道还不错。",
    },
    {
        "mood": "melancholy", "importance": "normal",
        "morning": "天气有些阴沉，心情也有些低落。今天可能需要适当放松一下。",
        "evening": "今天工作效率不太高，有些任务没完成。提醒自己不要给自己太大压力。\n\n### 今天最有价值的一件事情\n\n意识到了自己最近有些过度工作，需要调整节奏。\n\n### 今天发生的好事情\n\n晚上泡了杯热茶，听着音乐发了一会儿呆，感觉放松了些。",
    },
    {
        "mood": "joy", "importance": "important",
        "morning": "今天是周末，计划做一些自己想做的事情：看书、运动、整理房间。",
        "evening": "度过了充实而放松的一天。运动后身体感觉很舒服。\n\n### 今天最有价值的一件事情\n\n花了两个小时深入阅读了一直想读的技术书籍，做了详细的笔记。\n\n### 今天发生的好事情\n\n整理完房间后感觉整个空间都清爽了许多。",
    },
    {
        "mood": "calm", "importance": "important",
        "morning": "新的一周开始，回顾了上周的进展并制定了本周计划。关键任务是 {feature}。",
        "evening": "周一的节奏控制得不错，完成了周计划的分解和任务分配。\n\n### 今天最有价值的一件事情\n\n制定了清晰的本周目标和任务分解，对接下来几天的工作有了明确方向。\n\n### 今天发生的好事情\n\n下班后在阳台看了会儿星星，夜空很清澈。",
    },
]

# 时间悖论模板
TIME_PARADOX_ENTRIES = [
    {
        "mode": "past",
        "content": """回顾过去一年，最大的变化是在技术能力上的成长。从最初的简单 CRUD 到现在能够独立负责一个模块的架构设计。同时也意识到自己在沟通表达方面还有提升空间。过去的某些选择虽然当时看是困难的，但现在回头看都是必要的成长过程。""",
        "ai_abstract": "过去一年的成长回顾：技术能力提升、独立架构设计能力建立，沟通表达仍需加强"
    },
    {
        "mode": "present",
        "content": """当前状态：正在推进一个重要的项目迭代，同时在学习新的技术框架。日常在编码、学习、运动之间寻找平衡。有时会感到时间不够用的压力，但整体上对现在的状态还算满意。正在尝试更系统地管理自己的时间和精力。""",
        "ai_abstract": "当前状态：项目推进+学习新技术，寻求工作与生活的平衡"
    },
    {
        "mode": "future",
        "content": """对未来一年的期待：希望能够在专业领域有更深入的发展，完成至少一个有影响力的项目。同时也希望能保持健康的身体状态，养成长期的良好习惯。不给自己设太宏大的目标，专注于持续进步和积累。""",
        "ai_abstract": "未来展望：专业深入发展、完成有影响力项目、保持健康习惯"
    },
]

# 目标日志模板
GOAL_JOURNAL_TEMPLATES = [
    {"goal_id": "goal-daily", "date": None, "time": None, "content": "今天按计划推进了项目开发，完成了计划中的主要任务", "mood": "calm", "duration": 240},
    {"goal_id": "goal-daily", "date": None, "time": None, "content": "学习了新技术框架的基础概念，做了一些实践练习", "mood": "joy", "duration": 90},
    {"goal_id": "goal-daily", "date": None, "time": None, "content": "今天效率一般，只完成了部分计划任务，需要调整节奏", "mood": "pensive", "duration": 120},
    {"goal_id": "goal-example", "date": None, "time": None, "content": "完善了项目的文档结构，补充了关键模块的使用说明", "mood": "calm", "duration": 60},
    {"goal_id": "goal-example", "date": None, "time": None, "content": "进行了代码审查，发现并修复了 2 个潜在问题", "mood": "joy", "duration": 45},
]

# 待办事项模板
TODO_TEMPLATES = [
    # scheduled (在过去几天)
    {"content": "完成 {feature} 功能开发", "state": "completed", "link_to_goal_id": "goal-daily"},
    {"content": "代码审查：检查 {component} 模块", "state": "completed", "link_to_goal_id": "goal-daily"},
    {"content": "更新项目 README 文档", "state": "completed", "link_to_goal_id": "goal-example"},
    {"content": "修复 {component} 模块的高优先级 bug", "state": "completed", "link_to_goal_id": "goal-daily"},
    {"content": "学习 {topic} 核心概念", "state": "completed", "link_to_goal_id": "goal-daily"},
    {"content": "整理本周工作日志", "state": "completed", "link_to_goal_id": "goal-daily"},
    {"content": "编写 {feature} 单元测试", "state": "scheduled", "link_to_goal_id": "goal-daily"},
    {"content": "优化数据库查询性能", "state": "scheduled", "link_to_goal_id": "goal-daily"},
    {"content": "技术方案评审准备", "state": "scheduled", "link_to_goal_id": "goal-example"},
    {"content": "完成前端组件的响应式适配", "state": "scheduled", "link_to_goal_id": "goal-daily"},
    # pool
    {"content": "调研 WebSocket 长连接方案", "state": "pool", "link_to_goal_id": "goal-example"},
    {"content": "学习 Docker 容器化部署", "state": "pool", "link_to_goal_id": "goal-daily"},
    {"content": "搭建自动化 CI/CD 流水线", "state": "pool", "link_to_goal_id": "goal-example"},
    {"content": "编写 API 接口文档", "state": "pool", "link_to_goal_id": "goal-daily"},
    {"content": "设计数据缓存策略", "state": "pool", "link_to_goal_id": "goal-example"},
    # shelved
    {"content": "尝试搭建个人博客", "state": "shelved", "link_to_goal_id": None},
    {"content": "学习 Rust 编程语言", "state": "shelved", "link_to_goal_id": "goal-daily"},
]


# ==================== 工具函数 ====================

def iso_now() -> str:
    """当前 UTC 时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).isoformat()


def random_time_between(start_hour: int, end_hour: int, date: datetime) -> str:
    """在指定日期的小时范围内生成随机时间"""
    hour = random.randint(start_hour, end_hour - 1)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    t = date.replace(hour=hour, minute=minute, second=second, microsecond=0)
    return t.strftime("%Y-%m-%d %H:%M:%S")


def random_duration(min_minutes: int = 5, max_minutes: int = 120) -> int:
    """随机持续时间（秒）"""
    return random.randint(min_minutes, max_minutes) * 60


def uid(prefix: str = "") -> str:
    """生成简短唯一 ID"""
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def format_iso(dt: datetime) -> str:
    """格式化为 ISO 字符串"""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# ==================== 数据库操作 ====================

class DemoDataGenerator:
    """演示数据生成器"""

    def __init__(self, data_path: Path, days: int = 7, force: bool = False):
        self.data_path = data_path.resolve()
        self.days = days
        self.force = force
        self.db_path = self.data_path / "dataset" / "lifewatch_ai.db"
        self.today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.start_date = self.today - timedelta(days=days - 1)

    # ==================== 入口 ====================

    def run(self):
        """执行所有数据生成"""
        if not self.db_path.exists():
            print(f"[ERROR] 数据库不存在: {self.db_path}")
            print("[提示] 请先启动一次 web-demo 以初始化数据库（建表 + 默认数据）")
            sys.exit(1)

        print(f"[INFO] 数据目录: {self.data_path}")
        print(f"[INFO] 数据库:   {self.db_path}")
        print(f"[INFO] 时间范围: {self.start_date.date()} ~ {self.today.date()} ({self.days} 天)")
        print(f"[INFO] 强制覆盖: {self.force}")

        if not self.force and self._has_demo_data():
            print("[WARN] 检测到已有演示数据，跳过生成（使用 --force 强制覆盖）")
            return

        if self.force:
            print("\n[0/3] 清理已有演示数据...")
            self._cleanup_demo_data()

        print("\n[1/3] 生成数据库演示数据...")
        self._generate_db_data()

        print("\n[2/3] 生成文件演示数据...")
        self._generate_file_data()

        print("\n[3/3] 生成 recent_state.md...")
        self._generate_recent_state()

        print("\n[DONE] 演示数据生成完成！")

    def _has_demo_data(self) -> bool:
        """检查是否已有演示数据（通过检查 habit 表）"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM habits WHERE id LIKE 'hab-demo-%'")
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception:
            return False

    def _cleanup_demo_data(self):
        """清理已有演示数据（force 模式下先删除再生成）"""
        conn = sqlite3.connect(str(self.db_path))

        date_start = self.start_date.strftime("%Y-%m-%d")
        date_end = self.today.strftime("%Y-%m-%d")

        # 日期范围表：删除时间范围内的数据
        date_range_tables = [
            ("user_app_behavior_log", "start_time"),
            ("behavior_analysis", "start_time"),
            ("raw_behavior_analysis", "start_time"),
            ("diary", "date"),
            ("daily_focus", "date"),
            ("goal_stats", "date"),
            ("goal_journal", "date"),
            ("timeline_custom_block", "start_time"),
            ("habit_checkins", "date"),
            ("mood_entries", "created_at"),
        ]
        for table, col in date_range_tables:
            conn.execute(
                f"DELETE FROM {table} WHERE {col} >= ? AND {col} <= ? || ' 23:59:59'",
                (date_start, date_end)
            )

        # todo_list：删除 demo ID 前缀的
        conn.execute("DELETE FROM todo_list WHERE id LIKE 't-demo-%'")

        # ID 前缀表
        prefix_tables = {
            "habits": "hab-demo-%",
            "habit_challenges": "chall-demo-%",
            "user_values": "val-demo-%",
            "commitments": "cmt-demo-%",
        }
        for table, prefix in prefix_tables.items():
            conn.execute(f"DELETE FROM {table} WHERE id LIKE '{prefix}'")

        # tokens_usage_log 主键是 session_id，非 id
        conn.execute("DELETE FROM tokens_usage_log WHERE session_id LIKE 'session-demo-%'")

        # 整表清理（无 demo 标记，全删）
        conn.execute("DELETE FROM habit_chains")
        conn.execute("DELETE FROM habit_chain_nodes")
        conn.execute("DELETE FROM time_paradoxes")
        conn.execute("DELETE FROM weekly_focus")
        conn.execute("DELETE FROM category_map_cache")
        conn.execute("DELETE FROM multi_purpose_map_cache")
        conn.execute("DELETE FROM single_purpose_map_cache")

        conn.commit()
        conn.close()

        deleted_count = sum(1 for _ in [
            "user_app_behavior_log", "behavior_analysis", "raw_behavior_analysis",
            "diary", "daily_focus", "goal_stats", "goal_journal",
            "timeline_custom_block", "habit_checkins", "mood_entries",
            "todo_list", "habits", "habit_challenges", "user_values",
            "commitments", "tokens_usage_log", "habit_chains",
            "habit_chain_nodes", "time_paradoxes", "weekly_focus",
            "category_map_cache", "multi_purpose_map_cache", "single_purpose_map_cache",
        ])
        print(f"  已清理 {deleted_count} 张表的已有数据")

    # ==================== 数据库数据生成 ====================

    def _generate_db_data(self):
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

        conn.commit()
        conn.close()
        print("  数据库数据生成完成")

    # --- 辅助方法 ---

    def _date_range(self):
        """生成日期列表"""
        for i in range(self.days):
            yield self.start_date + timedelta(days=i)

    def _exists(self, conn: sqlite3.Connection, table: str, condition: str = "1=1") -> bool:
        """检查表是否已有数据"""
        if not self.force:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {condition}")
            return cursor.fetchone()[0] > 0
        return False

    # --- 各表生成 ---

    def _gen_app_cache(self, conn):
        """生成应用分类缓存数据"""
        if self._exists(conn, "category_map_cache"):
            print("  [skip] category_map_cache 已有数据")
            return

        seen = set()
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
                (app, title, is_mp,
                 f"{title} 应用程序", f"{title} 的标题分析",
                 cat_id, sub_id, iso_now(), iso_now())
            )

        # multi/single purpose cache
        for app, title, cat_id, sub_id, is_mp in DEMO_APPS:
            if is_mp:
                if not self._exists(conn, "multi_purpose_map_cache", f"app='{app}' AND title='{title}'"):
                    conn.execute(
                        """INSERT INTO multi_purpose_map_cache
                           (id, app, title, category_id, sub_category_id, state, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                        (f"m-{uuid.uuid4().hex[:8]}", app, title, cat_id, sub_id, iso_now(), iso_now())
                    )
            else:
                if not self._exists(conn, "single_purpose_map_cache", f"app='{app}'"):
                    conn.execute(
                        """INSERT INTO single_purpose_map_cache
                           (id, app, title, category_id, sub_category_id, state, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                        (f"s-{uuid.uuid4().hex[:8]}", app, title, cat_id, sub_id, iso_now(), iso_now())
                    )
        print(f"  [ok] 缓存数据: {len(seen)} 条")

    def _gen_behavior_logs(self, conn):
        """生成过去 N 天的应用使用日志"""
        if self._exists(conn, "user_app_behavior_log", "id IS NOT NULL"):
            print("  [skip] user_app_behavior_log 已有数据")
            return

        total = 0
        for day in self._date_range():
            # 每天 8:00 ~ 23:30 生成 ~25-35 条记录
            num_entries = random.randint(25, 35)
            # 工作时间段偏好
            work_blocks = [
                (8, 12, 0.7),   # 上午：70% 工作类应用
                (13, 18, 0.65),  # 下午：65% 工作类
                (19, 23, 0.3),   # 晚上：30% 工作类
            ]

            entries = []
            for _ in range(num_entries):
                hour_block = random.choice(work_blocks)
                start_time_str = random_time_between(hour_block[0], hour_block[1], day)
                start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")

                # 按概率选工作/娱乐应用
                if random.random() < hour_block[2]:
                    pool = [a for a in DEMO_APPS if a[2] in ("cat-work", "cat-study")]
                else:
                    pool = DEMO_APPS

                app, title, cat_id, sub_id, _ = random.choice(pool)
                duration = random_duration(3, 90)
                end_dt = start_dt + timedelta(seconds=duration)
                end_time_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

                entries.append((start_time_str, end_time_str, duration, app, title, cat_id, sub_id))

            # 按 start_time 排序
            entries.sort(key=lambda x: x[0])

            for start_time_str, end_time_str, duration, app, title, cat_id, sub_id in entries:
                conn.execute(
                    """INSERT INTO user_app_behavior_log
                       (start_time, end_time, duration, app, title, is_multipurpose_app,
                        category_id, sub_category_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
                    (start_time_str, end_time_str, duration, app, title,
                     cat_id, sub_id, iso_now(), iso_now())
                )
                total += 1

        print(f"  [ok] user_app_behavior_log: {total} 条")

    def _gen_behavior_analysis(self, conn):
        """生成行为分析数据"""
        if self._exists(conn, "behavior_analysis"):
            print("  [skip] behavior_analysis 已有数据")
            return

        total = 0
        for day in self._date_range():
            num_entries = random.randint(7, 12)
            for i in range(num_entries):
                start_time_str = random_time_between(8, 22, day)
                start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                end_dt = start_dt + timedelta(seconds=random_duration(10, 120))
                end_time_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

                template = random.choice(BEHAVIOR_TEMPLATES)
                behavior_detail = template.format(
                    feature=random.choice(FEATURE_NAMES),
                    component=random.choice(COMPONENT_NAMES),
                    topic=random.choice(TOPIC_NAMES),
                    module=random.choice(COMPONENT_NAMES),
                )

                conn.execute(
                    """INSERT INTO behavior_analysis
                       (start_time, end_time, behavior, behavior_summary, title,
                        screen_count, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (start_time_str, end_time_str, behavior_detail,
                     behavior_detail[:50], f"行为片段 {i+1}",
                     random.randint(3, 15), iso_now(), iso_now())
                )
                total += 1
        print(f"  [ok] behavior_analysis: {total} 条")

    def _gen_raw_behavior_analysis(self, conn):
        """生成原始行为分析"""
        if self._exists(conn, "raw_behavior_analysis"):
            print("  [skip] raw_behavior_analysis 已有数据")
            return

        total = 0
        for day in self._date_range():
            num_entries = random.randint(5, 8)
            for _ in range(num_entries):
                start_time_str = random_time_between(8, 22, day)
                start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                end_dt = start_dt + timedelta(seconds=random_duration(10, 120))
                end_time_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

                behaviors = ["开发编码", "查阅文档", "沟通协作", "休闲娱乐", "学习阅读", "其他活动"]
                behavior = random.choice(behaviors)

                conn.execute(
                    """INSERT INTO raw_behavior_analysis
                       (start_time, end_time, behavior, screen_count, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (start_time_str, end_time_str, behavior,
                     random.randint(1, 10), iso_now())
                )
                total += 1
        print(f"  [ok] raw_behavior_analysis: {total} 条")

    def _gen_mood_entries(self, conn):
        """生成心情记录"""
        if self._exists(conn, "mood_entries"):
            print("  [skip] mood_entries 已有数据")
            return

        total = 0
        for day in self._date_range():
            # 每天 1-2 条
            for _ in range(random.randint(1, 2)):
                template = random.choice(MOOD_TEMPLATES)
                factors_json = '["工作","健康","学习"]'
                conn.execute(
                    """INSERT INTO mood_entries
                       (id, mood_type_id, score, content, factors, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (f"mood-{uuid.uuid4().hex[:8]}",
                     template["mood_type_id"], template["score"],
                     template["content"], factors_json,
                     day.strftime("%Y-%m-%dT%H:%M:%S"), iso_now())
                )
                total += 1
        print(f"  [ok] mood_entries: {total} 条")

    def _gen_diary(self, conn):
        """生成日记元数据"""
        if self._exists(conn, "diary"):
            print("  [skip] diary 已有数据")
            return

        total = 0
        for i, day in enumerate(self._date_range()):
            template = DIARY_TEMPLATES[i % len(DIARY_TEMPLATES)]
            conn.execute(
                """INSERT INTO diary
                   (date, mood, importance, custom_tags, word_count,
                    ai_summary, diary_source_hash, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (day.strftime("%Y-%m-%d"), template["mood"], template["importance"],
                 '["日常"]', random.randint(200, 800),
                 f"{template['morning'][:50]}... {template['evening'][:50]}...",
                 uid("hash-"), iso_now(), iso_now())
            )
            total += 1
        print(f"  [ok] diary: {total} 条")

    def _gen_todos(self, conn):
        """生成待办事项"""
        if self._exists(conn, "todo_list", "id LIKE 't-demo-%'"):
            print("  [skip] todo_list 已有数据")
            return

        total = 0
        # scheduled (过去几天 + 今天)
        for day in self._date_range():
            num_todos = random.randint(2, 4)
            templates = random.sample(TODO_TEMPLATES[:10], min(num_todos, 10))
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
                    (todo_id, idx, content, random.choice(["#5B8FF9", "#5AD8A6", "#F6BD16"]),
                     state, tmpl["link_to_goal_id"],
                     day.strftime("%Y-%m-%d"), actual_finished, iso_now(), iso_now())
                )
                total += 1

        # pool tasks
        for idx, tmpl in enumerate(TODO_TEMPLATES[10:15]):
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
                (f"t-demo-pool-{idx}", idx, content, "#E8684A",
                 "pool", tmpl["link_to_goal_id"], iso_now(), iso_now())
            )
            total += 1

        # shelved
        for idx, tmpl in enumerate(TODO_TEMPLATES[15:]):
            content = tmpl["content"]
            conn.execute(
                """INSERT INTO todo_list
                   (id, order_index, content, color, state, created_at, updated_at)
                   VALUES (?, 0, ?, ?, 'shelved', ?, ?)""",
                (f"t-demo-shelved-{idx}", content, "#cbd5e1", iso_now(), iso_now())
            )
            total += 1

        print(f"  [ok] todo_list: {total} 条")

    def _gen_goal_journals(self, conn):
        """生成目标日志"""
        if self._exists(conn, "goal_journal", "id LIKE 'journal-demo-%'"):
            print("  [skip] goal_journal 已有数据")
            return

        total = 0
        for day in self._date_range():
            if random.random() < 0.4:  # ~40% 的天有 goal_journal
                continue
            tmpl = random.choice(GOAL_JOURNAL_TEMPLATES)
            conn.execute(
                """INSERT INTO goal_journal
                   (id, goal_id, date, time, content, mood, duration, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"journal-demo-{uuid.uuid4().hex[:8]}",
                 tmpl["goal_id"], day.strftime("%Y-%m-%d"),
                 f"{random.randint(8, 22):02d}:{random.randint(0, 59):02d}",
                 tmpl["content"], tmpl["mood"], tmpl["duration"],
                 iso_now(), iso_now())
            )
            total += 1
        print(f"  [ok] goal_journal: {total} 条")

    def _gen_daily_focus(self, conn):
        """生成日焦点"""
        if self._exists(conn, "daily_focus", "id IS NOT NULL"):
            print("  [skip] daily_focus 已有数据")
            return

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
                (day.strftime("%Y-%m-%d"), content, iso_now(), iso_now())
            )
        print(f"  [ok] daily_focus: {self.days} 条")

    def _gen_weekly_focus(self, conn):
        """生成周焦点"""
        if self._exists(conn, "weekly_focus"):
            print("  [skip] weekly_focus 已有数据")
            return

        today = self.today
        for week_offset in range(4):
            week_start = today - timedelta(weeks=week_offset, days=today.weekday())
            conn.execute(
                """INSERT INTO weekly_focus
                   (year, month, week_num, content, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (week_start.year, week_start.month,
                 (week_start.day - 1) // 7 + 1,
                 f"第 {4-week_offset} 周重点：推进核心功能开发与代码质量提升",
                 iso_now(), iso_now())
            )
        print("  [ok] weekly_focus: 4 条")

    def _gen_habits(self, conn):
        """生成习惯定义"""
        if self._exists(conn, "habits", "id LIKE 'hab-demo-%'"):
            print("  [skip] habits 已有数据")
            return

        for h in DEMO_HABITS:
            conn.execute(
                """INSERT INTO habits
                   (id, name, description, frequency_type, frequency_config,
                    current_level, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, '{}', ?, 'active', ?, ?)""",
                (h["id"], h["name"], h["description"], h["frequency_type"],
                 h["current_level"], iso_now(), iso_now())
            )
        print(f"  [ok] habits: {len(DEMO_HABITS)} 条")

    def _gen_habit_challenges(self, conn):
        """生成习惯挑战"""
        if self._exists(conn, "habit_challenges", "id LIKE 'chall-demo-%'"):
            print("  [skip] habit_challenges 已有数据")
            return

        for i, h in enumerate(DEMO_HABITS):
            challenge_start = self.start_date
            challenge_end = self.today + timedelta(days=7)
            conn.execute(
                """INSERT INTO habit_challenges
                   (id, habit_id, challenge_weeks, required_completions,
                    from_level, to_level, start_date, end_date,
                    completed_count, streak_base, status, created_at, updated_at)
                   VALUES (?, ?, 4, ?, ?, ?, ?, ?, ?, 0, 'in_progress', ?, ?)""",
                (f"chall-demo-{i:03d}", h["id"],
                 random.randint(20, 25),
                 h["current_level"], h["current_level"] + 1,
                 challenge_start.strftime("%Y-%m-%d"), challenge_end.strftime("%Y-%m-%d"),
                 random.randint(5, 18), iso_now(), iso_now())
            )
        print(f"  [ok] habit_challenges: {len(DEMO_HABITS)} 条")

    def _gen_habit_checkins(self, conn):
        """生成习惯打卡"""
        if self._exists(conn, "habit_checkins", "id LIKE 'checkin-demo-%'"):
            print("  [skip] habit_checkins 已有数据")
            return

        total = 0
        for day in self._date_range():
            if day >= self.today:
                continue  # 今天不生成，留给 daily refresh
            for i, h in enumerate(DEMO_HABITS):
                # ~70% 完成率
                if random.random() < 0.7:
                    conn.execute(
                        """INSERT INTO habit_checkins
                           (id, habit_id, challenge_id, date, completed_at, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (f"checkin-demo-{uuid.uuid4().hex[:8]}",
                         h["id"], f"chall-demo-{i:03d}",
                         day.strftime("%Y-%m-%d"),
                         day.strftime("%Y-%m-%dT%H:%M:%S"), iso_now())
                    )
                    total += 1
        print(f"  [ok] habit_checkins: {total} 条")

    def _gen_habit_chain(self, conn):
        """生成习惯链"""
        if self._exists(conn, "habit_chains", "id IS NOT NULL"):
            print("  [skip] habit_chains 已有数据")
            return

        # 创建晨间习惯链
        conn.execute(
            """INSERT INTO habit_chains (name, description, show_in_timeline, created_at, updated_at)
               VALUES ('晨间例行', '每天早上的习惯链条', 1, ?, ?)""",
            (iso_now(), iso_now())
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
                (chain_id, idx + 1, name, habit_id, trigger_time, iso_now(), iso_now())
            )
        print("  [ok] habit_chain: 1 条链 + 4 个节点")

    def _gen_user_values(self, conn):
        """生成价值观"""
        if self._exists(conn, "user_values", "id LIKE 'val-demo-%'"):
            print("  [skip] user_values 已有数据")
            return

        for idx, v in enumerate(DEMO_VALUES):
            conn.execute(
                """INSERT INTO user_values
                   (id, keywords, content_positive, content_negative, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (v["id"], v["keywords"], v["content_positive"], v["content_negative"],
                 len(DEMO_VALUES) - idx, iso_now(), iso_now())
            )
        print(f"  [ok] user_values: {len(DEMO_VALUES)} 条")

    def _gen_commitments(self, conn):
        """生成承诺"""
        if self._exists(conn, "commitments", "id LIKE 'cmt-demo-%'"):
            print("  [skip] commitments 已有数据")
            return

        for c in DEMO_COMMITMENTS:
            conn.execute(
                """INSERT INTO commitments
                   (id, content, value_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (c["id"], c["content"], c["value_id"], c["status"], iso_now(), iso_now())
            )
        print(f"  [ok] commitments: {len(DEMO_COMMITMENTS)} 条")

    def _gen_time_paradoxes(self, conn):
        """生成时间悖论测试"""
        if self._exists(conn, "time_paradoxes"):
            print("  [skip] time_paradoxes 已有数据")
            return

        for idx, entry in enumerate(TIME_PARADOX_ENTRIES, start=1):
            conn.execute(
                """INSERT INTO time_paradoxes
                   (id, user_id, version, mode, content, ai_abstract, created_at, updated_at)
                   VALUES (?, 1, 1, ?, ?, ?, ?, ?)""",
                (idx, entry["mode"], entry["content"], entry["ai_abstract"],
                 iso_now(), iso_now())
            )
        print(f"  [ok] time_paradoxes: {len(TIME_PARADOX_ENTRIES)} 条")

    def _gen_timeline_custom_blocks(self, conn):
        """生成手动时间块"""
        if self._exists(conn, "timeline_custom_block", "id IS NOT NULL"):
            print("  [skip] timeline_custom_block 已有数据")
            return

        block_templates = [
            ("阅读时间", "cat-study", "subcat-study-other", "#5AD8A6"),
            ("运动锻炼", "cat-other", "subcat-other-other", "#F6BD16"),
            ("午休", "cat-other", "subcat-other-other", "#cbd5e1"),
            ("散步", "cat-other", "subcat-other-other", "#5AD8A6"),
            ("沟通讨论", "cat-work", "subcat-work-other", "#5B8FF9"),
            ("写日记", "cat-other", "subcat-other-other", "#E8684A"),
        ]

        total = 0
        for day in self._date_range():
            for _ in range(random.randint(2, 4)):
                content, cat_id, sub_id, color = random.choice(block_templates)
                hour = random.randint(8, 22)
                start_time_str = day.replace(hour=hour, minute=random.randint(0, 59)).strftime("%Y-%m-%dT%H:%M:%S")
                end_time_str = (datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S") +
                                timedelta(minutes=random.randint(20, 90))).strftime("%Y-%m-%dT%H:%M:%S")

                conn.execute(
                    """INSERT OR IGNORE INTO timeline_custom_block
                       (start_time, end_time, duration, content, color,
                        category_id, sub_category_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (start_time_str, end_time_str, random.randint(20, 90),
                     content, color, cat_id, sub_id, iso_now(), iso_now())
                )
                total += 1
        print(f"  [ok] timeline_custom_block: {total} 条")

    def _gen_goal_stats(self, conn):
        """生成目标统计数据"""
        if self._exists(conn, "goal_stats"):
            print("  [skip] goal_stats 已有数据")
            return

        for day in self._date_range():
            for goal_id in ["goal-daily", "goal-example"]:
                conn.execute(
                    """INSERT INTO goal_stats
                       (goal_id, date, time_spent, completed_todo_count, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (goal_id, day.strftime("%Y-%m-%d"),
                     random.randint(30, 300), random.randint(0, 3),
                     iso_now())
                )
        print(f"  [ok] goal_stats: {self.days * 2} 条")

    def _gen_tokens_usage(self, conn):
        """生成 token 使用统计（少量）"""
        if self._exists(conn, "tokens_usage_log"):
            print("  [skip] tokens_usage_log 已有数据")
            return

        for i, day in enumerate(self._date_range()):
            if i % 2 != 0:
                continue
            conn.execute(
                """INSERT INTO tokens_usage_log
                   (session_id, input_tokens, output_tokens, total_tokens,
                    search_count, result_items_count, mode, created_at)
                   VALUES (?, ?, ?, ?, 0, 0, 'chatbot', ?)""",
                (f"session-demo-{uuid.uuid4().hex[:8]}",
                 random.randint(500, 5000), random.randint(200, 3000),
                 random.randint(700, 8000), day.strftime("%Y-%m-%dT%H:%M:%S"))
            )
        print(f"  [ok] tokens_usage_log: {self.days // 2} 条")

    # ==================== 文件数据生成 ====================

    def _generate_file_data(self):
        """生成文件类演示数据"""
        self._generate_diary_files()
        self._generate_behavior_md()
        print("  文件数据生成完成")

    def _generate_diary_files(self):
        """生成日记 MD 文件"""
        diary_dir = self.data_path / "diary"
        total = 0
        for i, day in enumerate(self._date_range()):
            date_str = day.strftime("%Y-%m-%d")
            year_str = day.strftime("%Y")
            month_str = day.strftime("%m")
            file_path = diary_dir / year_str / month_str / f"{date_str}.md"

            if file_path.exists() and not self.force:
                continue

            file_path.parent.mkdir(parents=True, exist_ok=True)

            template = DIARY_TEMPLATES[i % len(DIARY_TEMPLATES)]
            feature = random.choice(FEATURE_NAMES)
            component = random.choice(COMPONENT_NAMES)

            morning = template["morning"].format(feature=feature, component=component)
            evening = template["evening"].format(feature=feature, component=component)

            content = f"## Morning Page\n\n{morning}\n\n## Evening Page\n\n{evening}\n"
            file_path.write_text(content, encoding="utf-8")
            total += 1

        print(f"  [ok] diary 文件: {total} 个")

    def _generate_behavior_md(self):
        """生成 behavior.md"""
        daily_data_dir = self.data_path / "user" / "daily_data"
        daily_data_dir.mkdir(parents=True, exist_ok=True)
        file_path = daily_data_dir / "behavior.md"

        if file_path.exists() and not self.force:
            print("  [skip] behavior.md 已存在")
            return

        lines = []
        for i, day in enumerate(self._date_range()):
            if day >= self.today:
                continue  # 今天留给 daily refresh
            date_str = day.strftime("%Y-%m-%d")
            template = DIARY_TEMPLATES[i % len(DIARY_TEMPLATES)]

            # 行为总结
            work_hours = random.uniform(4, 8)
            entertainment_hours = random.uniform(1, 4)
            lines.append(f"## {date_str}")
            lines.append("### 行为总结")
            lines.append(f"1. 今日概览：当天主要进行软件开发工作，辅以学习和休闲活动。电脑使用集中在上午和下午时段。")
            lines.append(f"2. 电脑使用总览：工作/学习约 {work_hours:.1f} 小时，娱乐约 {entertainment_hours:.1f} 小时。")
            lines.append("3. 高频使用时段：")
            lines.append(f"   - 08:30~12:00：以工作/学习为主")
            lines.append(f"   - 13:30~18:00：以工作/学习为主，伴有短暂休息")
            lines.append(f"   - 20:00~22:30：娱乐与学习交替")
            lines.append("")

            # 日记总结
            lines.append("### 日记总结")
            mood_label = {"joy": "有点开心", "calm": "平静", "pensive": "沉思",
                          "melancholy": "不太好", "anger": "不太好"}.get(template["mood"], "平静")
            lines.append(f"用户输入标签： 心情：{mood_label} 重要程度: {template['importance']}")
            lines.append(f"1. 客观事实与反应：")
            lines.append(f"   [{date_str}]")
            lines.append(f"   1. [上午] {template['morning'][:80]}...")
            lines.append(f"   2. [下午] 继续推进开发工作，处理代码审查反馈。")
            lines.append(f"   3. [晚上] {template['evening'][:80]}...")
            lines.append(f"2. 日记总结：记录了当天的开发工作进展和个人状态反思。")
            lines.append(f"3. 整体状态：心情{mood_label}，当天完成了计划中的主要任务。")
            lines.append("")

        file_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  [ok] behavior.md: {self.days - 1} 天数据")

    def _generate_recent_state(self):
        """生成 recent_state.md（仅一次）"""
        output_dir = self.data_path / "user" / "daily_data"
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / "recent_state.md"

        if file_path.exists() and not self.force:
            print("  [skip] recent_state.md 已存在")
            return

        end_date = self.today - timedelta(days=1)
        start_date = self.start_date
        content = f"""## 近期事件
[{start_date.strftime('%Y-%m-%d')}~{end_date.strftime('%Y-%m-%d')}]：近期主要进行软件项目开发工作，包括功能迭代、代码优化和文档完善。日常保持阅读和运动的习惯，整体状态稳定。

[当前仅描述最近发生的用户有较为强烈的情绪波动事件、关键事件，忽略部分不重要事件，但不代表也不能就此断章取义推测用户情绪容易波动]

## 心理状态和生理状态
1. 心理状态：
[缺少数据说明]：当前由于近7天体现心理状态的数据为演示数据，以下内容仅代表部分时间段的心理状态。近期心情以平静为主，偶尔因项目进度压力感到焦虑，但通过运动和自我调节能够恢复。对技术成长和个人发展持积极态度。

2. 生理状态：
[缺少数据说明]：当前由于体现生理状态的数据为演示数据，以下内容仅代表部分时间段的生理状态。近期睡眠基本规律，偶有晚睡。通过每日运动和散步保持基本活动量。饮食以自己做饭为主。

## 时间花费与目标
电脑使用总览：{start_date.strftime('%Y-%m-%d')}至{end_date.strftime('%Y-%m-%d')}期间，电脑使用以工作/学习为主（约70%），娱乐为辅（约25%），其他占5%。
电脑使用趋势：白天以密集开发工作为主，晚上适当放松。周末使用强度略有下降。
目标总结：持续进行技术开发工作，保持学习与工作平衡。

## 旧版本总结
（暂无历史数据 — 演示环境）
"""
        file_path.write_text(content, encoding="utf-8")
        print("  [ok] recent_state.md")


# ==================== 主入口 ====================

def main():
    parser = argparse.ArgumentParser(description="Web-Demo 演示数据生成脚本")
    parser.add_argument("--data-path", default="localData",
                        help="数据目录路径（默认: localData）")
    parser.add_argument("--days", type=int, default=7,
                        help="生成多少天的数据（默认: 7）")
    parser.add_argument("--force", action="store_true",
                        help="强制重新生成（覆盖已有数据）")
    args = parser.parse_args()

    data_path = Path(args.data_path).resolve()
    if not data_path.exists():
        print(f"[ERROR] 数据目录不存在: {data_path}")
        sys.exit(1)

    # 确保随机可复现（每天生成的数据不同但合理）
    random.seed(datetime.now().strftime("%Y%m%d"))

    generator = DemoDataGenerator(data_path, args.days, args.force)
    generator.run()


if __name__ == "__main__":
    main()
