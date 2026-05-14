---
version: 2.1
created_at: 2026-05-13
updated_at: 2026-05-14
last_updated: 添加参数声明与校验机制
abstract: Prompt 集中管理系统的规格说明，定义文件组织、格式规范、加载接口、使用统计、类型安全机制、参数校验等技术契约
id: prompt-management-system
title: Prompt 集中管理系统
status: implemented
module: llm/prompts
source_spec: docs/temp/prompt_management_analysis.md
related_plan: 已完成
code_scope:
  - lifeprism/llm/prompts/prompt_loader.py
  - lifeprism/llm/prompts/__init__.py
  - lifeprism/llm/utils/md_os.py (prompts_md_load 函数)
  - templates/prompts/schedule_prompts.md
  - templates/prompts/usage_stats.yaml
  - templates/prompts/README.md
contract_refs:
  - templates/prompts/schedule_prompts.md
  - templates/prompts/usage_stats.yaml
  - templates/prompts/README.md
---

# Prompt 集中管理系统

## 版本

| 版本 | 更新日期 | 更新内容 |
| ---- | -------- | -------- |
| 2.1  | 2026-05-14 | 添加参数声明与校验机制 |
| 2.0  | 2026-05-13 | 添加 PromptRef 和 Prompts 类型安全机制，更新加载接口 |
| 1.0  | 2026-05-13 | 创建 spec 初稿 |

## Overview

Prompt 集中管理系统用于统一管理项目中所有 LLM prompts，解决当前 prompts 散落在各个函数中的问题。

**核心目标**：
- 集中管理所有 prompts
- 支持版本管理和 A/B 测试
- 解耦 prompt 和业务代码
- 记录版本历史和使用统计
- **类型安全**：通过 PromptRef 和 Prompts 类避免字符串拼写错误

**设计原则**：
- 使用 Markdown 文件存储 prompt（与项目现有 user.md、agent.md 保持一致）
- 按模块分组组织文件
- 支持多版本共存
- 记录元数据和使用统计
- **提供类型安全的加载接口**：使用 dataclass 和嵌套类结构

## Scope

**包含**：
- Prompt 文件的组织结构
- Markdown 文件格式规范
- Prompt 命名规范
- Loader 加载接口
- 使用统计机制
- **类型安全机制**：PromptRef 数据类和 Prompts 嵌套类
- **向后兼容**：支持字符串方式调用

**不包含**：
- Loader 的具体实现细节
- 参数注入的模板引擎选择
- 热加载的实现方式
- Prompt 测试机制（待后续补充）

## Core Behavior

### 文件组织

1. **目录结构**：
   外置 prompt 目录结构，不写在代码文件夹中，写在 lifeprismData（开发环境下修改 templates 文件夹内容，代码会自动将 templates 内容复制到系统设定的 lifeprismData 文件夹，后端使用 config 模块的 settings.lifeprism_data_path 获取）
   ```
   templates/prompts/
     schedule_prompts.md      # Schedule 模块的 prompts
     prompt_template.md       # Prompt 文件格式模板
     README.md                # 使用说明文档
     usage_stats.yaml         # 使用统计（自动生成，不提交到 Git）
   ```

2. **组织原则**：
   - 按大模块分组（schedule、chat 等）
   - 一个文件包含该模块的多个相关 prompts
   - 文件命名：`{模块名}_prompts.md`

### 加载流程

1. 根据 prompt 名称定位所属模块文件
2. 使用 `prompts_md_load()` 函数解析文件获取 metadata 中的激活版本
3. 提取对应版本的 prompt 内容
4. 记录使用统计

### 缓存机制

1. **缓存策略**：
   - PromptLoader 使用字典缓存已加载的 prompt 文件
   - 缓存以 module 名称为 key，解析后的数据为 value
   - 缓存在 PromptLoader 实例的生命周期内有效

2. **缓存清理**：
   - 调用 `clear_cache()` 方法清空所有缓存
   - 适用场景：开发环境修改 prompt 文件后需要重新加载

