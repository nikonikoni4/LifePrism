from pydantic import BaseModel, Field

class MultiNodeResult(BaseModel):
    """存储多节点分类的中间结果"""
    # 节点1结果: 目标关联判断
    is_goal_related: bool | None = None  # 是否与goal高度相关
    node1_link_to_goal: str | None = None  # 节点1判断的关联目标
    node1_category: str | None = None  # 节点1判断的分类(如果与goal相关)
    node1_sub_category: str | None = None  # 节点1判断的子分类
    
    # 节点2结果: 信息补充
    website_name: str | None = None  # 从title中提取的网站名称
    website_purpose: str | None = None  # 网站的用途描述
    entity_name: str | None = None  # 从title中提取的实体名称
    entity_meaning: str | None = None  # 实体的含义描述
    title_analysis: str | None = None  # 对title的综合分析
    
    # 节点3结果: 最终分类(存储在LogItem的category/sub_category/link_to_goal中)

class LogItem(BaseModel):
    # 基础数据
    id: int
    app: str
    duration: int # 时长
    title: str | None
    # 分类结果
    category: str | None = None # 存储分类结果
    sub_category: str | None = None # 存储分类结果
    link_to_goal: str | None = None # 与goal相关联
    # 搜索标题
    search_title_query: str | None = None # 搜索标题的查询
    search_title_content: str | None = None # 搜索标题的结果
    # 上一条数据
    need_analyze_context: bool = False # 是否需要获取上一条数据信息
    # 多节点分类中间结果
    multi_node_result: MultiNodeResult | None = None
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