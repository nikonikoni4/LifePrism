"""
数据库配置模块
定义数据库表结构的完整元数据
"""

from lifeprism.config.exceptions import InvalidConfigError
from lifeprism.utils import get_logger

logger = get_logger(__name__)

"""
2026-1-2
重构cache表,将原来的表分为两个表
1. multi_purpose_app_cache
2. single_purpose_map_cache
"""

MULTI_PURPOSE_MAP_CACHE_CONFIG = {
    "table_name": "multi_purpose_map_cache",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "唯一标识符（格式：m-{uuid[:8]}）",
        },
        "app": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "应用程序的文件名（例如：chrome.exe）",
        },
        "title": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "应用程序的标题（例如：Google Chrome）",
        },
        "app_description": {"type": "TEXT", "constraints": [], "comment": "应用程序的描述"},
        "title_analysis": {"type": "TEXT", "constraints": [], "comment": "应用程序title的描述"},
        "category_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "主分类ID（关联 category.id）",
        },
        "sub_category_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "子分类ID（关联 sub_category.id）",
        },
        "state": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 1"],
            "comment": "记录状态（1: 有效, 0: 无效/分类被禁用）",
        },
        "link_to_goal_id": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "关联的goal_id",
        },
    },
    "table_constraints": ["UNIQUE (app, title, state)"],  # 唯一约束：保证数据不重复
    "indexes": [],
    "timestamps": True,  # 自动添加 created_at, updated_at
    "update_at": True,
}

SINGLE_PURPOSE_MAP_CACHE_CONFIG = {
    "table_name": "single_purpose_map_cache",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "唯一标识符（格式：s-{uuid[:8]}）",
        },
        "app": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "应用程序的文件名（例如：chrome.exe）",
        },
        "title": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "应用程序的标题（例如：Google Chrome）",
        },
        "app_description": {"type": "TEXT", "constraints": [], "comment": "应用程序的描述"},
        "category_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "主分类ID（关联 category.id）",
        },
        "sub_category_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "子分类ID（关联 sub_category.id）",
        },
        "state": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 1"],
            "comment": "记录状态（1: 有效, 0: 无效/分类被禁用）",
        },
        "link_to_goal_id": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "关联的goal_id",
        },
    },
    "table_constraints": ["UNIQUE (app, state)"],  # 唯一约束：保证数据不重复
    "indexes": [],
    "timestamps": True,  # 自动添加 created_at, updated_at
    "update_at": True,
}
category_map_cache_CONFIG = {
    "table_name": "category_map_cache",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY", "AUTOINCREMENT"],
            "comment": "自增主键，用于删除操作",
        },
        "app": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "应用程序的文件名（例如：chrome.exe）",
        },
        "title": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "应用程序的标题（例如：Google Chrome）",
        },
        "is_multipurpose_app": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "是否为被选择需要使用title信息来判断用途的应用（True/False）",
        },
        "app_description": {"type": "TEXT", "constraints": [], "comment": "应用程序的描述"},
        "title_analysis": {"type": "TEXT", "constraints": [], "comment": "应用程序title的描述"},
        "category_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "主分类ID（关联 category.id）",
        },
        "sub_category_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "子分类ID（关联 sub_category.id）",
        },
        "category": {
            "type": "TEXT",
            "constraints": [],
            "comment": "[已弃用] 默认分类名称，保留用于调试",
        },
        "sub_category": {
            "type": "TEXT",
            "constraints": [],
            "comment": "[已弃用] 子分类名称，保留用于调试",
        },
        "state": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 1"],
            "comment": "记录状态（1: 有效, 0: 无效/分类被禁用）",
        },
        "link_to_goal_id": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "关联的goal_id",
        },
    },
    "table_constraints": ["UNIQUE (app, title, state)"],  # 唯一约束：保证数据不重复
    "indexes": [
        {"name": "idx_category_map_cache_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,  # 自动添加 created_at, updated_at
    "update_at": True,
}


# 用户应用行为日志表配置
USER_APP_BEHAVIOR_LOG_CONFIG = {
    "table_name": "user_app_behavior_log",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY", "AUTOINCREMENT"],
            "comment": "自增主键",
        },
        "start_time": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "行为开始时间"},
        "end_time": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "行为结束时间"},
        "duration": {
            "type": "INTEGER",
            "constraints": [],
            "comment": "应用程序运行的持续时间（秒），用于数据验证和兼容性",
        },
        "app": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "应用程序的文件名"},
        "title": {"type": "TEXT", "constraints": [], "comment": "应用程序的标题"},
        "is_multipurpose_app": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "是否为被选择需要使用title信息来判断用途的应用",
        },
        "category_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "主分类ID（外键引用 category.id，新增字段）",
        },
        "sub_category_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "子分类ID（外键引用 sub_category.id，新增字段）",
        },
        "link_to_goal_id": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "关联的goal_id",
        },
    },
    "table_constraints": [
        "UNIQUE(app, start_time)",  # 复合唯一索引
        "CHECK(end_time > start_time)",  # 确保时间逻辑正确
    ],
    "indexes": [
        {"name": "idx_app_start_time", "columns": ["app", "start_time"]},
        {"name": "idx_start_time", "columns": ["start_time"]},
        {"name": "idx_end_time", "columns": ["end_time"]},
        {"name": "idx_time_range", "columns": ["start_time", "end_time"]},  # 时间范围查询优化
        {"name": "idx_user_app_behavior_log_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,  # 自动添加 created_at
    "update_at": True,
}

# 分类定义表配置（主分类）
CATEGORY_CONFIG = {
    "table_name": "category",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "分类唯一标识符（例如：work, entertainment）",
        },
        "name": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "分类名称（例如：工作/学习）",
        },
        "color": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "分类颜色（十六进制格式，例如：#5B8FF9）",
        },
        "state": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 1"],
            "comment": "分类状态（1: 启用, 0: 禁用）",
        },
    },
    "table_constraints": [],
    "indexes": [
        {"name": "idx_category_id", "columns": ["id"]},
        {"name": "idx_category_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,  # 自动添加 created_at, updated_at
    "update_at": True,
}

# 子分类定义表配置
SUB_CATEGORY_CONFIG = {
    "table_name": "sub_category",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "子分类唯一标识符（例如：coding, meeting）",
        },
        "category_id": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "所属主分类ID（外键引用 category.id）",
        },
        "name": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "子分类名称（例如：编程、会议）",
        },
        "state": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 1"],
            "comment": "子分类状态（1: 启用, 0: 禁用）",
        },
    },
    "table_constraints": ["FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE CASCADE"],
    "indexes": [
        {"name": "idx_sub_category_id", "columns": ["id"]},
        {"name": "idx_sub_category_parent", "columns": ["category_id"]},
        {"name": "idx_sub_category_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,  # 自动添加 created_at, updated_at
    "update_at": True,
}

# Token 使用统计表配置
TOKENS_USAGE_LOG_CONFIG = {
    "table_name": "tokens_usage_log",
    "columns": {
        "session_id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "会话ID（chatbot: UUID格式, classification: c-YYYY-MM-DD格式）",
        },
        "input_tokens": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "输入 token 数量",
        },
        "output_tokens": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "输出 token 数量",
        },
        "total_tokens": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "总 token 数量",
        },
        "search_count": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "搜索次数",
        },
        "result_items_count": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "分类结果数量（result_items 长度）",
        },
        "mode": {
            "type": "TEXT",
            "constraints": ["NOT NULL", 'DEFAULT "classification"'],
            "comment": "模式（classification 或 chatbot）",
        },
    },
    "table_constraints": [],
    "indexes": [
        {"name": "idx_tokens_usage_created_at", "columns": ["created_at"]},
        {"name": "idx_tokens_usage_mode", "columns": ["mode"]},
    ],
    "timestamps": True,  # 自动添加 created_at
    "update_at": True,
}


