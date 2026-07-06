from pydantic import BaseModel, Field


class SystemWarning(BaseModel):
    type: str = Field(description="警告类型，如 data_path, general")
    message: str = Field(description="警告消息内容")


class SystemWarningsResponse(BaseModel):
    warnings: list[SystemWarning] = Field(description="系统警告列表")
