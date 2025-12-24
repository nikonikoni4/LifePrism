"""
数据库配置模块
定义数据库表结构的完整元数据
"""

# 数据库路径
LW_DB_PATH = r"D:\desktop\软件开发\LifeWatch-AI\lifewatch\server\lifewatch_ai.db"
ACTIVITYWATCH_DB_PATH = r"C:\Users\15535\AppData\Local\activitywatch\activitywatch\aw-server\peewee-sqlite.v2.db"
# 应用程序用途分类表配置
category_map_cache_CONFIG = {
    'table_name': 'category_map_cache',
    'columns': {
        'id': {
            'type': 'INTEGER',
            'constraints': ['PRIMARY KEY', 'AUTOINCREMENT'],
            'comment': '自增主键，用于删除操作'
        },
        'app': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '应用程序的文件名（例如：chrome.exe）'
        },
        'title': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '应用程序的标题（例如：Google Chrome）'
        },
        'is_multipurpose_app': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 0'],
            'comment': '是否为被选择需要使用title信息来判断用途的应用（True/False）'
        },
        'app_description': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '应用程序的描述'
        },
        'title_analysis': { 
            'type': 'TEXT',
            'constraints': [],
            'comment': '应用程序title的描述'
        },
        'category_id': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '主分类ID（关联 category.id）'
        },
        'sub_category_id': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '子分类ID（关联 sub_category.id）'
        },
        'category': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '[已弃用] 默认分类名称，保留用于调试'
        },
        'sub_category': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '[已弃用] 子分类名称，保留用于调试'
        },
        'state': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 1'],
            'comment': '记录状态（1: 有效, 0: 无效/分类被禁用）'
        }
    },
    'table_constraints': ['UNIQUE (app, title, state)'],  # 唯一约束：保证数据不重复
    'indexes': [],
    'timestamps': True  # 自动添加 created_at, updated_at
}



# 用户应用行为日志表配置
USER_APP_BEHAVIOR_LOG_CONFIG = {
    'table_name': 'user_app_behavior_log',
    'columns': {
        'id': {
            'type': 'TEXT',
            'constraints': ['PRIMARY KEY'],
            'comment': 'ActivityWatch事件ID（原生态ID，与ActivityWatch系统匹配）'
        },
        'start_time': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '行为开始时间'
        },
        'end_time': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '行为结束时间'
        },
        'duration': {
            'type': 'INTEGER',
            'constraints': [],
            'comment': '应用程序运行的持续时间（秒），用于数据验证和兼容性'
        },
        'app': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '应用程序的文件名'
        },
        'title': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '应用程序的标题'
        },
        'is_multipurpose_app': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 0'],
            'comment': '是否为被选择需要使用title信息来判断用途的应用'
        },
        'category_id': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '主分类ID（外键引用 category.id，新增字段）'
        },
        'sub_category_id': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '子分类ID（外键引用 sub_category.id，新增字段）'
        }
    },
    'table_constraints': [
        'UNIQUE(app, start_time)',  # 复合唯一索引
        'CHECK(end_time > start_time)'  # 确保时间逻辑正确
    ],
    'indexes': [
        {'name': 'idx_app_start_time', 'columns': ['app', 'start_time']},
        {'name': 'idx_start_time', 'columns': ['start_time']},
        {'name': 'idx_end_time', 'columns': ['end_time']},
        {'name': 'idx_time_range', 'columns': ['start_time', 'end_time']}  # 时间范围查询优化
    ],
    'timestamps': True  # 自动添加 created_at
}

# 分类定义表配置（主分类）
CATEGORY_CONFIG = {
    'table_name': 'category',
    'columns': {
        'id': {
            'type': 'TEXT',
            'constraints': ['PRIMARY KEY'],
            'comment': '分类唯一标识符（例如：work, entertainment）'
        },
        'name': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '分类名称（例如：工作/学习）'
        },
        'color': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '分类颜色（十六进制格式，例如：#5B8FF9）'
        },
        'order_index': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 0'],
            'comment': '显示顺序索引'
        },
        'state': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 1'],
            'comment': '分类状态（1: 启用, 0: 禁用）'
        }
    },
    'table_constraints': [],
    'indexes': [
        {'name': 'idx_category_id', 'columns': ['id']}
    ],
    'timestamps': True  # 自动添加 created_at, updated_at
}

