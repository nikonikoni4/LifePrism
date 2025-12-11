from pydantic import BaseModel, Field

class TitleDescriptionInput(BaseModel):
    """标题描述查询的输入参数"""
    query_list: list[str] = Field(description="要查询的网站或实体关键词列表")

class TitleDescriptionOutput(BaseModel):
    """标题描述查询的输出参数"""
    result: dict[str,str] = Field(description="查询结果")