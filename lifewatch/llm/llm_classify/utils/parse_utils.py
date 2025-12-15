"""
LLM 结果解析工具

本模块提供用于解析 LLM 返回结果的工具函数，与 format_prompt_utils 形成对称：
- format_prompt_utils: 格式化输入数据给 LLM
- parse_utils: 解析 LLM 的输出结果
"""

from lifewatch.llm.llm_classify.schemas.classify_shemas import classifyState
import logging

logger = logging.getLogger(__name__)


def extract_json_from_response(content: str) -> str:
    """
    从 LLM 响应中提取 JSON 内容，处理可能的 Markdown 代码块标记
    
    LLM 有时会返回带有 ```json 或 ``` 标记的响应，这个函数会清理这些标记，
    返回纯 JSON 字符串以便 json.loads() 正确解析。
    
    Args:
        content: LLM 返回的原始响应内容
        
    Returns:
        清理后的 JSON 字符串
        
    Example:
        >>> content = '''```json
        ... {"id": 1}
        ... ```'''
        >>> extract_json_from_response(content)
        '{"id": 1}'
    """
    content = content.strip()
    
    # 如果包含代码块标记，提取其中的内容
    if content.startswith("```"):
        lines = content.split("\n")
        # 移除第一行（```json 或 ```）和最后一行（```）
        json_lines = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            json_lines.append(line)
        content = "\n".join(json_lines)
    
    return content.strip()


def parse_classification_result(
    state: classifyState, 
    classification_result: dict, 
    node_name: str
) -> classifyState:
    """
    通用的分类结果解析函数
    
    Args:
        state: classifyState 对象
        classification_result: LLM 返回的分类结果，格式为 {id: [category, sub_category, link_to_goal]}
        node_name: 节点名称，用于日志输出
        
    Returns:
        更新后的 classifyState 对象
        
    Example:
        >>> classification_result = {
        ...     "1": ["工作/学习", "编程", "完成项目"],
        ...     "2": ["娱乐", "看视频", None]
        ... }
        >>> state = parse_classification_result(state, classification_result, "single_classify")
    """
    # 创建 id 到 log_item 的映射
    id_to_item = {item.id: item for item in state.log_items}
    
    # 遍历分类结果，更新对应的 log_item
    for item_id_str, classification in classification_result.items():
        try:
            item_id = int(item_id_str)
            if item_id in id_to_item:
                # classification 格式: [category, sub_category, link_to_goal]
                if isinstance(classification, list) and len(classification) == 3:
                    category, sub_category, link_to_goal = classification
                    
                    # 将字符串 "null" 或 None 转换为 Python 的 None
                    category = None if (category == "null" or category is None) else category
                    sub_category = None if (sub_category == "null" or sub_category is None) else sub_category
                    link_to_goal = None if (link_to_goal == "null" or link_to_goal is None) else link_to_goal
                    
                    # 更新 log_item
                    id_to_item[item_id].category = category
                    id_to_item[item_id].sub_category = sub_category
                    id_to_item[item_id].link_to_goal = link_to_goal
                    
                    logger.debug(
                        f"[{node_name}] 已更新 log_item {item_id}: "
                        f"category={category}, sub_category={sub_category}, link_to_goal={link_to_goal}"
                    )
                else:
                    logger.error(
                        f"[{node_name}] 分类结果格式错误: item_id={item_id}, "
                        f"classification={classification}, 期望列表格式 [category, sub_category, link_to_goal]"
                    )
            else:
                logger.warning(f"[{node_name}] 分类结果中的 id {item_id} 在 log_items 中不存在")
        except (ValueError, TypeError) as e:
            logger.error(
                f"[{node_name}] 解析分类结果时出错: "
                f"item_id={item_id_str}, classification={classification}, error={e}"
            )
    
    return state
