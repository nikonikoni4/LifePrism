

"""
=========================API KEY==========================
"""
SELECT_MODEL = "qwen-flash"
MODEL_KEY = {
    "qwen-flash": {"api_key":"sk-b6f3052f6c4f46a9a658bfc020d90c3f","base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1"},
}



"""
=========================应用分类配置模块==========================
"""

def get_category_a():
    """
    获取默认分类列表（CATEGORY_A）
    
    TODO: 未来从数据库 category 表获取
    Returns:
        list: 分类名称列表
    """
    # 暂时返回静态列表，后续改为从数据库获取
    categories = ["工作/学习", "生活/娱乐", "其他"]
    return ",".join(categories)


def get_category_b():
    """
    获取目标分类列表（CATEGORY_B）
    
    TODO: 未来从数据库 sub_category 表获取
    Returns:
        list: 子分类名称列表
    """
    # 暂时返回静态列表，后续改为从数据库获取
    sub_categories = ["编写LifeWatch-AI项目(代码)", "其他"]
    return ",".join(sub_categories)


# 分类类别（保留变量名用于向后兼容）
CATEGORY_A = get_category_a()
CATEGORY_B = get_category_b()

# 2.被选择需要使用title信息来判断用途的应用（可配置）
MULTIPURPOSE_APP = [
    "chrome", "msedge", "firefox", "brave", 
    "opera", "safari", "vivaldi", "duckduckgo",
    "tor", "iexplore","explorer"
]

"""
=========================ActivityWatch配置模块==========================
"""
# ActivityWatch配置
AW_URL_CONFIG = {
    "base_url": "http://localhost:5600",
    "headers": {
        'Content-Type': 'application/json',
        'User-Agent': 'LifeWatch-AI Data Collector'
    }
}
# 本地时区
LOCAL_TIMEZONE = 'Asia/Shanghai'  
# 桌面应用数据桶
WINDOW_BUCKET_ID = 'aw-watcher-window_'


"""
=========================LLM配置模块==========================
"""

# 本地模型
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:0.6b"
# LLM配置
MAX_CHARS = 2000 # 请求时的最大tokens
MAX_ITEMS = 10 # 请求时的最大items

"""
数据清洗配置模块
"""
# 数据清洗配置
CLEAN_LOWER_BOUND = 60 # 数据清洗配置
