from lifewatch.llm import OllamaClient
from lifewatch.crawler.api_crawler import DDGSAPICrawler
from lifewatch import config
def is_app_description(client,app_name,text):
    """
    判断文本是否为指定应用程序的描述
    
    Args:
        app_name (str): 应用程序名称
        text (str): 输入文本
        
    Returns:
        bool: 如果是该应用程序描述则返回True，否则返回False
    """
    prompt = f"""
        请判断以下文本是否包含对{app_name}的用途定性描述（功能、用途、类型说明）。
    重要规则：
    1. 如果文本明确说明了{app_name}是什么类型的应用（如：浏览器、编辑器、播放器、管理器、游戏等），提取用途定性描述
    2. 如果文本只是描述{app_name}的新闻、发布信息、市场动态，不提取定性描述
    3. 如果文本包含"发布"、"宣布"、"财报"、"促销"等新闻词汇，不提取定性描述
    4. 如果文本与{app_name}无关，不提取定性描述
    处理要求：
    - 如果包含定性描述，返回格式：是
    - 如果不包含定性描述，返回：否
    - 定性描述要简洁准确，说明应用的核心类型和功能
    待处理文本：{text}
    
    请严格按规则判断，仅回答"是"或"否"。
    """
    response = client.generate(prompt)
    if response and "response" in response:
        return "是" in response["response"].strip()
    return False


def is_app_description_and_return_Info(client:OllamaClient,app_name,text):
    """
    判断文本是否包含对指定应用程序的定性描述，若是则返回定性描述的缩写
    
    Args:
        app_name (str): 应用程序名称
        text (str): 输入文本
        
    Returns:
        str: 如果包含定性描述则返回"应用名称是[用途定性描述]"，否则返回空字符串
    """
    prompt = f"""
    请判断以下文本是否包含对{app_name}的用途定性描述（功能、用途、类型说明）。
    重要规则：
    1. 如果文本明确说明了{app_name}是什么类型的应用（如：浏览器、编辑器、播放器、管理器、游戏等），提取用途定性描述
    2. 如果文本只是描述{app_name}的新闻、发布信息、市场动态，不提取定性描述
    3. 如果文本包含"发布"、"宣布"、"财报"、"促销"等新闻词汇，不提取定性描述
    4. 如果文本与{app_name}无关，不提取定性描述
    处理要求：
    - 如果包含定性描述，返回格式：{app_name}是[用途定性描述]
    - 如果不包含定性描述，返回：无
    - 定性描述要简洁准确，说明应用的核心类型和功能
    待处理文本：{text}
    
    请严格按规则处理，仅返回指定格式的定性描述或"无"。
    """
    response = client.generate(prompt)
    print(response)
    if response and "response" in response:
        result = response["response"].strip()
        if result != "无" and result:
            return result
    return ""
def get_app_description_abbr(client:OllamaClient,app_name,text):
    """
    获取应用程序的定性描述
    
    Args:
        app_name (str): 应用程序名称
        text (str): 应用程序描述文本
        
    Returns:
        str: 应用程序的定性描述
    """
    prompt = f"""
    请从以下文本中提取关于{app_name}应用的定性描述，格式为：{app_name}是[用途定性描述]
    注意：
    可能包含非{app_name}应用的描述，只提取关于{app_name}的描述。
    要求：
    1. 提取最核心的定性描述（功能、用途、类型说明），说明这是什么类型的应用
    2. 格式统一为：{app_name}是[用途定性描述]
    待处理文本：{text}
    请仅返回定性描述，不要包含其他内容。
    示例输出：{app_name}是社交应用程式。
    """
    response = client.generate(prompt)
    if response and "response" in response:
        return response["response"].strip()
    return ""
def fetch_app_descriptions(query:str,max_results:int = 20,max_descriptions:int = 3):
    """
    从DuckDuckGo搜索中获取应用程序描述
    流程：1.搜索 2.判断是否为应用描述 3.应用描述组合在一起 4.缩写
    Args:
        query (str): 搜索查询
        max_results (int): 最大搜索结果数量
        
    Returns:
        list: 包含应用程序描述的列表
    """
    client = OllamaClient(config.OLLAMA_BASE_URL,"qwen3:8b")
    crawler = DDGSAPICrawler(max_results=max_results,llm_client=client)
    results = crawler._search_single_query(query)
    if not results:
        return []
    descriptions = []
    count = 0
    for item in results:
        print(f"搜索到的结果: {item['body']}")
        if is_app_description(client,query,item["body"][:300]): # config.MAX_WEB_SEARCH_RESULTS
            print(True)
            descriptions.append(item["body"])
            count += 1
            if count >= max_descriptions:
                break
        else:
            print(False)
    descriptions = " ".join(descriptions)
    descriptions = get_app_description_abbr(client,query,descriptions)
    print(descriptions)
    return descriptions
