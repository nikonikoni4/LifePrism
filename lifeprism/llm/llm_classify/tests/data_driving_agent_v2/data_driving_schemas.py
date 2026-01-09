from typing import Annotated, TypedDict, Literal, Type, Any
from pydantic import BaseModel, Field, create_model, model_validator
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
import operator 
from langchain_core.output_parsers import PydanticOutputParser

# ============================================================================
# 节点类型定义
# ============================================================================
# 1. llm-first: LLM先执行，可选工具调用
# 2. tool-first: 工具先执行，然后LLM分析
# 3. planning: 规划节点，生成子计划并递归执行
# ============================================================================

NodeType = Literal["llm-first", "tool-first", "planning"]

# 所有可用的节点类型
ALL_NODE_TYPES: set[NodeType] = {"llm-first", "tool-first", "planning"}

# 预定义的权限集合
MAIN_EXECUTOR_PERMISSIONS: set[NodeType] = {"llm-first", "tool-first", "planning"}
SUB_EXECUTOR_PERMISSIONS: set[NodeType] = {"llm-first", "tool-first"}


# ============================================================================
# 线程元信息
# ============================================================================
class ThreadMeta(TypedDict):
    """线程元信息，用于追踪线程父子关系"""
    parent_thread: str | None  # 父线程ID，主线程为 None


class Context(TypedDict):
    """
    执行上下文
    
    结构说明:
    - messages: 按 thread_id 隔离的消息列表
    - data_out: 子线程向外输出的结果，格式为 {role: 'assistant', content: description + result}
    - thread_meta: 线程元信息，记录父子关系用于合并时确定目标
    
    合并逻辑:
    当子线程节点 data_out=True 时，将结果写入 data_out[thread_id]
    执行器会根据 thread_meta[thread_id].parent_thread 将其合并到父线程的 messages 中
    """
    messages: dict[str, list[AIMessage | HumanMessage | ToolMessage]]  # thread_id : messages
    data_out: dict[str, Any]  # thread_id : 输出内容 {role: 'assistant', content: ...}


# ============================================================================
# 基础节点定义（带类型标识）
# ============================================================================
class NodeDefinition(BaseModel):
    """
    节点定义
    
    节点类型说明:
    - llm-first: LLM先执行，可选调用工具。适用于需要先推理再行动的场景
    - tool-first: 工具先执行，然后LLM分析结果。适用于需要先获取数据再分析的场景
    - planning: 规划节点，生成子计划并递归执行（暂未实现）
    
    数据流说明:
    - 输入：
        - data_in_thread: 指定输入数据来源线程ID，None表示使用parent_thread_id
        - data_in_slice: 指定消息切片范围 [start, end)。None时取最后一条消息
    - 输出：
        - data_out_thread: 指定输出数据的目标线程ID，None表示不输出
        - data_out: 是否将结果输出到父（输出）线程
    """
    
    # ===== 核心标识 =====
    node_type: NodeType = Field(
        description="节点类型: llm-first(LLM先执行), tool-first(工具先执行), planning(规划节点)"
    )
    node_name: str = Field(description="节点名称，用于日志和调试")
    
    # ===== 线程配置 =====
    thread_id: str = Field(description="当前节点的线程ID")

    
    # ===== LLM 配置 =====
    task_prompt: str = Field(
        default="",
        description="LLM的任务描述。tool-first节点可为空（表示只执行工具，不调用LLM）"
    )
    
    # ===== 工具配置 =====
    tools: list[str] | None = Field(
        default=None, 
        description="节点可调用的工具列表。None表示不绑定任何工具"
    )
    enable_tool_loop: bool = Field(
        default=False,
        description="是否启用工具调用循环。True时LLM可多次调用工具直到完成任务"
    )
    
    # ===== tool-first 专用 =====
    initial_tool_name: str | None = Field(
        default=None,
        description="[tool-first专用] 初始工具名称，tool-first节点必须指定"
    )
    initial_tool_args: dict[str, Any] | None = Field(
        default=None,
        description="[tool-first专用] 初始工具参数"
    )
    
    # ===== 数据输入配置 =====
    data_in_thread: str | None = Field(
        default=None, 
        description="输入数据来源线程ID。None时使用parent_thread_id"
    )
    data_in_slice: tuple[int | None, int | None] | None = Field(
        default=None, 
        description="消息切片范围 [start, end)。None时取最后一条消息"
    )
    
    # ===== 数据输出配置 =====
    data_out_thread: str | None = Field(
        default=None, 
        description="输出数据目标线程ID，用于确定合并目标。主线程节点为None"
    )
    data_out: bool = Field(
        default=False, 
        description="是否将结果输出到父线程"
    )
    data_out_description: str = Field(
        default="", 
        description="输出内容的描述前缀"
    )
    
    @model_validator(mode='after')
    def validate_node(self):
        """验证节点配置的一致性"""
        # 规则1: tool-first 必须指定 initial_tool_name
        if self.node_type == "tool-first" and not self.initial_tool_name:
            raise ValueError("tool-first 节点必须指定 initial_tool_name")
        
        # 规则2: llm-first 不应有 initial_tool_name
        if self.node_type == "llm-first" and self.initial_tool_name:
            raise ValueError("llm-first 节点不应指定 initial_tool_name，请使用 tool-first 类型")
        
        return self
