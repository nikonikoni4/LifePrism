# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## rules

### 语言

对话时除了专有名词外，需要使用中文回答

### 后端server rules

1. 在lifeprism\config\database.py完成数据表的配置 
2. 在lifeprism\server\providers创建数据提供类，继承LWBaseDataProvider实现，使用LWBaseDataProvider中的db类成员实现数据库操作  
3. 在schemas中编写前后端数据沟通的schemas 
4. **Service 单例模式判断规则**：在 service 中，若当前 service 涉及到状态缓存，需要创建单一 service 实例，采用懒加载方式 `lifeprism\utils\lazy_singleton.py`。若不涉及状态缓存，则直接使用纯函数模块。

   **需要单例的场景（任一条件满足即需要）：**
   
   1. **ID → Name 名称映射缓存**：维护 `id → name` 的内存字典，供其他模块快速查找
      - 例：`CategoryService.category_name_map`、`GoalService.goal_name_map`
      - 原因：避免每次查名称都访问数据库，且需要保证多处访问时数据一致
   
   2. **实体关系映射缓存**：维护实体间关系的内存字典
      - 例：`CategoryService.sub_to_parent_map`（子分类 → 父分类 ID）
      - 原因：关系查询频繁，缓存可显著提升性能
   
   3. **原始数据 DataFrame/列表缓存**：将数据库查询结果缓存为 DataFrame 或列表
      - 例：`CategoryService._categories_df`、`CategoryService._sub_categories_df`
      - 原因：避免重复查询，适用于数据量小且变更不频繁的配置类数据
   
   4. **运行时实例状态**：维护需要跨请求保持的运行时对象或状态
      - 例：`ChatbotService._chatbot`（LLM 实例）、`ChatbotService._current_session_id`
      - 原因：实例创建成本高，或需要维护会话状态
   
   **不需要单例的场景（使用纯函数模块）：**
   
   1. **纯数据转换/查询**：每次调用直接访问数据库或 provider，无内存缓存
      - 例：`timeline_service`、`usage_service`、`report_service`
   
   2. **仅持有 provider 引用**：类成员只有 `self.xxx_provider = xxx_provider`，无自己的缓存字典
      - 例：`JournalService`（只有 `self.journal_provider`）
      - 这种情况可以改为纯函数，或保持类但不必强制单例
   
   3. **数据库层面缓存**：缓存存储在数据库表中而非内存
      - 例：`report_service` 的报告缓存存在 `daily_report`/`weekly_report` 表中
   
   **单例实现方式**：
   ```python
   # 在 service 模块底部
   from lifeprism.utils import LazySingleton
   
   # 懒加载单例（推荐，延迟初始化）
   category_service = LazySingleton(CategoryService)
   ```
   
   **缓存一致性**：有缓存的 service 必须提供 `_refresh_cache()` 方法，在 CRUD 操作后调用以保持缓存与数据库同步
