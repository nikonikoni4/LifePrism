"""
Ollama本地LLM分类器实现

Ollama本地模型没有网络搜索能力，因此需要两步流程：
1. 判断是否需要网络搜索
2. 使用本地爬虫搜索
3. 最终分类
"""

import json
from typing import List, Dict
from lifewatch.llm.base_classifier import BaseLLMClassifier, generate_llm_batches, extract_json, merge_classification_results
from lifewatch.llm.ollama_client import OllamaClient
import pandas as pd


class OllamaClassifier(BaseLLMClassifier):
    """
    基于Ollama本地模型的分类器实现
    
    特点：
    - 支持两步流程（判断 → 本地搜索 → 分类）
    - 支持一步流程（直接分类）
    """
    
    def __init__(self, client: OllamaClient, categoryA: str, categoryB: str):
        """
        初始化Ollama分类器
        
        Args:
            client (OllamaClient): Ollama客户端实例
            categoryA (str): 大类分类选项
            categoryB (str): 具体目的分类选项
        """
        super().__init__(categoryA, categoryB)
        self.client = client
    
    def classify(self, df: pd.DataFrame, enable_web_search: bool = True, 
                crawler_select: str = "BaiDuBrowerCrawler",
                max_chars: int = 2000, max_items: int = 15) -> pd.DataFrame:
        """
        分类方法
        
        Args:
            df (pd.DataFrame): 待分类的数据表
            enable_web_search (bool): 是否启用网络搜索（两步流程）
            crawler_select (str): 爬虫选择器
            max_chars (int): 每批次最大字符数
            max_items (int): 每批次最大条数
            
        Returns:
            pd.DataFrame: 包含分类结果的完整数据表
        """
        if enable_web_search:
            return self._classify_with_web_search(df, crawler_select, max_chars, max_items)
        else:
            return self._classify_simple(df, max_chars, max_items)
    
    def _classify_with_web_search(self, df: pd.DataFrame, crawler_select: str,
                                  max_chars: int, max_items: int) -> pd.DataFrame:
        """
        两步分类流程：第一步判断 -> 网络搜索 -> 第二步分类
        
        Args:
            df (pd.DataFrame): 待分类的数据表
            crawler_select (str): 爬虫选择器
            max_chars (int): 每批次最大字符数
            max_items (int): 每批次最大条数
            
        Returns:
            pd.DataFrame: 包含分类结果的完整数据表
        """
        from lifewatch.crawler.app_description_fetching import AppDescriptionFetcher
        
        print(f"=" * 60)
        print(f"开始Ollama两步分类流程 - 总数据量: {len(df)}")
        print(f"=" * 60)
        
        # 确保 DataFrame 有必要的列
        if 'class_by_default' not in df.columns:
            df['class_by_default'] = None
        if 'class_by_goals' not in df.columns:
            df['class_by_goals'] = None
        
        # ==================== 第一步：初步判断 ====================
        print("\n[第一步] 使用 LLM 进行初步判断（判断是否需要网络搜索）")
        batches = generate_llm_batches(df, max_chars=max_chars, max_items=max_items)
        print(f"生成批次总数: {len(batches)}")
        
        first_step_results = []
        for i, batch in enumerate(batches):
            print(f"\n处理第 {i+1}/{len(batches)} 批 (包含 {len(batch)} 条数据)...")
            try:
                response = self._call_llm_with_search_flag(batch)
                result_list = extract_json(response)
                first_step_results.extend(result_list)
            except Exception as e:
                print(f"第一步批次 {i+1} 处理出错: {e}")
                # 将批次中的所有条目标记为需要网络搜索
                for item in batch:
                    first_step_results.append({
                        'id': item['id'],
                        'A': None,
                        'B': None,
                        'need_web_search': True
                    })
        
        print(f"\n第一步完成，共处理 {len(first_step_results)} 条结果")
        
        # ==================== 提取需要网络搜索的应用 ====================
        need_search_items = [item for item in first_step_results if item.get('need_web_search', False)]
        print(f"\n需要网络搜索的应用数量: {len(need_search_items)}")
        
        # 如果没有需要搜索的应用，直接返回
        if len(need_search_items) == 0:
            print("\n所有应用都已完成分类，无需网络搜索")
            return merge_classification_results(df, first_step_results, [])
        
        # ==================== 第二步：网络搜索 ====================
        print("\n[第二步] 使用爬虫获取应用描述")
        
        # 提取需要搜索的应用名称
        need_search_app_names = []
        for item in need_search_items:
            idx = item['id']
            if idx in df.index:
                app_name = df.at[idx, 'app']
                need_search_app_names.append(app_name)
        
        print(f"需要搜索的应用: {need_search_app_names}")
        
        # 使用爬虫批量获取应用描述
        fetcher = AppDescriptionFetcher(crawler_select=crawler_select)
        search_results = fetcher.fetch_batch_app_descriptions(need_search_app_names)
        
        print(f"\n网络搜索完成，获取到 {len(search_results)} 条描述")
        
        # 将搜索结果合并到 DataFrame
        for item in need_search_items:
            idx = item['id']
            if idx in df.index:
                app_name = df.at[idx, 'app']
                if app_name in search_results and search_results[app_name]:
                    df.at[idx, 'app_description'] = search_results[app_name]
                    print(f"更新应用 '{app_name}' 的描述")
        
        # ==================== 第三步：最终分类 ====================
        print("\n[第三步] 对补充信息后的应用进行最终分类")
        
        # 提取需要重新分类的数据
        need_reclassify_df = df.loc[[item['id'] for item in need_search_items if item['id'] in df.index]]
        
        # 重新生成批次
        reclassify_batches = generate_llm_batches(need_reclassify_df, max_chars=max_chars, max_items=max_items)
        print(f"重新分类批次总数: {len(reclassify_batches)}")
        
        second_step_results = []
        for i, batch in enumerate(reclassify_batches):
            print(f"\n处理重分类批次 {i+1}/{len(reclassify_batches)} (包含 {len(batch)} 条数据)...")
            try:
                response = self._call_llm_classify(batch)
                result_list = extract_json(response)
                second_step_results.extend(result_list)
            except Exception as e:
                print(f"第二步批次 {i+1} 处理出错: {e}")
                # 使用默认值
                for item in batch:
                    second_step_results.append({
                        'id': item['id'],
                        'A': '其他',
                        'B': '其他'
                    })
        
        print(f"\n第三步完成，共处理 {len(second_step_results)} 条结果")
        
        # ==================== 合并结果 ====================
        print("\n[合并结果] 整合两步分类结果")
        final_df = merge_classification_results(df, first_step_results, second_step_results)
        
        print(f"=" * 60)
        print(f"分类流程完成！")
        print(f"=" * 60)
        
        return final_df
    
    def _classify_simple(self, df: pd.DataFrame, max_chars: int, max_items: int) -> pd.DataFrame:
        """
        简单分类流程：直接分类，不进行网络搜索
        
        Args:
            df (pd.DataFrame): 待分类的数据表
            max_chars (int): 每批次最大字符数
            max_items (int): 每批次最大条数
            
        Returns:
            pd.DataFrame: 包含分类结果的完整数据表
        """
        print(f"=" * 60)
        print(f"开始Ollama简单分类流程 - 总数据量: {len(df)}")
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
                response = self._call_llm_classify(batch)
                result_list = extract_json(response)
                
                # 回填数据到 DataFrame
                for res in result_list:
                    idx = res['id']
                    if idx in df.index:
                        df.at[idx, 'class_by_default'] = res.get('A', '其他')
                        df.at[idx, 'class_by_goals'] = res.get('B', '其他')
                        
            except Exception as e:
                print(f"批次 {i+1} 处理出错: {e}")
        
        print(f"\n=" * 60)
        print(f"分类流程完成！")
        print(f"=" * 60)
        
        return df
    
    def _call_llm_with_search_flag(self, batch_data: List[Dict]) -> str:
        """
        第一步：使用Ollama判断是否需要网络搜索
        
        Args:
            batch_data (list): 批次数据
            
        Returns:
            str: LLM返回的JSON字符串
        """
        # 优化 JSON 格式：将列表转换为更紧凑的格式
        compact_data = [
            [item["id"], item["app_name"], item.get("app_description"), 
             item["title"], item["is_multipurpose"]] 
            for item in batch_data
        ]
        
        prompt = f"""
        你是用户行为分析专家，需判断应用分类及是否需网络搜索补充信息。
        # 分类选项
        A (大类): {self.categoryA}
        B (具体目的): {self.categoryB}
        # 判断流程（重要）
        1. **先判断信息充分性**：
        - 若 app_name 是常见应用（Chrome/WeChat/Excel/PyCharm等）或 app_description 清晰 → 信息充分
        - 若 app_name 不认识,app_title用途不明确且app_description 为空/简略 → 信息不足
        - 若 app_name 不认识, 且app_description 为空/简略 但app_title用途明确 → 信息充分
        2. **根据信息充分性决定输出**：
        - 信息充分：need_web_search=false，正常分类 A 和 B
        - 信息不足：need_web_search=true，A 和 B 都设为 null
        # 分类规则（仅当信息充分时应用）
        - A 是背景，B 是行为，需逻辑自洽
        - 多用途应用(is_multipurpose=true)需依据 title 判断
        - 单用途应用(is_multipurpose=false)主要依据 app_name
        # 数据格式
        每行: [id, app_name, app_description, title, is_multipurpose]
        {json.dumps(compact_data, ensure_ascii=False)}
        # 输出格式（仅返回JSON数组，格式示例如下，请根据实际数据判断）
        [
        {{"id": <数字>, "A": "<分类值或null>", "B": "<分类值或null>", "need_web_search": <true或false>}},
        ...
        ]
        """
        
        options = {
            "temperature": 0.1,
            "repeat_penalty": 1.3
        }
        
        response = self.client.generate(prompt, options=options, return_raw=True)
        print("=*10 回答 =*10")
        print(response["response"])
        print("=*10 思考部分 =*10")
        print(response["thinking"])
        
        return response["response"]
    
    def _call_llm_classify(self, batch_data: List[Dict]) -> str:
        """
        第二步：使用Ollama进行最终分类
        
        Args:
            batch_data (list): 批次数据
            
        Returns:
            str: LLM返回的JSON字符串
        """
        # 优化 JSON 格式
        compact_data = [
            [item["id"], item["app_name"], item.get("app_description"), 
             item["title"], item["is_multipurpose"]] 
            for item in batch_data
        ]
        
        prompt = f"""
                你是用户行为分析专家，根据窗口活动推断用户意图。
                # 分类选项
                A (大类): {self.categoryA}
                B (具体目的): {self.categoryB}
                # 分类规则
                - A 是背景，B 是行为，需逻辑自洽
                - 多用途应用(is_multipurpose=true)需依据 title 判断
                - 单用途应用(is_multipurpose=false)主要依据 app_name
                - 无法确定时选择 "其他"
                # 数据格式
                每行: [id, app_name, app_description, title, is_multipurpose]
                {json.dumps(compact_data, ensure_ascii=False)}
                # 输出格式（仅返回JSON数组，格式示例如下，请根据实际数据分类）
                [
                {{"id": <数字>, "A": "<从A分类选项中选择>", "B": "<从B分类选项中选择>"}},
                ...
                ]
                """
        options = {
            "temperature": 0.1,
            "repeat_penalty": 1.3
        }
        
        response = self.client.generate(prompt, options=options, return_raw=True)
        print("=*10 回答 =*10")
        print(response["response"])
        print("=*10 思考部分 =*10")
        print(response["thinking"])
        
        return response["response"]