# TodoList 主任务表配置
TODO_LIST_CONFIG = {
    "table_name": "todo_list",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "任务 ID（格式：t-{uuid[:8]}，与 MD 锚点一致）",
        },
        "order_index": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "每天todolist的排序索引，用于拖拽排序",
        },
        "pool_order_index": {
            "type": "INTEGER",
            "constraints": ["DEFAULT NULL"],
            "comment": "任务池的排序索引（仅 pool 状态时使用）",
        },
        "content": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "任务内容"},
        "color": {
            "type": "TEXT",
            "constraints": ['DEFAULT "#FFFFFF"'],
            "comment": "任务颜色（十六进制格式）",
        },
        "state": {
            "type": "TEXT",
            "constraints": ['DEFAULT "pool"'],
            "comment": "任务状态（pool: 任务池中, scheduled: 已安排, completed: 已完成, shelved: 已搁置）",
        },
        "link_to_goal_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "关联的目标 ID（可为空，格式：goal-xxx）",
        },
        "date": {
            "type": "TEXT",
            "constraints": [],
            "comment": "任务日期（YYYY-MM-DD格式，scheduled 状态时有值）",
        },
        "expected_finished_at": {
            "type": "TEXT",
            "constraints": [],
            "comment": "预计完成日期（YYYY-MM-DD格式）",
        },
        "actual_finished_at": {
            "type": "TEXT",
            "constraints": [],
            "comment": "实际完成日期（YYYY-MM-DD格式，完成时填写）",
        },
        "cross_day": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "是否开启跨天追踪（0: 否, 1: 是），长期任务，非一天完成，主要用于review判断，当设置了expected_finished_at后，默认开启",
        },
        "folder_id": {
            "type": "INTEGER",
            "constraints": ["DEFAULT NULL"],
            "comment": "[已废弃] 所属任务池文件夹 ID",
        },
        "parent_id": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "父任务 ID（NULL 表示根任务，支持树形结构）",
        },
        "plan_doc_id": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "关联的计划书 ID",
        },
        "delay_days": {"type": "INTEGER", "constraints": ["DEFAULT NULL"], "comment": "延期天数"},
        "delay_reason": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "延期/未完成原因说明",
        },
        "waid_order": {
            "type": "INTEGER",
            "constraints": ["DEFAULT NULL"],
            "comment": "WAID 浮窗排序（NULL=不在浮窗, 0/1/2...=排序位置）",
        },
    },
    "table_constraints": [],
    "indexes": [
        {"name": "idx_todo_list_date", "columns": ["date"]},
        {"name": "idx_todo_list_cross_day_state", "columns": ["cross_day", "state"]},
        {"name": "idx_todo_list_link_to_goal_id", "columns": ["link_to_goal_id"]},
        {"name": "idx_todo_list_state", "columns": ["state"]},
        {"name": "idx_todo_list_parent_id", "columns": ["parent_id"]},
        {"name": "idx_todo_list_plan_doc_id", "columns": ["plan_doc_id"]},
        {"name": "idx_todo_list_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,  # 自动添加 created_at
    "update_at": True,
}


# Daily Focus 表配置（日焦点）
DAILY_FOCUS_CONFIG = {
    "table_name": "daily_focus",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY", "AUTOINCREMENT"],
            "comment": "自增主键",
        },
        "date": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "UNIQUE"],
            "comment": "日期 YYYY-MM-DD",
        },
        "content": {"type": "TEXT", "constraints": [], "comment": "日焦点内容"},
    },
    "table_constraints": [],
    "indexes": [
        {"name": "idx_daily_focus_date", "columns": ["date"]},
        {"name": "idx_daily_focus_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,
    "update_at": True,
}


# Weekly Focus 表配置（周焦点）
WEEKLY_FOCUS_CONFIG = {
    "table_name": "weekly_focus",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY", "AUTOINCREMENT"],
            "comment": "自增主键",
        },
        "year": {"type": "INTEGER", "constraints": ["NOT NULL"], "comment": "年份"},
        "month": {"type": "INTEGER", "constraints": ["NOT NULL"], "comment": "月份 1-12"},
        "week_num": {"type": "INTEGER", "constraints": ["NOT NULL"], "comment": "周序号 1-4"},
        "content": {"type": "TEXT", "constraints": [], "comment": "周焦点内容"},
    },
    "table_constraints": ["UNIQUE(year, month, week_num)"],
    "indexes": [
        {"name": "idx_weekly_focus_year_month", "columns": ["year", "month"]},
        {"name": "idx_weekly_focus_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,
    "update_at": True,
}


# Goal 目标表配置
GOAL_CONFIG = {
    "table_name": "goal",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "目标唯一标识符（格式：goal-{uuid[:8]}）",
        },
        "name": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "UNIQUE"],
            "comment": "目标名称（唯一，用于分类时的名称-ID映射）",
        },
        "content": {
            "type": "TEXT",
            "constraints": ['DEFAULT ""'],
            "comment": "目标详细内容（Markdown）",
        },
        "color": {
            "type": "TEXT",
            "constraints": ['DEFAULT "#5B8FF9"'],
            "comment": "目标颜色（十六进制）",
        },
        "link_to_category_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "关联的分类ID（用于ActivityWatch时间统计）",
        },
        "link_to_sub_category_id": {"type": "TEXT", "constraints": [], "comment": "关联的子分类ID"},
        "start_date": {"type": "TEXT", "constraints": [], "comment": "开始日期 YYYY-MM-DD"},
        "expected_finished_at": {
            "type": "TEXT",
            "constraints": [],
            "comment": "预计完成时间 YYYY-MM-DD",
        },
        "value": {"type": "TEXT", "constraints": [], "comment": "价值观/意义描述"},
        "commitment": {"type": "TEXT", "constraints": [], "comment": "承诺/行动计划"},
        "time_unit": {
            "type": "TEXT",
            "constraints": ['DEFAULT "HRS"'],
            "comment": "时间单位 HRS/MINS",
        },
        "time_invested": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "投入时间（分钟），手动模式时使用",
        },
        "track_time_automatically": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 1"],
            "comment": "是否自动追踪时间 1:是 0:否",
        },
        "milestones": {
            "type": "TEXT",
            "constraints": ['DEFAULT "[]"'],
            "comment": "里程碑JSON数组",
        },
        "status": {
            "type": "TEXT",
            "constraints": ['DEFAULT "active"'],
            "comment": "状态: active, completed, archived",
        },
        "order_index": {"type": "INTEGER", "constraints": ["DEFAULT 0"], "comment": "排序索引"},
        "time_invested_updated_at": {
            "type": "TEXT",
            "constraints": [],
            "comment": "投入时间最后计算时间（ISO 8601格式），用于判断是否需要重新计算",
        },
    },
    "table_constraints": [],
    "indexes": [
        {"name": "idx_goal_status", "columns": ["status"]},
        {"name": "idx_goal_category", "columns": ["link_to_category_id"]},
        {"name": "idx_goal_order", "columns": ["order_index"]},
        {"name": "idx_goal_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,
    "update_at": True,
}

# Goal Journal 目标日志表配置
GOAL_JOURNAL_CONFIG = {
    "table_name": "goal_journal",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "日志唯一标识符（格式：journal-{uuid[:8]}）",
        },
        "goal_id": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "关联的目标ID"},
        "date": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "日期 YYYY-MM-DD"},
        "time": {"type": "TEXT", "constraints": [], "comment": "时间 HH:MM"},
        "content": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "日志内容"},
        "mood": {
            "type": "TEXT",
            "constraints": ['DEFAULT "neutral"'],
            "comment": "心情（joy/calm/frustrated/neutral）",
        },
        "duration": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "持续时间（分钟）",
        },
        "tags": {"type": "TEXT", "constraints": ['DEFAULT "[]"'], "comment": "标签JSON数组"},
    },
    "table_constraints": ["FOREIGN KEY (goal_id) REFERENCES goal(id) ON DELETE CASCADE"],
    "indexes": [
        {"name": "idx_goal_journal_goal_id", "columns": ["goal_id"]},
        {"name": "idx_goal_journal_date", "columns": ["date"]},
        {"name": "idx_goal_journal_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,
    "update_at": True,
}

# Plan Doc 计划书表配置
PLAN_DOC_CONFIG = {
    "table_name": "plan_doc",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "计划书唯一标识符（格式：plandoc-{uuid[:8]}）",
        },
        "goal_id": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "关联的目标ID"},
        "content": {
            "type": "TEXT",
            "constraints": ['DEFAULT ""'],
            "comment": "计划书内容（Markdown）",
        },
        "status": {
            "type": "TEXT",
            "constraints": ['DEFAULT "active"'],
            "comment": "状态: active, completed, archived",
        },
        "order_index": {"type": "INTEGER", "constraints": ["DEFAULT 0"], "comment": "排序索引"},
    },
    "table_constraints": ["FOREIGN KEY (goal_id) REFERENCES goal(id) ON DELETE CASCADE"],
    "indexes": [
        {"name": "idx_plan_doc_goal_id", "columns": ["goal_id"]},
        {"name": "idx_plan_doc_status", "columns": ["status"]},
    ],
    "timestamps": True,
    "update_at": True,
}


