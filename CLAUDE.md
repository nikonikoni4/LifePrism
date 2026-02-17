# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## 外部文档加载规则

以下文档包含详细的代码规范和业务逻辑。**必须在对应场景下先读取再编码**：

| 触发场景 | 必须先读取的文档 |
|---------|----------------|
| 新建或修改后端模块（API / Service / Provider / Schema） | `docs/claude/backend-style-guide.md` |
| 修改 `taskpool_service` 或任何 PlanDoc / todoblock 相关代码 | `docs/claude/plandoc-sync.md` |
| 需要了解项目架构、数据流、分类系统、缓存策略 | `docs/claude/architecture.md` |
| 环境搭建、启动命令、配置修改、问题排查 | `docs/claude/project-setup.md` |
| 修改路径解析、数据目录、数据迁移、`settings_manager` 路径相关代码 | `docs/claude/path-config.md` |

**执行标准**：触发场景命中时，必须在编码前使用 Read 工具加载对应文档。不确定是否命中时，加载比不加载好。

---

## Rules

### 语言

对话时除了专有名词外，使用中文回答。

### 工作流程规则

1. **先方案后编码**：编写任何代码之前，先描述方案等待批准。需求不明确时先提问。
2. **拆分大任务**：修改超过 3 个文件时，先分解为更小的任务。
3. **列出风险**：编码后列出可能的问题，建议测试用例覆盖。
4. **困难bug排查**: 对于困难的bug，涉及到多个区域，或难以排查的bug，应该优先编写debug进行测试进行快速排查
5. **Bug 先测试**：修 bug 先写复现测试，再修复直到通过。
6. **记录教训**：每次被纠正后，在 CLAUDE.md 新增规则防止再犯。
7. **测试目录**：所有测试放在 test/ 目录下。

### 设计原则

7. **单一数据源（SSOT）**：禁止多文件重复硬编码同一数据。
   - 2 个及以上文件使用同一硬编码值 → 必须抽取到唯一数据源
   - 全局共享的配置信息（即使当前只有 1 处使用）→ 应提前抽取
   - 前后端共享数据：后端为数据源，前端通过 API 获取，禁止各自硬编码

8. **重构先搜索**：重构接口/常量/模块时，必须先搜索所有引用点，按引用数量选策略。
   - 0 个引用 → 直接删除
   - 1-5 个同模块内 → 一次性全改
   - 5-15 个跨模块 → 分步重构
   - 15+ 个或公开 API → 薄兼容层（只做一行转发，标注 DEPRECATED）
   - 兼容层代码行数不应超过被兼容接口的行数

9. **难度评估与暂停机制**：接到任务后必须先评估难度，不能未理清全貌就编码。
   - 低难度（局部改动）→ 正常执行
   - 中难度（跨 2-3 模块）→ 先说明方案和难点，获确认后执行
   - 高难度（架构变更、多模块联动）→ **必须暂停**，报告问题范围、难点、建议方案

   **暂停信号**（任一出现必须暂停）：
   - 任务前提假设可能有误
   - 需要改变已有架构约定（数据源、依赖方向、加载顺序）
   - 问题根因不明确，存在多种可能
   - 需要引入"临时妥协"或 bridge 层

   **禁止**：问题全貌不清时就编码 / 用"先临时方案后续优化"回避难点 / 上下文变化后沿用旧思路

10. **兼容决策前置**：接口变更、数据源迁移、模块职责调整时，必须在**规划阶段**向用户提出兼容性问题，不能编码时临时决定。
    - 列出哪些需要兼容、哪些直接重构、兼容的生命周期
    - 禁止因"怕改动大"默认选择兼容，应根据引用数量客观判断
    - 禁止沿用旧数据流方向做兼容

### 前端规则

1. **TaskPoolView 虚拟滚动禁止移除**：`@tanstack/react-virtual` 是必须保留的性能方案。视觉重叠是库的固有限制，不是 bug。优化只能调整 `estimateSize`/`measureElement`/`paddingBottom`，不能改为普通列表。

2. **Todo 操作必须通过 useTaskPoolStore**：禁止直接调用 `taskPoolApi`。原因：store 内置 PlanDoc 保存 Hook（`triggerAllPlanDocSaves`），操作前先保存编辑器内容，操作后刷新编辑器，避免 MD 文件冲突。

### 后端规则

1. **模块创建流程**：数据表 → `database.py` | Provider → `server/providers/` 继承 `LWBaseDataProvider` | Schema → `schemas/`

