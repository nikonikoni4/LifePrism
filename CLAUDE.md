# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## rules

### 通用rules

1. 在编写任何代码之前，请先描述你的方案，等待批准，如果需求不明确，在编写任何代码之前，务必提出澄清问题。
2. 如果一项任务需要修改超过三个文件，先停下来，将其分解成更小的任务。
3. 编写代码后，列出可能出现的问题，并建议相应的测试用例来覆盖这些问题。
4. 当发现bug首先需要编写一个能够重现该bug的测试，然后不断修复它，直到它通过测试为止。
5. 每次我纠正你之后，就在claude.md文件中新增加一条规则，这样就不会再发生这种情况了。
6. 所有测试内容都应该在test文件夹下，并且需要编写对应的测试用例。
7. **单一数据源原则（Single Source of Truth）**：当同一份硬编码数据（如配置映射、枚举值、常量列表等）需要在多处使用时，**禁止在多个文件中重复硬编码**，必须抽取到唯一的数据源文件中，其他所有使用方通过导入/引用该数据源获取数据。必要时，请求用户，是否需要将该数据源抽取到单独的外部文件中，比如yaml，json文件。

   **判断标准**：
   - 如果一个硬编码值（字典、列表、映射、常量等）已经或即将出现在 **2 个及以上文件** 中，必须进行同源处理
   - 即使当前只在一个文件中使用，但该数据本质上是**全局共享的配置信息**（如模型名称映射、服务商配置、功能开关等），也应提前抽取

   **做法**：
   - 后端：在合适的配置模块（如 `config/`）中定义唯一数据源，其他模块 `import` 使用
   - 前端：在合适的常量/配置文件中定义唯一数据源，其他模块 `import` 使用
   - 前后端共享的数据：由后端作为数据源，前端通过 API 获取，**不要前后端各自硬编码一份**

   **示例**：
   ```python
   # ❌ 错误：多个文件各自硬编码模型映射
   # file_a.py
   MODEL_MAP = {"qwen-plus": "qwen-plus-2025-01-01", ...}
   # file_b.py
   MODEL_MAP = {"qwen-plus": "qwen-plus-2025-01-01", ...}  # 重复！

   # ✅ 正确：唯一数据源 + 导入
   # config/model_config.py（唯一数据源）
   MODEL_MAP = {"qwen-plus": "qwen-plus-2025-01-01", ...}
   # file_a.py / file_b.py
   from config.model_config import MODEL_MAP
   ```

8. **重构策略规则（Refactor Strategy）**：重构接口/常量/模块时，**必须先搜索旧接口的所有引用点**，根据影响范围选择策略，禁止盲目添加向后兼容代码。

   **第一步：量化影响范围**：
   - 使用全局搜索（Grep/IDE）找出所有 `import`、直接引用、`__all__` 导出
   - 统计：影响了多少个文件？多少个调用点？是否涉及外部/公开 API？

   **第二步：根据引用数量选择策略**：

   | 引用点数量 | 策略 | 说明 |
   |-----------|------|------|
   | 0 个 | **直接删除**，不兼容 | 没人用，删了最干净 |
   | 1-5 个且同模块内 | **一次性全改**，不兼容 | 改动可控，一个 commit 搞定 |
   | 5-15 个跨模块 | **分步重构**：先加新接口 → 逐步迁移调用方 → 删旧接口 | 每步可独立验证 |
   | 15+ 个或涉及公开 API | **必须兼容**，但遵循薄兼容层原则 | 见下方 |

   **第三步：薄兼容层原则（如果必须兼容）**：
   - 兼容代码只做**一行转发**，禁止引入缓存、包装类、`property` 技巧等额外逻辑
   - **兼容层的代码行数不应超过被兼容接口的行数**，如果兼容代码比新代码还复杂，说明方案有问题
   - 兼容代码必须标注 `# DEPRECATED: 使用 xxx 替代` 注释

   **示例**：
   ```python
   # ✅ 正确的兼容：一行转发，零逻辑
   def get_support_provider():
       """DEPRECATED: 使用 provider_manager.provider_list 替代"""
       return provider_manager.provider_list

   # ❌ 错误的兼容：自建缓存 + 包装类 + 语法误用
   _cached = None
   def _get_cached():
       global _cached
       if _cached is None:
           _cached = get_support_provider()
       return _cached
   class _Constants:
       @property
       def SUPPORT_PROVIDER(self): ...
   SUPPORT_PROVIDER = property(lambda self: ...)  # 模块级 property 根本不工作
   ```

### 语言

对话时除了专有名词外，需要使用中文回答

### 前端 rules