class ExecutionPlan(BaseModel):
    """执行计划（无限制版本，支持所有节点类型）"""
    task: str = Field(description="任务名称")
    nodes: list[NodeDefinition] = Field(description="安排的节点列表")


# ============================================================================
# 动态 Schema 生成器
# ============================================================================
def create_node_definition_schema( 
    allowed_types: set[NodeType],
    class_name: str = "RestrictedNodeDefinition"
) -> Type[BaseModel]:
    """
    创建受限的节点定义 Schema
    
    Args:
        allowed_types: 允许的节点类型集合
        class_name: 生成的类名
        
    Returns:
        动态生成的 Pydantic 模型类
        
    Example:
        >>> SubNodeDef = create_node_definition_schema({"llm-first", "tool-first"})
        >>> node = SubNodeDef(node_type="llm-first", node_name="test", task_prompt="...")
    """
    if not allowed_types:
        raise ValueError("allowed_types 不能为空")
    
    if not allowed_types.issubset(ALL_NODE_TYPES):
        invalid = allowed_types - ALL_NODE_TYPES
        raise ValueError(f"无效的节点类型: {invalid}")
    
    # 创建 Literal 类型
    allowed_literal = Literal[tuple(allowed_types)]  # type: ignore
    
    # 生成类型描述
    type_descriptions = {
        "llm-first": "LLM先执行",
        "tool-first": "工具先执行",
        "planning": "规划节点"
    }
    desc_parts = [f"{t}({type_descriptions[t]})" for t in allowed_types]
    type_desc = f"节点类型: {', '.join(desc_parts)}"
    
    # 动态创建模型
    return create_model(
        class_name,
        node_type=(allowed_literal, Field(description=type_desc)),
        node_name=(str, Field(description="节点名称")),
        task_prompt=(str, Field(default="", description="LLM的任务描述")),
        thread_id=(str, Field(description="线程ID")),
        data_out_thread=(str | None, Field(default=None, description="父线程ID")),
        # 工具配置
        tools=(list[str] | None, Field(default=None, description="可调用的工具列表")),
        enable_tool_loop=(bool, Field(default=False, description="是否启用工具调用循环")),
        # tool-first 专用
        initial_tool_name=(str | None, Field(default=None, description="[tool-first专用] 初始工具名称")),
        initial_tool_args=(dict[str, Any] | None, Field(default=None, description="[tool-first专用] 初始工具参数")),
        # 数据配置
        data_in_thread=(str | None, Field(default=None, description="输入数据来源线程ID")),
        data_in_slice=(tuple[int | None, int | None] | None, Field(default=None, description="消息切片范围")),
        data_out=(bool, Field(default=False, description="是否输出到父线程")),
        data_out_description=(str, Field(default="", description="输出内容描述前缀"))
    )



