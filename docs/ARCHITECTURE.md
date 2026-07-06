---
version: 2.0
created_at: 2026-04-09
updated_at: 2026-07-07
last_updated: 全面重写，参照 agents-hub 格式重构，更新至当前实际代码结构，新增 LLM Agent/Channel/Repository 等核心模块，补充技术栈、分层图、数据流和文档导航
abstract: 项目架构地图，概述仓库物理结构、抽象分层、前后端架构、主干数据流和关键依赖方向。
---

# ARCHITECTURE

> 面向第一次进入项目的人或 AI，快速说明 LifePrism 的整体结构、主干数据流和关键依赖边界。

## 版本

| 版本 | 更新内容 |
|------|---------|
| 1.0 | 创建架构地图初稿 |
| 1.1 | 补充 abstract 字段 |
| 2.0 | 全面重写：参照 agents-hub 格式重构，新增 LLM Agent/Channel/Repository 等核心模块，补充技术栈表、分层架构图、4 条主干数据流和文档导航 |

## 项目概述

LifePrism 是一个围绕**个人成长**构建的桌面应用项目，核心目标是把行为数据、目标管理、习惯养成、心理记录和 AI 能力放到同一套系统里。项目名 **LifeWatch-AI** 为仓库名，产品名为 **LifePrism**。

## 技术栈

| 层面 | 技术选择 | 说明 |
|------|---------|------|
| **后端框架** | Python + FastAPI | REST API + WebSocket |
| **数据库** | SQLite（3 实例：lw / aw / chat_history） | 本地单文件，零运维 |
| **LLM** | LiteLLM + OpenAI SDK + LangChain | 多服务商适配，Agent 执行引擎 |
| **任务调度** | APScheduler | 定时截图、Dream、消息处理 |
| **前端框架** | React 19 + TypeScript | UI 框架 |
| **桌面端** | Electron 40 | 跨平台桌面应用 |
| **状态管理** | React Context + hooks | 模块级状态隔离 |
| **样式** | Tailwind CSS 4 | 实用优先 |
| **富文本** | TipTap (ProseMirror) | 块编辑器、Markdown 支持 |
| **图表** | ECharts + Recharts | 时间轴、统计图表 |
| **打包** | Vite + electron-builder (NSIS) | 前端构建 + Windows 安装包 |
| **后端打包** | PyInstaller | 后端二进制分发 |

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                       前端层                                 │
│           React 19 + TypeScript + Electron                  │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ LifeWatch│ │GoalMaster│ │Mind Space│ │  Settings    │   │
│  │ (时间追踪)│ │(目标管理) │ │(内心探索) │ │  (配置)      │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Core Layer (API Client / WebSocket / Shared Utils)  │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP + WebSocket
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                     API Server                               │
│               FastAPI + WebSocket                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐                 │
│  │  routes  │ │ services │ │  providers   │                 │
│  └──────────┘ └──────────┘ └──────────────┘                 │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ↓            ↓            ↓
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│  LLM 层      │ │Processor │ │  Monitor 层   │
│  Agent Loop  │ │ 数据清洗  │ │  窗口监控     │
│  Chat/频道   │ │ 分类管线 │ │  截图采集     │
│  Session     │ │          │ │               │
└──────┬───────┘ └────┬─────┘ └──────┬────────┘
       │              │              │
       └──────────────┼──────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                   基础设施层                                  │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────────────┐ │
│  │  Config  │  │ Repository │  │  Utils (log/errors/...)  │ │
│  │ 配置管理  │  │ 数据访问层  │  │  通用工具                │ │
│  └──────────┘  └────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**关键理解**：
- **前端**：Electron 桌面壳层内嵌 React 应用，按业务模块拆分 apps，core 层提供跨模块复用
- **API Server**：FastAPI 汇聚业务能力，通过 HTTP 暴露给前端，WebSocket 用于实时推送
- **LLM 层**：Agent 执行引擎，支持多渠道消息接入（ChatBot / WeChat Channel）、Session 管理、工具调用
- **Processor 层**：ActivityWatch 数据清洗与分类管线（EventTransformer → CacheMatcher → ClassifyCollector → LLM）
- **Monitor 层**：Windows 窗口监控、截图采集，是时间追踪的数据源头
- **基础设施层**：Config 负责路径解析和配置读取，Repository 负责 DB 连接池和 CRUD，Utils 提供日志/异常等基础能力