1. **任务池虚拟滚动 - 禁止修改**：`TaskPoolView.tsx` 使用 `@tanstack/react-virtual` 实现虚拟滚动，这是**必须保留**的性能优化方案。

   **原因**：
   - 前端一次性从后端获取所有 Todo 数据（无分页）
   - 任务数量可能很大，普通渲染会导致严重性能问题
   - 虚拟滚动只渲染可视区域内的元素，大幅提升性能

   **已知问题**：
   - 虚拟滚动的动态高度测量可能导致轻微的视觉重叠
   - 这是虚拟滚动库的固有限制，不是 bug
   - **不要尝试通过移除虚拟滚动来"修复"这个问题**

   **如果需要优化**：
   - 可以调整 `estimateSize` 的估计值
   - 可以调整 `measureElement` 的测量逻辑
   - 可以调整元素的 `paddingBottom` 间距
   - **不要移除虚拟滚动改为普通列表渲染**

2. **Todo 操作必须通过 useTaskPoolStore**：所有 Todo 的增删改操作（创建、更新、删除、状态变更）必须通过 `useTaskPoolStore` 进行，**禁止直接调用 `taskPoolApi`**。

   **原因**：
   - `useTaskPoolStore` 内置了 PlanDoc 保存 Hook（`triggerAllPlanDocSaves`）
   - 在任何 Todo 操作前，会先触发 PlanDoc 编辑器的未保存内容保存
   - 避免 PlanDoc 编辑器内容与 MD 文件产生冲突

   **冲突场景**：
   - 用户在 PlanDoc 编辑器修改文本（未保存）
   - 同时在任务池勾选 todo → 后端更新 DB 和 MD 文件
   - PlanDoc 编辑器的未保存内容与 MD 文件不同步

   **正确做法**：
   ```typescript
   // ✅ 正确：通过 store 操作
   const { updateTask, addTask, deleteTask } = useTaskPoolStore();
   await updateTask(id, { state: 'completed' });
   await addTask(newTodo);
   await deleteTask(id);

   // ❌ 错误：直接调用 API（绕过保存 Hook）
   await taskPoolApi.updateTodo(id, { state: 'completed' });
   await taskPoolApi.createTodo(data);
   await taskPoolApi.deleteTodo(id);
   ```

   **相关文件**：
   - `frontend/apps/goals/hooks/useTaskPoolStore.ts` - Todo 状态管理
   - `frontend/apps/goals/hooks/usePlanDocSaveHook.ts` - PlanDoc 保存 Hook 注册机制

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
     # 注意：以下是函数内的临时局部变量，仅用于一次性 name→id 转换，
     # 不是 service 级别的持久缓存，因此不违反"缓存 key 不能用 name"的规则
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

6. **外部存储路径规范**：所有外部存储的路径（如数据库、计划书 md、日志文件等）统一通过 `settings_manager` 获取。

   **核心原则**：
   - `settings_manager` 是路径的**唯一数据源**，所有模块通过 `settings.lifeprism_data_path` 获取数据目录
   - 禁止在其他模块中自行解析路径或读取环境变量
   - 数据库路径（`lw_db_path`、`chat_db_path`）由 `settings_manager` 自动推算，不需要单独配置

   **`settings.lifeprism_data_path` 路径解析优先级**（在 `settings_manager._resolve_default_data_path()` 中）：
   1. 环境变量 `LIFEPRISM_DATA_PATH`（由 Electron 启动时设置）
   2. yaml 配置中的 `lifeprism_data_path`（用户在设置页面自定义）
   3. 打包环境默认：`%APPDATA%/LifePrism/lifeprismData`
   4. 开发环境默认：`frontend/lifeprismData`

   **数据目录结构**：
   ```
   lifeprismData/
   ├── config/          # 配置文件（config.yaml, providers.yaml）
   ├── dataset/         # 数据库文件（lifewatch_ai.db, chat_history.db）
   ├── plan/            # 计划书 MD 文件
   ├── debug_logs/      # 日志文件（打包环境）
   └── workflow/        # LLM workflow 配置
   ```

   **适用场景**：
   - 数据库文件路径（`.db`）→ 使用 `settings.lw_db_path` / `settings.chat_db_path`
   - 计划书/文档路径（`.md`）→ 使用 `Path(settings.lifeprism_data_path) / "plan"`
   - 用户配置文件 → 使用 `Path(settings.lifeprism_data_path) / "config"`
   - 任何需要持久化存储的外部资源

   **示例**：
   ```python
   from lifeprism.config.settings_manager import settings

   # ✅ 正确：通过 settings 获取路径
   data_dir = Path(settings.lifeprism_data_path)
   plan_doc_path = data_dir / "plan" / f"{plan_id}.md"

   # ✅ 正确：数据库路径直接用属性
   db_path = settings.lw_db_path

   # ❌ 错误：硬编码绝对路径
   plan_doc_path = Path("D:/desktop/plans/plan.md")

   # ❌ 错误：直接读取环境变量获取路径
   data_path = os.environ.get('LIFEPRISM_DATA_PATH')

   # ❌ 错误：不区分环境直接使用相对路径
   plan_doc_path = Path("frontend/lifeprismData/plan/plan.md")
   ```

   **注意事项**：
   - 在 `lifeprismData` 目录下按功能创建子目录（如 `plan/`, `debug_logs/`, `workflow/`）
   - 确保目录存在后再写入文件：`path.parent.mkdir(parents=True, exist_ok=True)`
   - 打包后的路径结构：`%APPDATA%/LifePrism/lifeprismData/`（独立于安装目录）

   **Logger 与 Settings 的加载顺序**：
   - `logger.py` 模块级只配置 `StreamHandler`（控制台），不配置 `FileHandler`
   - `settings_manager._initialize()` 末尾调用 `setup_file_logging(log_dir)` 添加 `FileHandler`
   - `main.py` 第一个 lifeprism import 必须是 `from lifeprism.config.settings_manager import settings`
   - 这保证后续所有模块的 `get_logger()` 都能写入日志文件