# 聊天会话元数据表
CHAT_SESSION_CONFIG = {
    "table_name": "chat_session",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "会话ID（如 session-xxxxxxxx）",
        },
        "name": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "会话名称"},
        "message_count": {"type": "INTEGER", "constraints": ["DEFAULT 0"], "comment": "消息数量"},
        "created_at": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "创建时间（ISO格式）",
        },
        "updated_at": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "最后更新时间（ISO格式）",
        },
    },
    "table_constraints": [],
    "indexes": [{"name": "idx_chat_session_updated", "columns": ["updated_at"]}],
    "timestamps": False,  # 使用自定义时间戳字段
}


# Timeline 自定义时间块表配置（用户手动添加的活动记录）
TIMELINE_CUSTOM_BLOCK_CONFIG = {
    "table_name": "timeline_custom_block",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY", "AUTOINCREMENT"],
            "comment": "自增主键",
        },
        "start_time": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "开始时间（ISO格式，如 2025-12-27T14:00:00）",
        },
        "end_time": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "结束时间（ISO格式，如 2025-12-27T15:30:00）",
        },
        "duration": {"type": "INTEGER", "constraints": ["NOT NULL"], "comment": "持续时间（分钟）"},
        "content": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "活动内容描述"},
        "todo_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "关联的待办事项ID（格式：t-xxx）",
        },
        "color": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "活动颜色"},
        "category_id": {"type": "TEXT", "constraints": [], "comment": "分类ID"},
        "sub_category_id": {"type": "TEXT", "constraints": [], "comment": "子分类ID"},
    },
    "table_constraints": [
        "CHECK(end_time > start_time)",
        "CHECK(duration > 0)",
        "UNIQUE(start_time)",
    ],
    "indexes": [
        {"name": "idx_timeline_custom_block_start_time", "columns": ["start_time"]},
        {"name": "idx_timeline_custom_block_end_time", "columns": ["end_time"]},
        {"name": "idx_timeline_custom_block_time_range", "columns": ["start_time", "end_time"]},
        {"name": "idx_timeline_custom_block_todo_id", "columns": ["todo_id"]},
        {"name": "idx_timeline_custom_block_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,  # 自动添加 created_at, updated_at
    "update_at": True,
}

GOAL_STATS_CONFIG = {
    "table_name": "goal_stats",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY", "AUTOINCREMENT"],
            "comment": "自增主键",
        },
        "goal_id": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "目标ID"},
        "date": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "日期"},
        "time_spent": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "今天在该目标上花费的时间",
        },
        "completed_todo_count": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "今天完成的该目标的待办事项数量",
        },
    },
    "table_constraints": [],
    "indexes": [{"name": "idx_goal_stats_goal_id", "columns": ["goal_id"]}],
    "timestamps": True,
}

