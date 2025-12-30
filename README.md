# LifeWatch-AI 🧠⏱️

> **AI 驱动的个人时间管理与行为分析平台**

LifeWatch-AI 是一个基于 [ActivityWatch](https://activitywatch.net/) 的智能时间管理系统，利用 AI 技术自动分类应用使用行为，并提供丰富的数据可视化和智能对话功能，帮助用户深入了解自己的时间使用习惯。

---

## 🌟 核心功能

### 📊 数据采集与同步
- **ActivityWatch 集成**：自动采集用户的应用使用数据、窗口标题等行为信息
- **数据同步**：支持从 ActivityWatch 增量/全量同步行为日志数据

### 🤖 AI 智能分类
- **LLM 分类引擎**：通过大语言模型（如通义千问）自动分析应用用途
- **层级分类**：支持 大类 → 子类 → 具体应用 的多层分类体系
- **智能推理**：根据应用名称和窗口标题智能判断用途（学习、工作、娱乐等）

### 💬 AI 聊天机器人
- **LangGraph 驱动**：基于 LangGraph 构建的智能对话系统
- **会话持久化**：通过 AsyncSqliteSaver 实现聊天历史持久化存储
- **多会话管理**：支持创建、切换、删除多个聊天会话
- **工具集成**：可调用工具查询用户行为数据，提供个性化建议

### 📈 数据可视化
- **首页仪表盘**：展示当日活动概览、Top Apps、Top Titles
- **时间线视图**：按时间顺序查看详细的应用使用记录
- **旭日图统计**：层级展示分类时间占比
- **活动趋势图**：按周/月查看使用趋势

### 🎯 目标管理
- **目标设定**：创建和管理个人目标，支持分类关联
- **待办事项**：每日任务管理，支持拖拽排序
- **目标追踪**：跟踪目标完成状态和投入时间

### 📋 分类管理
- **可视化分类编辑器**：拖拽式调整分类层级
- **数据审核**：手动审核/修正 AI 分类结果
- **颜色管理**：自动为分类分配视觉颜色

### 📉 使用量追踪
- **Token 消耗统计**：追踪 AI API 调用的 Token 使用量和成本
- **历史记录**：按日期查看详细的 API 调用记录

---

## 🏗️ 技术架构

```
LifeWatch-AI/
├── 🐍 lifewatch/                 # Python 后端核心
│   ├── server/                   # FastAPI 服务
│   │   ├── api/                  # REST API 路由
│   │   ├── services/             # 业务服务层
│   │   ├── providers/            # 数据提供者
│   │   └── schemas/              # Pydantic 数据模型
│   ├── llm/                      # LLM 集成
│   │   └── llm_classify/         # 分类与聊天模块
│   │       ├── chat/             # LangGraph 聊天机器人
│   │       ├── classify/         # 分类引擎
│   │       └── tools/            # 自定义工具
│   ├── storage/                  # 数据存储层
│   ├── crawler/                  # 数据爬取
│   └── config/                   # 配置管理
│
├── ⚛️ frontend/                  # React 前端
│   ├── page/                     # 页面模块
│   │   ├── home/                 # 首页仪表盘
│   │   ├── timeline/             # 时间线
│   │   ├── category/             # 分类管理
│   │   ├── goals/                # 目标管理
│   │   ├── usage/                # 使用量统计
│   │   ├── chatbot/              # 聊天机器人
│   │   └── settings/             # 设置页面
│   ├── components/               # 共享组件
│   └── services/                 # 前端服务
│
└── 📦 activitywatch/             # ActivityWatch 子模块
```

---

## 🛠️ 技术栈

### 后端
| 技术 | 用途 |
|------|------|
| **FastAPI** | Web API 框架 |
| **SQLite** | 本地数据存储 |
| **LangGraph** | AI 聊天机器人工作流 |
| **LangChain** | LLM 集成框架 |
| **通义千问 (Qwen)** | 大语言模型（分类 & 对话） |

### 前端
| 技术 | 用途 |
|------|------|
| **React 18** | UI 框架 |
| **TypeScript** | 类型安全 |
| **Vite** | 构建工具 |
| **ECharts** | 数据可视化图表 |
| **TailwindCSS** | 样式框架 |
| **dnd-kit** | 拖拽排序 |

---

## 🚀 快速开始

### 环境要求
- Python ≥ 3.8
- Node.js ≥ 18
- ActivityWatch（需预先安装并运行）

### 后端启动

```bash
# 1. 安装依赖
pip install -e .

# 2. 启动 API 服务
python -m lifewatch.server.main
```

服务将在 `http://localhost:8000` 启动，访问 `/docs` 查看 Swagger 文档。

### 前端启动

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev
```

前端将在 `http://localhost:5173` 启动。

---

## 📡 API 端点

| 模块 | 路径 | 说明 |
|------|------|------|
| 同步 | `/api/v2/sync` | ActivityWatch 数据同步 |
| 活动 | `/api/v2/activity` | 首页数据、活动统计 |
| 时间线 | `/api/v2/timeline` | 时间线数据 |
| 分类 | `/api/v2/categories` | 分类管理 |
| 目标 | `/api/v2/goals` | 目标 & 待办事项 |
| 聊天 | `/api/v2/chatbot` | AI 聊天接口 |
| 使用量 | `/api/v2/usage` | Token 使用统计 |

---

## 📁 数据存储

项目使用 SQLite 作为本地存储：

- **`lifewatch_ai.db`**：主数据库（行为日志、分类、目标、待办事项）
- **`chatbot.db`**：聊天历史（LangGraph CheckPoint）
- **`chat_sessions.db`**：聊天会话元数据

---

## 🔧 配置

通过环境变量配置：

```bash
# 开发模式（启用热重载）
set LIFEWATCH_DEV=1

# AI API 配置
set DASHSCOPE_API_KEY=your_api_key
```

---

## 📝 开发状态

| 功能 | 状态 |
|------|------|
| 首页仪表盘 | ✅ 完成 |
| 时间线视图 | ✅ 完成 |
| 分类管理 | ✅ 完成 |
| AI 聊天 | ✅ 完成 |
| 目标管理 | ✅ 完成 |
| 使用量统计 | ✅ 完成 |
| 报告统计 | 🚧 开发中 |
| 设置页面 | 🚧 开发中 |

---

## 📄 许可证

本项目仅供学习和个人使用。

---

*最后更新: 2025-12-26*
