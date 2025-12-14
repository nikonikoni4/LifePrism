from pydantic import BaseModel,Field
from typing import Annotated
from langgraph.channels.binop import BinaryOperator
import operator

def remain_old_value(old_value,new_value):
    if old_value:
        return old_value
    else:
        return new_value

class LogItem(BaseModel):
    # 基础数据
    id: int
    app: str
    duration: int = Field(description="时长,单位秒") # 时长
    title: str | None
    title_analysis: str | None = None  # 搜索分析结果，初始为None
    # 分类结果
    category: str | None = Field(default=None, description="存储分类结果") # 存储分类结果
    sub_category: str | None = Field(default=None, description="存储分类结果") # 存储分类结果
    link_to_goal: str | None = Field(default=None, description="与goal相关联") # 与goal相关联

class Goal(BaseModel):
    goal: str = Field(description="用户的目标") # 用户的目标
    category: str = Field(description="用户的目标绑定的分类, Goal必须有第一个类别") # 用户的目标绑定的分类, Goal必须有第一个类别
    sub_category: str | None = Field(description="用户的目标绑定的子分类") # 用户的目标绑定的子分类

class AppInFo(BaseModel):
    description : str = Field(description="app的描述")
    is_multipurpose : bool = Field(description="是否为被选择需要使用title信息来判断用途的应用")
    titles : list[str] | None = Field(default=None, description="该app的典型标题示例列表，用于辅助识别app用途")
# 定义状态
class classifyState(BaseModel):
    app_registry: Annotated[dict[str, AppInFo], operator.or_] = Field(description="app : app_description") # app : app_description
    log_items: Annotated[list[LogItem],operator.add] = Field(description="分类数据") # 分类数据 
    goal: Annotated[list[Goal], remain_old_value]= Field(description="用户的目标") # 用户的目标
    node_token_usage: Annotated[dict[str, dict], operator.or_] = Field(default_factory=dict, description="记录每个 node 的 token 消耗: {node_name: {input_tokens, output_tokens, total_tokens}}") # 记录每个 node 的 token 消耗: {node_name: {input_tokens, output_tokens, total_tokens}}
    category_tree : Annotated[dict[str, list[str]| None], remain_old_value] = Field(description="具体分类") # 具体分类



class SearchOutput(BaseModel):
    title_analysis: Annotated[dict[int, str], operator.or_]  # 使用 dict 合并，key 为 id，value 为分析结果
    input_data: dict[int, str]  # key 为 id，value 为 title