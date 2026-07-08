---
version: 1.0
created_at: 2026-07-08
updated_at: 2026-07-08
last_updated: 2026-07-08
abstract: Linux 跨平台部署采用多入口架构（三个独立启动文件），而非单文件配置控制，以避免 Python import 机制导致的平台依赖问题
status: decided
---

# Linux 跨平台部署：多入口架构 vs 单文件配置控制

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

LifePrism 需要支持三种运行形态：
1. Windows 桌面完整版（FastAPI + Electron + Agent + Monitor）
2. Linux Web Demo（FastAPI + 静态前端 + Agent，无 Monitor）
3. Linux Agent Only（仅 Agent Loop + WeChat Channel，无 FastAPI、无前端、无 Monitor）

必须决定：如何组织启动逻辑，才能在不同平台和运行形态下正确加载/不加载对应模块？

### 讨论范围

- 启动入口文件的数量和组织方式
- 模块导入的时机和方式
- 如何避免 Linux 上导入 Windows 专有依赖（`pywin32`、`pynput`、`mss`）

### 非讨论范围

- 依赖管理（`pyproject.toml` vs `requirements/`）—— 已在对话中决定保持现状
- 路径解析逻辑 —— 已决定保持现有逻辑不变
- 数据同步 —— 作为 P2 单独讨论

### 问题深度

这是架构层面的决策，影响：
- 代码组织和可维护性
- 未来新增运行模式的扩展性
- 启动性能和资源占用
- 开发者理解和调试的复杂度

## 现状

**当前系统**：
- 只有一个启动入口：`lifeprism/server/main.py`
- 所有模块（FastAPI、Monitor、Agent）在顶部导入
- 启动时根据配置决定是否启动某些模块（如 Monitor）

**已知约束**：
- Python import 机制：模块顶部的 import 语句无论如何都会执行，即使后续代码不使用
- Monitor 模块强依赖 Windows API（`pywin32`、`pynput`、`mss`）
- Linux 上可能无法安装这些依赖（待验证）
- 即使能安装，导入时可能因缺少 Windows API 而报错

**已知风险**：
- 在单文件中通过 if/else 控制启动逻辑，无法避免顶部 import 执行
- 条件导入（if 块内 import）虽然可行，但会使代码结构复杂，难以维护

## 可选方案

### 方案 A：单文件 + 配置控制

保持单一启动文件 `main.py`，通过环境变量或配置文件控制运行模式。

**实现方式**：
```python
# main.py
if os.getenv("MODE") == "web_demo":
    # 不导入 Monitor
    from .agent import agent_loop
    app = FastAPI()
    # ...
elif os.getenv("MODE") == "agent_only":
    # 只导入 Agent
    from .agent import agent_loop
    # 不启动 FastAPI
else:
    # Windows 完整版
    from .monitor import monitor
    from .agent import agent_loop
    app = FastAPI()
    # ...
```

**优势**：
- 只有一个入口文件，代码集中
- 通过配置切换模式，灵活性高

**劣势**：
- Python import 机制限制：顶部 import 无论如何都会执行
- 条件导入（if 块内 import）会导致代码结构复杂
- 三种模式的启动逻辑混在一起，难以维护
- 无法避免 Linux 上意外导入 Windows 依赖的风险
- 单元测试困难：需要 mock 环境变量和配置

### 方案 B：多入口架构

创建三个独立的启动文件，每个文件对应一种运行形态。

**实现方式**：
```python
# main.py（Windows 完整版）
from .monitor import monitor
from .agent import agent_loop
app = FastAPI()
# ...

# main_web_demo.py（Linux Web Demo）
from .agent import agent_loop
app = FastAPI()
# 不导入 Monitor

# main_agent_only.py（Linux Agent Only）
from .agent import agent_loop
# 不启动 FastAPI，不导入 Monitor
```

**优势**：
- 每个入口文件职责单一，代码清晰
- 避免 Python import 机制问题：不需要的模块根本不导入
- 依赖按需加载，减少启动时间和内存占用
- 易于测试：每个入口文件独立测试
- 三种运行形态是**不同的产品形态**，而非同一产品的"模式切换"

**劣势**：
- 多个入口文件，代码分散
- 公共逻辑需要抽取到独立模块（但这通常是好的设计）
- 新增运行模式时需要创建新文件

## 最终决策

选择**方案 B：多入口架构**。

创建三个独立启动文件：
- `lifeprism/server/main.py`（Windows 桌面完整版，现有文件小幅修改）
- `lifeprism/server/main_web_demo.py`（Linux Web Demo，新增）
- `lifeprism/server/main_agent_only.py`（Linux Agent Only，新增）

## 决策原因

1. **避免 Python import 机制问题**：
   - 在单文件中无论如何组织 if/else，顶部 import 都会执行
   - 条件导入虽然可行，但会让代码结构变得复杂且难以维护
   - 多入口架构从根本上避免了不需要的模块被导入

2. **运行形态是不同的产品形态**：
   - Windows 完整版、Linux Web Demo、Linux Agent Only 是三种不同的使用场景
   - 不是同一产品的"模式切换"，而是面向不同用户需求的独立形态
   - 独立文件更清晰地表达这种差异

3. **代码可维护性**：
   - 每个入口文件职责单一，易于理解和维护
   - 三种启动逻辑不会互相干扰
   - 公共逻辑自然会被抽取到独立模块，提高代码复用性

4. **启动性能和资源占用**：
   - Agent Only 模式不需要导入 FastAPI 和所有路由
   - 预期内存占用从 ~500MB 降至 < 200MB
   - 启动时间从 ~15 秒降至 < 5 秒

5. **未来扩展性**：
   - 新增运行模式时，只需创建新的入口文件
   - 不会影响现有模式的启动逻辑
   - 易于独立测试和验证

## 后续影响

**代码结构**：
- 需要创建 `main_web_demo.py` 和 `main_agent_only.py`
- 需要将公共初始化逻辑抽取到独立模块（如 `init_database`、`init_logger`）

**启动命令**：
- Windows 桌面版：`uvicorn lifeprism.server.main:app`
- Linux Web Demo：`uvicorn lifeprism.server.main_web_demo:app --host 0.0.0.0 --port 8101`
- Linux Agent Only：`python -m lifeprism.server.main_agent_only`

**文档**：
- 需要在部署文档中说明三种运行模式的区别和使用场景
- 需要提供对应的启动脚本（`start_web_demo.sh`、`start_agent_only.sh`）

**测试**：
- 每个入口文件需要独立的集成测试
- 测试需要验证各模式下模块导入的正确性

**运维**：
- 部署时需要明确使用哪个入口文件
- 监控和日志需要区分不同运行模式

**风险**：
- 如果未来需要在单个进程中支持多种模式，会需要重构
- 但根据当前需求，这种场景不太可能出现
