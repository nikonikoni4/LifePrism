from pydantic import BaseModel, Field

class MultiNodeResult(BaseModel):
    """存储多节点分类的中间结果"""
    # 节点1结果: 目标关联判断
    is_goal_related: bool | None = Field(default=None, description="是否与goal高度相关") # 是否与goal高度相关
    node1_link_to_goal: str | None = Field(default=None, description="节点1判断的关联目标")  # 节点1判断的关联目标
    node1_category: str | None = Field(default=None, description="节点1判断的分类(如果与goal相关)")  # 节点1判断的分类(如果与goal相关)
    node1_sub_category: str | None = Field(default=None, description="节点1判断的子分类")  # 节点1判断的子分类
    
    # 节点2结果: 信息补充
    website_name: str | None = Field(default=None, description="从title中提取的网站名称")  # 从title中提取的网站名称
    website_purpose: str | None = Field(default=None, description="网站的用途描述")  # 网站的用途描述
    entity_name: str | None = Field(default=None, description="从title中提取的实体名称")  # 从title中提取的实体名称
    entity_meaning: str | None = Field(default=None, description="实体的含义描述")  # 实体的含义描述
    title_analysis: str | None = Field(default=None, description="对title的综合分析")  # 对title的综合分析
    
    # 节点3结果: 最终分类(存储在LogItem的category/sub_category/link_to_goal中)

class LogItem(BaseModel):
    # 基础数据
    id: int
    app: str
    duration: int = Field(description="时长,单位秒") # 时长
    title: str | None
    # 分类结果
    category: str | None = Field(default=None, description="存储分类结果") # 存储分类结果
    sub_category: str | None = Field(default=None, description="存储分类结果") # 存储分类结果
    link_to_goal: str | None = Field(default=None, description="与goal相关联") # 与goal相关联
    # 搜索标题
    search_title_query: str | None = Field(default=None, description="搜索标题的查询") # 搜索标题的查询
    search_title_content: str | None = Field(default=None, description="搜索标题的结果") # 搜索标题的结果
    # 上一条数据
    need_analyze_context: bool = False # 是否需要获取上一条数据信息
    # 多节点分类中间结果
    multi_node_result: MultiNodeResult | None = None
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
    app_registry: dict[str, AppInFo] = Field(description="app : app_description") # app : app_description
    log_items: list[LogItem] = Field(description="分类数据") # 分类数据 
    goal: list[Goal] = Field(description="用户的目标") # 用户的目标
    node_token_usage: dict[str, dict] = Field(default_factory=dict, description="记录每个 node 的 token 消耗: {node_name: {input_tokens, output_tokens, total_tokens}}") # 记录每个 node 的 token 消耗: {node_name: {input_tokens, output_tokens, total_tokens}}
    category_tree : dict[str, list[str]| None] = Field(description="具体分类") # 具体分类