## 物理结构

| 路径 | 作用 |
|------|------|
| `frontend/` | React + Electron 前端，负责界面、交互、桌面壳层（其中 `my-ui-kit/` 为 git submodule） |
| `lifeprism/` | Python 后端，负责配置、服务、数据处理、LLM 能力、存储与监控 |
| `scripts/` | 项目脚本，包含 CI 检查、pre-commit、webapp 测试 |
| `test/` | 后端测试用例 |
| `templates/` | 用户、代理、日记等模板资产 |
| `docs/` | 项目文档资产，包括规则、规格、计划、架构决策、数据流 |
| `assets/` | 项目级静态资源（截图、GIF） |
| `build/` | PyInstaller 构建产物 |
| `localData/` | 开发环境本地数据目录 |

## 后端架构详解

### 目录结构

```
lifeprism/
├── server/                         # FastAPI 服务层
│   ├── main.py                     # 应用入口，生命周期管理
│   ├── api/                        # HTTP 路由
│   ├── services/                   # 业务编排
│   ├── providers/                  # 数据访问封装
│   ├── schemas/                    # Pydantic 模型
│   ├── middleware/                  # 中间件
│   └── errors/                     # 错误处理
│
├── llm/                            # LLM 智能层
│   ├── agent/                      # Agent 执行引擎（AgentLoop、命令处理）
│   ├── chat/                       # ChatBot API 入口
│   ├── channel/                    # 多渠道消息接入（WeChat Channel 等）
│   ├── session/                    # Session 生命周期（JSONL 持久化 + 内存缓存）
│   ├── classify/                   # AI 内容分类（ClassifyGraph / ClassifySimple）
│   ├── providers/                  # LLM Provider 适配（LiteLLM + Custom）
│   ├── tools/                      # Tool 注册、执行、安全沙箱
│   ├── bus/                        # Event Bus 消息队列（asyncio.Queue）
│   ├── function/                   # LLM Functions（日记总结/截图分析等）
│   ├── prompts/                    # Prompt 模板管理（Markdown 文件）
│   ├── schemas/                    # LLM 请求/响应数据结构
│   ├── summary_context/            # Summary Context 构建
│   ├── aggregator/                 # 数据聚合器
│   └── utils/                      # LLM 层工具函数
│
├── processors/                     # 数据处理层
│   ├── provider/                   # ActivityWatch 数据源适配
│   ├── components/                 # EventTransformer / CacheMatcher / ClassifyCollector
│   └── models/                     # 数据模型
│
├── monitor/                        # 监控层
│   ├── windows_monitor/            # Windows 窗口监控
│   ├── screenshot/                 # 截图采集（定时/主动/Enter 三类）
│   └── provider/                   # 监控数据源
│
├── config/                         # 配置管理
│   ├── settings_manager.py         # SettingsManager 单例（7 步初始化）
│   ├── provider_manager.py         # ProviderManager（3 步并行初始化）
│   └── migrations/                 # 配置文件迁移
│
├── repository/                     # 数据访问层
│   ├── __init__.py                 # 3 个 DB 实例 + 连接池
│   ├── base_providers/             # LWBaseDataProvider / AWBaseDataProvider
│   ├── providers/                  # 业务 DataProvider
│   ├── aggregators/                # 多表聚合查询（GoalAggregator 等）
│   └── migrations/                 # 数据库迁移（版本检测→备份→执行）
│
└── utils/                          # 基础设施
    ├── logger.py                   # 日志（延迟 FileHandler）
    ├── exceptions.py               # 异常体系
    ├── common_utils.py             # 通用工具函数
    ├── lazy_singleton.py            # 惰性单例模式
    └── decorator_tool.py            # 装饰器工具
```