3. **缓存生命周期**：
   - 缓存随 PromptLoader 实例创建而创建
   - 缓存随 PromptLoader 实例销毁而销毁
   - 不支持跨实例共享缓存

### 版本管理

1. **多版本共存**：同一个 prompt 可以有多个版本（v1, v2, v3...）
2. **激活版本**：metadata 中的 `active_version` 指定默认使用的版本
3. **版本切换**：通过参数指定版本号进行 A/B 测试
4. **版本历史**：metadata 中的 `version_history` 记录每个版本的创建时间和修改原因

### 使用统计

1. **统计维度**：
   - 总使用次数
   - 各版本使用次数
   - 最后使用时间

2. **统计时机**：每次调用 `load_prompt()` 时自动记录

3. **统计存储**：写入 `usage_stats.yaml`（不提交到 Git）

4. **隐私说明**：统计只记录调用次数和时间，不记录参数内容或用户数据

## Technical Contract

### 文件命名规范

**模块文件命名**：
- 格式：`{模块名}_prompts.md`
- 规范：snake_case，必须以 `_prompts.md` 结尾
- 示例：
  - `schedule_prompts.md`
  - `chat_prompts.md`
  - `memory_prompts.md`

### Prompt 命名规范

**Prompt 名称**（文件内一级标题）：
- 格式：snake_case
- 建议：`{动作}_{对象}` 或 `{功能描述}`
- 示例：
  - `activity_summary`
  - `mood_summary`
  - `update_memory`
  - `extract_chat`

**命名原则**：
- 不需要在 prompt 名称中重复模块名
- 命名要清晰表达功能，避免模糊命名

### Markdown 文件格式

**文件结构**：
```markdown
---
module: {模块名}
description: {模块描述}
author: {作者}
---

# {prompt_name_1}

## metadata

```yaml
active_version: v2
version_history:
  v2:
    created_at: YYYY-MM-DD
    change_reason: {具体的修改原因}
  v1:
    created_at: YYYY-MM-DD
    change_reason: 初始版本
```

## v2

```md
{prompt 内容}
```

## v1

```md
{prompt 内容}
```

---

# {prompt_name_2}

## metadata

```yaml
active_version: v1
version_history:
  v1:
    created_at: YYYY-MM-DD
    change_reason: 初始版本
```

## v1

```md
{prompt 内容}
```
```

**格式说明**：
- **文件级 frontmatter**：模块级元数据（module, description, author）
- **一级标题 `#`**：prompt 名称
- **二级标题 `##`**：
  - `metadata`：该 prompt 的元数据（YAML 格式）
  - `v1`, `v2`, `v3` 等：各个版本的 prompt 内容
- **分隔符 `---`**：分隔不同的 prompts
- **代码块 ` ```md ``` `**：包裹 prompt 内容，避免 Markdown 格式干扰

**metadata 字段**：
- `active_version`：当前激活的版本（必需）
- `version_history`：版本历史记录（必需）
  - 每个版本包含：
    - `created_at`：创建日期（YYYY-MM-DD）
    - `change_reason`：修改原因（具体说明改了什么、为什么改）
    - `params`：参数声明列表（可选，仅当该版本需要参数注入时声明）
      - 格式：字符串列表，每个元素为参数名称
      - 所有声明的参数均为必需参数
      - 调用时传入的参数必须与声明完全匹配

**prompt 内容格式**：
- 必须使用 ` ```md ``` ` 代码块包裹
- 代码块内可以自由使用 Markdown 格式（标题、列表、代码块等）
- 解析时只提取代码块内的内容

**参数注入语法**：
- 使用 Python format 语法：`{param_name}`
- 支持的语法：`{param_name}` 基本替换
- 不支持的语法：`{param_name:format_spec}` 格式化规范
- 示例：`文件路径：{file_path}` 会被替换为 `文件路径：/path/to/file.md`

**参数校验规则**：
- 校验时机：`load_prompt()` 加载含参数声明的 prompt 时
- 校验内容：
  1. **未知参数**：调用方传入了声明之外的参数 → 抛出 `ValueError`
  2. **缺少必需参数**：调用方未传入声明中的参数 → 抛出 `ValueError`
