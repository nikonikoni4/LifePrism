---
version: 2.1
created_at: 2026-04-09
updated_at: 2026-07-06
last_updated: 去除 key_function 时间戳；新增 Functional Checklist 章节（功能完整性清单）
abstract: 正式 spec 写入规则，定义 spec 的职责、结构、函数位置标注、功能完整性清单和模块拆分判断
---

# spec-write-rules.md

## 1. Spec 的定位

### Spec = 业务意图 + 技术契约 + 设计决策

**Spec 应该回答的问题**：
1. **这个模块要解决什么业务问题？**（业务意图）
2. **这个模块对外承诺什么？**（技术契约：API、Schema、状态机规则）
3. **为什么这样设计？**（设计决策：权衡、约束、演进史）

**Spec 不应该写的**：
1. **怎么实现的？**（这是 Flow 的职责）
2. **完整的调用链路？**（这是 Flow 的职责）
3. **详细的执行步骤？**（这是 Flow 的职责）

### Spec 与 Flow 的分工

| 维度 | Spec | Flow |
|------|------|------|
| **业务意图** | ✅ 核心职责 | ❌ 不写 |
| **功能完整性清单** | ✅ 核心职责 | ❌ 不写 |
| **技术契约** | ✅ 完整定义 | 📝 引用（不重复定义） |
| **对外接口** | ✅ 函数签名 + 位置 | 📝 引用 + 完整调用链 |
| **状态机规则** | ✅ 抽象定义 | ✅ 具体实现路径 |
| **设计决策** | 📝 简要说明 | ❌ 不写 |
| **数据流路径** | ❌ 不写 | ✅ 核心职责 |
| **内部实现函数** | ❌ 不写 | ✅ 核心职责 |
| **反常设计** | ❌ 不写 | ✅ 核心职责 |

## 2. 核心规则

### 2.1 对外接口的函数位置标注（⭐ 核心）

#### "对外接口"的定义

1. **模块的公共接口**（被其他模块调用的关键函数）
2. **架构关键节点**（核心编排入口，如 `GroupChat.send_message_to_agent`）
3. **导出的工具函数**（如果有专门的工具模块）

#### 不同类型模块的特殊处理

**基础数据模型层**（如 foundation）：
- 标注工具函数（renderer、paths、token 工具等）
- **不标注**：数据类、枚举类、常量、异常类

**API 路由层**（如 FastAPI、Flask）：
- 标注**路由处理函数**，而非 Service 层函数
- **只标注核心端点**（用户最常用的 3-8 个端点），而非全部端点
- 在端点总览表格中添加"路由处理函数"列，建立 HTTP 端点与函数的映射

**前端模块**（TypeScript/JavaScript）：
- 标注导出的类的公共方法（如 `WebSocketManager.connect`）
- 标注关键工具函数（如 `mockableRequest`）
- **不标注**：简单的 API 封装函数（函数体只有一行 `return apiClient.get/post(...)`）
- **不标注**：类的私有方法（以 `_` 开头）、类型定义（interface、type）

#### 必须使用 key_function 标签

**格式**（严格遵守，自动同步工具依赖此格式）：
```markdown
<key_function>
- lifeprism/core/communication/message_router.py
  - message_router.MessageRouter.register:45
  - message_router.MessageRouter.unregister:67
  - message_router.MessageRouter.send_message:89
</key_function>
```

**格式规则**（必须严格遵守）：
- 标签格式：`<key_function>` 和 `</key_function>`
- 文件路径：从仓库根目录开始，使用 `-` 开头
- 函数列表：使用 `  -` 开头（2个空格 + `-`）
- 函数签名格式（重要）：[file_name].[class_name(如果有)].[func_name]
  - Python 类方法：`FileName.ClassName.method_name`
  - Python 模块函数：`FileName.function_name`
  - TypeScript/JavaScript 类方法：`FileName.ClassName.method_name`
  - TypeScript/JavaScript 模块函数：`FileName.function_name`
- 行号：`:行号`（编辑器可点击）

**自动同步机制**：
- 读取 `docs/specs/*.md` 时 hook 自动调用 `sync_docs.py`
- 脚本解析此标签格式，从 `ast_scan_result.json` 查找函数行号
- 自动更新行号（不更新时间戳，避免频繁无意义提交）

#### spec 与 flow 的 key_function 区别

| 维度 | spec 的 key_function | flow 的 key_function |
|------|---------------------|---------------------|
| **范围** | 只写对外接口（契约入口） | 写完整调用链路（包括内部函数） |
| **目的** | 提供契约验证入口 | 提供导航索引 |
| **数量** | 少（3-10 个） | 多（10-50 个） |
| **选择标准** | 被其他模块调用 or 架构关键节点 | 影响 Flow 对象的所有关键节点 |

#### 判断标准：哪些函数应该写进 spec？

**写进 spec**：
- ✅ 模块的公共 API（被其他模块调用）
- ✅ 架构关键节点（核心编排入口）
- ✅ 导出的工具函数

**不写进 spec**：
- ❌ 内部实现函数（只被模块内部调用）
- ❌ 辅助函数（格式化、校验）
- ❌ 回调函数

### 2.2 内容边界

**必须写入**：
1. 数据库表结构（字段、约束、索引）
2. 核心 API 接口（路径、参数、Response 格式）
3. API Request/Response Schemas（**完整定义所有字段**）
   - 原因：Schema 是技术契约的核心，相对稳定，对调用方至关重要
   - API 层：所有请求和响应的 Schema
   - Service 层：对外返回的数据结构 Schema
4. 核心数据流转规则（状态机、优先级、计算规则）
5. 对外接口的函数位置（使用 key_function 标签）

