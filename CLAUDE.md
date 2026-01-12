# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

### Frontend (React + Vite)

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
```

**Frontend Dev Server**: http://localhost:3000
**API Proxy**: `/api` → `http://localhost:8000` (configured in `vite.config.ts`)

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

**Documentation**: `lifeprism/llm/llm_classify/data_driving_agent/README.md`

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

The frontend uses a simple page-based routing system (not React Router):

| Page | Component | Status | Route |
|------|-----------|--------|-------|
| Home | `page/home/Home` | ✅ Complete | `currentPage === 'home'` |
| Timeline | `page/timeline/Timeline` | ✅ Complete | `currentPage === 'timeline'` |
| Category | `page/category/CategoryPage` | ✅ Complete | `currentPage === 'category'` |
| Goals | `page/goals/GoalsPage` | 🚧 In Progress | `currentPage === 'goals'` |
| Chatbot | `page/chatbot/` | ✅ Complete | Overlay panel (controlled by `chatDisplayMode`) |
| Reports | `page/reports/ReportsPage` | 🚧 In Progress | `currentPage === 'reports'` |
| Settings | `page/settings/SettingsPage` | ✅ Complete | `currentPage === 'settings'` |
| Usage | `page/usage/UsagePage` | ✅ Complete | `currentPage === 'usage'` |

**Navigation**: Controlled by `App.tsx` state `currentPage` and `<Sidebar>` component

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

## Dependencies

### Backend Key Dependencies
- `fastapi`: Web framework
- `langgraph>=1.0.0`: LLM agent orchestration
- `requests>=2.25.0`: HTTP client

### Frontend Key Dependencies
- `react@^19.2.1`: UI framework
- `vite@^6.2.0`: Build tool
- `@google/genai`: Google AI SDK
- `echarts`, `recharts`: Data visualization
- `framer-motion`: Animations
- `lucide-react`: Icons
- `react-markdown`: Markdown rendering

## License

Apache License 2.0 - see `LICENSE` file for details.