- 校验逻辑在参数注入（`format()`）之前执行
- 无 `params` 声明的版本跳过校验（向后兼容）

### prompts_md_load 函数

**作用**：解析 Markdown 格式的 prompt 文件，提取模块信息、prompt 内容和元数据。

**位置**：`lifeprism/llm/utils/md_os.py`

**输入**：Prompt 文件路径

**输出**：包含模块信息和所有 prompts 的字典结构

**异常**：文件不存在或格式错误时抛出异常

### 使用统计文件格式

**文件路径**：`templates/prompts/usage_stats.yaml`

**文件格式**：
```yaml
activity_summary:
  total_count: 1523
  version_stats:
    v1: 856
    v2: 667
  last_used: "2026-05-13T14:30:00"

mood_summary:
  total_count: 892
  version_stats:
    v1: 892
  last_used: "2026-05-13T14:25:00"
```

**字段说明**：
- `total_count`：总使用次数
- `version_stats`：各版本使用次数
- `last_used`：最后使用时间（ISO 8601 格式）

### 类型安全机制

**PromptRef 数据类**：

不可变的 prompt 引用，包含 module 和 name 信息。用于类型安全的 prompt 加载。

**Prompts 嵌套类**：

按 module 分组的 prompt 常量定义。提供 IDE 自动补全和类型检查支持。

示例：
```python
class Prompts:
    class Schedule:
        """定时任务相关 prompts (schedule_prompts.md)"""
        ACTIVITY_SUMMARY = PromptRef("schedule", "activity_summary")
        MOOD_SUMMARY = PromptRef("schedule", "mood_summary")
        UPDATE_MEMORY = PromptRef("schedule", "update_memory")
        EXTRACT_CHAT = PromptRef("schedule", "extract_chat")
```

**组织原则**：
- 按 module 分组，使用嵌套类
- 类名使用 PascalCase（如 Schedule, Chat）
- 常量名使用 UPPER_SNAKE_CASE（如 ACTIVITY_SUMMARY）
- 类文档字符串注明对应的文件名

**扩展方式**：
- 添加新 module：在 Prompts 类中添加新的嵌套类
- 添加新 prompt：在对应的嵌套类中添加新的 PromptRef 常量

### 加载接口

**PromptLoader 类**：

统一的 prompt 加载器，负责文件解析、版本管理、缓存和使用统计。

**核心功能**：
- 加载指定的 prompt（支持 PromptRef 和字符串两种方式）
- 版本管理（默认使用 active_version，可指定版本）
- 参数注入（使用 Python format 语法）
- 使用统计记录
- 元数据查询
- 缓存管理

**调用示例**：

```python
from lifeprism.llm.prompts import PromptLoader, Prompts

loader = PromptLoader("templates/prompts")

# 推荐方式：使用 Prompts 类
prompt = loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)

# 指定版本
prompt = loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY, version="v1")

# 参数注入
prompt = loader.load_prompt(
    Prompts.Schedule.UPDATE_MEMORY,
    recent_state_path="/path/to/recent_state.md",
    user_md_path="/path/to/user.md"
)

# 向后兼容：字符串方式
prompt = loader.load_prompt("activity_summary", module="schedule")
```

**错误处理**：
- 文件不存在：`FileNotFoundError`
- Prompt 不存在：`ValueError`
- 版本不存在：`ValueError`
- 参数类型错误：`TypeError`
- 缺少 module 参数：`ValueError`

**接口优势**：
- ✅ IDE 自动补全 module 和 name
- ✅ 避免 module 和 name 拼写错误
- ✅ 重构友好，IDE 可以找到所有引用
- ✅ 代码更简洁，一次性指定 module 和 name
- ✅ 向后兼容，仍支持字符串方式

### 统计查询接口

**PromptLoader 提供的查询方法**：

- `get_prompt_metadata()` - 获取 prompt 的元数据（active_version 和 version_history）
- `get_available_versions()` - 获取 prompt 的所有可用版本
- `get_usage_stats()` - 获取使用统计数据（单个 prompt 或所有 prompts）
- `clear_cache()` - 清空缓存，强制重新加载文件

