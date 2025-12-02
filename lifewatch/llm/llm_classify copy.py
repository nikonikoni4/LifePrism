import pandas as pd
import json
from lifewatch.llm.ollama_client import OllamaClient
from lifewatch import config

def generate_llm_batches(df, max_chars=2000, max_items=15):
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
    # 这是一个安全余量，根据你的实际 Prompt 长度调整
    base_prompt_overhead = 500 

    for index, row in df.iterrows():
        # 1. 构造单条数据对象
        # 关键：一定要把 index 放入，作为后续回填数据的唯一 Key
        item = {
            "id": index, 
            "app_name": row['app'],
            "app_description": row['app_description'],
            "title": row['title'],
            "is_multipurpose": row['is_multipurpose_app']
        }
        
        # 2. 计算当前 Item 的字符长度 (转为 JSON 字符串计算)
        item_json_str = json.dumps(item, ensure_ascii=False)
        item_len = len(item_json_str)
        
        # 3. 检查是否触发限制 (双重阈值检查)
        # 条件 A: 条数达到上限
        # 条件 B: (当前累计字符 + 新增字符 + 预留 System Prompt) 超过上限
        if (len(current_batch) >= max_items) or \
           (current_chars + item_len + base_prompt_overhead > max_chars):
            
            # 这里的 batch 就是准备发送给 LLM 的一次请求的数据体
            batches.append(current_batch)
            
            # 重置计数器
            current_batch = []
            current_chars = 0
        
        # 4. 添加当前条目
        current_batch.append(item)
        current_chars += item_len
    
    # 5. 处理最后一个未满的批次
    if current_batch:
        batches.append(current_batch)
        
    return batches

def process_and_fill_dataframe(df, mock_llm_func=None):
    """
    主流程控制函数：生成批次 -> 模拟请求 -> 解析结果 -> 回填 DataFrame
    """
    print(f"原始数据总数: {len(df)}")
    
    # 1. 生成批次
    # 这里设置较为严格的限制用于演示
    batches = generate_llm_batches(df, max_chars=config.MAX_CHARS, max_items=config.MAX_ITEMS)
    print(f"生成批次总数: {len(batches)}")
    
    # 2. 遍历批次进行请求
    for i, batch in enumerate(batches):
        print(f"正在处理第 {i+1}/{len(batches)} 批 (包含 {len(batch)} 条数据)...")
        
        try:
            # === 这里调用实际的 LLM API ===
            response = mock_llm_func(batch)
            result_list = extract_json(response)
            
            # 3. 回填数据到 DataFrame
            # 根据返回结果中的 'id' 找到对应的行
            for res in result_list:
                idx = res['id']
                
                # 安全检查：确保索引存在
                if idx in df.index:
                    df.at[idx, 'category'] = res.get('A', 'Error')
                    df.at[idx, 'sub_category'] = res.get('B', 'Error')
                    
        except Exception as e:
            print(f"Error in batch {i+1}: {e}")
            # 实际工程中这里建议做重试机制或者记录失败的 batch_id
            
    return df


def call_ollama_llm_api(batch_data, client: OllamaClient, category: str, sub_category: str):
    """
    调用 LLM API 进行分类
    
    Args:
        batch_data (list): 包含多个数据项的列表，每个项是一个字典
        client (OllamaClient): Ollama 客户端实例
        category (str): 大类分类选项
        sub_category (str): 具体目的分类选项
        
    Returns:
        str: LLM API 返回的原始字符串响应
    """
    # 优化 JSON 格式：将列表转换为更紧凑的格式
    compact_data = [[item["id"], item["app_name"], item.get("app_description"), item["title"], item["is_multipurpose"]] for item in batch_data]
    
    prompt = f"""
你是用户行为分析专家，根据窗口活动推断用户意图。
# 分类选项
A (大类): {category}
B (具体目的): {sub_category}
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
    
    response = client.generate(prompt, options=options, return_raw=True)
    print("=*10 回答 =*10")
    print(response["response"])
    print("=*10 思考部分 =*10")
    print(response["thinking"])
    return response["response"]


def call_ollama_llm_api_with_search_flag(batch_data, client: OllamaClient, category: str, sub_category: str):
    """
    调用 LLM API 进行分类，并判断是否需要网络搜索
    
    Args:
        batch_data (list): 包含多个数据项的列表，每个项是一个字典
        client (OllamaClient): Ollama 客户端实例
        category (str): 大类分类选项
        sub_category (str): 具体目的分类选项
        
    Returns:
        str: LLM API 返回的原始字符串响应，包含 need_web_search 字段
    """
    # 优化 JSON 格式：将列表转换为更紧凑的格式
    compact_data = [[item["id"], item["app_name"], item.get("app_description"), item["title"], item["is_multipurpose"]] for item in batch_data]
    
    prompt = f"""