## 后端代码风格规范

### API 设计规范

#### 路由定义
- 使用 `APIRouter` 创建路由组
- 前缀格式：`/{module_name}`（如 `/goal`, `/category`）
- 标签格式：`{Module}`（如 `Goal`, `Category`）
- 使用 `summary` 参数描述端点功能

#### HTTP 方法规范
- `GET`: 获取资源（幂等）
- `POST`: 创建资源
- `PATCH`: 部分更新资源
- `DELETE`: 删除资源

#### 参数验证
- 查询参数：使用 `Query()` 进行验证
- 路径参数：使用 `Path()` 进行验证
- 请求体：使用 Pydantic 模型
- 提供详细的 `description` 参数说明

#### 错误响应
- 404: 资源不存在
- 400: 参数验证失败
- 500: 服务器内部错误
- 错误消息格式：简洁、清晰、包含关键信息

**示例**：
```python
from fastapi import APIRouter, Query, HTTPException, Path

router = APIRouter(prefix="/goal", tags=["Goal"])

@router.get("/goals", response_model=GoalListResponse, summary="获取目标列表")
async def get_goals(
    status: Optional[str] = Query(default=None, description="按状态筛选 (active, completed, archived)"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量")
):
    """获取目标列表"""
    return goal_service.get_goals(status, page, page_size)

@router.get("/goals/{goal_id}", response_model=GoalItem, summary="获取目标详情")
async def get_goal_detail(
    goal_id: str = Path(..., description="目标 ID (格式: goal-xxx)")
):
    """获取目标详情"""
    result = goal_service.get_goal_detail(goal_id)
    if not result:
        raise HTTPException(status_code=404, detail="目标不存在")
    return result
```

### Schema 设计规范

#### 请求模型
- 命名：`Create{Entity}Request`, `Update{Entity}Request`
- 必需字段：`Field(..., description="...")`
- 可选字段：`Optional[T] = Field(default=None, description="...")`
- 字段验证：使用 `ge`, `le`, `min_length` 等约束

#### 响应模型
- 命名：`{Entity}Item`, `{Entity}ListResponse`
- 包含完整的字段信息
- 使用 `Field(..., description="...")` 提供字段说明

#### 部分更新请求
- 所有字段都应该是 `Optional[T]`
- 允许用户只更新需要修改的字段

**示例**：
```python
from pydantic import BaseModel, Field
from typing import Optional, List

class CreateGoalRequest(BaseModel):
    """创建目标请求"""
    name: str = Field(..., description="目标名称")
    content: str = Field(default="", description="目标内容")
    color: str = Field(default="#5B8FF9", description="目标颜色")
    link_to_category_id: Optional[str] = Field(default=None, description="关联分类 ID")

class UpdateGoalRequest(BaseModel):
    """更新目标请求（部分更新）"""
    name: Optional[str] = Field(default=None, description="目标名称")
    content: Optional[str] = Field(default=None, description="目标内容")
    status: Optional[str] = Field(default=None, description="目标状态")

class GoalItem(BaseModel):
    """目标项"""
    id: str = Field(..., description="唯一标识符")
    name: str = Field(..., description="目标名称")
    created_at: str = Field(..., description="创建时间")

class GoalListResponse(BaseModel):
    """目标列表响应"""
    items: List[GoalItem] = Field(default=[], description="目标列表")
    total: int = Field(default=0, description="总数")
```

### 类型注解规范

