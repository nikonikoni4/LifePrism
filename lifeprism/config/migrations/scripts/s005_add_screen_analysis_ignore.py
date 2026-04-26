"""
配置迁移 s005: 添加截图分析忽略配置

添加字段:
- screen_analysis_ignore: 截图分析忽略的分类 ID 列表 (默认 [])
"""

VERSION = 5
NAME = "s005_add_screen_analysis_ignore"


def check_if_applied(data: dict) -> bool:
    """检查迁移是否已应用"""
    return 'screen_analysis_ignore' in data


def upgrade(data: dict) -> dict:
    """执行迁移"""
    if 'screen_analysis_ignore' not in data:
        data['screen_analysis_ignore'] = []

    return data
