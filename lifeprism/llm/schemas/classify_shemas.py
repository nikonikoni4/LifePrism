from pydantic import BaseModel, Field


class LogItem(BaseModel):
    id: int
    app: str
    duration: int = Field(description="时长,单位秒")
    title: str | None
    title_analysis: str | None = None
    category: str | None = Field(default=None)
    sub_category: str | None = Field(default=None)
    link_to_goal: str | None = Field(default=None)


class Goal(BaseModel):
    goal: str
    category: str
    sub_category: str | None


class AppInFo(BaseModel):
    description: str = Field(description="app的描述")
    is_multipurpose: bool = Field(description="是否为多用途应用")
    titles: list[str] | None = Field(default=None)


class classifyState(BaseModel):
    app_registry: dict[str, AppInFo] = Field(description="app : AppInFo")
    log_items: list[LogItem] = Field(description="原始分类数据")
    result_items: list[LogItem] | None = Field(default=None, description="输出结果")