#### 基本规则
- 所有函数必须有返回类型注解
- 所有参数必须有类型注解
- 使用 `Optional[T]` 表示可选值
- 使用 `Union[T1, T2]` 表示多种类型

#### 常见返回类型
- 单个对象：`Optional[Dict[str, Any]]`
- 对象列表：`List[Dict[str, Any]]`
- 列表 + 总数：`tuple[List[Dict[str, Any]], int]`
- Pydantic 模型：`GoalItem`, `GoalListResponse`

**示例**：
```python
from typing import Optional, List, Dict, Any

def get_goal_by_id(self, goal_id: str) -> Optional[Dict[str, Any]]:
    """按 ID 获取单个目标"""
    pass

def get_goals(self, page: int = 1) -> tuple[List[Dict[str, Any]], int]:
    """获取目标列表，返回 (列表, 总数)"""
    pass

async def create_goal(request: CreateGoalRequest) -> GoalItem:
    """创建新目标"""
    pass
```

### 文档字符串规范

#### Google 风格格式
- 第一行：简短的功能描述
- 空行
- Args 部分：参数说明
- Returns 部分：返回值说明
- Raises 部分（可选）：异常说明

#### 参数格式说明
- ID 参数：`"目标 ID (格式: goal-xxx)"`
- 时间参数：`"时间戳或 ISO 8601 格式"`
- 枚举参数：`"可选值: active, completed, archived"`

**示例**：
```python
def get_goals(
    self,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> tuple[List[Dict[str, Any]], int]:
    """
    获取目标列表

    Args:
        status: 按状态筛选（active, completed, archived）
        page: 页码（从1开始）
        page_size: 每页数量

    Returns:
        tuple: (目标列表, 总数)
    """
    pass

def create_goal(self, data: Dict[str, Any]) -> Optional[str]:
    """
    创建新目标

    Args:
        data: 目标数据

    Returns:
        Optional[str]: 新目标 ID (格式: goal-xxx)，失败返回 None
    """
    pass
```

### 日志记录规范

#### 日志级别
- `logger.info()`: 重要操作成功（创建、更新、删除）
- `logger.warning()`: 警告信息（未找到资源、数据异常）
- `logger.error()`: 错误信息（异常、操作失败）
- `logger.debug()`: 调试信息（缓存刷新、中间步骤）

#### 日志格式
- 包含操作描述、关键参数、结果
- 示例：`logger.info(f"成功创建目标: {goal_id}")`
- 错误日志：`logger.error(f"创建目标失败: {e}")`

**示例**：
```python
from lifeprism.utils import get_logger

logger = get_logger(__name__)

# 初始化时
logger = get_logger(__name__)

# 使用日志
logger.info(f"成功创建目标: {goal_id}")
logger.warning(f"未找到分类 {category_id}")
logger.error(f"创建目标失败: {e}")
logger.debug(f"刷新缓存成功，共 {count} 个目标")
```

### 错误处理分层规范

#### Provider 层（数据访问层）
- 返回 `None` 表示查询失败或资源不存在
- 返回空列表 `[]` 表示无结果
- 捕获异常并记录日志，不向上抛出

#### Service 层（业务逻辑层）
- 可以抛出 `ValueError` 等业务异常
- 可以返回 `None` 表示操作失败
- 调用 Provider 时检查返回值

#### API 层（路由处理层）
- 必须抛出 `HTTPException`
- 状态码：404（不存在）、400（参数错误）、500（服务器错误）
- 错误消息必须清晰、用户友好

**示例**：
```python
# Provider 层
def get_goal_by_id(self, goal_id: str) -> Optional[Dict[str, Any]]:
    try:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM goal WHERE id = ?", (goal_id,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    except Exception as e:
        logger.error(f"获取目标 {goal_id} 失败: {e}")
        return None

# Service 层
def create_goal(self, request: CreateGoalRequest) -> Optional[GoalItem]:
    try:
        new_id = self.goal_provider.create_goal(data)
        if new_id is None:
            return None
        self._refresh_cache()
        return self.get_goal_detail(new_id)
    except Exception as e:
        logger.error(f"创建目标失败: {e}")
        return None

# API 层
@router.post("/goals", response_model=GoalItem)
async def create_goal(request: CreateGoalRequest):
    try:
        result = goal_service.create_goal(request)
        if not result:
            raise HTTPException(status_code=500, detail="创建目标失败")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建目标失败: {str(e)}")
```

### 数据库操作规范

#### 基本要求

- 不能直接创建数据库对象
- 需要使用lifeprism\storage中的基础类，通过继承或直接使用单例调用数据库对象


#### 连接管理
- 使用 `with self.db.get_connection() as conn:` 管理连接
- 自动处理连接关闭和事务提交