你是用户行为分析专家，需判断应用分类及是否需网络搜索补充信息。
# 分类选项
A (大类): {category}
B (具体目的): {sub_category}
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
    
    # 限制生成的最大 token 数，避免思考部分过长
    options = {
        "temperature": 0.1,      # 低温度，更确定性
        "repeat_penalty": 1.3    # 防止重复循环
    }
    
    response = client.generate(prompt, options=options, return_raw=True)
    print("=*10 回答 =*10")
    print(response["response"])
    print("=*10 思考部分 =*10")
    print(response["thinking"])
    return response["response"]


def extract_json(response_str: str):
    """
    从 LLM 响应字符串中提取 JSON 列表
    Args:
        response_str (str): LLM 原始响应字符串
    Returns:
        list: 解析后的 JSON 列表
    """
    try:
        # 尝试直接解析 JSON 字符串
        json_list = json.loads(response_str)
        if isinstance(json_list, list):
            return json_list
        else:
            print("警告：解析后的 JSON 不是列表格式")
            return []
    except json.JSONDecodeError:
        print("错误：无法解析 JSON 字符串")
        return []


def merge_classification_results(df, first_step_results, second_step_results):
    """
    合并第一步和第二步的分类结果
    
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
        
        # 检查索引是否存在
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


def classify_with_web_search(df, client: OllamaClient, category: str, sub_category: str, 
                             crawler_select="BaiDuBrowerCrawler", max_chars=2000, max_items=15):
    """
    完整的两步分类流程：第一步判断 -> 网络搜索 -> 第二步分类
    
    Args:
        df (pd.DataFrame): 待分类的数据表，需包含 ['app', 'title', 'is_multipurpose_app', 'app_description'] 列
        client (OllamaClient): Ollama 客户端实例
        category (str): 大类分类选项
        sub_category (str): 具体目的分类选项
        crawler_select (str): 爬虫选择器，默认 "BaiDuBrowerCrawler"
        max_chars (int): 每批次最大字符数
        max_items (int): 每批次最大条数
        
    Returns:
        pd.DataFrame: 包含分类结果的完整数据表（添加 'category' 和 'sub_category' 列）
    """
    from lifewatch.crawler.app_description_fetching import AppDescriptionFetcher
    
    print(f"=" * 60)
    print(f"开始完整分类流程 - 总数据量: {len(df)}")
    print(f"=" * 60)
    
    # 确保 DataFrame 有必要的列
    if 'category' not in df.columns:
        df['category'] = None
    if 'sub_category' not in df.columns:
        df['sub_category'] = None
    
    # ==================== 第一步：初步判断 ====================
    print("\n[第一步] 使用 LLM 进行初步判断（判断是否需要网络搜索）")
    batches = generate_llm_batches(df, max_chars=max_chars, max_items=max_items)
    print(f"生成批次总数: {len(batches)}")
    
    first_step_results = []
    for i, batch in enumerate(batches):
        print(f"\n处理第 {i+1}/{len(batches)} 批 (包含 {len(batch)} 条数据)...")
        try:
            response = call_ollama_llm_api_with_search_flag(batch, client, category, sub_category)
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
            response = call_ollama_llm_api(batch, client, category, sub_category)
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


if __name__ == "__main__":
    client = OllamaClient(config.OLLAMA_BASE_URL, "qwen3:8B")
    category = "工作/学习,娱乐,其他"
    sub_category = "写笔记,编程,学习AI相关内容,其他"
    batch_data = [
        {
            "id": 1,
            "app_name": "Antigravity",
            "title": "LifeWatch-AI - Antigravity -llm_classify.py",
            "is_multipurpose": False,
            "app_description": None
        },
        {
            "id": 2,
            "app_name": "Doubao",
            "title": None,
            "is_multipurpose": False,
            "app_description": None
        },
        {
            "id": 3,
            "app_name": "AFFiNE",
            "title": "AFFiNE",
            "is_multipurpose": False,
            "app_description": None
        }
    ]
    call_ollama_llm_api_with_search_flag(batch_data, client, category, sub_category)