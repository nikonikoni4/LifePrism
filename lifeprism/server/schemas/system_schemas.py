from pydantic import BaseModel, Field
from typing import List


class SystemWarningsResponse(BaseModel):
    warnings: List[str] = Field(description="系统警告消息列表")
