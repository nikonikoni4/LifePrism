"""
基于DuckDuckGo_search库的应用程序描述爬虫函数
用于获取应用程序的描述信息，支持多个搜索引擎
"""

from typing import Optional, List, Dict
import re
from ddgs import DDGS
from lifewatch.llm import OllamaClient
from lifewatch import config
from lifewatch.crawler.app_description_processor import AppDescriptionProcessor

def web_resultes_clean(text: str) -> str:
        """
        清洗搜索摘要，移除导航干扰、元数据，保留核心语义。
        """
        if not text:
            return ""

        # --- 1. 预处理：先移除特定的干扰短语 (合并正则以提高效率) ---
        
        # 移除"来源"、"描述"标签
        text = re.sub(r'(-?\s*来源\s*-?\s*)|(-?\s*描述\s*-?\s*)', ' ', text, flags=re.IGNORECASE)

        # 移除 URL 和 域名
        text = re.sub(r'[a-zA-Z0-9-]+\.(com|cn|net|org|gov)', ' ', text)

        # 移除 日期
        text = re.sub(r'\d{4}-\d{2}-\d{2}', ' ', text)

        # --- 2. 移除无关的"跳转/下载"引导词 ---
        # 使用 | 连接所有模式，只扫描一次
        jump_patterns = r'|'.join([
            r'点击?\s*跳转', r'跳转\s*到', r'访问\s*链接', r'点击\s*查看',
            r'更多\s*信息', r'详细信息', r'查看\s*详情', r'Download',
            r'下载\s*链接', r'官网\s*地址', r'主页\s*链接'
        ])
        text = re.sub(jump_patterns, ' ', text, flags=re.IGNORECASE)
        # --- 3. 移除通用平台来源 (修正：去掉了具体的App名称) ---
        # 只保留真正的"平台噪音"，保留 doubao 等具体 App 名
        platform_patterns = r'|'.join([
            r'\b微软应用商店\b', r'\bMicrosoft\s*Store\b',
            r'\bWindows官方下载\b', r'\bMicrosoft\s*Edge\s*Add-ons?\b',
            r'\b维基百科\b', r'\bWikipedia\b', r'\b百科全书\b',
            r'\b自由的百科全书\b'
        ])
        text = re.sub(platform_patterns, ' ', text, flags=re.IGNORECASE)
        # --- 4. 移除引用标记和特殊符号 ---
        # 移除 [1], [2] 或 3.0 3.1 这种引用序号
        text = re.sub(r'\[\d+\]', ' ', text)
        # 移除孤立的数字 (如列表序号 1. 2.)
        text = re.sub(r'\s\d+(\.\d+)?\s', ' ', text)
        # 移除连续特殊字符
        text = re.sub(r'[-_=*#@\.]{2,}', ' ', text)
        # --- 5. 最后一步：压缩空白 ---
        # 这一步最后做，确保前面的正则不受影响，同时把所有删除留下的坑填平
        text = re.sub(r'\s+', ' ', text).strip()
        return text


class DDGSAPICrawler:
    """DuckDuckGo搜索爬虫类"""
    
    def __init__(self, max_results: int = 20, region: str = "cn-zh", 
                 llm_client: OllamaClient = None, llm_base_url: str = None, 
                 llm_model: str = "qwen3:0.6B"):
        """
        初始化爬虫
        
        Args:
            max_results: 最大搜索结果数量
            region: 搜索区域
            llm_client: 已有的OllamaClient实例，如果提供则直接使用
            llm_base_url: LLM服务地址，默认使用config中的配置（仅在llm_client为None时使用）
            llm_model: LLM模型名称（仅在llm_client为None时使用）
        """
        self.max_results = max_results
        self.ddgs = DDGS()
        self.region = region
        
        # 初始化LLM客户端和描述处理器
        if llm_client is not None:
            # 使用传入的客户端实例
            self.llm_client = llm_client
        else:
            # 创建新的客户端实例
            base_url = llm_base_url or config.OLLAMA_BASE_URL
            self.llm_client = OllamaClient(base_url, llm_model)
        
        self.description_processor = AppDescriptionProcessor(self.llm_client)

    def _search_single_query(self, query: str) -> Optional[List[Dict]]:
        """
        执行单个搜索查询
        
        Args:
            query: 搜索查询
            
        Returns:
            List[Dict]: 搜索结果列表，失败返回None
        """
        try:
            # 构造站点特定查询
            site_query = f"{query}"
            
            # 在指定网站上执行搜索
            results = self.ddgs.text(
                site_query,
                max_results=self.max_results,
                region=self.region,
            )
            for result in results:
                result['title'] = web_resultes_clean(result['title'])
                result['body'] = web_resultes_clean(result['body'])
            return results 
        except Exception as e:
            print(f"⚠️ _search_single_query 搜索失败: {query} - {str(e)}")
            return None
    
    def fetch_app_description(self, query: str, max_descriptions: int = 3) -> str:
        """
        从DuckDuckGo搜索中获取应用程序描述
        流程：1.搜索 2.判断是否为应用描述 3.应用描述组合在一起 4.缩写
        
        Args:
            query: 搜索查询（应用名称）
            max_descriptions: 最大应用程序描述数量
            
        Returns:
            str: 应用程序的定性描述
        """
        results = self._search_single_query(query)
        if not results:
            return ""
        
        descriptions = []
        count = 0
        
        for item in results:
            print(f"搜索到的结果: {item['body'][:100]}...")
            # 只取前300个字符进行判断，提高效率
            if self.description_processor.is_app_description(query, item["body"][:300]):
                print(f"✓ 符合应用描述")
                descriptions.append(item["body"])
                count += 1
                if count >= max_descriptions:
                    break
            else:
                print(f"✗ 不符合应用描述")
        
        if not descriptions:
            return ""
        
        # 合并所有描述并生成缩写
        combined_descriptions = " ".join(descriptions)
        final_description = self.description_processor.get_app_description_abbr(
            query, combined_descriptions
        )
        print(f"\n最终描述: {final_description}")
        return final_description


if __name__ == "__main__":
    # 测试1: 使用默认配置（自动创建LLM客户端）
    print("=" * 50)
    print("测试1: 使用默认配置")
    print("=" * 50)
    crawler1 = DDGSAPICrawler(max_results=5, region="cn")
    description1 = crawler1.fetch_app_description("trae", max_descriptions=2)
    print(f"\n最终结果: {description1}\n")
    
    # 测试2: 传入已有的LLM客户端实例
    print("=" * 50)
    print("测试2: 使用传入的LLM客户端")
    print("=" * 50)
    custom_client = OllamaClient(config.OLLAMA_BASE_URL, "qwen3:8b")
    crawler2 = DDGSAPICrawler(max_results=5, region="cn", llm_client=custom_client)
    description2 = crawler2.fetch_app_description("vscode", max_descriptions=2)
    print(f"\n最终结果: {description2}")