## Acceptance Notes

### 功能验收

1. **文件组织**：
   - ✅ 创建 `schedule_prompts.md` 包含 4 个 prompts
   - ✅ 文件格式符合规范
   - ✅ 创建 `prompt_template.md` 作为模板示例

2. **版本管理**：
   - ✅ 可以在文件中保留多个版本
   - ✅ metadata 正确记录 `active_version` 和 `version_history`

3. **加载功能**：
   - ✅ 默认加载激活版本
   - ✅ 支持指定版本号加载
   - ✅ 参数注入功能正常
   - ✅ 支持 PromptRef 方式加载
   - ✅ 向后兼容字符串方式加载

4. **使用统计**：
   - ✅ 每次调用自动更新统计文件
   - ✅ 统计数据准确
   - ✅ 统计文件自动生成

5. **类型安全**：
   - ✅ PromptRef 数据类实现
   - ✅ Prompts 嵌套类实现
   - ✅ IDE 自动补全支持
   - ✅ 类型检查支持

6. **接口导出**：
   - ✅ 可以从 `lifeprism.llm.prompts` 导入 PromptLoader, PromptRef, Prompts

### 质量验收

1. **命名规范**：
   - ✅ 文件命名符合规范（{module}_prompts.md）
   - ✅ Prompt 命名符合规范（snake_case）
   - ✅ 类命名符合规范（PascalCase）
   - ✅ 常量命名符合规范（UPPER_SNAKE_CASE）

2. **格式规范**：
   - ✅ Markdown 文件格式正确
   - ✅ metadata YAML 格式正确
   - ✅ 分隔符使用正确

3. **错误处理**：
   - ✅ 文件不存在时有明确错误提示
   - ✅ Prompt 不存在时有明确错误提示
   - ✅ 版本不存在时有明确错误提示
   - ✅ 参数类型错误时有明确错误提示

4. **文档完整性**：
   - ✅ README.md 使用说明完整
   - ✅ 代码注释清晰
   - ✅ 测试文件覆盖主要功能

### 实现验证

**已实现的文件**：
- `lifeprism/llm/prompts/prompt_loader.py` - PromptLoader, PromptRef, Prompts 类
- `lifeprism/llm/prompts/__init__.py` - 导出接口
- `lifeprism/llm/utils/md_os.py` - prompts_md_load 解析函数
- `templates/prompts/schedule_prompts.md` - Schedule 模块的 4 个 prompts
- `templates/prompts/prompt_template.md` - 模板示例
- `templates/prompts/usage_stats.yaml` - 使用统计（自动生成）
- `templates/prompts/README.md` - 使用文档
- `test_prompt_system.py` - 完整测试套件
- `test_prompt_ref.py` - PromptRef 功能测试

**测试结果**：
- ✅ 所有核心功能测试通过
- ✅ PromptRef 和 Prompts 类测试通过
- ✅ 向后兼容性测试通过
- ✅ 参数注入测试通过
- ✅ 错误处理测试通过

## Out of Spec

以下内容不在本 spec 范围内：

1. **Loader 实现细节**：
   - ✅ 已实现：使用正则表达式解析 Markdown
   - ✅ 已实现：基于字典的缓存机制
   - ❌ 未实现：热加载机制（需要时可添加）

2. **参数注入实现**：
   - ✅ 已实现：使用 Python format 语法
   - ❌ 未实现：参数验证逻辑（当前仅记录警告）

3. **Prompt 测试机制**：
   - ❌ 未实现：如何测试 prompt 效果
   - ❌ 未实现：如何评估 prompt 质量
   - ❌ 未实现：测试数据的组织方式
   - **（待后续补充到本 spec 或独立 spec）**

4. **性能优化**：
   - ❌ 未实现：统计数据的批量写入（当前每次调用都写入）
   - ❌ 未实现：异步写入机制
   - ✅ 已实现：文件读取缓存