def create_execution_plan_schema(
    allowed_node_types: set[NodeType],
    class_name: str = "RestrictedExecutionPlan"
) -> Type[BaseModel]:
    """
    创建受限的执行计划 Schema
    
    这是核心工厂函数，用于生成只允许特定节点类型的 ExecutionPlan Schema。
    主执行器可以使用完整权限，子执行器可以使用受限权限。
    
    Args:
        allowed_node_types: 允许使用的节点类型集合
        class_name: 生成的类名
        
    Returns:
        动态生成的 ExecutionPlan Pydantic 模型类
        
    Example:
        >>> # 主执行器 - 所有权限
        >>> MainPlan = create_execution_plan_schema(MAIN_EXECUTOR_PERMISSIONS)
        >>> 
        >>> # 子执行器 - 只允许 tool 和 query
        >>> SubPlan = create_execution_plan_schema(SUB_EXECUTOR_PERMISSIONS)
        >>> sub_plan = SubPlan(task="子任务", nodes=[...])
    """
    # 创建受限的节点定义类型
    RestrictedNodeDef = create_node_definition_schema(
        allowed_node_types, 
        f"{class_name}NodeDefinition"
    )
    
    # 生成节点类型描述
    type_list = ", ".join(allowed_node_types)
    nodes_desc = f"安排的节点列表（仅允许类型: {type_list}）"
    
    # 动态创建 ExecutionPlan 模型
    return create_model(
        class_name,
        task=(str, Field(description="任务名称")),
        nodes=(list[RestrictedNodeDef], Field(description=nodes_desc))
    )


# ============================================================================
# 预生成的常用 Schema
# ============================================================================
# 主执行器 Schema（所有权限）
MainExecutorPlan = create_execution_plan_schema(
    MAIN_EXECUTOR_PERMISSIONS,
    "MainExecutorPlan"
)

# 子执行器 Schema（仅 tool 和 query）
SubExecutorPlan = create_execution_plan_schema(
    SUB_EXECUTOR_PERMISSIONS,
    "SubExecutorPlan"
)


# ============================================================================
# 便捷函数
# ============================================================================
def get_output_parser(
    allowed_node_types: set[NodeType] | None = None
) -> PydanticOutputParser:
    """
    获取对应权限的输出解析器
    
    Args:
        allowed_node_types: 允许的节点类型，None 表示使用所有权限
        
    Returns:
        配置好的 PydanticOutputParser
        
    Example:
        >>> # 主执行器
        >>> parser = get_output_parser()
        >>> 
        >>> # 子执行器
        >>> parser = get_output_parser(SUB_EXECUTOR_PERMISSIONS)
    """
    if allowed_node_types is None:
        allowed_node_types = MAIN_EXECUTOR_PERMISSIONS
    
    schema = create_execution_plan_schema(allowed_node_types)
    return PydanticOutputParser(pydantic_object=schema)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("测试动态 Schema 生成")
    print("=" * 60)
    
    # 1. 测试主执行器 Schema
    print("\n1. 主执行器 Schema (所有权限):")
    print(f"   允许的类型: {MAIN_EXECUTOR_PERMISSIONS}")
    main_parser = get_output_parser(MAIN_EXECUTOR_PERMISSIONS)
    print(f"   格式说明:\n{main_parser.get_format_instructions()}...")
    
    # 2. 测试子执行器 Schema
    print("\n2. 子执行器 Schema (tool + query):")
    print(f"   允许的类型: {SUB_EXECUTOR_PERMISSIONS}")
    sub_parser = get_output_parser(SUB_EXECUTOR_PERMISSIONS)
    print(f"   格式说明:\n{sub_parser.get_format_instructions()}...")
    
