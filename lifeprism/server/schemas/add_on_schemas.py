"""
Add-on 扩展功能的数据模型定义
"""

from pydantic import BaseModel, Field
from typing import List
from datetime import datetime


class ExpandDirBase(BaseModel):
    """扩展文件夹基础模型"""
    name: str = Field(..., description="文件夹名称")
    path: str = Field(..., description="文件夹路径")
    description: str = Field(..., description="文件夹描述")
    ai_index: bool = Field(..., description="是否启用AI索引")


class ExpandDirCreate(ExpandDirBase):
    """创建扩展文件夹的请求模型"""
    pass


class ExpandDirUpdate(ExpandDirBase):
    """更新扩展文件夹的请求模型"""
    pass


class ExpandDirResponse(ExpandDirBase):
    """扩展文件夹的响应模型"""
    id: str = Field(..., description="唯一标识符（数字字符串）")
    created_at: datetime = Field(..., description="创建时间")


class ExpandDirListResponse(BaseModel):
    """扩展文件夹列表响应"""
    expand_dirs: List[ExpandDirResponse]
