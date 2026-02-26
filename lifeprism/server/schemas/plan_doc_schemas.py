"""
PlanDoc Schemas 定义

计划书同步相关的请求/响应模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class TodoDeletePreview(BaseModel):
    """待删除任务预览"""
    id: str = Field(..., description="任务 ID（即 MD 锚点）")
    content: str = Field(..., description="任务内容")
    state: str = Field(..., description="任务状态")


class SyncPlanDocRequest(BaseModel):
    """同步计划书任务请求"""
    plan_doc_id: str = Field(..., description="计划书 ID")
    dry_run: bool = Field(default=False, description="预检模式：只返回差异，不执行操作")
    confirm_delete: bool = Field(default=False, description="确认删除：True=删除全部待删除任务，False=保留全部")


class SyncPlanDocResponse(BaseModel):
    """同步计划书任务响应"""
    created: int = Field(default=0, description="新创建的任务数")
    updated: int = Field(default=0, description="更新的任务数")
    deleted: int = Field(default=0, description="删除的任务数")
    cleaned: int = Field(default=0, description="清理的锚点数")
    total: int = Field(default=0, description="该计划书关联的总任务数")
    to_delete: Optional[List[TodoDeletePreview]] = Field(default=None, description="待删除任务列表（dry_run 模式返回）")


class RegenerateSummaryRequest(BaseModel):
    """重新生成系统展示区请求"""
    plan_doc_id: str = Field(..., description="计划书 ID")


class RegenerateSummaryResponse(BaseModel):
    """重新生成系统展示区响应"""
    success: bool = Field(..., description="是否成功")
    message: Optional[str] = Field(default=None, description="提示信息")
