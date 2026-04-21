# LLM 数据集 Provider 创建完成

## 完成内容

### 1. 创建新的 LLM 数据集 Provider

**文件**: `lifeprism/llm/providers/dataset_providers/llm_dataset_provider.py`

这是一个全新的、简洁的 LLM 数据库通用接口，专注于数据获取，不包含业务逻辑。

#### 核心特性

- **纯数据查询**: 只负责从数据库获取数据，不做数据整合和业务逻辑处理
- **清晰的接口**: 函数命名和参数设计清晰明确
- **完整的文档**: 包含 Google 风格的文档字符串和类型注解
- **单例模式**: 使用 `LazySingleton` 提供全局单例

#### 当前接口

**`query_todos()`** - 统一的 TodoList 查询接口

支持两种查询模式：
- **单日查询**: 只传 `start_date`，`end_date` 为 `None`
- **日期范围查询**: 传 `start_date` 和 `end_date`

参数：
- `start_date`: 开始日期（YYYY-MM-DD）
- `end_date`: 结束日期（YYYY-MM-DD，可选）
  - `None`: 单日查询
  - 指定日期: 日期范围查询
- `goal_id`: 目标 ID 过滤（可选）
- `plandoc_id`: 计划文档 ID 过滤（可选）
- `state`: 状态过滤（可选，如 'active', 'completed', 'pool'）
- `include_cross_day`: 是否包含跨天未完成任务（默认 True，仅单日查询时生效）

返回：TodoList 列表，按日期和 order_index 排序

### 2. 导出配置

已更新以下文件的导出配置：

- `lifeprism/llm/providers/dataset_providers/__init__.py`
- `lifeprism/llm/providers/__init__.py`

可通过以下方式导入：

```python
from lifeprism.llm.providers import LLMDatasetProvider, llm_dataset_provider
# 或
from lifeprism.llm.providers.dataset_providers import LLMDatasetProvider, llm_dataset_provider
```

### 3. 测试验证

**文件**: `test/core/unit/llm/test_llm_dataset_provider.py`

创建了完整的测试套件，包括：

- **基础功能测试** (2个测试)
  - Provider 初始化测试
  - 单例模式测试

- **query_todos 接口测试** (9个测试)
  - 空日期范围查询
  - 日期范围查询
  - 单日查询
  - 单日查询（不包含跨天任务）
  - goal_id 过滤测试
  - plandoc_id 过滤测试
  - state 过滤测试
  - 多条件组合过滤测试
  - 单日查询带过滤条件测试

- **数据结构测试** (3个测试)
  - 字段完整性测试
  - 日期范围查询排序测试
  - 单日查询排序测试

**测试结果**: ✅ 14/14 测试全部通过

### 4. old_llm_lw_data_provider 引用情况

检查结果：只有 2 处引用

1. **`dataset_providers/__init__.py`** - 导出用途
   ```python
   from .old_llm_lw_data_provider import LLMLWDataProvider, old_llm_lw_data_provider
   ```

2. **`summary_read_provider.py`** - 实际使用
   ```python
   from lifeprism.llm.providers.dataset_providers.old_llm_lw_data_provider import old_llm_lw_data_provider
   ```
   - 在 `get_activity_logs_by_range()` 方法中调用 `old_llm_lw_data_provider.query_behavior_logs()`

## 使用示例

```python
from lifeprism.llm.providers import llm_dataset_provider

# 单日查询
today_todos = llm_dataset_provider.query_todos(
    start_date="2026-04-21"
)

# 单日查询（不包含跨天任务）
today_todos_only = llm_dataset_provider.query_todos(
    start_date="2026-04-21",
    include_cross_day=False
)

# 日期范围查询
todos = llm_dataset_provider.query_todos(
    start_date="2026-04-19",
    end_date="2026-04-21"
)

# 带过滤条件的查询
filtered_todos = llm_dataset_provider.query_todos(
    start_date="2026-04-19",
    end_date="2026-04-21",
    goal_id="goal-abc123",  # 可选
    plandoc_id="plandoc-xyz",  # 可选
    state="active"  # 可选
)

# 遍历结果
for todo in todos:
    print(f"{todo['date']} - {todo['content']} ({todo['state']})")
```

## 与 old_llm_lw_data_provider 的区别

| 特性 | old_llm_lw_data_provider | llm_dataset_provider |
|------|-------------------------|---------------------|
| 代码行数 | 1565+ 行 | 150 行 |
| 功能范围 | 包含大量数据整合和业务逻辑 | 纯数据查询 |
| 接口数量 | 50+ 个方法 | 1 个统一接口（可扩展） |
| 缓存机制 | 内置分类、目标等映射缓存 | 无缓存（纯查询） |
| 数据整合 | 包含时间线构建、事件切片等 | 不做数据整合 |
| 维护性 | 复杂，难以维护 | 简洁，易于维护 |
| 接口设计 | 多个独立方法 | 单一统一接口 |

## 设计原则

1. **单一职责**: 只负责数据查询，不做业务逻辑
2. **接口统一**: 一个接口支持多种查询模式
3. **易于扩展**: 可以轻松添加新的查询接口
4. **无副作用**: 纯查询函数，不修改数据库
5. **完整文档**: 每个函数都有详细的文档字符串和示例

## 接口设计亮点

### 统一接口设计

通过 `end_date` 参数的可选性，实现了单日查询和日期范围查询的统一：

- `end_date=None`: 单日查询模式
- `end_date=指定日期`: 日期范围查询模式

这种设计的优势：
- **简化 API**: 用户只需要记住一个接口
- **灵活性**: 通过参数组合支持多种查询场景
- **一致性**: 所有查询都使用相同的过滤参数

## 后续扩展

可以根据需要添加更多查询接口，例如：
- `query_goals()` - 查询目标
- `query_activity_logs()` - 查询活动日志
- `query_screen_captures()` - 查询截图记录
- 等等

每个接口都应该遵循相同的设计原则：纯数据查询，参数清晰，文档完整。
