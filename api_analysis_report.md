# LifeWatch-AI 前后端 API 架构分析报告

## 一、当前项目数据结构和 API 结构分析

### 1.1 前端数据结构 (`types.ts`)

前端定义了 **18 个核心接口**，按功能可分为以下类别：

#### 📊 仪表盘相关
| 接口名称 | 用途 | 关键字段 |
|---------|------|----------|
| `DashboardResponse` | 仪表盘主数据 | `date`, `total_active_time`, `summary` |
| `DashboardSummary` | 统计摘要 | `top_apps`, `top_titles`, `categories_by_default` |
| `TopItem` | 排行榜项目 | `name`, `duration`, `percentage` |
| `CategorySummary` | 分类统计 | `category`, `duration`, `percentage` |

#### 📈 时间概览相关
| 接口名称 | 用途 | 关键字段 |
|---------|------|----------|
| `TimeOverviewResponse` | 时间分布图表 | `pieData`, `barData`, `details` |
| `ChartSegment` | 饼图数据段 | `key`, `name`, `value`, `color` |
| `BarConfig` | 柱状图配置 | `key`, `label`, `color` |
| `TimeDistribution` | 时间分布数据 | `timeRange`, `[key]: number` |

#### 🕐 时间线相关
| 接口名称 | 用途 | 关键字段 |
|---------|------|----------|
| `TimelineResponse` | 时间线响应 | `date`, `events`, `currentTime` |
| `TimelineEventData` | 时间线事件 | `startTime`, `endTime`, `title`, `category`, `subCategoryId` |

#### 🏷️ 分类管理相关
| 接口名称 | 用途 | 关键字段 |
|---------|------|----------|
| `CategoryDef` | 主分类定义 | `id`, `name`, `color`, `subCategories` |
| `SubCategoryDef` | 子分类定义 | `id`, `name` |
| `ActivityRecord` | 活动记录 | `appName`, `windowTitle`, `categoryId` |

---

### 1.2 前端 API 服务层 (`services/`)

共有 **5 个服务文件**，封装了所有后端 API 调用：

```
frontend/services/
├── dashboardService.ts   # 5 个方法：getTimeOverview, getDashboardData, getActivitySummaryData, getHomepageData, getTimelineOverview
├── timelineService.ts    # 2 个方法：getTimelineData, updateEventCategory
├── syncService.ts        # 4 个方法：syncActivityWatchData, incrementalSync, fullSync, syncActivityWatchDataByTimeRange
├── categoryService.ts    # 7 个方法：getAllCategories, createCategory, updateCategory, deleteCategory, + 3个子分类方法
└── geminiService.ts      # AI 对话服务
```

---

### 1.3 后端 API 路由 (`lifewatch/server/api/`)

共有 **6 个 API 路由模块**，注册在 `/api/v1` 前缀下：

| 模块 | 前缀 | 端点数量 | 主要功能 |
|------|------|----------|----------|
| `dashboard.py` | `/dashboard` | 5 | 仪表盘、时间概览、首页、时间线 |
| `timeline.py` | `/timeline` | 2 | 时间线事件、时间范围概览 |
| `categories.py` | `/categories` | 10 | 分类 CRUD（主分类 + 子分类） |
| `sync.py` | `/sync` | 2 | ActivityWatch 数据同步 |
| `activity_summary_api.py` | `/activity-summary` | 1 | 活动总结 |
| `behavior.py` | `/behavior` | 1 | 行为日志 |

---

### 1.4 后端数据模式 (`lifewatch/server/schemas/`)

共有 **11 个 Pydantic 模型文件**：

```
lifewatch/server/schemas/
├── dashboard_schemas.py    # TimeOverviewResponse, ChartSegment, BarConfig
├── timeline_schemas.py     # TimelineEventSchema, TimelineResponse, TimelineOverviewResponse
├── category_schemas.py     # CategoryListResponse, CategoryResponse, SubCategoryResponse, CreateCategoryRequest...
├── categories.py           # AppCategoryList, AppCategory, UpdateCategoryRequest
├── sync.py                 # SyncRequest, SyncTimeRangeRequest, SyncResponse
├── activity_summary_schemas.py
├── behavior.py
├── dashboard.py
├── homepage.py
└── response.py             # StandardResponse（通用响应）
```

---

## 二、优秀 API 架构应具备的特征

### 2.1 设计原则

| 原则 | 描述 | 当前项目状态 |
|------|------|-------------|
| ✅ **RESTful 规范** | 使用标准 HTTP 方法和资源导向 URL | ✅ 已实现 |
| ✅ **版本控制** | API 路径包含版本号 | ✅ `/api/v1` |
| ✅ **统一响应格式** | 所有响应采用一致的 JSON 结构 | ⚠️ 部分实现 |
| ✅ **类型安全** | 请求/响应有明确的类型定义 | ✅ Pydantic + TypeScript |
| ✅ **文档化** | 自动生成 API 文档 | ✅ FastAPI Swagger/ReDoc |
| ⚠️ **错误处理规范** | 统一的错误码和错误消息格式 | ⚠️ 需要改进 |
| ❌ **认证授权** | JWT/OAuth2 等安全机制 | ❌ 缺失 |
| ⚠️ **分页机制** | 列表接口支持分页 | ⚠️ 部分实现 |
| ❌ **速率限制** | 防止 API 滥用 | ❌ 缺失 |
| ⚠️ **缓存策略** | 响应缓存头配置 | ⚠️ 未配置 |

