---
version: 1.0
created_at: 2026-07-06
updated_at: 2026-07-06
last_updated: 创建文档初稿
abstract: lifeprism 项目 ruff check 检测结果报告，包含 336 个错误分类统计与分布概览
---

# 0001-ruff-lint-report

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 检测概况

```bash
ruff check lifeprism
```

- **检测工具**: ruff (linter)
- **检测范围**: `lifeprism/` 包
- **总错误数**: 336
- **格式化检测**: `ruff format --check` — 276 个文件全部通过（无格式问题）
- **可自动修复**: 117 个错误可通过 `--unsafe-fixes` 修复

## 错误分类统计

### 1. 异常处理相关（107 个）

| 规则 | 数量 | 等级 | 说明 |
|------|------|------|------|
| B904 `raise-without-from-inside-except` | 106 | 高风险 | 在 `except` 块中 `raise` 新异常时未使用 `from err`，丢失异常链 |
| B025 `duplicate-try-block-exception` | 1 | 低风险 | 同一个 `try` 中捕获了重复的异常类型 |

### 2. 导入规范（79 个）

| 规则 | 数量 | 等级 | 说明 |
|------|------|------|------|
| E402 `module-import-not-at-top-of-file` | 66 | 中风险 | 模块导入不在文件顶部（常见于文件末尾的 `LazySingleton` 导入） |
| F401 `unused-import` | 11 | 低风险 | 导入了未使用的模块 |
| F403 `undefined-local-with-import-star` | 2 | 中风险 | `from xxx import *` 导致局部作用域未定义 |

### 3. 代码简化/风格（45 个）

| 规则 | 数量 | 等级 | 说明 |
|------|------|------|------|
| SIM108 `if-else-block-instead-of-if-exp` | 18 | 低风险 | 简单的 `if-else` 赋值可替换为三元表达式 |
| SIM102 `collapsible-if` | 9 | 低风险 | 嵌套的 `if` 可以合并 |
| SIM105 `suppressible-exception` | 4 | 低风险 | 可用 `contextlib.suppress` 替代空的 `try-except` |
| SIM103 `needless-bool` | 2 | 低风险 | 多余的布尔返回，可直接返回条件本身 |
| SIM110 `reimplemented-builtin` | 1 | 低风险 | 手动重新实现了内置函数 |
| SIM201 `negate-equal-op` | 1 | 低风险 | 可用 `!=` 替代 `not ... ==` |
| E731 `lambda-assignment` | 2 | 低风险 | 不应将 `lambda` 赋值给变量，应改用 `def` |
| E741 `ambiguous-variable-name` | 4 | 低风险 | 使用了含义模糊的变量名（如 `l`, `O`, `I`） |
| E722 `bare-except` | 1 | 高风险 | 裸 `except:` 未指定异常类型 |

### 4. 空格/格式问题（54 个）

| 规则 | 数量 | 等级 | 说明 |
|------|------|------|------|
| W291 `trailing-whitespace` | 43 | 低风险 | 行尾有多余空格 |
| W293 `blank-line-with-whitespace` | 11 | 低风险 | 空行中包含空格 |

### 5. 变量/函数问题（29 个）

| 规则 | 数量 | 等级 | 说明 |
|------|------|------|------|
| F821 `undefined-name` | 9 | 高风险 | 使用了未定义的名称（潜在运行时 `NameError`） |
| F841 `unused-variable` | 9 | 低风险 | 赋值了但未使用的变量 |
| B007 `unused-loop-control-variable` | 6 | 低风险 | 循环控制变量未在循环体中使用 |
| F405 `undefined-local-with-import-star-usage` | 2 | 中风险 | 使用了 `import *` 引入的变量，可能未定义 |
| F811 `redefined-while-unused` | 1 | 中风险 | 函数/变量被重定义且原定义未使用 |
| B027 `empty-method-without-abstract-decorator` | 1 | 低风险 | 空方法缺少 `@abstractmethod` 装饰器 |

### 6. 其他（22 个）

| 规则 | 数量 | 等级 | 说明 |
|------|------|------|------|
| B905 `zip-without-explicit-strict` | 24 | 中风险 | `zip()` 未指定 `strict` 参数，可能导致静默数据截断 |
| SIM115 `open-file-with-context-handler` | 2 | 中风险 | 打开文件未使用 `with` 上下文管理器 |

## 主要分布模块

### lifeprism/server/services/（错误集中区）

- **B904**（异常链丢失）：大量 `except` 块中 `raise ValueError/ConflictError` 缺少 `from e`
- **E402**（导入位置）：文件末尾 `from lifeprism.utils import LazySingleton` 不在顶部
- **W291**（行尾空格）：多处 SQL 多行字符串末尾有空格
- **SIM108**（三元表达式）：多处简单 `if-else` 赋值可简化

涉及文件：`category_service.py`, `chatbot_service.py`, `goal_service.py`, `habit_stats_service.py`, `journal_service.py`, `plandoc_sync_service.py`, `report_service.py`, `setting_service.py`, `timeline_builder.py`, `timeline_service.py`, `usage_service.py`, `value_service.py` 等

### lifeprism/server/providers/

- **B904**（异常链丢失）：多处类似 services 的问题
- **E402**（导入位置）：部分文件末尾导入

### lifeprism/server/schemas/ 与 lifeprism/server/api/

- **W291/W293**（空格问题）：行尾空格和空行空格
- **B904**（异常链丢失）：少量
- **F401**（未使用导入）：部分

### lifeprism/llm/

- **B905**（zip 缺少 strict）：多个子模块
- **F401**（未使用导入）：`__init__.py` 中常见
- **B904**（异常链丢失）：部分
- **F821**（未定义名称）：部分

### lifeprism/repository/

- **B904**（异常链丢失）：多处
- **E402**（导入位置）：部分
- **F401**（未使用导入）：部分

### lifeprism/monitor/ 与 lifeprism/processors/

- 少量分布，以 B904、B905 为主

### lifeprism/utils/

- **SIM115**（未使用上下文管理器）：`logger.py` 中 2 处 `open()` 调用
- 其他少量问题

## 修复优先级建议

### 第一优先级 — 高风险（116 个）

| 规则 | 数量 | 理由 |
|------|------|------|
| B904 | 106 | 丢失异常链，调试时无法追踪根因 |
| F821 | 9 | 潜在运行时 `NameError` |
| E722 | 1 | 裸 except 会吞掉 `KeyboardInterrupt` 等系统异常 |

### 第二优先级 — 中风险（94 个）

| 规则 | 数量 | 理由 |
|------|------|------|
| E402 | 66 | 导入位置不当，可能影响模块初始化顺序 |
| B905 | 24 | zip 缺少 strict，数据可能静默截断 |
| SIM115 | 2 | 文件句柄可能未正确关闭 |
| F403/F405 | 4 | import * 导致命名空间污染 |

### 第三优先级 — 低风险（126 个）

| 规则 | 数量 |
|------|------|
| W291/W293 | 54 |
| SIM108/SIM102/SIM105/SIM103/SIM110/SIM201 | 35 |
| F401/F841/B007/F811 | 27 |
| E731/E741/B025/B027 | 8 |
| 其他 | 2 |

## 相关命令

```bash
# 查看当前错误
ruff check lifeprism

# 统计错误分类
ruff check lifeprism --statistics

# 查看受影响文件列表
ruff check lifeprism --show-files

# 自动修复（安全修复）
ruff check --fix lifeprism

# 自动修复（含不安全修复）
ruff check --fix --unsafe-fixes lifeprism
```