### 分层架构

后端采用**分层架构**，遵循**单向依赖原则**：

```
┌─────────────────────────────────────────────────────────────┐
│  server/  (服务层)  — 对外汇总，暴露 API                      │
├─────────────────────────────────────────────────────────────┤
│  llm/  (智能层)         processors/  (处理层)                 │
│  Agent 执行 / 会话管理   数据清洗 / 分类管线                   │
├─────────────────────────────────────────────────────────────┤
│  monitor/  (监控层)  — 窗口监控 / 截图采集                     │
├─────────────────────────────────────────────────────────────┤
│  repository/  (数据层)  — DB 连接池 / CRUD / 迁移              │
├─────────────────────────────────────────────────────────────┤
│  config/  (配置层)  — SettingsManager / ProviderManager       │
├─────────────────────────────────────────────────────────────┤
│  utils/  (基础层)  — 日志 / 异常 / 通用工具                    │
└─────────────────────────────────────────────────────────────┘
```

**依赖方向**：
```
utils → config → repository → monitor → processors → server
                                    ↓           ↓
                                  llm ──────────┘
```

**已知耦合**：
- `llm` 中的部分 provider / summary_context 代码反向依赖了 `server` 的 provider 或 service
- 主体结构上 `server` 是对外汇总层，但 `llm` 与 `server` 之间尚未完全解耦

### 各模块职责

| 模块 | 职责 | 通信方式 | Spec |
|------|------|---------|------|
| server/ | FastAPI 服务入口，REST API + WebSocket，生命周期管理 | HTTP + WebSocket | - |
| llm/agent/ | Agent 执行引擎，消息分发、命令处理、工具调用循环 | 内部调用 | [llm-agent](specs/2026-07-06-llm-agent-spec.md) |
| llm/chat/ | ChatBot 无状态对话 API | HTTP | [llm-communication](specs/2026-07-06-llm-communication-spec.md) |
| llm/channel/ | 多渠道消息接入（WeChat Channel 完整实现） | HTTP 轮询 | [wechat-channel-integration](specs/2026-05-01-wechat-channel-integration-spec.md) |
| llm/session/ | Session 生命周期，JSONL 持久化 + 内存缓存 | 内部调用 | [llm-communication](specs/2026-07-06-llm-communication-spec.md) |
| llm/classify/ | AI 内容分类（ClassifyGraph 多步 / ClassifySimple 单步） | 内部调用 | [classify](specs/2026-04-16-classify-spec.md) |
| llm/providers/ | LLM Provider 适配（LiteLLM 多服务商 + Custom OpenAI SDK） | HTTPS | [llm-infrastructure](specs/2026-07-06-llm-infrastructure-spec.md) |
| llm/tools/ | Tool 注册、参数校验、安全沙箱（白名单 + 命令黑名单） | 内部调用 | [llm-agent](specs/2026-07-06-llm-agent-spec.md) |
| llm/bus/ | Event Bus 消息队列（asyncio.Queue），解耦消息收发 | 内部调用 | [llm-agent](specs/2026-07-06-llm-agent-spec.md) |
| processors/ | ActivityWatch 数据清洗与分类管线 | 内部调用 | [classify](specs/2026-04-16-classify-spec.md) |
| monitor/ | Windows 窗口监控、截图采集（定时/主动/Enter） | 系统 API | [monitor-screenshot](specs/2026-04-02-monitor-screenshot-spec.md) |
| config/ | SettingsManager + ProviderManager 单例，路径解析、配置读写 | 内部调用 | [config-path](specs/2026-07-06-config-path-spec.md) / [config-settings](specs/2026-07-06-config-settings-spec.md) |
| repository/ | DB 连接池、元数据驱动 CRUD、迁移系统 | SQLite | [repository-core](specs/2026-07-06-repository-core-spec.md) |
| utils/ | 日志、异常、单例、通用工具，**零依赖** | - | - |

