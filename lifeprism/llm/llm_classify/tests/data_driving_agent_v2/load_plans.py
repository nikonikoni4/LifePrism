"""
Plan 读取函数

提供多种方式加载执行计划:
- 从 JSON 模板文件加载
- 从 dict 数据加载
- 从 JSON 字符串加载

支持的节点类型:
- llm-first: LLM先执行，可选工具调用
- tool-first: 工具先执行，然后LLM分析
- planning: 规划节点、生成子计划

支持的节点字段:
- enable_tool_loop: 是否启用工具调用循环
- initial_tool_name / initial_tool_args: tool-first 节点初始工具配置
- data_in_thread / data_in_slice: 子线程启动时的输入数据配置
- data_out / data_out_description: 子线程向父线程输出结果
"""
import json
from pathlib import Path
from typing import Any

from lifeprism.llm.llm_classify.tests.data_driving_agent_v2.data_driving_schemas import (
    ExecutionPlan, 
    NodeDefinition,
    NodeType,
    ALL_NODE_TYPES,
    create_execution_plan_schema
)


# ============================================================================
# 核心加载函数
# ============================================================================
def load_plan_from_dict(
    plan_data: dict[str, Any],
    allowed_node_types: set[NodeType] | None = None
) -> ExecutionPlan:
    """
    从字典加载 ExecutionPlan
    
    Args:
        plan_data: 包含 task 和 nodes 的字典数据
        allowed_node_types: 允许的节点类型，None 表示使用所有类型
        
    Returns:
        ExecutionPlan 对象
        
    Raises:
        ValueError: 节点类型不在允许范围内
        
    Example:
        >>> data = {
        ...     "task": "示例任务",
        ...     "nodes": [{"node_type": "llm-first", "node_name": "test", ...}]
        ... }
        >>> plan = load_plan_from_dict(data)
    """
    # 如果指定了允许的节点类型，进行验证
    if allowed_node_types is not None:
        for node in plan_data.get("nodes", []):
            node_type = node.get("node_type")
            if node_type not in allowed_node_types:
                raise ValueError(
                    f"节点类型 '{node_type}' 不在允许范围内，"
                    f"允许的类型: {allowed_node_types}"
                )
        # 使用动态 schema 验证
        schema = create_execution_plan_schema(allowed_node_types)
        return schema(**plan_data)
    
    return ExecutionPlan(**plan_data)


def load_plan_from_json_str(
    json_str: str,
    allowed_node_types: set[NodeType] | None = None
) -> ExecutionPlan:
    """
    从 JSON 字符串加载 ExecutionPlan
    
    Args:
        json_str: JSON 格式的字符串
        allowed_node_types: 允许的节点类型
        
    Returns:
        ExecutionPlan 对象
        
    Example:
        >>> json_str = '{"task": "test", "nodes": []}'
        >>> plan = load_plan_from_json_str(json_str)
    """
    plan_data = json.loads(json_str)
    return load_plan_from_dict(plan_data, allowed_node_types)


def load_plan_from_template(
    json_path: str | Path,
    pattern_name: str,
    date: str | None = None,
    extra_replacements: dict[str, str] | None = None,
    allowed_node_types: set[NodeType] | None = None
) -> tuple[ExecutionPlan, dict[str, int] | None]:
    """
    从 JSON 模板文件加载执行计划
    
    Args:
        json_path: JSON 模板文件路径
        pattern_name: 要加载的模式名称
        date: 替换 {date} 占位符的实际日期 (可选)
        extra_replacements: 额外的占位符替换，格式 {"{placeholder}": "actual_value"}
        allowed_node_types: 允许的节点类型
        
    Returns:
        tuple[ExecutionPlan, dict | None]: (执行计划, 工具限制配置)
        
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: pattern_name 不存在或节点类型不允许
        
    Example:
        >>> plan, tools_limit = load_plan_from_template(
        ...     json_path="patterns/daily.json",
        ...     pattern_name="simple",
        ...     date="2026-01-07"
        ... )
    """
    if isinstance(json_path, str):
        json_path = Path(json_path)
    
    if not json_path.exists():
        raise FileNotFoundError(f"JSON 文件不存在: {json_path}")
    
    # 读取 JSON 模板
    with open(json_path, "r", encoding="utf-8") as f:
        all_patterns = json.load(f)
    
    # 获取指定的 pattern
    if pattern_name not in all_patterns:
        available = list(all_patterns.keys())
        raise ValueError(f"未知的 pattern_name: '{pattern_name}'，可用: {available}")
    
    plan_data = all_patterns[pattern_name]
    
    # 替换占位符
    plan_json_str = json.dumps(plan_data, ensure_ascii=False)
    
    if date is not None:
        plan_json_str = plan_json_str.replace("{date}", date)
    
    # 替换额外的占位符
    if extra_replacements:
        for placeholder, actual_value in extra_replacements.items():
            plan_json_str = plan_json_str.replace(placeholder, actual_value)
    
    plan_data = json.loads(plan_json_str)
    
    # 提取 tools_limit
    tools_limit = plan_data.pop("tools_limit", None)
    
    # 加载为 ExecutionPlan
    plan = load_plan_from_dict(plan_data, allowed_node_types)
    
    return plan, tools_limit