#### 参数化查询
- 使用 `?` 作为占位符
- 参数通过元组传递：`cursor.execute(sql, (param1, param2))`
- 防止 SQL 注入

#### 结果转换
```python
# 转换为字典列表
columns = [description[0] for description in cursor.description]
rows = cursor.fetchall()
items = [dict(zip(columns, row)) for row in rows]
```

#### 事务处理
- `with` 语句自动提交事务
- 多个操作在同一 `with` 块中执行

**示例**：
```python
def get_goals(self, status: Optional[str] = None) -> tuple[List[Dict[str, Any]], int]:
    try:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 构建查询条件
            conditions = []
            params = []
            if status:
                conditions.append("status = ?")
                params.append(status)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # 执行查询
            sql = f"SELECT * FROM goal {where_clause}"
            cursor.execute(sql, params)

            # 转换为字典列表
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            items = [dict(zip(columns, row)) for row in rows]

            return items, len(items)
    except Exception as e:
        logger.error(f"获取目标列表失败: {e}")
        return [], 0

def delete_goal(self, goal_id: str) -> bool:
    try:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 先清除关联
            cursor.execute(
                "UPDATE todo_list SET link_to_goal_id = NULL WHERE link_to_goal_id = ?",
                (goal_id,)
            )

            # 然后删除
            cursor.execute("DELETE FROM goal WHERE id = ?", (goal_id,))

            # with 语句自动 commit
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"删除目标失败: {e}")
        return False
```

### Service 层职责划分

#### service 函数编写规则

- 不能在 service 中编写函数默认值

   **原因**：前端可选字段未传时，API 层传入 `None` 给 service。若 service 参数有默认值，`None` 会被默认值覆盖，导致"用户未填写"被误判为"用户填了默认值"，引发业务逻辑错误。默认值应仅在 API 层通过 `Query(default=...)` / `Field(default=...)` 定义，service 层所有参数必须由调用方显式传入。

#### 有状态 vs 纯函数 Service 判断

详见**后端 rule 4（Service 单例模式判断规则）**，此处不再重复。

#### 职责
- 调用 Provider 获取数据
- 实现业务逻辑
- 数据转换和聚合
- 缓存管理（如果有）

**示例**：
```python
# 有状态 Service
class GoalService:
    """目标服务类 - 维护 goal_name_map 缓存"""

    def __init__(self):
        self.goal_provider = goal_provider
        self.goal_name_map: Dict[str, str] = {}
        self._refresh_cache()

    def _refresh_cache(self):
        """刷新目标名称缓存"""
        try:
            items, _ = self.goal_provider.get_goals(page=1, page_size=1000)
            self.goal_name_map = {}
            for item in items:
                goal_id = str(item.get('id', ''))
                name = item.get('name', '')
                if goal_id and name:
                    self.goal_name_map[goal_id] = name
            logger.debug(f"刷新目标缓存成功，共 {len(self.goal_name_map)} 个目标")
        except Exception as e:
            logger.error(f"刷新目标缓存失败: {e}")

goal_service = LazySingleton(GoalService)

# 纯函数 Service
def get_activity_stats(date: str) -> ActivityStatsResponse:
    """获取活动统计数据"""
    pass

def get_usage_stats(date: str) -> UsageStatsResponse:
    """获取使用统计"""
    pass
```

### Provider 层职责

#### 职责
- 只负责数据库操作
- 不涉及业务逻辑
- 返回原始数据（字典或列表）
- 继承 `LWBaseDataProvider`

#### 方法命名
- `get_xxx_by_id()`: 按 ID 获取单个记录
- `get_xxxs()`: 获取多个记录
- `create_xxx()`: 创建记录
- `update_xxx()`: 更新记录
- `delete_xxx()`: 删除记录

#### 返回值
- 单个记录：`Optional[Dict[str, Any]]`
- 多个记录：`tuple[List[Dict[str, Any]], int]` (列表, 总数)
- 操作结果：`bool`

**示例**：
```python
from lifeprism.storage import LWBaseDataProvider

class GoalProvider(LWBaseDataProvider):
    """目标数据提供者"""

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def get_goal_by_id(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 获取单个目标"""
        pass

    def get_goals(self, page: int = 1, page_size: int = 20) -> tuple[List[Dict[str, Any]], int]:
        """获取目标列表"""
        pass

    def create_goal(self, data: Dict[str, Any]) -> Optional[str]:
        """创建目标，返回新 ID"""
        pass

    def update_goal(self, goal_id: str, data: Dict[str, Any]) -> bool:
        """更新目标"""
        pass

    def delete_goal(self, goal_id: str) -> bool:
        """删除目标"""
        pass

goal_provider = LazySingleton(GoalProvider)
```