# 子分类定义表配置
SUB_CATEGORY_CONFIG = {
    'table_name': 'sub_category',
    'columns': {
        'id': {
            'type': 'TEXT',
            'constraints': ['PRIMARY KEY'],
            'comment': '子分类唯一标识符（例如：coding, meeting）'
        },
        'category_id': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '所属主分类ID（外键引用 category.id）'
        },
        'name': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '子分类名称（例如：编程、会议）'
        },
        'order_index': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 0'],
            'comment': '显示顺序索引'
        },
        'state': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 1'],
            'comment': '子分类状态（1: 启用, 0: 禁用）'
        }
    },
    'table_constraints': [
        'FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE CASCADE'
    ],
    'indexes': [
        {'name': 'idx_sub_category_id', 'columns': ['id']},
        {'name': 'idx_sub_category_parent', 'columns': ['category_id']}
    ],
    'timestamps': True  # 自动添加 created_at, updated_at
}

# Token 使用统计表配置
TOKENS_USAGE_LOG_CONFIG = {
    'table_name': 'tokens_usage_log',
    'columns': {
        'id': {
            'type': 'INTEGER',
            'constraints': ['PRIMARY KEY', 'AUTOINCREMENT'],
            'comment': '自动生成的唯一标识符'
        },
        'input_tokens': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL', 'DEFAULT 0'],
            'comment': '输入 token 数量'
        },
        'output_tokens': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL', 'DEFAULT 0'],
            'comment': '输出 token 数量'
        },
        'total_tokens': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL', 'DEFAULT 0'],
            'comment': '总 token 数量'
        },
        'search_count': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL', 'DEFAULT 0'],
            'comment': '搜索次数'
        },
        'result_items_count': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL', 'DEFAULT 0'],
            'comment': '分类结果数量（result_items 长度）'
        },
        'mode': {
            'type': 'TEXT',
            'constraints': ['NOT NULL', 'DEFAULT "classification"'],   
            'comment': '模式'
        }
    },
    'table_constraints': [],
    'indexes': [
        {'name': 'idx_tokens_usage_created_at', 'columns': ['created_at']}
    ],
    'timestamps': True  # 自动添加 created_at
}


# TodoList 主任务表配置
TODO_LIST_CONFIG = {
    'table_name': 'todo_list',
    'columns': {
        'id': {
            'type': 'INTEGER',
            'constraints': ['PRIMARY KEY', 'AUTOINCREMENT'],
            'comment': '自增主键'
        },
        'order_index': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL', 'DEFAULT 0'],
            'comment': '排序索引，用于拖拽排序'
        },
        'content': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '任务内容'
        },
        'color': {
            'type': 'TEXT',
            'constraints': ['DEFAULT "#FFFFFF"'],
            'comment': '任务颜色（十六进制格式）'
        },
        'completed': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 0'],
            'comment': '是否完成（0: 未完成, 1: 已完成）'
        },
        'link_to_goal': {
            'type': 'INTEGER',
            'constraints': [],
            'comment': '关联的目标 ID（可为空）'
        },
        'date': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '任务日期（YYYY-MM-DD格式，用于日历筛选）'
        },
        'expected_finished_at': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '预计完成日期（YYYY-MM-DD格式）'
        },
        'actual_finished_at': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '实际完成日期（YYYY-MM-DD格式，完成时填写）'
        },
        'cross_day': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 0'],
            'comment': '是否开启跨天追踪（0: 否, 1: 是），开启后在未完成前会持续显示'
        }
    },
    'table_constraints': [],
    'indexes': [
        {'name': 'idx_todo_list_date', 'columns': ['date']},
        {'name': 'idx_todo_list_cross_day_completed', 'columns': ['cross_day', 'completed']},
        {'name': 'idx_todo_list_link_to_goal', 'columns': ['link_to_goal']}
    ],
    'timestamps': True  # 自动添加 created_at
}


# SubTodoList 子任务表配置
SUB_TODO_LIST_CONFIG = {
    'table_name': 'sub_todo_list',
    'columns': {
        'id': {
            'type': 'INTEGER',
            'constraints': ['PRIMARY KEY', 'AUTOINCREMENT'],
            'comment': '自增主键'
        },
        'parent_id': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL'],
            'comment': '父任务 ID（关联 todo_list.id）'
        },
        'order_index': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL', 'DEFAULT 0'],
            'comment': '排序索引，用于拖拽排序'
        },
        'content': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '子任务内容'
        },
        'completed': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 0'],
            'comment': '是否完成（0: 未完成, 1: 已完成）'
        }
    },
    'table_constraints': [
        'FOREIGN KEY (parent_id) REFERENCES todo_list(id) ON DELETE CASCADE'
    ],
    'indexes': [
        {'name': 'idx_sub_todo_list_parent_id', 'columns': ['parent_id']},
        {'name': 'idx_sub_todo_list_order', 'columns': ['parent_id', 'order_index']}
    ],
    'timestamps': True  # 自动添加 created_at
}