5. **ID 优先原则**：用户可修改的"名称"字段（如分类名称、目标名称、习惯名称、任务内容等）不能作为数据查找、匹配或关联的依据，必须使用系统生成的、用户不可修改的 `id` 作为唯一标识。

   **适用范围**：
   - 涉及实体间关联的场景（如 Todo 关联 Goal、Cache 关联 Category）
   - 涉及数据查找/匹配的场景（如根据条件获取某条记录）
   - 涉及缓存 key 设计的场景

   **不适用的场景**：
   - 纯展示用途（UI 显示名称）
   - 数据库 UNIQUE 约束（防止用户创建重复名称，这是业务约束，与数据关联无关）
   - 搜索功能（用户按名称搜索是合理的，但返回结果后的后续操作应基于 id）
   - **外部系统边界转换**（如 LLM 分类输出）：LLM 只能输出人类可读的 `name`，后端需要将其转换为 `id` 存储。这是外部边界的必要转换，转换后数据库存储的仍是 `id`。
     ```python
     # ✅ 正确：LLM 边界转换（data_processing_service.py）
     # LLM 输出: { category: "工作", link_to_goal: "学习英语" }
     # 转换为 id 后存储
     category_name_to_id = {cat['name']: cat['id'] for cat in categories}
     goal_name_to_id = {g['name']: g['id'] for g in goals}

     cat_id = category_name_to_id.get(llm_result.category)  # name → id
     goal_id = goal_name_to_id.get(llm_result.link_to_goal)  # name → id

     # 最终存储的是 id
     record = {'category_id': cat_id, 'link_to_goal_id': goal_id}
     ```
     **注意**：此场景需要对 LLM 输出的 name 进行校验，确保其存在于系统中，否则应记录警告或回退处理。

   **数据库层约束**：
   ```
   ✅ 正确：
   - PRIMARY KEY 必须是 id（如 goal-xxx, cat-xxx）
   - 外键字段存储 id（如 link_to_goal_id, category_id）
   - name 字段可设置 UNIQUE 约束（业务需要）

   ❌ 错误：
   - 用 name 作为外键关联字段
   - 用 name 作为 PRIMARY KEY
   ```

   **后端层约束**：
   ```python
   # ✅ 正确：用 id 查找/匹配
   goal = goal_provider.get_goal_by_id("goal-abc123")
   cache = cache_provider.get_by_category_id("cat-xxx")

   # ❌ 错误：用 name 查找/匹配（用户改名后关联断裂）
   goal = goal_provider.get_goal_by_name("学习英语")

   # ✅ 正确：缓存 key 用 id
   goal_name_map = {"goal-abc123": "学习英语"}  # id → name

   # ❌ 错误：缓存 key 用 name
   goal_id_map = {"学习英语": "goal-abc123"}  # name → id

   # ✅ 正确：API 关联参数用 id
   class CreateTodoRequest:
       link_to_goal_id: str  # 存 "goal-abc123"

   # ❌ 错误：API 关联参数用 name
   class CreateTodoRequest:
       link_to_goal_name: str  # 存 "学习英语"
   ```

   **前端层约束**：
   ```typescript
   // ✅ 正确：存储和传递 id
   const todo = { linkToGoalId: "goal-abc123" }
   await api.createTodo({ link_to_goal_id: selectedGoal.id })

   // ❌ 错误：存储和传递 name
   const todo = { linkToGoalName: "学习英语" }
   await api.createTodo({ link_to_goal_name: selectedGoal.name })

   // ✅ 正确：name 仅用于展示
   <span>{goal.name}</span>
   ```

   **核心原因**：`name` 是用户可随时修改的，如果用 `name` 做关联/查找，用户修改名称后原有关联会断裂，导致数据不一致

## Project Overview

**LifeWatch-AI** (LifePrism) is an AI-powered personal time management and analysis platform that monitors user computer activity through ActivityWatch, classifies applications using LLM, and provides insights through a React frontend.

### Architecture

```
LifeWatch-AI/
├── frontend/           # React + TypeScript + Vite frontend
│   ├── page/          # Page components (home, timeline, category, etc.)
│   ├── components/    # Shared React components
│   ├── services/      # API service layer
│   └── App.tsx        # Main app with routing
├── lifeprism/         # Python backend package
│   ├── server/        # FastAPI backend server
│   │   ├── api/       # API route handlers
│   │   ├── services/  # Business logic services
│   │   ├── schemas/   # Pydantic data models
│   │   └── main.py    # FastAPI app entry point
│   ├── llm/           # LLM-based classification system
│   │   └── llm_classify/
│   │       ├── classify/        # Classification logic
│   │       ├── chat/            # Chatbot implementation
│   │       ├── data_driving_agent/  # Sequential executor for LLM agents
│   │       └── custom_prompt/   # Custom prompts
│   ├── processors/     # Data processing pipeline
│   │   ├── data_clean.py       # Main data cleaning function
│   │   └── components/         # Processing components (cache matcher, etc.)
│   ├── storage/        # Database layer
│   │   ├── database_manager.py    # Database connection management
│   │   └── lw_table_manager.py    # Table initialization
│   ├── config/         # Configuration management
│   │   ├── settings.yaml          # User settings (LLM provider, DB paths)
│   │   └── database.py            # Database configuration
│   └── updater/        # Auto-update functionality
└── docs/               # Documentation
```