### ID 生成规范

#### ID 格式
- 格式：`{prefix}-{uuid[:8]}`
- 示例：`goal-a1b2c3d4`, `cat-e5f6g7h8`

#### 前缀列表
- `goal-`: 目标
- `cat-`: 分类
- `sub-`: 子分类
- `journal-`: 日志
- `todo-`: 待办事项

#### 生成方式
```python
import uuid

def generate_id(prefix: str) -> str:
    """生成带前缀的 ID"""
    return f"{prefix}-{str(uuid.uuid4())[:8]}"

# 使用示例
goal_id = generate_id("goal")  # goal-a1b2c3d4
```

### 命名约定补充

#### 缓存变量
- 映射缓存：`_xxx_map` (如 `_category_name_map`)
- DataFrame 缓存：`_xxx_df` (如 `_categories_df`)
- 列表缓存：`_xxx_list` (如 `_active_goals_list`)

#### 私有方法
- 前缀：`_` (如 `_refresh_cache()`, `_convert_to_dict()`)

#### 常量
- 全大写：`CONSTANT_NAME`
- 示例：`DEFAULT_PAGE_SIZE = 20`

#### 类成员变量
- 公共缓存：无前缀 (如 `self.category_name_map`)
- 私有缓存：`_` 前缀 (如 `self._categories_df`)
- 依赖注入：无前缀 (如 `self.goal_provider`)

**示例**：
```python
class CategoryService:
    def __init__(self):
        # 公共缓存
        self.category_name_map: Dict[str, str] = {}
        self.sub_to_parent_map: Dict[str, str] = {}

        # 私有缓存
        self._categories_df = None
        self._sub_categories_df = None

        # 依赖注入
        self.server_lw_data_provider = server_lw_data_provider
        self.db = server_lw_data_provider.db

    def _refresh_cache(self):
        """私有方法：刷新缓存"""
        pass

    def _convert_to_dict(self, row):
        """私有方法：转换为字典"""
        pass

# 常量
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
```
 
## 业务模块

在这个模块中会记录一些重要的业务逻辑变更，若代码中存在与之不符合的逻辑，需要以这个模块的内容为准

### goal 模块

#### 用户目标追踪

goal表中新增track_time_automatically字段，只有track_time_automatically == 1 ，status =="active"并且设定了分类类别的goal才能被自动追踪（数据处理时，lifeprism\server\services\data_processing_service.py 将goal传入分类器中）

### 计划书 MD 文档同步规则

计划书（PlanDoc）使用 Markdown 文件存储任务列表，通过 `taskpool_service.py` 实现 MD 与数据库的双向同步。

#### Todoblock 格式规范

**基本结构**：
```markdown
<!-- lp:todoblock -->
- [ ] 任务内容 <!-- lp:t-a1b2c3d4 -->
	- [x] 子任务 <!-- lp:t-e5f6g7h8 -->
<!-- /lp:todoblock -->
```

**关键特性**：
- 支持多个 todoblock，每个 block 独立解析
- 父子关系仅在同一 block 内有效（不跨 block）
- 若 MD 文件无 todoblock，同步时自动创建

#### 锚点（Anchor）格式

**格式**：`<!-- lp:t-{uuid[:8]} -->`

**规则**：
- 前缀固定为 `t-`，后跟 UUID 前 8 位十六进制字符
- 锚点必须在任务行末尾
- 每个任务必须有唯一锚点（用于 MD 和数据库关联）
- 无锚点的任务在同步时自动生成

#### 任务行格式

**完整格式**：`{Tab缩进}- [{空格或x}] {内容} <!-- lp:t-xxx -->`

**解析正则**：
```python
r'^(\t*)-\s*\[([ xX])\]\s*(.+?)(?:\s*<!--\s*lp:(t-[a-f0-9]+)\s*-->)?$'
```

**示例**：
```markdown
- [ ] 根任务 <!-- lp:t-a1b2c3d4 -->
	- [x] 子任务 1 <!-- lp:t-e5f6g7h8 -->
	- [ ] 子任务 2 <!-- lp:t-i9j0k1l2 -->
		- [ ] 孙任务 <!-- lp:t-m3n4o5p6 -->
```

#### 缩进与父子关系

**规则**：
- 缩进级别 = Tab 字符数（必须用 Tab，不能用空格）
- 0 个 Tab = 根任务，1 个 Tab = 一级子任务，以此类推
- 父子关系仅在同一 todoblock 内有效

**算法**（栈结构）：
1. 遍历任务，弹出栈中所有 level >= 当前 level 的项
2. 栈顶元素的 anchor_id 即为当前任务的父任务
3. 当前任务入栈

#### 状态同步规则

