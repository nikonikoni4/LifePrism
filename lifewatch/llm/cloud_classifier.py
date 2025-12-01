"""
云端API LLM分类器实现

云端LLM模型自带网络搜索能力，因此只需一步即可完成分类
"""

import json
from typing import List, Dict
import pandas as pd
from lifewatch.llm.base_classifier import BaseLLMClassifier, generate_llm_batches, extract_json


class CloudAPIClassifier(BaseLLMClassifier):
    """
    云端API分类器抽象基类
    
    特点：
    - 一步流程（模型自带网络搜索能力）
    - 为不同的云端API提供统一接口
    """
    
    def __init__(self, api_key: str, categoryA: str, categoryB: str, **kwargs):
        """
        初始化云端API分类器
        
        Args:
            api_key (str): API密钥
            categoryA (str): 大类分类选项
            categoryB (str): 具体目的分类选项
            **kwargs: 其他配置参数（如base_url、model_name等）
        """
        super().__init__(categoryA, categoryB)
        self.api_key = api_key
        self.config = kwargs
    
    def classify(self, df: pd.DataFrame, max_chars: int = 2000, max_items: int = 15, **kwargs) -> pd.DataFrame:
        """
        一步分类流程：直接调用云端API进行分类
        
        云端模型自带网络搜索能力，无需本地爬虫辅助
        
        Args:
            df (pd.DataFrame): 待分类的数据表
            max_chars (int): 每批次最大字符数
            max_items (int): 每批次最大条数
            **kwargs: API特定参数
            
        Returns:
            pd.DataFrame: 包含分类结果的完整数据表
        """
        print(f"=" * 60)
        print(f"开始云端API分类流程 - 总数据量: {len(df)}")
        print(f"分类器类型: {self.__class__.__name__}")
        print(f"=" * 60)
        
        # 确保 DataFrame 有必要的列
        if 'class_by_default' not in df.columns:
            df['class_by_default'] = None
        if 'class_by_goals' not in df.columns:
            df['class_by_goals'] = None
        
        # 生成批次
        batches = generate_llm_batches(df, max_chars=max_chars, max_items=max_items)
        print(f"生成批次总数: {len(batches)}")
        
        # 遍历批次进行分类
        for i, batch in enumerate(batches):
            print(f"\n处理第 {i+1}/{len(batches)} 批 (包含 {len(batch)} 条数据)...")
            
            try:
                # 构建prompt
                prompt = self._build_classify_prompt(batch)
                
                # 调用云端API
                response = self._call_api(prompt, temperature=kwargs.get('temperature', 0.1))
                
                # 解析结果
                result_list = extract_json(response)
                
                # 回填数据到 DataFrame
                for res in result_list:
                    idx = res['id']
                    if idx in df.index:
                        df.at[idx, 'class_by_default'] = res.get('A', '其他')
                        df.at[idx, 'class_by_goals'] = res.get('B', '其他')
                        
            except Exception as e:
                print(f"批次 {i+1} 处理出错: {e}")
                # 使用默认值
                for item in batch:
                    if item['id'] in df.index:
                        df.at[item['id'], 'class_by_default'] = '其他'
                        df.at[item['id'], 'class_by_goals'] = '其他'
        
        print(f"\n=" * 60)
        print(f"分类流程完成！")
        print(f"=" * 60)
        
        return df
    
    def _build_classify_prompt(self, batch_data: List[Dict]) -> str:
        """
        构建分类prompt（云端API版本，简洁）
        
        Args:
            batch_data (list): 批次数据
            
        Returns:
            str: 构建好的prompt
        """
        compact_data = [
            [item["id"], item["app_name"], item.get("app_description"), 
             item["title"], item["is_multipurpose"]] 
            for item in batch_data
        ]
        
        prompt = f"""你是用户行为分析专家。请对以下应用进行分类。
分类选项：
- A (大类): {self.categoryA}
- B (具体目的): {self.categoryB}
分类规则：
- A是背景，B是行为，需逻辑自洽
- 如果应用信息不足，可以使用你的网络搜索能力查找应用信息
- 多用途应用(is_multipurpose=true)根据title判断
- 单用途应用(is_multipurpose=false)根据app_name判断
- 无法确定时选择"其他"
数据格式：[id, app_name, app_description, title, is_multipurpose]
{json.dumps(compact_data, ensure_ascii=False)}
请返回JSON数组（仅JSON，无其他文本）：
[
  {{"id": <数字>, "A": "<分类值>", "B": "<分类值>"}}
]
"""
        return prompt
    
    def _call_api(self, prompt: str, **kwargs) -> str:
        """
        调用云端API的抽象方法（子类必须实现）
        
        Args:
            prompt (str): 提示词
            **kwargs: API特定参数
            
        Returns:
            str: API返回的文本响应
        """
        raise NotImplementedError("子类必须实现 _call_api 方法")


# ==================== 具体实现 ====================

class QwenAPIClassifier(CloudAPIClassifier):
    """
    通义千问API分类器实现（使用LLMClient）
    
    使用阿里云通义千问API进行分类，支持网络搜索
    """
    
    def __init__(self, api_key: str, base_url: str, categoryA: str, categoryB: str, 
                 model: str = "qwen-plus"):
        """
        初始化通义千问分类器
        
        Args:
            api_key (str): 通义千问API密钥
            base_url (str): API基础URL
            categoryA (str): 大类分类选项
            categoryB (str): 具体目的分类选项
            model (str): 模型名称，默认qwen-plus
        """
        super().__init__(api_key, categoryA, categoryB, model=model, base_url=base_url)
        self.model = model
        self.base_url = base_url
        
        # 初始化LLMClient
        from lifewatch.llm.remote_client import LLMClient
        self.client = LLMClient(api_key=api_key, base_url=base_url)
    
    def _call_api(self, prompt: str, **kwargs) -> str:
        """
        调用通义千问API（使用LLMClient）
        
        Args:
            prompt (str): 提示词
            **kwargs: API参数
            
        Returns:
            str: API返回的文本
        """
        try:
            # 构建消息格式
            messages = [
                {"role": "system", "content": "你是一个专业的应用分类助手，严格按照JSON格式返回结果。"},
                {"role": "user", "content": prompt}
            ]
            
            # 使用非流式调用获取结果
            # enable_thinking=False: 不需要思考过程，直接返回结果
            # enable_search=True: 启用网络搜索能力
            result = self.client.sent_message_no_stream(
                messages=messages,
                model=self.model,
                enable_thinking=False,  # 分类任务不需要思考过程
                enable_search=True      # 启用网络搜索
            )
            
            if result and 'content' in result:
                # 打印API调用统计（可选）
                print(f"  ├─ 本次tokens: {result.get('total_tokens', 0):,}")
                return result['content']
            else:
                raise Exception("API调用失败，未返回有效结果")
                
        except Exception as e:
            raise Exception(f"通义千问API调用失败: {e}")
