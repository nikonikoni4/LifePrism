"""
数据库配置模块
定义数据库表结构的完整元数据
"""

# 数据库路径
LW_DB_PATH = r"D:\desktop\软件开发\LifeWatch-AI\lifewatch\server\lifewatch_ai.db"
ACTIVITYWATCH_DB_PATH = r"C:\Users\15535\AppData\Local\activitywatch\activitywatch\aw-server\peewee-sqlite.v2.db"
# 应用程序用途分类表配置
APP_PURPOSE_CATEGORY_CONFIG = {
    'table_name': 'app_purpose_category',
    'columns': {
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
        'category': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '默认分类（工作/学习/其他）'
        },
        'sub_category': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '根据目标分类（编码，读书笔记等）'
        }
    },
    'table_constraints': ['PRIMARY KEY (app, title)'],  # 表级约束：复合主键
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


# 所有表配置的映射
TABLE_CONFIGS = {
    'app_purpose_category': APP_PURPOSE_CATEGORY_CONFIG,
    'user_app_behavior_log': USER_APP_BEHAVIOR_LOG_CONFIG,
    'category': CATEGORY_CONFIG,
    'sub_category': SUB_CATEGORY_CONFIG,
    'tokens_usage_log': TOKENS_USAGE_LOG_CONFIG
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
