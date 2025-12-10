from pydantic import BaseModel

class LogItem(BaseModel):
    # 基础数据
    id: int
    app: str
    duration: int # 时长
    title: str | None
    # 分类结果
    category: str | None # 存储分类结果
    sub_category: str | None # 存储分类结果
    link_to_goal:str | None # 与goal相关联
    # 搜索标题
    search_title_query: str | None # 搜索标题的查询
    search_title_content: str | None # 搜索标题的结果
    # 上一条数据
    need_analyze_context: bool # 是否需要获取上一条数据信息
class Goal(BaseModel):
    goal: str # 用户的目标
    category: str # 用户的目标绑定的分类, Goal必须有第一个类别
    sub_category: str | None # 用户的目标绑定的子分类

class AppInFo(BaseModel):
    description : str
    is_multipurpose : bool
# 定义状态
class classifyState(BaseModel):
    app_registry: dict[str, AppInFo] # app : app_description
    log_items: list[LogItem] # 分类数据 
    goal: list[Goal] # 用户的目标
    node_token_usage: dict[str, dict] = {} # 记录每个 node 的 token 消耗: {node_name: {input_tokens, output_tokens, total_tokens}}
    category_tree : dict[str, list[str]| None] # 具体分类 