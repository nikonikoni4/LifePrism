"""
Goal 数据提供者
提供目标（Goal）相关的数据库操作
"""
from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class GoalProvider(LWBaseDataProvider):
    """
    目标模块数据提供者
    
    继承 LWBaseDataProvider，提供目标相关的 CRUD 操作
    """
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    # TODO: 添加具体的 CRUD 方法
    # def get_goals(self, ...) -> list[dict]: ...
    # def get_goal_by_id(self, goal_id: str) -> Optional[dict]: ...
    # def create_goal(self, data: dict) -> str: ...
    # def update_goal(self, goal_id: str, data: dict) -> bool: ...
    # def delete_goal(self, goal_id: str) -> bool: ...