## Development Commands

### Frontend (React + Vite + Electron)

```bash
cd frontend

# Install dependencies
npm install

# Development server (runs on port 3000, proxies /api to localhost:8000)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Electron desktop app (development)
npm run electron:dev

# Electron desktop app (Windows build)
npm run electron:build
```

**Frontend Dev Server**: http://localhost:3000
**API Proxy**: `/api` → `http://localhost:8000` (configured in `vite.config.ts`)
**Electron Build Output**: `frontend/release/`

### Backend (Python + FastAPI)

```bash
# Install Python package in development mode
pip install -e .

# Run development server with hot reload
cd lifeprism/server
python main.py

# Or set environment variable for dev mode
LIFEWATCH_DEV=1 python -m lifeprism.server.main
```

**Backend API Server**: http://localhost:8000
**API Docs (Swagger)**: http://localhost:8000/docs
**API Docs (ReDoc)**: http://localhost:8000/redoc

### Running Both Services

For development, run both services simultaneously:
1. Terminal 1: `cd frontend && npm run dev`
2. Terminal 2: `python -m lifeprism.server.main`

## Key Architecture Concepts

### Data Flow Pipeline

The core data pipeline processes ActivityWatch events into classified insights:

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

**Key File**: `lifeprism/processors/data_clean.py` - Contains `clean_activitywatch_data_v2()` main function

**Documentation**: `lifeprism/processors/README.md` - Detailed cache hit rules

### LLM Classification System

The LLM classification uses a **sequential executor** pattern (`data_driving_agent/`) that processes nodes in order with thread-based context isolation.

**Key Features**:
- **Thread-based context isolation**: Each execution thread has isolated message history
- **Sequential execution**: Nodes execute in ID order (not parallel)
- **Data injection**: `data_in` config injects context from parent threads when creating new threads
- **Data merging**: `data_out` flag merges results back to parent threads

**Documentation**: `lifeprism/llm/llm_classify/tests/data_driving_agent_v2/README.md`

### Cache Matching Strategy

The system uses a three-tier caching strategy to minimize LLM API calls:

1. **Single-purpose apps**: Cached by `app` name only (e.g., `vscode` → `cat-work`)
2. **Multi-purpose apps**: Cached by `app` + `title` (e.g., `msedge` + `github.com` → `cat-work`)
3. **App descriptions**: Cached separately and reused for classification context

**Cache Tables**:
- `category_map_cache`: Stores classification results
- `_single_purpose_apps`: Index for single-purpose app lookups
- `_multipurpose_apps` + `_multipurpose_titles`: Index for multi-purpose app lookups
- `_app_description_map`: App description cache (independent of classification)

### Frontend Page Structure

The frontend uses a simple page-based routing system (not React Router). Navigation is controlled by `App.tsx` state `currentPage` and `<Sidebar>` component. Pages are located in `frontend/page/[pagename]/`.

## Configuration

### Backend Configuration

**Main Config File**: `lifeprism/config/settings.yaml`

```yaml
# LLM Provider Configuration
provider: "阿里云百炼 (Aliyun)"  # or "火山引擎 (VolcEngine)"
model: qwen-plus-2025-12-01
input_tokens_cost: 0.0008
output_tokens_cost: 0.002

# Classification Settings
classification_mode: classify_graph  # or classify_simple
long_log_threshold: 300  # Token threshold for switching classification mode
multi_purpose_app_names:
  - chrome
  - msedge
  - firefox

# Database Paths
lw_db_path: D:/desktop/.../lifewatch_ai.db
aw_db_path: C:/Users/.../peewee-sqlite.v2.db
chat_db_path: D:/desktop/.../chat_history.db

# Data Cleaning
data_cleaning_threshold: 10  # Minimum events for classification
```

**User-specific settings**: Modify `settings.yaml` directly or use the Settings page UI

### Frontend Configuration

**Vite Config**: `frontend/vite.config.ts`
- Dev server: `localhost:3000`
- API proxy: `/api` → `http://localhost:8000`