# def fetch_app_descriptions(query:str,max_results:int = 20,max_descriptions:int = 1):
#     """
#     从DuckDuckGo搜索中获取应用程序描述
#     这个版本是：1、搜索 2.判断的同时进行缩写 3.max_descriptions条符合条件的描述缩写
#     缺点：若max_descriptions过大，最终生成的描述也会过大
#     优点：只是少了一次请求
#     Args:
#         query (str): 搜索查询
#         max_results (int): 最大搜索结果数量
        
#     Returns:
#         str: 应用程序的定性描述

#     """
#     client = OllamaClient(config.OLLAMA_BASE_URL)
#     crawler = DDGSAPICrawler(max_results=max_results)
#     results = crawler._search_single_query(query)
#     if not results:
#         return []
#     descriptions = []
#     count = 0
#     for item in results:
#         print(f"搜索到的结果: {item['body']}")
#         if is_app_description_and_return_Info(client,query,item["body"]):
#             print(True)
#             descriptions.append(item["body"])
#             count += 1
#             if count >= max_descriptions:
#                 break
#         else:
#             print(False)
#     descriptions = " ".join(descriptions)
#     print(descriptions)
#     return descriptions
def test_get_app_description_abbr():
    client = OllamaClient(config.OLLAMA_BASE_URL)
    text = "抖音（Douyin）是智能手机短视频社交應用程式，直播电商团购平台，由中國大陸字节跳动公司所創辦，主要面向中国大陆 、香港和澳门地区營運。抖音用户可錄製15秒至1分钟、3分鐘或者更长10分鐘內的視頻，也能上传视频、照片等。到達一定 粉絲可以開啟直播，收取觀眾的打賞，平台會抽走一定的打賞。抖音自2016年9月20日由字节跳动孵化上線，定位為適合中國大陸年輕人的音樂短视频社區，應用為垂直音樂的UGC短視頻，2017年以來獲得用户規模快速增長。2020年3月18日，抖音上 线团购功能，扩大了抖音的商业版图：餐饮业、酒店业、零售业等行业的商家可通过认证为企业号用户，创建植入直播和短 视频中的团购活动，对于用户而言，团购则意味着可以通过更低的价格购买商品和服务。 抖音让每一个人看见并连接更大的世界，鼓励表达、沟通和记录，激发创造，丰富人们的精神世界，让现实生活更美好。 2 天之前 · 抖音综合搜索帮你找到 更多相关视频、图文、直播内容，支持在线观看。 更有海量高清视频、相关直播、用户，满足您的在线观看需求。Trae AI IDE | 国内首款AI原生集成开发环境，深度集成Doubao-1.5-pro与DeepSeek模型，支持中文自然语言一键生成完整代码框架，实时 。"
    abbr = get_app_description_abbr(client,text)
    print(abbr)

# def fetch_batch_app_descriptions(query_set:set,max_results:int = 20,max_descriptions:int = 2):
#     """
#     批量获取应用程序描述
    
#     Args:
#         query_set (set): 包含搜索查询的集合
#         max_results (int): 最大搜索结果数量
#         max_descriptions (int): 每个查询最大应用程序描述数量
        
#     Returns:
#         dict: 包含查询和应用程序描述的字典
#     """
#     results = {}
#     for query in query_set: 
#         results[query] = fetch_app_descriptions(query,max_results,max_descriptions)
#     return results

def fetch_batch_app_descriptions(query_set:set,max_results:int = 20,max_descriptions:int = 2):
    """
    批量获取应用程序描述
    
    Args:
        query_set (set): 包含搜索查询的集合
        max_results (int): 最大搜索结果数量
        max_descriptions (int): 每个查询最大应用程序描述数量
        
    Returns:
        dict: 包含查询和应用程序描述的字典
    """
    import time
    results = {}
    for query in query_set: 
        results[query] = {}
        results[query]= fetch_app_descriptions(query,max_results,max_descriptions)
        time.sleep(1)
    return results
def test():
    print(fetch_app_descriptions("trae",max_results=20,max_descriptions=2))
    # client = OllamaClient("qwen3:0.6B")
    # app_name = "trae"
    # text = "Trap Nation是一家美国音乐赞助者，因在其YouTube频道上发布电子音乐而闻名。 2025年3月10日 · Trae 国外 版使用国外的模型，对于国内用户来说，存在连接不上、等待时间长、网速较慢等问题。 "
    # s = is_app_description(client,app_name,text)
    # print(s)


if __name__ == "__main__":
    print(fetch_app_descriptions("trae",max_results=20,max_descriptions=2))
    # client = OllamaClient("qwen3:0.6B")
    # app_name = "trae"
    # text = "Trap Nation是一家美国音乐赞助者，因在其YouTube频道上发布电子音乐而闻名。 2025年3月10日 · Trae 国外 版使用国外的模型，对于国内用户来说，存在连接不上、等待时间长、网速较慢等问题。 "
    # s = is_app_description(client,app_name,text)
    # print(s)