**MD → DB（同步时）**：
| MD Checkbox | 数据库 state | 说明 |
|------------|-------------|------|
| `[ ]` | 保持原状态 | 不改变 pool/scheduled |
| `[x]` | `completed` | 设置 `actual_finished_at` |

**重要限制**：同步时只能 `[ ]` → `[x]`，不能 `[x]` → `[ ]`

**DB → MD（回写时）**：
| 触发条件 | 操作 |
|---------|------|
| `state` 变为 `completed` | `[ ]` → `[x]` |
| `state` 从 `completed` 变为其他 | `[x]` → `[ ]` |
| `content` 变更 | 更新 MD 中的任务内容 |

#### 同步流程（sync_plan_doc）

```
1. 验证计划书存在
2. 读取 MD 文件
3. 获取所有 todoblock
4. 解析每个 block 中的任务
5. 为无锚点的任务生成锚点并写回 MD
6. 构建父任务映射（每个 block 独立）
7. 获取现有任务（数据库）
8. 检测待删除任务（DB 有但 MD 无）
9. 处理每个任务（存在→更新，不存在→创建）
10. 执行数据库操作
11. 处理删除（需 confirm_delete=True）
12. 保存 MD 文件
```

**参数**：
- `dry_run=True`：预检模式，只返回差异不执行
- `confirm_delete=True`：确认删除 DB 中多余的任务

#### 任务创建与插入

**插入策略**（`_insert_todo_to_md`）：
- 有 `parent_anchor_id` → 插入到父任务所在的 block
- 无 `parent_anchor_id` → 插入到第一个 todoblock
- 缩进级别 = 父任务缩进 + 1
- 插入位置 = 父任务的最后一个子任务之后

**子任务继承**（`create_todo_v2`）：
- 自动继承父任务的 `plan_doc_id`
- 自动继承父任务的 `link_to_goal_id`

#### 任务删除

**删除流程**（`delete_todo`）：
1. 从 MD 删除任务及其所有子任务
2. 级联删除数据库记录

**MD 删除算法**：
1. 查找锚点所在行，记录缩进级别
2. 删除该行
3. 删除所有缩进级别 > 该行的后续行（子任务）
4. 清理连续的多余空行

#### 安全处理

**回写前置检查**：
- 无 `plan_doc_id` → 跳过 MD 操作
- 无 `source_anchor_id` → 跳过 MD 操作
- 计划书不存在 → 清除关联
- MD 文件不存在 → 跳过 MD 操作
- 锚点不存在 → 跳过 MD 操作

#### 文件路径

**计划书目录**：`Path(settings.lifeprism_data_path) / "plan"`

**文件命名**：`{plan_doc_id}.md`

#### 关键数据库字段

| 字段 | 说明 |
|------|------|
| `plan_doc_id` | 关联的计划书 ID |
| `source_anchor_id` | MD 锚点 ID（格式：t-xxx） |
| `parent_id` | 父任务 ID |
| `pool_order_index` | 任务池排序（全局顺序） |

#### 前端 PlanDoc 保存 Hook 机制

**问题背景**：
PlanDoc 编辑器、任务池、本地 MD 文件三者可能产生数据冲突：
- 用户在 PlanDoc 编辑器修改文本（未保存，仅在前端 `localContent` 中）
- 同时在任务池勾选 todo → 后端更新 DB 和 MD 文件
- PlanDoc 编辑器的 `localContent` 与 MD 文件不同步

**解决方案**：
1. 在前端 Todo 操作前，先触发 PlanDoc 编辑器的保存，确保 MD 文件与编辑器内容同步
2. 在 Todo 操作完成后，自动刷新 PlanDoc 编辑器内容，让用户立即看到更改

**实现机制**：

1. **保存 Hook 注册器**（`usePlanDocSaveHook.ts`）：
   - `registerPlanDocSaveCallback(planDocId, callback)` - 注册保存回调
   - `unregisterPlanDocSaveCallback(planDocId)` - 注销保存回调
   - `triggerAllPlanDocSaves()` - 触发所有已注册的保存

2. **刷新 Hook 注册器**（`usePlanDocSaveHook.ts`）：
   - `registerPlanDocRefreshCallback(planDocId, callback)` - 注册刷新回调
   - `unregisterPlanDocRefreshCallback(planDocId)` - 注销刷新回调
   - `triggerAllPlanDocRefreshes()` - 触发所有已注册的刷新

3. **PlanDocListView 注册回调**：
   - 组件挂载时注册 `silentSave` 回调（静默保存，不显示 toast）
   - 组件挂载时注册 `silentRefresh` 回调（静默刷新，不显示 toast）
   - 组件卸载时注销所有回调