## 前端架构

### 技术栈

| 层面 | 技术选择 | 说明 |
|------|---------|------|
| **框架** | React 19 | UI 框架 |
| **语言** | TypeScript 5.8 | 类型安全 |
| **桌面端** | Electron 40 | 跨平台桌面应用 |
| **状态管理** | React Context + hooks | 模块级状态隔离，无全局 store |
| **路由** | React Router v7 | 主窗口 / 浮窗 / 对话框分流 |
| **样式** | Tailwind CSS 4 | 实用优先 |
| **富文本** | TipTap (ProseMirror) | 块编辑器，支持 Markdown |
| **图表** | ECharts 6 + Recharts 3 | 时间轴、可视化 |
| **动画** | Framer Motion | 过渡动效 |
| **拖拽** | dnd-kit | 任务排序 |
| **打包** | Vite 6 + electron-builder (NSIS) | 快速构建 + Windows 安装包 |

### 目录结构

```
frontend/
├── App.tsx                         # 路由入口，分流主窗口/浮窗/对话框
├── index.tsx                       # React 挂载点
├── apps/                           # 业务模块
│   ├── lifewatch/                  # 时间追踪（layout / pages）
│   ├── goals/                      # 目标管理（components / hooks / context / apis / types）
│   ├── habits/                     # 习惯养成（components / hooks / apis / types / data）
│   ├── mindspace/                  # 内心探索（components / services / utils / data）
│   ├── settings/                   # 设置页
│   └── addons/                     # 拓展功能
├── core/                           # 跨应用核心层
│   ├── components/                 # 共享组件（含 Chatbot 对话组件）
│   ├── services/                   # API 客户端、同步服务
│   ├── hooks/                      # 通用 hooks
│   ├── context/                    # 全局 Context
│   ├── utils/                      # 工具函数
│   ├── types/                      # 通用类型
│   └── styles/                     # 全局样式
├── shell/                          # 主应用壳层与导航
├── dialogs/                        # 独立对话框窗口（record-activity / todo-picker）
├── floating/                       # 浮窗入口（what-am-i-doing）
├── electron/                       # Electron 主进程、预加载、更新逻辑
└── my-ui-kit/                      # 自研 UI 组件库（日历/拖拽/编辑器/里程碑等）
```

### 架构原则

- **模块隔离**：`apps/` 之间不直接相互依赖，通过 `core/` 层通信
- **入口统一**：`App.tsx` 负责路由分流，`core/services` 负责后端通信
- **类型集中**：`frontend/types/` 存放跨模块共享类型，每个 app 内部维护自身类型

## 主干数据流

### 1. ActivityWatch 数据处理流

这是 LifeWatch 时间追踪的核心链路：

```
ActivityWatch / Monitor 采集原始事件
  → monitor/provider 读取
    → processors/components/EventTransformer（数据清洗）
      → CacheMatcher（缓存匹配）
        → ClassifyCollector（待分类收集）
          → llm/classify（LLM 分类）
            → CategoryCache / repository（持久化）
              → server/services → API
                → frontend/apps/lifewatch（可视化）
```

### 2. 前后端交互流

```
React UI
  → frontend/core/services（API 调用）
    → FastAPI api/routes
      → server/services（业务编排）
        → providers / repository / llm
          → API response
            → frontend/apps（渲染）
```

### 3. 配置与启动流

```
settings_manager（单例初始化）
  → _resolve_config_base_path()（固定路径）
  → config.yaml 加载 + 迁移
  → _resolve_lifeprism_data_path()（三级优先级：yaml > env var > default）
  → setup_file_logging()（日志文件输出）
  → DatabaseManager 初始化（3 个 DB + 连接池）
  → LWTableManager 建表
  → migration_runner（版本检测→备份→执行）
  → data_initializer（默认数据填充）
  → resource_initializer（资源文件初始化）
  → 启动 monitor / channel / agent loop
```

