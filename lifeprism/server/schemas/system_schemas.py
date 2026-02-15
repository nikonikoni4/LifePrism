from pydantic import BaseModel, Field
from typing import List


class SystemWarning(BaseModel):
    type: str = Field(description="警告类型，如 data_path, general")
    message: str = Field(description="警告消息内容")


class SystemWarningsResponse(BaseModel):
    warnings: List[SystemWarning] = Field(description="系统警告列表")
