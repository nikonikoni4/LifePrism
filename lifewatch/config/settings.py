
"""
=========================ActivityWatch配置模块==========================
"""
# ActivityWatch配置
# 本地时区（自动获取系统时区）
try:
    from tzlocal import get_localzone
    LOCAL_TIMEZONE = str(get_localzone())
except ImportError:
    # 如果没有安装 tzlocal，使用默认值
    LOCAL_TIMEZONE = 'Asia/Shanghai'  
# 桌面应用数据桶
WINDOW_BUCKET_ID = 'aw-watcher-window_'

# 本地模型
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:0.6b"