### 4. LLM Agent 对话流

```
用户消息（ChatBot API / WeChat Channel）
  → channel 接收 → bus.send() 入队
    → AgentLoop.consume_inbound()
      → 命令处理（/new /continue /session-list）
        → Context 构建（CHAT/CLASSIFY/GENERAL_TASK/DREAM_TASK 四路分支）
          → Tool 注册（7 类 17 个工具）
            → auto_compact（token 阈值检测 → LLM 压缩）
              → _run_agent_loop（LLM 调用 → 工具执行循环，最多 20 轮）
                → publish_outbound（结果推送）
                  → Session 持久化（JSONL 文件 + 内存缓存）
```

**关键点**：
- 消息通过 `asyncio.Queue` 解耦收发
- 工具调用含安全沙箱（`allowed_dir_path` 白名单 + 命令黑名单）
- Session 采用 JSONL 文件持久化 + 内存缓存双层架构

## 关键依赖方向

完整依赖链：

```
utils → config → repository → monitor → processors → server
                          ↘         ↓           ↓
                            llm ────┘ ──────────┘
```

各层职责：

1. **utils** — 最底层通用能力：日志（延迟 FileHandler）、异常体系、单例模式
2. **config** — 建立在 utils 之上：SettingsManager（路径解析 + 配置读写）、ProviderManager（LLM Provider 配置）
3. **repository** — 依赖 config + utils：DatabaseManager（3 个 DB 实例 + 连接池）、LWTableManager（建表）、BaseDataProvider（元数据驱动 CRUD，`_TABLE_NAME`/`_PRIMARY_KEY` 白名单防注入）
4. **monitor** — 依赖 repository + config + utils：窗口监控、截图采集
5. **processors** — 依赖 repository + config + utils + 部分 llm：数据清洗与分类管线
6. **llm** — 依赖 utils + config + repository：Agent 引擎、Session 管理、多渠道接入
7. **server** — 对外服务层：汇总 repository / processors / llm / config 的能力，对前端暴露 API

> **注意**：`llm` 与 `server` 之间存在现实代码耦合（`llm` 中部分 provider/summary_context 代码反向依赖 `server`），尚未完全解耦。

## 文档导航

| 文档类型 | 路径 | 说明 |
|---------|------|------|
| **产品规格（Spec）** | `docs/specs/` | 技术契约文档，定义模块接口和功能完整性清单 |
| **数据状态流（Flow）** | `docs/flows/` | 数据流转与状态变化，提供调用链路和函数位置导航 |
| **架构决策（ADR）** | `docs/adr/` | 长期重要的架构决定记录 |
| **编码规则** | `docs/coding-rules/` | 编写代码时必须遵守的规范 |
| **文档规则** | `docs/docs-rules/` | 编写文档时必须遵守的规范 |
| **权威参考** | `docs/authority/` | 特定且关键的实现知识 |
| **技术债** | `docs/technical-debt/` | 已知技术债务及清理计划 |
| **历史 Bug** | `docs/history-bugs/` | 可复用的 bug 经验 |
| **自动生成** | `docs/generated/` | 代码镜像，不手工维护 |
| **执行计划** | `docs/plans/` | 任务分解和执行记录 |
| **临时内容** | `docs/temp/` | 非正式文档、草稿、临时记录 |

## 更新触发条件

以下变化通常意味着应回看并更新本文件：

1. 顶层目录职责发生变化
2. 前端或后端的主分层发生变化
3. 关键数据流被重构
4. 关键依赖方向或启动顺序发生变化
5. 文档体系的分类和职责边界发生变化
6. 新增或移除核心模块（llm/processors/monitor 等一级目录）

## 参考资料

- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/)
- [Electron](https://www.electronjs.org/)
- [LiteLLM](https://docs.litellm.ai/)
- [ActivityWatch](https://activitywatch.net/)