# REWARD_CONFIG - 已废弃，里程碑功能整合到 goal.milestones

# report 界面数据库保存
# daily report
daily_report_config = {
    "table_name": "daily_report",
    "columns": {
        "date": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "日期 YYYY-MM-DD",
        },
        "comparison": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "与前一天的环比对比 (ComparisonStatsData JSON)",
        },
        "sunburst_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "旭日图数据 (TimeOverviewData JSON)",
        },
        "todo_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "Todo统计数据 (TodoStatsData JSON)",
        },
        "goal_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "Goal进度数据 (GoalProgressData[] JSON)",
        },
        "daily_trend_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "24小时趋势数据 (TimeDistributionPoint[] JSON)",
        },
        "state": {
            "type": "TEXT",
            "constraints": ["DEFAULT 0"],
            "comment": "数据状态 (0: 未完成, 1: 已完成)",
        },
        "data_version": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 1"],
            "comment": "数据格式版本号",
        },
        "ai_summary": {"type": "TEXT", "constraints": ["DEFAULT NULL"], "comment": "AI总结"},
        "ai_summary_abstract": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "AI总结摘要",
        },
    },
    "table_constraints": [],
    "indexes": [{"name": "idx_daily_report_date", "columns": ["date"]}],
    "timestamps": True,
    "update_at": True,
}


weekly_report_config = {
    "table_name": "weekly_report",
    "columns": {
        "date": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "日期 YYYY-MM-DD",
        },
        "comparison": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "与前一周的环比对比 (ComparisonStatsData JSON)",
        },
        "sunburst_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "旭日图数据 (TimeOverviewData JSON)",
        },
        "todo_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "Todo统计数据 (TodoStatsData JSON)",
        },
        "goal_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "Goal进度数据 (GoalProgressData[] JSON)",
        },
        "daily_trend_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "24小时趋势数据 (TimeDistributionPoint[] JSON)",
        },
        "state": {
            "type": "TEXT",
            "constraints": ["DEFAULT 0"],
            "comment": "数据状态 (0: 未完成, 1: 已完成)",
        },
        "data_version": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 1"],
            "comment": "数据格式版本号",
        },
        "ai_summary": {"type": "TEXT", "constraints": ["DEFAULT NULL"], "comment": "AI总结"},
    },
    "table_constraints": [],
    "indexes": [{"name": "idx_daily_report_date", "columns": ["date"]}],
    "timestamps": True,
    "update_at": True,
}


