---
date: 2026-04-25
type: investigation
status: completed
topic: 分层架构中的异常处理最佳实践
---

# 异常处理最佳实践调查报告

## 1. 背景

在代码审查过程中发现，当前 repository 层的数据库操作存在异常处理不一致的问题：部分方法在捕获异常后返回默认值（如 `None`、`False`、空列表），而不是将异常向上传播。这导致上层无法区分"数据不存在"和"数据库错误"两种情况，影响错误处理和调试。

为验证现有编码规范的合理性，启动本次调查，研究主流框架和架构理论中的异常处理最佳实践。

## 2. 当前仓库规则

根据 `docs/coding-rules/backend-core-rules.md` 第 92-105 行，当前规则为：

### 错误处理分层

- **repository 层（数据访问层）**
  - 范围：repository、llm、processor、monitor 等外部接口
  - 职责：捕获外部异常，转换为业务异常并抛出

- **Service 层（业务逻辑层）**
  - 范围：server/service
  - 职责：让异常自然冒泡，不捕获异常

- **API 层（路由处理层）**
  - 范围：server/api
  - 职责：使用全局异常处理器统一处理

## 3. 调查结果

### 3.1 主流框架实践

调查了三个主流框架的异常处理模式：

| 框架 | Repository 层 | Service 层 | API 层 | 全局处理器 |
|------|--------------|-----------|--------|-----------|
| **FastAPI** | 让异常传播 | 仅在需要时转换 | 最小化处理 | `@app.exception_handler()` |
| **Django** | 抛出 ORM 异常 | 传播异常 | 捕获并转换 | DRF exception handler |
| **Spring Boot** | 让异常传播 | 传播或包装 | 委托给全局 | `@ControllerAdvice` |

**共识**：所有框架都遵循"让异常从 repository 向上传播到全局处理器"的模式。

### 3.2 Clean Architecture 原则

根据 Clean Architecture 和 DDD 理论：

1. **Repository 必须转换异常**
   - 理由：保护领域层不受基础设施污染（依赖倒置原则）
   - 做法：捕获技术异常（如 `SQLException`）→ 转换为领域异常（如 `PersistenceException`）→ **抛出**

2. **Service 层通常不捕获异常**
   - 理由："Throw Early, Catch Late" 原则
   - 做法：让异常自然传播，仅在需要添加业务上下文时才捕获并重新抛出

3. **异常转换发生在架构边界**
   - 基础设施层 → 领域层：Repository 转换
   - 领域层 → 应用层：通常不转换
   - 应用层 → 表示层：全局处理器转换为 HTTP 响应

### 3.3 规则验证结果

| 当前规则 | 是否合理 | 证据强度 | 需要补充 |
|---------|---------|---------|---------|
| Repository 层捕获并转换异常 | ✅ 正确 | 高（Tier A） | ⚠️ 必须明确"转换后抛出"，不能返回默认值 |
| Service 层不捕获异常 | ✅ 正确 | 高（Tier A） | 无 |
| API 层全局异常处理器 | ✅ 正确 | 高（Tier A） | 无 |

### 3.4 关键发现

**当前规则正确，但缺少关键细节：**

1. **Repository 层的正确做法**：
   - ✅ 捕获技术异常（如数据库错误）
   - ✅ 转换为领域异常
   - ✅ **抛出异常**（使用 `raise`）
   - ❌ **不应返回默认值**（如 `None`、`False`、`[]`）

2. **为什么不能返回默认值**：
   - 无法区分"数据不存在"和"数据库错误"
   - 上层无法做出正确决策（如是否重试）
   - 违反"Fail Fast"原则
   - 调试困难（堆栈跟踪丢失）

3. **异常链保留**：
   - 使用 `raise ... from e` 保留原始异常信息
   - 便于调试和日志分析

## 4. 信息来源

### Tier A 来源（官方文档、权威讨论）

- [FastAPI Official - Handling Errors](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Microsoft: Design for exception safety](https://learn.microsoft.com/en-us/cpp/cpp/how-to-design-for-exception-safety)
- [Where would you handle exceptions: controller, service, repository?](https://softwareengineering.stackexchange.com/questions/393307)
- [Should service layer catch all dao exceptions?](https://softwareengineering.stackexchange.com/questions/260673)
- [Clean Architecture exceptions](https://stackoverflow.com/questions/73339309)
- [Exceptions: Why throw early? Why catch late?](https://softwareengineering.stackexchange.com/questions/231057)

### Tier B 来源（高质量工程博客、社区共识）

- [FastAPI Error Handling Patterns](https://betterstack.com/community/guides/scaling-python/error-handling-fastapi/)
- [Spring boot exception handling best practice](https://stackoverflow.com/questions/66762006)
- [Should Repositories Throw Domain Errors](https://stackoverflow.com/questions/66480794)
- [Infrastructure storage exception handling in DDD-ish app](https://stackoverflow.com/questions/79827485)
- [Error handling in Clean Architecture](https://gist.github.com/navinpd/efe14b49f4a638a7316ead2176d73d87)

## 5. 结论与建议

### 5.1 结论

当前编码规范的三层异常处理策略**完全正确**，符合主流框架和架构理论的最佳实践。

### 5.2 建议补充规则

在 `docs/coding-rules/backend-core-rules.md` 中补充以下细节：

1. **Repository 层必须抛出异常**：
   - 捕获技术异常后，转换为领域异常并使用 `raise` 抛出
   - 禁止返回 `None`、`False`、空列表等默认值来掩盖错误
   - 使用 `raise ... from e` 保留异常链

2. **区分"数据不存在"和"操作失败"**：
   - 数据不存在：抛出 `EntityNotFoundException`（404）
   - 数据库错误：抛出 `PersistenceException`（500）

3. **Service 层的例外情况**：
   - 仅在需要添加业务上下文时才捕获并重新抛出
   - 大多数情况下应让异常自然传播

### 5.3 实施方案

项目可根据规模选择两种实施方案：

- **方案 A（严格 Clean Architecture）**：定义领域异常层次结构，适合大型项目
- **方案 B（FastAPI 实用主义）**：直接使用 `HTTPException`，适合中小型项目

具体实施细节可参考调查过程中收集的代码示例。

---

**调查完成日期**：2026-04-25  
**调查人员**：Claude (Opus 4.7)  
**审查状态**：待团队评审