---

### 2.2 数据传输优化

| 特性 | 描述 | 当前项目状态 |
|------|------|-------------|
| ✅ **聚合 API** | 减少网络请求 | ✅ `/dashboard/homepage` 整合了 3 个 API |
| ✅ **字段别名** | 驼峰/蛇形命名转换 | ✅ Pydantic `alias` 配置 |
| ⚠️ **字段过滤** | 客户端按需获取字段 | ❌ 未实现 (GraphQL 风格) |
| ⚠️ **压缩传输** | gzip 压缩响应体 | ⚠️ 依赖服务器配置 |

---

### 2.3 代码组织规范

| 特性 | 描述 | 当前项目状态 |
|------|------|-------------|
| ✅ **分层架构** | Router → Service → Provider → DB | ✅ 已实现 |
| ✅ **依赖注入** | 服务层解耦 | ⚠️ 部分实现 |
| ✅ **模块化** | 按功能划分模块 | ✅ 已实现 |
| ⚠️ **接口契约测试** | 前后端类型同步 | ⚠️ 手动维护，无自动化 |

---

## 三、当前项目存在的问题

### 3.1 🔴 严重问题

#### 1. 类型名称不一致
```
问题：categoryService.ts 中类名拼写错误
位置：frontend/services/categoryService.ts:24
错误：export class categoryPI  ← 应为 CategoryAPI
```

#### 2. API 基础 URL 不一致
```
问题：不同服务文件使用不同的 BASE_URL 格式
dashboardService.ts: const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';
syncService.ts:      const API_BASE_URL = 'http://localhost:8000/api/v1';
建议：应统一为环境变量配置
```

#### 3. API 路径重复定义
```
问题：Timeline API 在两个路由模块中重复定义
位置：
  - dashboard.py: @router.get("/timeline", ...)  → /api/v1/dashboard/timeline
  - timeline.py:  @router.get("", ...)           → /api/v1/timeline
建议：统一到一个路由模块
```

---

### 3.2 🟡 中等问题

#### 4. 前后端类型不同步
```
问题：后端 Schema 使用 snake_case，前端需要手动维护 camelCase 映射
示例：
  后端：sub_category_id (Python)
  前端：subCategoryId (TypeScript)
建议：使用代码生成工具（如 openapi-typescript）自动生成前端类型
```

#### 5. 缺少通用错误处理
```
问题：前端服务仅抛出 Error，没有统一的错误类型
示例：throw new Error(`Failed to fetch: ${response.statusText}`);
建议：定义 ApiError 类，包含 status, code, message
```

#### 6. 硬编码的 Mock 数据
```
问题：constants.ts 包含大量 Mock 数据与实际 API 类型混合
位置：frontend/constants.ts (210行)
建议：将 Mock 数据移至独立的 __mocks__ 目录或测试文件
```

#### 7. 缺少请求/响应拦截器
```
问题：每个服务方法都重复 fetch + 错误处理逻辑
建议：创建统一的 apiClient 封装，处理：
  - 请求头设置
  - 响应状态检查
  - 错误转换
  - 日志记录
```

---

### 3.3 🟢 改进建议

#### 8. API 响应缺少元数据
```
当前：直接返回数据数组或对象
建议：统一响应包装
{
  "success": true,
  "data": {...},
  "meta": {
    "timestamp": "2024-12-18T14:00:00Z",
    "request_id": "uuid"
  }
}
```

#### 9. 缺少 API 请求取消机制
```
问题：页面切换时未取消进行中的请求
建议：使用 AbortController 实现请求取消
```

#### 10. 日期格式不统一
```
问题：部分接口使用 date 对象，部分使用字符串
示例：
  dashboard.py: query_date: date     # Python date 对象
  timeline.py:  date: str            # YYYY-MM-DD 字符串
建议：统一使用 ISO 8601 字符串格式
```

---

## 四、改进优先级建议

| 优先级 | 问题 | 建议操作 |
|--------|------|----------|
| **P0** | 类名拼写错误 `categoryPI` | 立即修复为 `CategoryAPI` |
| **P0** | API 路径重复 | 整合 Timeline 路由 |
| **P1** | BASE_URL 不一致 | 使用环境变量统一配置 |
| **P1** | 创建统一 apiClient | 封装 fetch + 错误处理 |
| **P2** | 自动生成前端类型 | 集成 openapi-typescript |
| **P2** | 添加请求取消机制 | 使用 AbortController |
| **P3** | Mock 数据分离 | 移至 __mocks__ 目录 |
| **P3** | 统一日期格式 | 全部使用 ISO 8601 字符串 |

---

## 五、总结

### 5.1 当前架构优点
1. ✅ 采用 RESTful 设计，路径清晰
2. ✅ FastAPI + Pydantic 提供强类型和自动文档
3. ✅ 前端 TypeScript 接口定义完善
4. ✅ 聚合 API (`/homepage`) 减少请求次数
5. ✅ 分层架构（Router → Service → Provider）清晰

### 5.2 主要改进方向
1. 🔧 统一命名规范和 API 基础 URL 配置
2. 🔧 消除 API 路径重复定义
3. 🔧 创建统一的前端 API 客户端封装
4. 🔧 自动化前后端类型同步
5. 🔧 补充认证授权机制（后续阶段）
