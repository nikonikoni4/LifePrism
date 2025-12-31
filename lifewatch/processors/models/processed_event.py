"""
数据模型定义
用于数据清洗过程中的中间数据结构
"""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ProcessedEvent:
    """
    标准化后的事件数据模型
    
    包含从 ActivityWatch 原始事件转换而来的标准化数据，
    以及可选的分类结果（来自缓存或待 LLM 分类）
    """
    # 基础字段
    id: str
    start_time: str  # 格式: YYYY-MM-DD HH:MM:SS (本地时间)
    end_time: str    # 格式: YYYY-MM-DD HH:MM:SS (本地时间)
    duration: int    # 秒
    app: str         # 已标准化: 小写、去除 .exe
    title: str       # 已标准化: 小写、去除多余后缀
    is_multipurpose: bool
    
    # 分类结果（可选，来自缓存匹配或待 LLM 分类后填充）
    category_id: Optional[str] = None
    sub_category_id: Optional[str] = None
    link_to_goal_id: Optional[str] = None
    
    # 匹配状态
    cache_matched: bool = False
    
    def to_dict(self) -> dict:
        """
        转换为字典格式，用于构建 DataFrame
        """
        return {
            'id': self.id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'app': self.app,
            'title': self.title,
            'is_multipurpose_app': 1 if self.is_multipurpose else 0,
            'category_id': self.category_id,
            'sub_category_id': self.sub_category_id,
            'link_to_goal_id': self.link_to_goal_id,
        }