monthly_report_config = {
    "table_name": "monthly_report",
    "columns": {
        "date": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "日期 YYYY-MM-DD",
        },
        "comparison": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "与前一个月的环比对比 (ComparisonStatsData JSON)",
        },
        "sunburst_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "旭日图数据 (TimeOverviewData JSON)",
        },
        "todo_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "Todo统计数据 (TodoStatsData JSON)",
        },
        "goal_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "Goal进度数据 (GoalProgressData[] JSON)",
        },
        "daily_trend_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "24小时趋势数据 (TimeDistributionPoint[] JSON)",
        },
        "state": {
            "type": "TEXT",
            "constraints": ["DEFAULT 0"],
            "comment": "数据状态 (0: 未完成, 1: 已完成)",
        },
        "data_version": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 1"],
            "comment": "数据格式版本号",
        },
        "ai_summary": {"type": "TEXT", "constraints": ["DEFAULT NULL"], "comment": "AI总结"},
        "heatmap_data": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "热力图数据 (HeatmapDataItem[] JSON)",
        },
    },
    "table_constraints": [],
    "indexes": [{"name": "idx_daily_report_date", "columns": ["date"]}],
    "timestamps": True,
    "update_at": True,
}
"""时间悖论里的测试，过去，现在，未来"""
TIME_PARADOXES_CONFIG = {
    "table_name": "time_paradoxes",
    "columns": {
        "id": {"type": "INTEGER", "constraints": ["PRIMARY KEY", "NOT NULL"], "comment": "ID"},
        "user_id": {"type": "INTEGER", "constraints": ["NOT NULL"], "comment": "用户ID"},
        "version": {"type": "INTEGER", "constraints": ["NOT NULL"], "comment": "版本号"},
        "mode": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "模式（past/present/future）",
        },
        "content": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "具体测试内容"},
        "ai_abstract": {"type": "TEXT", "constraints": ["DEFAULT NULL"], "comment": "AI总结"},
    },
    "table_constraints": ["UNIQUE(user_id,mode,version)"],
    "indexes": [
        {
            "name": "idx_time_paradoxes_user_id_mode_version",
            "columns": ["user_id", "mode", "version"],
        }
    ],
    "timestamps": True,
    "update_at": True,
}


# 日记表配置（Mind Space 日记模块）
DIARY_CONFIG = {
    "table_name": "diary",
    "columns": {
        "date": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "日期 YYYY-MM-DD，唯一标识",
        },
        "mood": {
            "type": "TEXT",
            "constraints": [],
            "comment": "心情: very_happy, happy, calm, bad, very_bad",
        },
        "importance": {
            "type": "TEXT",
            "constraints": [],
            "comment": "平凡程度: important, normal, unimportant",
        },
        "custom_tags": {
            "type": "TEXT",
            "constraints": ["DEFAULT '[]'"],
            "comment": "自定义 tag，JSON 数组",
        },
        "word_count": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "字数统计，用于日历视图展示",
        },
        "ai_summary": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "AI 总结（保留字段）",
        },
        "diary_source_hash": {
            "type": "TEXT",
            "constraints": ["DEFAULT NULL"],
            "comment": "生成当前 ai_summary 时使用的正文 hash",
        },
    },
    "table_constraints": [],
    "indexes": [],
    "timestamps": True,
    "update_at": True,
}


# 心情类型表配置（Mind Space 心情模块）
MOOD_TYPES_CONFIG = {
    "table_name": "mood_types",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "心情类型 ID，默认类型用固定 id（如 joy, calm），自定义用 mood-type-{uuid[:8]}",
        },
        "name": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": '心情名称（如"喜悦"、"宁静"），最长 4 字符',
        },
        "icon": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "Lucide 图标名（如 Sun, Wind）",
        },
        "color": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "十六进制颜色值（如 #fed7aa）",
        },
        "score": {
            "type": "INTEGER",
            "constraints": ["NOT NULL"],
            "comment": "心情评分权重 0-100，用于点图 Y 轴",
        },
        "is_dark": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "是否深色主题（影响前端文字颜色）",
        },
        "sort_order": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "排序权重，越大越靠前",
        },
    },
    "table_constraints": [],
    "indexes": [],
    "timestamps": True,
    "update_at": True,
}

# 心情记录表配置（Mind Space 心情模块）
MOOD_ENTRIES_CONFIG = {
    "table_name": "mood_entries",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "心情记录 ID，格式 mood-{uuid[:8]}",
        },
        "mood_type_id": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "关联 mood_types.id",
        },
        "score": {
            "type": "INTEGER",
            "constraints": ["NOT NULL"],
            "comment": "该条记录的心情评分（冗余存储，取自 mood_type 的 score）",
        },
        "content": {"type": "TEXT", "constraints": [], "comment": "用户输入的文字内容（可为空）"},
        "factors": {"type": "TEXT", "constraints": [], "comment": "JSON 数组，影响心情的 tag 列表"},
        "event_time": {
            "type": "TEXT",
            "constraints": [],
            "comment": "事件时间（UTC ISO 8601），Agent 可控，替代 created_at 用于查询/排序",
        },
    },
    "table_constraints": [],
    "indexes": [
        {"name": "idx_mood_entries_mood_type_id", "columns": ["mood_type_id"]},
        {"name": "idx_mood_entries_event_time", "columns": ["event_time"]},
        {"name": "idx_mood_entries_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,
    "update_at": True,
}

# 影响因素配置表（Mind Space 心情模块）
MOOD_IMPACTS_CONFIG = {
    "table_name": "mood_impacts",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY", "AUTOINCREMENT"],
            "comment": "自增 ID",
        },
        "name": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "UNIQUE"],
            "comment": '因素名称（如"健康"、"工作"）',
        },
        "sort_order": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "排序权重，越大越靠前",
        },
    },
    "table_constraints": [],
    "indexes": [],
    "timestamps": True,
    "update_at": True,
}