# ============================================================================
# 便捷函数
# ============================================================================
def list_available_patterns(json_path: str | Path) -> list[str]:
    """
    列出 JSON 文件中所有可用的 pattern 名称
    
    Args:
        json_path: JSON 模板文件路径
        
    Returns:
        pattern 名称列表
        
    Example:
        >>> patterns = list_available_patterns("patterns/daily.json")
        >>> print(patterns)  # ['simple', 'complex', ...]
    """
    if isinstance(json_path, str):
        json_path = Path(json_path)
    
    if not json_path.exists():
        raise FileNotFoundError(f"JSON 文件不存在: {json_path}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        all_patterns = json.load(f)
    
    return list(all_patterns.keys())


def get_pattern_info(
    json_path: str | Path,
    pattern_name: str
) -> dict[str, Any]:
    """
    获取指定 pattern 的元信息（不替换占位符）
    
    Args:
        json_path: JSON 模板文件路径
        pattern_name: pattern 名称
        
    Returns:
        包含 task, nodes 数量, tools_limit 等信息的字典
        
    Example:
        >>> info = get_pattern_info("patterns/daily.json", "simple")
        >>> print(info)
        {
            "task": "每日行为总结 {date}",
            "node_count": 2,
            "node_types": ["tool-first", "llm-first"],
            "tools_limit": {"get_daily_stats": 1},
            "has_placeholders": True # 是否包含占位符 比如 {date}
        }
    """
    if isinstance(json_path, str):
        json_path = Path(json_path)
    
    if not json_path.exists():
        raise FileNotFoundError(f"JSON 文件不存在: {json_path}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        all_patterns = json.load(f)
    
    if pattern_name not in all_patterns:
        available = list(all_patterns.keys())
        raise ValueError(f"未知的 pattern_name: '{pattern_name}'，可用: {available}")
    
    plan_data = all_patterns[pattern_name]
    nodes = plan_data.get("nodes", [])
    
    # 收集节点类型
    node_types = list(set(node.get("node_type") for node in nodes))
    
    # 检查是否有占位符
    plan_json_str = json.dumps(plan_data, ensure_ascii=False)
    has_placeholders = "{" in plan_json_str and "}" in plan_json_str
    
    return {
        "task": plan_data.get("task", ""),
        "node_count": len(nodes),
        "node_types": node_types,
        "tools_limit": plan_data.get("tools_limit"),
        "has_placeholders": has_placeholders
    }


def validate_plan_data(
    plan_data: dict[str, Any],
    allowed_node_types: set[NodeType] | None = None
) -> tuple[bool, list[str]]:
    """
    验证 plan 数据的有效性（不创建对象）
    
    Args:
        plan_data: 待验证的 plan 数据
        allowed_node_types: 允许的节点类型
        
    Returns:
        tuple[bool, list[str]]: (是否有效, 错误信息列表)
        
    Example:
        >>> is_valid, errors = validate_plan_data(data)
        >>> if not is_valid:
        ...     print("验证失败:", errors)
    """
    errors = []
    
    # 检查基本结构
    if "task" not in plan_data:
        errors.append("缺少 'task' 字段")
    
    if "nodes" not in plan_data:
        errors.append("缺少 'nodes' 字段")
        return False, errors
    
    nodes = plan_data.get("nodes", [])
    if not isinstance(nodes, list):
        errors.append("'nodes' 必须是列表")
        return False, errors
    
    if len(nodes) == 0:
        errors.append("'nodes' 列表不能为空")
    
    # 验证每个节点
    allowed = allowed_node_types or ALL_NODE_TYPES
    
    for i, node in enumerate(nodes):
        prefix = f"节点[{i}]"
        
        # 必需字段
        if "node_type" not in node:
            errors.append(f"{prefix}: 缺少 'node_type'")
        elif node["node_type"] not in allowed:
            errors.append(
                f"{prefix}: 节点类型 '{node['node_type']}' 不在允许范围 {allowed}"
            )
        
        if "node_name" not in node:
            errors.append(f"{prefix}: 缺少 'node_name'")
        
        if "task_prompt" not in node:
            errors.append(f"{prefix}: 缺少 'task_prompt'")
        
        if "thread_id" not in node:
            errors.append(f"{prefix}: 缺少 'thread_id'")
        
        # tool-first 节点特殊验证
        if node.get("node_type") == "tool-first":
            if not node.get("initial_tool_name"):
                errors.append(f"{prefix}: tool-first 类型节点必须有 'initial_tool_name'")
        
        # data_in_slice 格式验证
        if "data_in_slice" in node and node["data_in_slice"] is not None:
            slice_val = node["data_in_slice"]
            if not isinstance(slice_val, (list, tuple)) or len(slice_val) != 2:
                errors.append(f"{prefix}: 'data_in_slice' 必须是长度为2的数组 [start, end]")
    
    return len(errors) == 0, errors


# ============================================================================
# 测试代码
# ============================================================================
if __name__ == "__main__":
    import os
    
    # 获取当前文件所在目录
    current_dir = Path(__file__).parent
    example_path = current_dir / "patterns" / "example_daily_plan.json"
    
    print("=" * 60)
    print("测试 Plan 读取函数")
    print("=" * 60)
    
    # 1. 测试列出可用 patterns
    print("\n1. 列出可用 patterns:")
    try:
        patterns = list_available_patterns(example_path)
        print(f"   可用模式: {patterns}")
    except FileNotFoundError as e:
        print(f"   文件不存在: {e}")
    
    # 2. 测试获取 pattern 信息
    print("\n2. 获取 pattern 信息:")
    try:
        info = get_pattern_info(example_path, "simple")
        print(f"   任务: {info['task']}")
        print(f"   节点数量: {info['node_count']}")
        print(f"   节点类型: {info['node_types']}")
        print(f"   工具限制: {info['tools_limit']}")
        print(f"   含占位符: {info['has_placeholders']}")
    except Exception as e:
        print(f"   错误: {e}")
    
    # 3. 测试从模板加载
    print("\n3. 从模板加载 plan:")
    try:
        plan, tools_limit = load_plan_from_template(
            example_path,
            pattern_name="simple",
            date="2026-01-07"
        )
        print(f"   任务: {plan.task}")
        print(f"   节点数量: {len(plan.nodes)}")
        for node in plan.nodes:
            print(f"   - {node.node_name} ({node.node_type})")
        print(f"   工具限制: {tools_limit}")
    except Exception as e:
        print(f"   错误: {e}")
    
    # 4. 测试从 dict 加载 (包含 data_in 配置)
    print("\n4. 从 dict 加载 plan (含 data_in):")
    test_data = {
        "task": "测试任务",
        "nodes": [
            {
                "node_type": "llm-first",
                "node_name": "主线程节点",
                "task_prompt": "这是一个测试",
                "thread_id": "main",
                "parent_thread_id": None  # 主线程，无父线程
            },
            {
                "node_type": "llm-first",
                "node_name": "子线程节点",
                "task_prompt": "查询详细数据",
                "thread_id": "sub_1",
                "parent_thread_id": "main",
                "data_in_thread": None,  # 使用父线程作为数据来源
                "data_in_slice": [-2, None],  # 取父线程最后2条消息
                "tools": ["query_behavior_logs"],
                "enable_tool_loop": True
            }
        ]
    }
    plan = load_plan_from_dict(test_data)
    print(f"   任务: {plan.task}")
    print(f"   节点: {plan.nodes[0].node_name}")
    
    # 5. 测试验证函数
    print("\n5. 测试验证函数:")
    
    # 有效数据
    is_valid, errors = validate_plan_data(test_data)
    print(f"   有效数据验证: {is_valid}")
    
    # 无效数据
    invalid_data = {"task": "test", "nodes": [{"node_type": "invalid"}]}
    is_valid, errors = validate_plan_data(invalid_data)
    print(f"   无效数据验证: {is_valid}")
    print(f"   错误: {errors}")  # 只显示前两个错误
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
