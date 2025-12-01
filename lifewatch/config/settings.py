

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
# 分类类别
CATEGORY_A = "工作/学习,生活/娱乐,其他"
CATEGORY_B = "编写LifeWatch-AI项目(代码),其他"
# 2.被选择需要使用title信息来判断用途的应用（可配置）
MULTIPURPOSE_APP = [
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", 
    "opera.exe", "safari.exe", "vivaldi.exe", "duckduckgo.exe",
    "tor.exe", "iexplore.exe","explorer.exe"
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