# Daily Focus 表配置（日焦点）
DAILY_FOCUS_CONFIG = {
    'table_name': 'daily_focus',
    'columns': {
        'id': {
            'type': 'INTEGER',
            'constraints': ['PRIMARY KEY', 'AUTOINCREMENT'],
            'comment': '自增主键'
        },
        'date': {
            'type': 'TEXT',
            'constraints': ['NOT NULL', 'UNIQUE'],
            'comment': '日期 YYYY-MM-DD'
        },
        'content': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '日焦点内容'
        }
    },
    'table_constraints': [],
    'indexes': [
        {'name': 'idx_daily_focus_date', 'columns': ['date']}
    ],
    'timestamps': True
}


# Weekly Focus 表配置（周焦点）
WEEKLY_FOCUS_CONFIG = {
    'table_name': 'weekly_focus',
    'columns': {
        'id': {
            'type': 'INTEGER',
            'constraints': ['PRIMARY KEY', 'AUTOINCREMENT'],
            'comment': '自增主键'
        },
        'year': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL'],
            'comment': '年份'
        },
        'month': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL'],
            'comment': '月份 1-12'
        },
        'week_num': {
            'type': 'INTEGER',
            'constraints': ['NOT NULL'],
            'comment': '周序号 1-4'
        },
        'content': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '周焦点内容'
        }
    },
    'table_constraints': ['UNIQUE(year, month, week_num)'],
    'indexes': [
        {'name': 'idx_weekly_focus_year_month', 'columns': ['year', 'month']}
    ],
    'timestamps': True
}


# Goal 目标表配置
GOAL_CONFIG = {
    'table_name': 'goal',
    'columns': {
        'id': {
            'type': 'INTEGER',
            'constraints': ['PRIMARY KEY', 'AUTOINCREMENT'],
            'comment': '自增主键'
        },
        'name': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '目标名称'
        },
        'abstract': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '目标摘要/别名'
        },
        'content': {
            'type': 'TEXT',
            'constraints': ['DEFAULT ""'],
            'comment': '目标详细内容'
        },
        'color': {
            'type': 'TEXT',
            'constraints': ['DEFAULT "#5B8FF9"'],
            'comment': '目标颜色（十六进制）'
        },
        'link_to_category_id': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '关联的分类 ID'
        },
        'link_to_sub_category_id': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '关联的子分类 ID'
        },
        'link_to_reward_id': {
            'type': 'INTEGER',
            'constraints': [],
            'comment': '关联的奖励 ID'
        },
        'expected_finished_at': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '预计完成时间 YYYY-MM-DD'
        },
        'expected_hours': {
            'type': 'INTEGER',
            'constraints': [],
            'comment': '预计耗时（小时）'
        },
        'actual_finished_at': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '实际完成时间 YYYY-MM-DD'
        },
        'actual_hours': {
            'type': 'INTEGER',
            'constraints': [],
            'comment': '实际耗时（小时）'
        },
        'completion_rate': {
            'type': 'REAL',
            'constraints': ['DEFAULT 0.0'],
            'comment': '完成度 0-1'
        },
        'status': {
            'type': 'TEXT',
            'constraints': ['DEFAULT "active"'],
            'comment': '状态: active, completed, archived'
        },
        'order_index': {
            'type': 'INTEGER',
            'constraints': ['DEFAULT 0'],
            'comment': '排序索引'
        }
    },
    'table_constraints': [],
    'indexes': [
        {'name': 'idx_goal_status', 'columns': ['status']},
        {'name': 'idx_goal_category', 'columns': ['link_to_category_id']},
        {'name': 'idx_goal_order', 'columns': ['order_index']}
    ],
    'timestamps': True
}


# 所有表配置的映射
TABLE_CONFIGS = {
    'category_map_cache': category_map_cache_CONFIG,
    'user_app_behavior_log': USER_APP_BEHAVIOR_LOG_CONFIG,
    'category': CATEGORY_CONFIG,
    'sub_category': SUB_CATEGORY_CONFIG,
    'tokens_usage_log': TOKENS_USAGE_LOG_CONFIG,
    'todo_list': TODO_LIST_CONFIG,
    'sub_todo_list': SUB_TODO_LIST_CONFIG,
    'daily_focus': DAILY_FOCUS_CONFIG,
    'weekly_focus': WEEKLY_FOCUS_CONFIG,
    'goal': GOAL_CONFIG,
}


def get_table_config(table_name: str) -> dict:
    """
    获取指定表的配置
    
    Args:
        table_name: 表名
        
    Returns:
        dict: 表配置字典
        
    Raises:
        ValueError: 如果表名不存在
    """
    if table_name not in TABLE_CONFIGS:
        raise ValueError(f"未找到表 '{table_name}' 的配置")
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
    return list(config['columns'].keys())


def get_all_table_names() -> list:
    """
    获取所有已定义的表名
    
    Returns:
        list: 表名列表
    """
    return list(TABLE_CONFIGS.keys())