# 价值表配置（Mind Space 承诺与价值模块）
USER_VALUES_CONFIG = {
    "table_name": "user_values",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "价值 ID，格式 val-{uuid[:8]}",
        },
        "keywords": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "UNIQUE"],
            "comment": '关键词（支持多个，使用分号分隔，如"健康;活力;自律"），UNIQUE 防止重复',
        },
        "content_positive": {
            "type": "TEXT",
            "constraints": [],
            "comment": "正向描述（我想成为什么样的人）",
        },
        "content_negative": {
            "type": "TEXT",
            "constraints": [],
            "comment": "负向描述（我不想成为什么样的人）",
        },
        "sort_order": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "排序权重，越大越靠前",
        },
    },
    "table_constraints": [],
    "indexes": [],
    "timestamps": True,
    "update_at": True,
}

# 承诺表配置（Mind Space 承诺与价值模块）
COMMITMENTS_CONFIG = {
    "table_name": "commitments",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "承诺 ID，格式 cmt-{uuid[:8]}",
        },
        "content": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "承诺的具体行动描述"},
        "value_id": {
            "type": "TEXT",
            "constraints": [],
            "comment": "关联价值 ID（删除价值时可置空）",
        },
        "status": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "DEFAULT 'active'"],
            "comment": "状态: active / completed / archived",
        },
    },
    "table_constraints": ["CHECK(status IN ('active', 'completed', 'archived'))"],
    "indexes": [
        {"name": "idx_commitments_value_id", "columns": ["value_id"]},
        {"name": "idx_commitments_status", "columns": ["status"]},
    ],
    "timestamps": True,
    "update_at": True,
}


# 数据库迁移版本表配置
SCHEMA_VERSION_CONFIG = {
    "table_name": "schema_version",
    "columns": {
        "version": {"type": "INTEGER", "constraints": ["PRIMARY KEY"], "comment": "迁移版本号"},
        "name": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "迁移脚本名称"},
        "applied_at": {
            "type": "TIMESTAMP",
            "constraints": ["DEFAULT (datetime('now'))"],
            "comment": "执行时间（UTC）",
        },
    },
    "table_constraints": [],
    "indexes": [],
    "timestamps": False,
    "update_at": False,
}


HABITS_CONFIG = {
    "table_name": "habits",
    "columns": {
        "id": {"type": "TEXT", "constraints": ["PRIMARY KEY"], "comment": "习惯唯一标识"},
        "name": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "习惯名称"},
        "description": {"type": "TEXT", "constraints": [], "comment": "习惯描述"},
        "frequency_type": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "频率类型: 'daily'|'weekly'",
        },
        "frequency_config": {
            "type": "TEXT",
            "constraints": [],
            "comment": "JSON 存储额外频率配置（如 weekDays 数组）",
        },
        "current_level": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "当前等级 0-4",
        },
        "status": {
            "type": "TEXT",
            "constraints": ["DEFAULT 'active'"],
            "comment": "'active'|'paused'",
        },
        "value_id": {"type": "TEXT", "constraints": [], "comment": "关联价值ID（可空）"},
        "commitment_id": {"type": "TEXT", "constraints": [], "comment": "关联承诺ID（可空）"},
        "paused_at": {"type": "TEXT", "constraints": [], "comment": "暂停时间（可空）"},
    },
    "table_constraints": [],
    "indexes": [],
    "timestamps": True,
    "update_at": True,
}

HABIT_CHALLENGES_CONFIG = {
    "table_name": "habit_challenges",
    "columns": {
        "id": {"type": "TEXT", "constraints": ["PRIMARY KEY"], "comment": "挑战唯一标识"},
        "habit_id": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "所属习惯ID"},
        "challenge_weeks": {"type": "INTEGER", "constraints": ["NOT NULL"], "comment": "挑战周数"},
        "required_completions": {
            "type": "INTEGER",
            "constraints": ["NOT NULL"],
            "comment": "最低完成次数",
        },
        "from_level": {"type": "INTEGER", "constraints": ["NOT NULL"], "comment": "起始等级"},
        "to_level": {"type": "INTEGER", "constraints": ["NOT NULL"], "comment": "目标等级"},
        "start_date": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "开始日期 YYYY-MM-DD",
        },
        "end_date": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "结束日期 YYYY-MM-DD"},
        "completed_count": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "已完成次数",
        },
        "streak_base": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "Streak基数（上次挑战遗留）",
        },
        "status": {
            "type": "TEXT",
            "constraints": ["DEFAULT 'in_progress'"],
            "comment": "'in_progress'|'succeeded'|'failed'|'cancelled'",
        },
        "finished_at": {"type": "TEXT", "constraints": [], "comment": "结束时间（可空）"},
    },
    "table_constraints": [
        "FOREIGN KEY (habit_id) REFERENCES habits(id)",
    ],
    "indexes": [
        {"name": "idx_challenges_habit_id", "columns": ["habit_id"]},
    ],
    "timestamps": True,
    "update_at": True,
}

HABIT_CHECKINS_CONFIG = {
    "table_name": "habit_checkins",
    "columns": {
        "id": {"type": "TEXT", "constraints": ["PRIMARY KEY"], "comment": "打卡记录唯一标识"},
        "habit_id": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "关联习惯ID"},
        "challenge_id": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "所属挑战ID"},
        "date": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "打卡日期 YYYY-MM-DD"},
        "completed_at": {"type": "TEXT", "constraints": [], "comment": "实际完成时间戳（可空）"},
    },
    "table_constraints": [
        "FOREIGN KEY (habit_id) REFERENCES habits(id)",
        "FOREIGN KEY (challenge_id) REFERENCES habit_challenges(id)",
        "UNIQUE(habit_id, date)",
    ],
    "indexes": [
        {"name": "idx_checkins_habit_date", "columns": ["habit_id", "date"]},
    ],
    "timestamps": True,
    "update_at": True,
}

