# 项目架构

## 数据流管道

ActivityWatch 事件 → 分类洞察的核心处理流程：

```
ActivityWatch Raw Events
    ↓
EventTransformer (normalize events)
    ↓
CacheMatcher (check cache for existing classifications)
    ↓
ClassifyCollector (collect items needing LLM classification)
    ↓
LLM Classifier (LangGraph sequential executor)
    ↓
CategoryCache (store results for future use)
    ↓
SQLite Database (persistent storage)
```

**关键文件**：`lifeprism/processors/data_clean.py` - `clean_activitywatch_data_v2()`
**缓存规则文档**：`lifeprism/processors/README.md`

## LLM 分类系统

使用 **sequential executor** 模式（`data_driving_agent/`），按顺序处理节点，线程级上下文隔离。

- **Thread-based context isolation**：每个执行线程有独立消息历史
- **Sequential execution**：节点按 ID 顺序执行
- **Data injection**：`data_in` 从父线程注入上下文
- **Data merging**：`data_out` 将结果合并回父线程

**文档**：`lifeprism/llm/llm_classify/tests/data_driving_agent_v2/README.md`

## 缓存匹配策略

三级缓存，最小化 LLM API 调用：

1. **单用途应用**：按 `app` 缓存（如 `vscode` → `cat-work`）
2. **多用途应用**：按 `app` + `title` 缓存（如 `msedge` + `github.com` → `cat-work`）
3. **应用描述**：独立缓存，复用于分类上下文

缓存表：
- `category_map_cache`：分类结果
- `_single_purpose_apps`：单用途应用索引
- `_multipurpose_apps` + `_multipurpose_titles`：多用途应用索引
- `_app_description_map`：应用描述缓存

## 多用途应用处理

- `multi_purpose_app_names` 列表中的应用（浏览器）需要按标题分别分类
- 缓存 key 是 `(app, title)` 元组而非单独 `app`

## 分类模式

- `classify_simple`：单次 LLM 调用（快，精度低）
- `classify_graph`：LangGraph 顺序处理（慢，精度高）
- 切换依据：`settings.yaml` 中的 `long_log_threshold`

## 前端架构

apps/core/shell 三层架构：

| 层次 | 目录 | 职责 |
|------|------|------|
| Shell | `shell/` | ModuleDock 导航、全局布局 |
| Core | `core/` | 跨应用共享组件、服务、类型、Hooks |
| Apps | `apps/` | 独立功能模块 |

应用模块：
- `apps/lifewatch/`：时间追踪（首页、时间线、分类、使用量、报告）
- `apps/goals/`：目标管理（目标列表、计划书、任务池、日历、每日任务）
- `apps/habits/`：习惯养成（习惯列表、习惯链、锚点时间线）
- `apps/settings/`：全局设置

**详细文档**：`frontend/docs/组织架构.md`

## 数据同步策略

前端使用增量同步（`frontend/core/services/syncService.ts`）：
- 获取上次同步时间戳，只请求新/变更事件
- 异步执行不阻塞 UI

## 数据库

SQLite 持久化，关键表：
- Events 表：清洗后的 ActivityWatch 事件
- Category 表：应用分类
- `category_map_cache`：分类缓存
- Goals/Todo：用户目标追踪
- Chat history：AI 对话历史

**表定义**：`lifeprism/storage/lw_table_manager.py`

## 常见开发任务

### 添加新 LLM 分类节点
1. 在 `data_driving_agent/executor.py` 创建 handler
2. 在 `custom_prompt/` 的 plan JSON 中添加节点配置
3. 配置 `data_in`/`data_out`/`thread_id`

### 添加新前端应用
1. 创建 `frontend/apps/[appname]/`
2. 创建主组件 `[AppName]App.tsx`
3. 添加到 `shell/ModuleDock.tsx` 导航
4. 注册路由到 `frontend/App.tsx`

### 修改缓存规则
1. 编辑 `lifeprism/processors/data_clean.py`
2. 更新 `lifeprism/processors/components/category_cache.py`
3. 更新 `lifeprism/processors/README.md`