5. **迁移方案**：
   - ⚠️ 部分完成：已将 `agent_schedule_job.py` 的 4 个 prompts 迁移
   - ❌ 未定义：其他模块的迁移步骤
   - ❌ 未定义：迁移的自动化工具

6. **CI 检查**：
   - ❌ 未实现：文件格式的自动检查
   - ❌ 未实现：命名规范的自动检查

7. **扩展策略**：
   - ✅ 已定义：按 module 分组的嵌套类结构
   - ❌ 未定义：当某个 module prompts > 10 个时如何拆分子模块
   - ❌ 未定义：子模块的目录结构设计

8. **使用示例**：
   - ✅ 已完成：详见 `templates/prompts/README.md`
   - ✅ 已完成：详见 `test_prompt_system.py` 和 `test_prompt_ref.py`
   - ✅ 已完成：详见 `templates/prompts/usage_example.py`

**状态标记说明**：
- ✅ 已实现
- ⚠️ 部分实现
- ❌ 未实现/不在范围内

## Implementation Notes

### 关键设计决策

1. **为什么使用 PromptRef + Prompts 类？**
   - **问题**：字符串方式需要同时传入 module 和 prompt_name，容易拼错
   - **解决方案**：PromptRef 数据类包含完整的 module 和 name 信息
   - **优势**：完整的类型安全、清晰的层级结构、IDE 友好、向后兼容

2. **为什么使用 dataclass？**
   - 自动生成常用方法（`__init__`, `__repr__`, `__eq__`）
   - `frozen=True` 确保不可变性
   - 代码简洁

3. **为什么使用嵌套类？**
   - 按 module 分组，结构清晰
   - 避免命名冲突
   - 扩展性好

### 使用建议

1. **新代码推荐使用 Prompts 类**：
   ```python
   # 推荐
   prompt = loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)
   
   # 不推荐（但仍支持）
   prompt = loader.load_prompt("activity_summary", module="schedule")
   ```

2. **添加新 prompt 的步骤**：
   - 在对应的 `{module}_prompts.md` 文件中添加 prompt
   - 在 `Prompts.{Module}` 类中添加对应的 `PromptRef` 常量

3. **添加新 module 的步骤**：
   - 创建 `{module}_prompts.md` 文件
   - 在 `Prompts` 类中添加新的嵌套类
   - 在嵌套类中定义该 module 的所有 prompts

### 迁移现有代码

**迁移步骤**：

1. **识别散落的 prompts**：
   - 在代码中搜索多行字符串或 prompt 变量
   - 识别需要迁移的 prompt 内容

2. **创建 prompt 文件**：
   - 按模块创建 `{module}_prompts.md` 文件
   - 按照格式规范编写 prompt 内容
   - 添加 metadata（active_version, version_history）

3. **更新 Prompts 类**：
   - 在 `Prompts` 类中添加对应的嵌套类和常量

4. **修改调用代码**：
   ```python
   # 修改前
   prompt = """
   你需要总结用户今天的活动...
   """
   
   # 修改后
   from lifeprism.llm.prompts import PromptLoader, Prompts
   loader = PromptLoader("templates/prompts")
   prompt = loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)
   ```

5. **测试验证**：
   - 运行相关功能测试
   - 确认 prompt 加载正常
   - 检查使用统计是否记录

**已完成的迁移示例**：
- `agent_schedule_job.py` 的 4 个 prompts 已迁移到 `schedule_prompts.md`

### 已知限制

1. **统计数据写入性能**：
   - 当前影响：每次调用都写入文件，高频调用可能影响性能
   - 适用场景：prompt 加载不是高频操作，当前性能可接受
   - 未来优化：可考虑批量写入或异步写入

2. **参数注入验证**：
   - 当前状态：✅ 已实现
   - 实现方式：通过 version_history 中的 params 声明进行校验
   - 校验内容：未知参数、缺少必需参数

3. **无热加载**：
   - 当前影响：修改 prompt 文件后需要清空缓存或重启
   - 适用场景：生产环境 prompt 不常修改
   - 未来优化：可添加文件监听和自动重载
