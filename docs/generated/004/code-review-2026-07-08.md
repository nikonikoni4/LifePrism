# Code Review Report

**审查范围**: 当前工作区变更（`git diff`）  
**审查时间**: 2026-07-08  
**变更文件**: `CONTEXT.md` (+37), `lifeprism/server/main.py` (+25/-9)  
**参考上下文**: `.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## 架构上下文

### 相关 ADR
- 无直接相关的跨平台部署 ADR（**缺失**，建议新增）

### 相关 Spec
- `docs/specs/2026-07-06-config-path-spec.md`：路径解析体系（间接相关）
- `docs/specs/2026-07-06-config-settings-spec.md`：SettingsManager 初始化流程（间接相关）

### 决策覆盖
- 2/2 变更文件无 ADR 关联
- PRD 定义了 7 项实现决策，当前变更仅实现了决策 2（Monitor 平台隔离）的一部分

---

## 审查结果

Found 6 issues:

### Issue 1: CONTEXT.md 将 P2 数据同步描述为已实现功能
- **类型**: Documentation / Architecture
- **置信度**: 92
- **位置**: `CONTEXT.md:27-41`
- **详情**: CONTEXT.md 以现在时肯定语气描述了跨机器数据同步的完整技术设计（主备模式、双向同步、LWW 冲突解决、ID 生成规则、同步范围），但 PRD 明确标注数据同步为 P2（"Out of Scope > P2 - 数据方案"，"数据同步作为 P2 单独讨论，本期不实现"）。代码库中搜索 `双向`、`bidirectional`、`主备`、`last-write-wins`、跨平台同步代码均为**零匹配**。任何读到 CONTEXT.md 的人都会认为数据同步是已实现的现有功能。
- **依据**: PRD L45 "数据同步作为 P2 单独讨论，本期不实现"；PRD L261-273 "Out of Scope > P2 - 数据方案"

### Issue 2: `sys.platform` 平台检查与"多入口架构"决策存在概念冲突
- **类型**: Architecture
- **置信度**: 88
- **位置**: `lifeprism/server/main.py:223-230`
- **详情**: PRD 决策 1 明确要求"创建三个独立的启动入口文件，而非在单一文件中用 if/else 控制"，理由是"不同运行形态是不同的产品形态，不是同一产品的'模式切换'"。但当前在 `main.py` 中增加了 `sys.platform != "win32"` 检查，使 `main.py` 具备了在 Linux 上运行的能力（跳过 Monitor），模糊了三个入口的边界。`main.py` 按设计应该是 Windows 桌面版专属入口，不应存在"在 Linux 上运行 main.py"的合法场景。
- **依据**: PRD L79-83 "多入口架构"决策；PRD L81 "避免 Python import 机制导致的平台依赖问题"

### Issue 3: PRD 定义的测试未实现
- **类型**: Testing
- **置信度**: 85
- **位置**: `test/` 目录（缺失）
- **详情**: PRD 的 Testing Decisions 章节定义了 3 个测试文件共 12 个测试用例：
  - `test/integration/test_startup_modes.py`（5 个用例）
  - `test/core/unit/config/test_settings_manager_cross_platform.py`（4 个用例）
  - `test/core/unit/monitor/test_monitor_platform_check.py`（3 个用例）
  
  经搜索，这 3 个测试文件均**不存在**。新增代码有 4 个执行路径（正常启动 / 非 Windows 跳过 / ImportError 降级 / Exception 降级），缺少自动化测试验证。
- **依据**: PRD L198-258 "Testing Decisions"

### Issue 4: 注释遗漏 `monitor_type` 前置条件
- **类型**: 代码注释合规
- **置信度**: 85
- **位置**: `lifeprism/server/main.py:222`
- **详情**: 注释 `# 集成内置监控进程（仅 Windows 平台）` 只描述了平台条件，完全遗漏了 `monitor_type == "lifeprism"` 这一更前置的配置条件。当 `monitor_type` 为 `"activitywatch"` 时，即使在 Windows 上也**不会**启动 Monitor。注释暗示"只要是 Windows 就会启动"，与代码实际行为不符。
- **依据**: `main.py:223` `if settings._config.get("monitor_type") == "lifeprism"` 是第一层门控

### Issue 5: `app.state.monitor_process = None` 重复赋值
- **类型**: Code Quality
- **置信度**: 82
- **位置**: `lifeprism/server/main.py:223-249`
- **详情**: `app.state.monitor_process = None` 在非 Windows 跳过分支、ImportError 处理分支、Exception 处理分支、以及外层 else 分支中共出现 **4 次**。更简洁的模式是在条件逻辑之前初始化为 `None`，仅在实际启动成功时覆盖赋值，消除 3 处冗余。
- **依据**: 编码规则 DRY 原则

### Issue 6: CONTEXT.md 定位偏离——部署拓扑不是域语言定义
- **类型**: Documentation
- **置信度**: 80
- **位置**: `CONTEXT.md:6-41`
- **详情**: CONTEXT.md 的定位是"项目核心域语言与概念定义。当 issue、提案、测试名、spec 引用这些概念时，使用此处定义的术语"。但新增内容包含部署拓扑（哪个入口有 FastAPI、哪个有 Electron）、Nginx 配置要点、数据同步策略等技术方案细节，属于架构设计文档和部署文档的范畴，不是可被 issue/spec 引用的领域术语。对比同文件 Custom Records 章节，后者定义了 *Custom Record Type*、*Slug*、*Meta Table* 等真正可引用的领域概念，粒度合适。
- **依据**: CONTEXT.md 头部注释定位声明

---

## 变更摘要

本次变更实现了 Linux 跨平台部署 PRD 中的部分内容：

1. **`CONTEXT.md`** (+37 行)：新增跨平台部署域概念，定义三种运行形态和数据同步策略
2. **`lifeprism/server/main.py`** (+25/-9 行)：Monitor 启动逻辑增加三层防护——平台检查（`sys.platform != "win32"`）→ ImportError 捕获 → 通用 Exception 兜底，使 Windows 桌面版在非 Windows 平台上可优雅降级

**正面评价**：
- Monitor 延迟导入 + ImportError 捕获的实现正确，符合 Python 最佳实践
- 日志消息清晰准确，使用 `%s` 占位符符合项目规范
- 降级行为（设置 `None` 后继续运行）合理，Monitor 是辅助功能不应阻塞启动