**禁止写入**：
1. 内部实现的函数签名（只能写对外接口）
2. 具体的代码逻辑（循环、条件判断、查询语句）
3. 完整的调用链路（这是 Flow 的职责）
4. 临时的执行细节（迁移步骤、阶段拆解）
5. 过度具体的前端细节（TypeScript 类型、组件状态、样式代码）

**判断原则**：
- 如果内容在 3 个月后可能已经变化 → 不写
- 如果内容是"怎么实现"而非"是什么" → 不写

### 2.3 功能完整性清单（⭐ Functional Checklist）

#### 目的

**防止 AI agent 修改代码时破坏已实现的功能。**

Functional Checklist 是该模块**已验证可正常工作**的功能点列表。它的核心作用是：
1. **回归验证** — 修改代码后，逐项检查清单确保已有功能未被破坏
2. **功能边界** — 明确告诉 AI "这些功能已经实现且必须保持正常"
3. **可检查性** — 每一项都是可验证的具体行为，而非抽象描述

#### 写法要求

**每项功能点必须是可逐项打勾的**：
- ✅ 好的写法：`用户点击"开始监控"按钮后，系统在 3 秒内开始截图`
- ❌ 坏的写法：`监控功能正常工作`

**按功能分组**，每组对应一个用户可感知的功能模块：
```markdown
### 核心监控
- [ ] 定时截图：按配置间隔自动触发截图
- [ ] 手动截图：用户点击按钮立即截图
- [ ] 截图存储：截图保存到 lifeprismData/dataset/ 目录

### AI 分析
- [ ] 文本分析：截图文字提取并发送到 LLM 分析
- [ ] 行为总结：每小时生成行为摘要
```

**不写进 Functional Checklist 的**：
- 内部实现细节（如"数据库连接池大小=5"）
- 性能指标（除非是用户可感知的功能承诺）
- 已在 Technical Contract 中详细定义的内容（避免重复）

#### 与 Technical Contract 的关系

| Functional Checklist | Technical Contract |
|---------------------|-------------------|
| 用户视角的功能行为 | 技术视角的接口契约 |
| "做什么"（面向验收） | "怎么对接"（面向调用方） |
| 修改代码时的回归检查清单 | 修改接口时的兼容性检查依据 |

两者互补，不重复。Checklist 关注功能完整性，Contract 关注接口稳定性。

### 2.4 文档结构

每个正式 `spec` 默认按以下结构编写：

1. `Overview` - 业务问题和核心职责
2. `Scope` - 范围内和范围外
3. `Functional Checklist` - 功能完整性清单（可逐项验证的功能点）
4. `Technical Contract` - 技术契约（对外接口、数据模型、状态机规则）
5. `Design Rationale` - 设计理由、约束、已知限制
6. `Interaction / UX Notes`（可选）- 前端交互规则
7. `Out of Scope` - 链接到其他相关 spec

### 2.5 模块拆分判断（⭐ 重要）

#### 应该拆分成多个 spec

- 每个子模块有明确的单一职责
- 子模块之间通过明确的接口交互
- 依赖方向单向（A 依赖 B，B 不依赖 A）
- 单个 spec > 500 行

#### 应该合并成一个 spec

- 必须一起理解才能明白完整逻辑
- 子模块之间没有清晰的接口边界
- 即使拆分，每个 spec < 100 行

#### 拆分后需要总览文档

拆分后添加模块总览文档（如 `core-module-overview.md`），包含：
1. 模块整体职责
2. 子模块分层架构图
3. 依赖规则说明
4. 子模块 spec 索引
5. 跨层交互的典型场景

#### 保持 spec 之间的链接

每个 spec 都应该：
- 在 **Scope** 章节明确范围外的内容
- 在 **Out of Scope** 章节链接到相关的其他 spec

## 3. 写入模板

```md
---
version: 1.0
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
last_updated:
abstract:
---

# {title}

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |

## Overview

**业务问题**：[这个模块要解决什么问题？]

**核心职责**：[这个模块做什么、不做什么？]

## Scope

### 范围内

- [列出本模块的核心职责]

### 范围外

- [列出不属于本模块的内容，并链接到相关 spec]

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### [功能分组 1]

- [ ] [可验证的功能点描述]
- [ ] [可验证的功能点描述]

### [功能分组 2]

- [ ] [可验证的功能点描述]

## Technical Contract

### [子系统名称]

<key_function>
- path/to/file.py
  - file.ClassName.method_name:行号
  - file.function_name:行号
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| method_name(params) | 接口说明 | 约束条件 |

### 数据模型

[核心数据结构定义]

### 状态机规则（如果有）

[状态转换规则的抽象定义]

### API 端点（如果有）

[HTTP API 的完整契约]

## Design Rationale

**为什么这样设计？**
- [设计理由]

**有哪些约束？**
- [技术约束、业务约束]

**有哪些已知限制？**
- [当前无法支持的场景]

**相关 ADR**：
- [链接到相关的架构决策记录]

## Interaction / UX Notes

[仅在前端功能或交互功能需要时保留]

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **[模块名]**：[链接] - [说明]
```

## 4. 禁止事项

1. 直接将 `brainstorming` 产出的高细节内容原样写入 `docs/specs`
2. 把执行步骤、迁移步骤、阶段拆解直接写成正式 `spec`
3. 在缺少 `Technical Contract` 的情况下，将文档标记为正式 `spec`
4. **写明内部实现的函数签名**（只能写对外接口的函数签名，使用 key_function 标签）
5. **写入完整的调用链路**（这是 Flow 文档的职责）
6. **对外接口不使用 key_function 标签标注函数位置**