HABIT_CHAINS_CONFIG = {
    "table_name": "habit_chains",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY AUTOINCREMENT"],
            "comment": "链条自增ID",
        },
        "name": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "链条名称"},
        "description": {"type": "TEXT", "constraints": [], "comment": "链条描述（可空）"},
        "show_in_timeline": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "0=不显示, 1=在Timeline展示",
        },
    },
    "table_constraints": [],
    "indexes": [],
    "timestamps": True,
    "update_at": True,
}

HABIT_CHAIN_NODES_CONFIG = {
    "table_name": "habit_chain_nodes",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY AUTOINCREMENT"],
            "comment": "节点自增ID",
        },
        "chain_id": {"type": "INTEGER", "constraints": ["NOT NULL"], "comment": "所属链条ID"},
        "sort_order": {
            "type": "INTEGER",
            "constraints": ["NOT NULL"],
            "comment": "排序顺序（从1开始）",
        },
        "name": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "节点名称"},
        "habit_id": {"type": "TEXT", "constraints": [], "comment": "关联习惯ID（NULL=纯锚点节点）"},
        "trigger_time": {"type": "TEXT", "constraints": [], "comment": "触发时间 HH:mm（可空）"},
    },
    "table_constraints": [
        "FOREIGN KEY (chain_id) REFERENCES habit_chains(id) ON DELETE CASCADE",
        "FOREIGN KEY (habit_id) REFERENCES habits(id)",
    ],
    "indexes": [
        {"name": "idx_chain_nodes_chain_id", "columns": ["chain_id"]},
        {"name": "idx_chain_nodes_habit_id", "columns": ["habit_id"]},
    ],
    "timestamps": True,
    "update_at": True,
}

SCREEN_CAPTURES_CONFIG = {
    "table_name": "screen_captures",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "截屏记录 ID（如 sc-{uuid[:8]}）",
        },
        "captured_at": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "截屏时间戳（ISO 格式）",
        },
        "capture_reason": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "触发截屏的原因",
        },
        "file_path": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "相对 lifeprism_data_path 的路径",
        },
        "window_app": {"type": "TEXT", "constraints": [], "comment": "截屏时的应用程序名称"},
        "window_title": {"type": "TEXT", "constraints": [], "comment": "截屏时的窗口标题"},
        "frequency_level": {
            "type": "INTEGER",
            "constraints": [],
            "comment": "截屏频率等级（scheduled 为 NULL）",
        },
        "engaged_segment_id": {"type": "TEXT", "constraints": [], "comment": "关联时间段 ID"},
        "is_afk": {
            "type": "INTEGER",
            "constraints": ["DEFAULT 0"],
            "comment": "是否处于 AFK 状态（0=否, 1=是）",
        },
    },
    "table_constraints": ["UNIQUE (file_path)"],
    "indexes": [
        {"name": "idx_screen_captures_captured_at", "columns": ["captured_at"]},
        {"name": "idx_screen_captures_segment_id", "columns": ["engaged_segment_id"]},
        {"name": "idx_screen_captures_reason_time", "columns": ["capture_reason", "captured_at"]},
    ],
    "timestamps": True,
    "update_at": False,
}

WINDOW_EVENTS_CONFIG = {
    "table_name": "window_events",
    "columns": {
        "id": {
            "type": "INTEGER",
            "constraints": ["PRIMARY KEY AUTOINCREMENT"],
            "comment": "自增ID",
        },
        "timestamp": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "事件发生的时间戳 (ISO格式)",
        },
        "duration": {"type": "REAL", "constraints": ["NOT NULL"], "comment": "持续时长(秒)"},
        "app": {"type": "TEXT", "constraints": [], "comment": "应用程序名称"},
        "title": {"type": "TEXT", "constraints": [], "comment": "窗口标题"},
    },
    "table_constraints": [],
    "indexes": [
        {"name": "idx_window_events_timestamp", "columns": ["timestamp"]},
    ],
    "timestamps": True,
    "update_at": False,
}

RAW_BEHAVIOR_ANALYSIS_CONFIG = {
    "table_name": "raw_behavior_analysis",
    "columns": {
        "start_time": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "开始时间（YYYY-MM-DD HH:MM:SS 格式）",
        },
        "end_time": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "结束时间（YYYY-MM-DD HH:MM:SS 格式）",
        },
        "behavior": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "行为描述"},
        "screen_count": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "截图数量",
        },
    },
    "table_constraints": ["CHECK(end_time > start_time)"],
    "indexes": [
        {"name": "idx_raw_behavior_start_time", "columns": ["start_time"]},
        {"name": "idx_raw_behavior_time_range", "columns": ["start_time", "end_time"]},
    ],
    "timestamps": True,
    "update_at": True,
}

BEHAVIOR_ANALYSIS_CONFIG = {
    "table_name": "behavior_analysis",
    "columns": {
        "start_time": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "开始时间（YYYY-MM-DD HH:MM:SS 格式）",
        },
        "end_time": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "结束时间（YYYY-MM-DD HH:MM:SS 格式）",
        },
        "behavior": {"type": "TEXT", "constraints": ["NOT NULL"], "comment": "行为详细描述"},
        "behavior_summary": {"type": "TEXT", "constraints": [], "comment": "行为摘要"},
        "title": {"type": "TEXT", "constraints": [], "comment": "行为标题"},
        "screen_count": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "截图数量",
        },
    },
    "table_constraints": ["CHECK(end_time > start_time)"],
    "indexes": [
        {"name": "idx_behavior_start_time", "columns": ["start_time"]},
        {"name": "idx_behavior_time_range", "columns": ["start_time", "end_time"]},
        {"name": "idx_behavior_analysis_updated_at", "columns": ["updated_at"]},
    ],
    "timestamps": True,
    "update_at": True,
}