**Environment Variables** (for frontend):
- `GEMINI_API_KEY`: For Google Generative AI client (optional)

## Database Schema

The system uses SQLite for persistence. Key tables:

- **Events tables**: Store cleaned ActivityWatch events
- **Category tables**: Store app/titel classifications
- **category_map_cache**: Classification cache (see cache matching rules above)
- **Goals/Todo**: User goal tracking
- **Chat history**: Conversations with the AI assistant

**Table Manager**: `lifeprism/storage/lw_table_manager.py` - Defines all table schemas

## API Endpoints

Base URL: `http://localhost:8000/api/v2`

| Module | Prefix | Endpoints |
|--------|--------|-----------|
| Sync | `/sync` | `POST /activitywatch` - Sync from ActivityWatch |
| Categories | `/categories` | `GET /apps`, `POST /classify`, etc. |
| Activity | `/activity` | `GET /summary`, `GET /timeline` |
| Timeline | `/timeline` | `GET /` - Timeline data |
| Usage | `/usage` | `GET /` - Token usage statistics |
| Goals | `/goals` | CRUD for goals/todos |
| Chatbot | `/chatbot` | Chat endpoints |
| Settings | `/settings` | Configuration management |
| Reports | `/reports` | Daily reports |
| Being | `/being` | Time paradox test |

**Full API docs**: http://localhost:8000/docs (auto-generated Swagger UI)

## Important Implementation Details

### Multi-Purpose Application Handling

Multi-purpose apps (browsers) require special handling:

1. **Detection**: Apps in `multi_purpose_app_names` list are flagged
2. **Title-based classification**: Each unique title needs separate classification
3. **Cache key**: `(app, title)` tuple instead of just `app`

**Example**:
- `msedge` + `github.com` → `cat-work`
- `msedge` + `bilibili.com` → `cat-entertainment`

### Classification Modes

The system supports two classification modes:

1. **`classify_simple`**: Single LLM call per batch (faster, less accurate)
2. **`classify_graph`**: LangGraph-based sequential processing (slower, more accurate)

**Selection**: Based on `long_log_threshold` in `settings.yaml`

### Data Sync Strategy

The frontend uses **incremental sync** on startup (`frontend/services/syncService.ts`):

- Fetches last sync timestamp from backend
- Only requests new/changed events since last sync
- Runs asynchronously without blocking UI
- Shows progress indicator at top of screen

## Common Tasks

### Adding a New LLM Classification Node

1. Create handler function in `lifeprism/llm/llm_classify/data_driving_agent/executor.py`
2. Add node configuration to plan JSON in `lifeprism/llm/llm_classify/custom_prompt/`
3. Configure `data_in`, `data_out`, `thread_id` as needed (see README)
4. Test with existing data

### Adding a New Frontend Page

1. Create component in `frontend/page/[pagename]/`
2. Add route case in `frontend/App.tsx`
3. Add navigation item in `frontend/components/Sidebar.tsx`
4. Create API endpoints in `lifeprism/server/api/` if needed

### Modifying Cache Rules

1. Edit `lifeprism/processors/data_clean.py`
2. Update `lifeprism/processors/components/category_cache.py`
3. Update `lifeprism/processors/README.md` documentation

## Troubleshooting

### Common Issues

**Problem**: Frontend can't connect to backend
- **Solution**: Ensure backend is running on port 8000, check CORS settings in `lifeprism/server/main.py`

**Problem**: LLM classification not working
- **Solution**: Check API key in `lifeprism/config/settings.yaml`, verify `provider` and `model` settings

**Problem**: Database locked errors
- **Solution**: Close all database connections, check for multiple server instances

**Problem**: Cache not matching expected results
- **Solution**: Clear `category_map_cache` table and re-run classification, check `multi_purpose_app_names` list

## Testing

**Test Directory**: `lifeprism/llm/llm_classify/tests/`

Run tests with pytest (if configured):
```bash
cd lifeprism
pytest llm/llm_classify/tests/
```

Note: Test infrastructure is still in development.