2. **Service 单例判断**：有状态缓存 → `LazySingleton`，无状态 → 纯函数模块。
   - 需要单例：ID→Name 映射缓存 / 实体关系映射缓存 / DataFrame 列表缓存 / 运行时实例状态
   - 不需要单例：纯数据查询（无内存缓存）/ 仅持有 provider 引用 / 数据库层面缓存
   - 有缓存的 service 必须提供 `_refresh_cache()` 方法

3. **Service 函数禁止写参数默认值**：默认值只在 API 层定义（`Query(default=...)` / `Field(default=...)`）。原因：前端未传字段时 API 层传入 `None`，若 service 有默认值会覆盖 `None`，导致"未填写"被误判为"填了默认值"。

4. **ID 优先原则**：关联、查找、缓存 key 必须用 `id`，禁止用用户可修改的 `name`。
   - 适用：实体关联、数据查找、缓存 key、API 参数、前端存储传递
   - 不适用：纯展示、UNIQUE 约束、搜索功能
   - **LLM 边界例外**：LLM 输出 name 是允许的，但必须在边界处转换为 id 后存储，并校验 name 存在性

5. **路径统一通过 settings_manager**：
   - `settings_manager` 是路径唯一数据源，禁止其他模块自行解析路径或读环境变量
   - DB 路径用 `settings.lw_db_path` / `settings.chat_db_path`
   - 数据目录用 `settings.lifeprism_data_path`
   - 路径优先级：环境变量 `LIFEPRISM_DATA_PATH` → yaml 配置 → 打包默认 `%LOCALAPPDATA%/LifePrism/lifeprismData` → 开发默认 `localData`
   - 数据目录结构：`config/` | `dataset/` | `plan/` | `debug_logs/` | `workflow/`

6. **Logger 与 Settings 加载顺序**（脆弱约定，勿破坏）：
   - `logger.py` 模块级只配置 StreamHandler（控制台），不配置 FileHandler
   - `settings_manager._initialize()` 末尾调用 `setup_file_logging(log_dir)` 添加 FileHandler
   - `main.py` 第一个 lifeprism import 必须是 `from lifeprism.config.settings_manager import settings`
   - 这保证后续所有模块的 `get_logger()` 都能写入日志文件

7. **异常处理规范**：
   - **层级职责**：
     - Provider 层：捕获外部异常（sqlite3.Error, IOError 等），转换为业务异常（DataAccessError, NotFoundError 等）
     - Service 层：通常让异常自然冒泡；仅在聚合多步操作（需回滚/清理）或补充业务上下文时捕获包装
     - API 层：捕获业务异常映射为 HTTPException；main.py 注册全局 exception_handler 兜底
   - **允许 try/except 的场景**：外部 I/O 边界、不可信数据解析（JSON/日期/数字）、全局兜底 handler
   - **禁止的模式**：
     - 内部业务逻辑的 try/except（bug 应暴露而非捕获）
     - catch-and-return-default（except → return None/False/[]/0），错误必须以异常传播
     - except Exception 宽泛捕获（全局兜底 handler 除外），必须捕获具体异常类型
   - **冒泡原则**：不需要额外处理的异常让其自然冒泡，不写 catch-log-rethrow
   - **异常类定义**：统一放 `utils/exceptions.py`，继承 `LWBaseError`；新模块若需特有异常，在同文件新增
   - **迁移策略**：新代码必须遵守。修改现有文件时仅重构自己触及的函数

### 业务规则

- **Goal 自动追踪条件**：`track_time_automatically == 1` AND `status == "active"` AND 已设定分类类别。只有满足全部条件的 goal 才传入分类器（`data_processing_service.py`）。

---

## Project Overview

**LifeWatch-AI** (LifePrism)：AI 驱动的个人时间管理平台，通过 ActivityWatch 监控电脑活动，LLM 分类应用，React 前端展示。

```
LifeWatch-AI/
├── frontend/              # React + TypeScript + Vite + Electron（apps/core/shell 三层架构）
│   ├── apps/              # lifewatch / goals / habits / settings / mindspace / addons
│   ├── core/              # 共享组件、服务、类型、Hooks
│   └── shell/             # ModuleDock 导航、全局布局
├── lifeprism/             # Python 后端
│   ├── server/            # FastAPI（api/ services/ schemas/ providers/）
│   ├── llm/               # LLM 分类系统
│   ├── processors/        # 数据处理管道（data_clean.py）
│   ├── storage/           # 数据库层（database_manager, lw_table_manager）
│   └── config/            # 配置（settings_manager, database.py）
└── docs/                  # 文档
```

**子模块**：`frontend/`、`lifeprism/llm/custom_prompt`、`lifeprism/llm/llm_linear_executor`

**API 文档**：http://localhost:8000/docs (Swagger UI)
