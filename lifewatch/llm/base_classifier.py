"""
LLM分类器模块 - 抽象基类和工具函数

提供了可扩展的LLM分类架构，支持多种LLM后端（Ollama本地、云端API等）
"""

import pandas as pd
import json
from abc import ABC, abstractmethod
from typing import List, Dict


# ==================== 工具函数（无状态，独立使用） ====================

def generate_llm_batches(df: pd.DataFrame, max_chars: int = 2000, max_items: int = 15) -> List[List[Dict]]:
    """
    将DataFrame转换为符合LLM请求限制的批次列表。
    
    Args:
        df (pd.DataFrame): 待分类的数据表
        max_chars (int): 每次请求的最大字符数限制 (用于预估 Payload)
        max_items (int): 每次请求的最大条数限制 (防止 Attention 丢失)
        
    Returns:
        list: 包含多个批次的列表，每个批次是一个字典列表
    """
    batches = []
    current_batch = []
    current_chars = 0
    
    # 基础 Prompt 字符数预估 (System Prompt + 格式说明的大致长度)
    base_prompt_overhead = 500 

    for index, row in df.iterrows():
        # 构造单条数据对象
        item = {
            "id": index, 
            "app_name": row['app'],
            "app_description": row['app_description'],
            "title": row['title'],
            "is_multipurpose": row['is_multipurpose_app']
        }
        
        # 计算当前 Item 的字符长度
        item_json_str = json.dumps(item, ensure_ascii=False)
        item_len = len(item_json_str)
        
        # 检查是否触发限制
        if (len(current_batch) >= max_items) or \
           (current_chars + item_len + base_prompt_overhead > max_chars):
            batches.append(current_batch)
            current_batch = []
            current_chars = 0
        
        current_batch.append(item)
        current_chars += item_len
    
    # 处理最后一个未满的批次
    if current_batch:
        batches.append(current_batch)
        
    return batches


def extract_json(response_str: str) -> List[Dict]:
    """
    从 LLM 响应字符串中提取 JSON 列表
    
    Args:
        response_str (str): LLM 原始响应字符串
        
    Returns:
        list: 解析后的 JSON 列表
    """
    try:
        json_list = json.loads(response_str)
        if isinstance(json_list, list):
            return json_list
        else:
            print("警告：解析后的 JSON 不是列表格式")
            return []
    except json.JSONDecodeError as e:
        print(f"错误：无法解析 JSON 字符串 - {e}")
        return []


def merge_classification_results(df: pd.DataFrame, 
                                 first_step_results: List[Dict], 
                                 second_step_results: List[Dict]) -> pd.DataFrame:
    """
    合并第一步和第二步的分类结果（用于Ollama两步流程）
    
    Args:
        df (pd.DataFrame): 原始数据表
        first_step_results (list): 第一步分类结果列表，包含 need_web_search 标志
        second_step_results (list): 第二步分类结果列表（仅针对需要网络搜索的应用）
        
    Returns:
        pd.DataFrame: 包含分类结果的完整数据表
    """
    # 创建第二步结果的字典，方便查找
    second_step_dict = {item['id']: item for item in second_step_results}
    
    # 遍历第一步结果并回填到 DataFrame
    for result in first_step_results:
        idx = result['id']
        
        if idx not in df.index:
            continue
            
        # 如果不需要网络搜索，直接使用第一步结果
        if not result.get('need_web_search', False):
            df.at[idx, 'category'] = result.get('A', '其他')
            df.at[idx, 'sub_category'] = result.get('B', '其他')
        # 如果需要网络搜索，使用第二步结果
        elif idx in second_step_dict:
            df.at[idx, 'category'] = second_step_dict[idx].get('A', '其他')
            df.at[idx, 'sub_category'] = second_step_dict[idx].get('B', '其他')
        else:
            # 如果第二步没有结果，使用默认值
            df.at[idx, 'category'] = '其他'
            df.at[idx, 'sub_category'] = '其他'
            
    return df


# ==================== 抽象基类 ====================

class BaseLLMClassifier(ABC):
    """
    LLM分类器抽象基类
    
    定义了分类器的标准接口，所有具体实现（Ollama、云端API等）都需要继承此类
    
    注意：
    - Ollama本地分类器：需要两步流程（判断 → 本地搜索 → 分类）
    - 云端API分类器：只需一步（模型自带网络搜索能力）
    """
    
    def __init__(self, category: str, sub_category: str):
        """
        初始化分类器
        
        Args:
            category (str): 大类分类选项，逗号分隔，如 "工作/学习,娱乐,其他"
            sub_category (str): 具体目的分类选项，逗号分隔
        """
        self.category = category
        self.sub_category = sub_category
    
    @abstractmethod
    def classify(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        分类方法（抽象方法，子类必须实现）
        
        不同的分类器有不同的实现：
        - Ollama: 可能需要两步流程（enable_web_search参数）
        - 云端API: 一步完成（模型自带搜索）
        
        Args:
            df (pd.DataFrame): 待分类的数据表
            **kwargs: 子类特定的参数
            
        Returns:
            pd.DataFrame: 包含分类结果的完整数据表
        """
        pass
