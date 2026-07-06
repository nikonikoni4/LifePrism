"""全局配置 - 修改此处即可更新所有脚本"""

# 服务配置
BASE_URL = "http://localhost:5173"
PORT = 5173

# 浏览器配置
VIEWPORT = {"width": 1920, "height": 1080}
HEADLESS = True

# 等待配置
WAIT_TIMEOUT = 5000  # 毫秒
NETWORK_IDLE = True

# 截图配置
SCREENSHOT_DIR = "scripts/webapp-test/截图"
FULL_PAGE = True

# 页面路由（相对路径）
ROUTES = {
    "home": "/",
    "settings": "/settings",
    "profile": "/profile",
    "chat": "/chat",
}