# ==================== 自定义记录模块 Meta 表 ====================

CUSTOM_RECORD_TYPES_CONFIG = {
    "table_name": "custom_record_types",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "类型 ID（格式：crt-{uuid[:8]}）",
        },
        "name": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "类型显示名",
        },
        "slug": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "UNIQUE"],
            "comment": "语义化标识，用作数据表名后缀",
        },
        "description": {
            "type": "TEXT",
            "constraints": [],
            "comment": "类型描述",
        },
        "card_template": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "DEFAULT 'clean'"],
            "comment": "卡片模板（clean|paper|minimal|bold|metric）",
        },
        "icon": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "DEFAULT 'fileText'"],
            "comment": "类型图标名",
        },
        "accent_color": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "DEFAULT 'blue'"],
            "comment": "强调色",
        },
    },
    "table_constraints": [],
    "indexes": [],
    "timestamps": True,
    "update_at": True,
}

CUSTOM_RECORD_FIELDS_CONFIG = {
    "table_name": "custom_record_fields",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY", "NOT NULL"],
            "comment": "字段定义 ID（格式：crf-{uuid[:8]}）",
        },
        "type_id": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "关联 custom_record_types.id",
        },
        "field_name": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "字段显示名",
        },
        "field_key": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "数据库列名，正则 ^[a-z][a-z0-9_]*$",
        },
        "field_type": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "字段类型（P1 仅 text）",
        },
        "sort_order": {
            "type": "INTEGER",
            "constraints": ["NOT NULL", "DEFAULT 0"],
            "comment": "列顺序",
        },
        "display_role": {
            "type": "TEXT",
            "constraints": ["NOT NULL", "DEFAULT 'auto'"],
            "comment": "字段展示角色（auto|title|main|chip|hidden）",
        },
    },
    "table_constraints": ["UNIQUE (type_id, field_key)"],
    "indexes": [],
    "timestamps": True,
    "update_at": True,
}


# 所有表配置的映射
TABLE_CONFIGS = {
    "category_map_cache": category_map_cache_CONFIG,
    "multi_purpose_map_cache": MULTI_PURPOSE_MAP_CACHE_CONFIG,
    "single_purpose_map_cache": SINGLE_PURPOSE_MAP_CACHE_CONFIG,
    "user_app_behavior_log": USER_APP_BEHAVIOR_LOG_CONFIG,
    "category": CATEGORY_CONFIG,
    "sub_category": SUB_CATEGORY_CONFIG,
    "tokens_usage_log": TOKENS_USAGE_LOG_CONFIG,
    "todo_list": TODO_LIST_CONFIG,
    "daily_focus": DAILY_FOCUS_CONFIG,
    "weekly_focus": WEEKLY_FOCUS_CONFIG,
    "goal": GOAL_CONFIG,
    "goal_journal": GOAL_JOURNAL_CONFIG,
    "plan_doc": PLAN_DOC_CONFIG,
    "chat_session": CHAT_SESSION_CONFIG,
    "timeline_custom_block": TIMELINE_CUSTOM_BLOCK_CONFIG,
    "goal_stats": GOAL_STATS_CONFIG,
    "daily_report": daily_report_config,
    "weekly_report": weekly_report_config,
    "monthly_report": monthly_report_config,
    "time_paradoxes": TIME_PARADOXES_CONFIG,
    "diary": DIARY_CONFIG,
    "mood_types": MOOD_TYPES_CONFIG,
    "mood_entries": MOOD_ENTRIES_CONFIG,
    "mood_impacts": MOOD_IMPACTS_CONFIG,
    "user_values": USER_VALUES_CONFIG,
    "commitments": COMMITMENTS_CONFIG,
    "schema_version": SCHEMA_VERSION_CONFIG,
    "habits": HABITS_CONFIG,
    "habit_challenges": HABIT_CHALLENGES_CONFIG,
    "habit_checkins": HABIT_CHECKINS_CONFIG,
    "habit_chains": HABIT_CHAINS_CONFIG,
    "habit_chain_nodes": HABIT_CHAIN_NODES_CONFIG,
    "screen_captures": SCREEN_CAPTURES_CONFIG,
    "window_events": WINDOW_EVENTS_CONFIG,
    "raw_behavior_analysis": RAW_BEHAVIOR_ANALYSIS_CONFIG,
    "behavior_analysis": BEHAVIOR_ANALYSIS_CONFIG,
    "custom_record_types": CUSTOM_RECORD_TYPES_CONFIG,
    "custom_record_fields": CUSTOM_RECORD_FIELDS_CONFIG,
}


def get_table_config(table_name: str) -> dict:
    """
    获取指定表的配置

    Args:
        table_name: 表名

    Returns:
        dict: 表配置字典

    Raises:
        InvalidConfigError: 如果表名不存在
    """
    if table_name not in TABLE_CONFIGS:
        logger.error("表配置缺失: table_name=%s, 可用表=%s", table_name, list(TABLE_CONFIGS.keys()))
        raise InvalidConfigError(
            key=table_name,
            expected="valid table name",
            actual="not found",
        )
    return TABLE_CONFIGS[table_name]


def get_table_columns(table_name: str) -> list:
    """
    获取表的所有列名（不包括时间戳字段）

    Args:
        table_name: 表名

    Returns:
        list: 列名列表
    """
    config = get_table_config(table_name)
    return list(config["columns"].keys())


def get_all_table_names() -> list:
    """
    获取所有已定义的表名

    Returns:
        list: 表名列表
    """
    return list(TABLE_CONFIGS.keys())