4. **useTaskPoolStore 触发保存和刷新**：
   - `addTask`、`updateTask`、`deleteTask` 操作前调用 `triggerAllPlanDocSaves()`
   - 操作成功后调用 `triggerAllPlanDocRefreshes()`

**数据流**：
```
用户在任务池勾选 todo
    ↓
useTaskPoolStore.updateTask()
    ↓
triggerAllPlanDocSaves()  ← 先保存所有编辑中的 PlanDoc
    ↓
PlanDocListView.silentSave()  ← 静默保存到后端
    ↓
taskPoolApi.updateTodo()  ← 执行 todo 更新
    ↓
后端更新 DB 和 MD 文件
    ↓
triggerAllPlanDocRefreshes()  ← 刷新所有 PlanDoc 编辑器
    ↓
PlanDocListView.silentRefresh()  ← 从后端获取最新内容
```

**相关文件**：
- `frontend/apps/goals/hooks/usePlanDocSaveHook.ts` - 保存/刷新 Hook 注册机制
- `frontend/apps/goals/hooks/useTaskPoolStore.ts` - Todo 状态管理（调用 `triggerAllPlanDocSaves` 和 `triggerAllPlanDocRefreshes`）
- `frontend/apps/goals/components/views/PlanDocListView/PlanDocListView.tsx` - 注册 `silentSave` 和 `silentRefresh` 回调




## Project Overview

**LifeWatch-AI** (LifePrism) is an AI-powered personal time management and analysis platform that monitors user computer activity through ActivityWatch, classifies applications using LLM, and provides insights through a React frontend.

### Architecture

```
LifeWatch-AI/
├── frontend/           # React + TypeScript + Vite frontend (apps/core/shell 三层架构)
│   ├── apps/          # 应用模块层
│   │   ├── lifewatch/ #   时间追踪核心（首页、时间线、分类、报告）
│   │   ├── goals/     #   目标管理应用
│   │   ├── habits/    #   习惯养成应用
│   │   ├── mindspace/ #   思维空间（待开发）
│   │   ├── settings/  #   设置应用
│   │   └── addons/    #   插件扩展（待开发）
│   ├── core/          # 核心共享层（组件、服务、类型、工具）
│   ├── shell/         # 应用外壳层（ModuleDock 导航）
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

### Frontend Architecture

前端采用 **apps/core/shell** 三层架构：

| 层次 | 目录 | 职责 |
|------|------|------|
| **Shell** | `shell/` | 应用外壳、ModuleDock 模块导航、全局布局 |
| **Core** | `core/` | 跨应用共享的组件、服务、类型、工具 |
| **Apps** | `apps/` | 独立的功能应用模块 |

**应用模块**：
- `apps/lifewatch/`: 时间追踪核心（首页、时间线、分类、使用量、报告）
- `apps/goals/`: 目标管理（目标列表、计划书、任务池、日历、每日任务）
- `apps/habits/`: 习惯养成（习惯列表、习惯链、锚点时间线）
- `apps/settings/`: 全局设置
- `apps/mindspace/`: 思维空间（待开发）
- `apps/addons/`: 插件扩展（待开发）

**核心共享**：
- `core/components/`: 共享组件（Chatbot、Toast、CategoryFilter 等）
- `core/services/`: 共享服务（syncService、aiService、apiConfig 等）
- `core/types/`: 共享类型定义
- `core/hooks/`: 共享 Hooks（useUserSettings 等）

**详细文档**: `frontend/docs/组织架构.md`

## Configuration

### Backend Configuration

**Main Config File**: `lifeprism/config/settings.yaml`

> 注意：以下路径为用户本地配置示例，代码中不应硬编码这些路径，应通过 `settings_manager` 读取（参见后端 rule 6 外部存储路径规范）。

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

# Data Paths
lifeprism_data_path: ''  # 空=使用默认路径（开发: frontend/lifeprismData, 打包: %APPDATA%/LifePrism/lifeprismData）
aw_db_path: ~/AppData/Local/activitywatch/activitywatch/aw-server/peewee-sqlite.v2.db
# 注意：lw_db_path 和 chat_db_path 已移除，自动从 lifeprism_data_path 推算

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

The frontend uses **incremental sync** on startup (`frontend/core/services/syncService.ts`):

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

### Adding a New Frontend App

1. Create app directory in `frontend/apps/[appname]/`
2. Create main app component `[AppName]App.tsx`
3. Add app to `shell/ModuleDock.tsx` navigation
4. Register route in `frontend/App.tsx`
5. Create API endpoints in `lifeprism/server/api/` if needed

### Adding a New Page to Existing App

1. Create page in `frontend/apps/[appname]/pages/[pagename]/`
2. Add route in the app's main component
3. Add navigation in the app's sidebar/layout

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
