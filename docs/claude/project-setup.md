# 项目环境与配置

## 开发命令

### 前端（React + Vite + Electron）

```bash
cd frontend
npm install              # 安装依赖
npm run dev              # 开发服务器 (localhost:3000, /api 代理到 localhost:8000)
npm run build            # 生产构建
npm run electron:dev     # Electron 开发模式
npm run electron:build   # Electron Windows 打包
```

### 后端（Python + FastAPI）

```bash
pip install -e .                          # 安装开发模式
cd lifeprism/server && python main.py     # 启动开发服务器
# 或
LIFEWATCH_DEV=1 python -m lifeprism.server.main
```

### 同时运行

1. Terminal 1: `cd frontend && npm run dev`
2. Terminal 2: `python -m lifeprism.server.main`

**前端**：http://localhost:3000 | **后端**：http://localhost:8000 | **API 文档**：http://localhost:8000/docs

## 后端配置

**配置文件**：`lifeprism/config/settings.yaml`

```yaml
# LLM Provider
provider: "阿里云百炼 (Aliyun)"
model: qwen-plus-2025-12-01
input_tokens_cost: 0.0008
output_tokens_cost: 0.002

# 分类设置
classification_mode: classify_graph  # 或 classify_simple
long_log_threshold: 300
multi_purpose_app_names: [chrome, msedge, firefox]

# 数据路径
lifeprism_data_path: ''  # 空=使用默认路径
aw_db_path: ~/AppData/Local/activitywatch/activitywatch/aw-server/peewee-sqlite.v2.db
# lw_db_path/chat_db_path 已移除，自动从 lifeprism_data_path 推算

# 数据清洗
data_cleaning_threshold: 10
```

## 前端配置

- **Vite Config**：`frontend/vite.config.ts`
- Dev server: `localhost:3000`，API proxy: `/api` → `http://localhost:8000`
- 环境变量：`GEMINI_API_KEY`（可选）

## 常见问题排查

| 问题 | 解决方案 |
|------|---------|
| 前端连不上后端 | 确认后端在 8000 端口运行，检查 `main.py` CORS 设置 |
| LLM 分类不工作 | 检查 `settings.yaml` 中的 API key、provider、model |
| 数据库锁定错误 | 关闭所有数据库连接，检查是否有多个服务器实例 |
| 缓存匹配异常 | 清空 `category_map_cache` 表重新分类，检查 `multi_purpose_app_names` |

## 测试

测试目录：`lifeprism/llm/llm_classify/tests/`

```bash
cd lifeprism && pytest llm/llm_classify/tests/
```
