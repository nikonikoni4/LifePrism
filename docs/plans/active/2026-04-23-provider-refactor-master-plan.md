---
version: 1.0
created_at: 2026-04-23
updated_at: 2026-04-23
last_updated: 创建 provider 重构总计划
abstract: Provider 重构总计划，定义重构顺序、流程和必读文档
title: Provider 重构总计划
status: active
related_spec: 
---

# Provider 重构总计划

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 provider 重构总计划 |

---

## 1. 重构目标

将分散在 `server/providers/` 和 `llm/providers/dataset_providers/` 的数据访问层代码统一迁移到 `storage/providers/`，建立清晰的三层架构：

- **Provider 层**（`storage/providers/`）：原子的数据库操作
- **Aggregator 层**（`storage/aggregators/`）：数据聚合计算
- **Service 层**（`server/services/` 或 `llm/services/`）：业务逻辑

---

## 2. 重构顺序

按照耦合度和复杂度从低到高，分 5 个阶段进行：

### 阶段 1：试点重构（验证流程）
**目标**：验证迁移流程和测试方法的可行性

| Provider | 方法数 | 耦合度 | 预计时间 |
|---------|--------|--------|---------|
| diary_provider | 5 | 低（仅 diary_service） | 3 天 |
| mood_provider | 15 | 低（仅 mood_service） | 2 天 |

**里程碑**：完成 2 个最简单的 provider 迁移，验证快照测试方法有效

### 阶段 2：生态迁移（保持内聚）
**目标**：迁移 habit 相关的 provider 生态

| Provider | 方法数 | 耦合度 | 预计时间 |
|---------|--------|--------|---------|
| habit_provider | 6 | 低-中（habit_service + 3 个相关 provider） | 3 天 |
| habit_checkin_provider | 8 | 低-中 | 2 天 |
| habit_stats_provider | 4 | 低-中 | 2 天 |

**里程碑**：habit 模块内部数据访问统一到 storage 层

### 阶段 3：LLM 前置（goal）
**目标**：在 LLM 模块重构前完成 goal_provider 迁移

| Provider | 方法数 | 耦合度 | 预计时间 |
|---------|--------|--------|---------|
| goal_provider | 13 | 中（3 个 service + LLM 分类） | 5 天 |

**里程碑**：goal 数据访问统一，为 LLM 模块集成做准备

### 阶段 4：核心业务（todo）
**目标**：迁移最核心的 todo 业务逻辑

| Provider | 方法数 | 耦合度 | 预计时间 |
|---------|--------|--------|---------|
| todo_provider | 22 | 中（4 个 service） | 5 天 |

**里程碑**：todo 核心功能迁移完成，充分测试

### 阶段 5：复杂统计（statistical_data）
**目标**：迁移最复杂的统计查询 provider

| Provider | 方法数 | 耦合度 | 预计时间 |
|---------|--------|--------|---------|
| statistical_data_providers | 21 | 高（6 个 service + LLM 集成） | 7 天 |

**里程碑**：所有统计查询迁移完成，完整回归测试通过

### 阶段 6：提取 Aggregator
**目标**：将复杂的数据聚合逻辑从 service 提取到 aggregator 层

**预计时间**：3 天

**里程碑**：创建 `storage/aggregators/` 目录，提取多表联合查询和统计逻辑

### 阶段 7：LLM 模块集成与清理
**目标**：删除 `llm/providers/dataset_providers/`，LLM 模块直接使用 `storage.providers`

**预计时间**：3 天

**里程碑**：
- 删除旧代码
- 全量测试通过
- 更新架构文档

---

## 3. 重构流程

每个 provider 的迁移遵循以下 4 步流程：

### 步骤 1：测试准备（1 天）
- [ ] 识别依赖该 provider 的所有 service
- [ ] 为每个 service 编写快照测试
- [ ] 准备测试数据（确保非空）
- [ ] 运行测试，生成快照文件
- [ ] 提交快照到 git

### 步骤 2：重构 provider（1-2 天）
- [ ] 在 `storage/providers/` 创建新 provider
- [ ] 实现 5 个核心方法（query/get/insert/update/delete）
- [ ] 实现特殊方法（批量操作、统计查询等）
- [ ] 编写 provider 单元测试

### 步骤 3：替换调用（1-2 天）
- [ ] 在 service 中逐步替换 provider 调用
- [ ] 每替换一个方法，运行快照测试
- [ ] 如有差异，分析并修复
- [ ] 确认所有快照测试通过

### 步骤 4：清理验证（0.5 天）
- [ ] 删除旧 provider
- [ ] 运行完整测试套件
- [ ] 手动测试关键功能
- [ ] 更新文档

---

## 4. 必须阅读的文档

### 4.1 重构前必读

在开始任何 provider 迁移之前，必须阅读以下文档：

1. **架构设计草案**（理解重构目标和新架构）
   - `docs/temp/refactor-repository-architecture-draft/2026-04-23-refactor-repository-architecture-draft.md`

2. **测试规范**（掌握快照测试方法）
   - `docs/temp/refactor-repository-architecture-draft/2026-04-23-provider-migration-testing-guide.md`

3. **Provider 编写规范**（待创建，阶段 0 产出）
   - `docs/coding-rules/provider-standards.md`

### 4.2 迁移过程中参考

在迁移具体 provider 时，参考以下文档：

1. **通用查询接口规范**
   - 见架构草案第 3.3 节

2. **方法命名规范**
   - 见架构草案第 3.2 节

3. **错误处理规范**
   - 见架构草案第 3.7 节

4. **快照测试模板**
   - 见测试指南第 2.2 节

### 4.3 完成后更新

每个阶段完成后，需要更新以下文档：

1. **架构文档**
   - `docs/ARCHITECTURE.md`

2. **设计决策记录**（重构完成后）
   - `docs/design-decisions/YYYY-MM-DD-provider-layer-refactor.md`

---

## 5. 关键规则

### 5.1 测试规则

1. **数据非空原则**：快照测试必须基于真实数据，空数据应 skip 测试
2. **排除动态字段**：时间戳、自动生成 ID 等不应包含在快照中
3. **排序一致性**：列表数据必须排序后再对比
4. **人工审查**：快照不匹配时，必须人工确认差异是否合理

### 5.2 迁移规则

1. **渐进式替换**：每替换一个方法，立即运行测试验证
2. **保持兼容**：迁移期间保留旧 provider，确保可回滚
3. **先测试后重构**：必须先生成快照，再开始重构
4. **验证后删除**：所有测试通过后，才能删除旧代码

### 5.3 Provider 编写规则

1. **5 个核心方法必须实现**：
   - `query_{table}()` - 通用查询接口
   - `get_{table}_by_id()` - 按 ID 查询
   - `insert_{table}()` - 插入记录
   - `update_{table}()` - 更新记录
   - `delete_{table}()` - 删除记录

2. **职责单一**：Provider 只做数据库操作，不包含业务逻辑

3. **返回原始数据**：返回 Dict，不做业务转换

---

## 6. 风险和缓解措施

### 6.1 风险

1. **迁移工作量大**：20+ provider，73 个方法
2. **测试覆盖不足**：部分 provider 可能缺少测试
3. **导入路径变更**：可能影响现有代码
4. **快照测试数据准备**：需要确保测试数据非空且有效

### 6.2 缓解措施

1. **渐进式迁移**：按优先级排序，从简单到复杂
2. **快照测试保障**：重构前为所有 service 编写快照测试
3. **兼容层**：保留旧导入路径，逐步过渡
4. **测试数据生成器**：编写 fixtures 自动生成测试数据
5. **回滚机制**：使用 git 分支管理，确保可回滚

---

## 7. 时间估算

| 阶段 | 任务 | 预计时间 |
|------|------|---------|
| 阶段 0 | 制定标准文档 + 测试规范 | 1 天 |
| 阶段 1 | 试点重构（diary + mood） | 5 天 |
| 阶段 2 | 生态迁移（habit 系列） | 7 天 |
| 阶段 3 | LLM 前置（goal） | 5 天 |
| 阶段 4 | 核心业务（todo） | 5 天 |
| 阶段 5 | 复杂 provider（statistical_data） | 7 天 |
| 阶段 6 | 提取 aggregator | 3 天 |
| 阶段 7 | LLM 模块集成 + 清理 | 3 天 |

**总计**：约 5-6 周

---

## 8. 成功标准

### 8.1 技术标准

- [ ] 所有 provider 迁移到 `storage/providers/`
- [ ] 所有快照测试通过
- [ ] 删除 `server/providers/` 和 `llm/providers/dataset_providers/`
- [ ] 创建 `storage/aggregators/` 并提取聚合逻辑
- [ ] 所有集成测试通过

### 8.2 质量标准

- [ ] 代码覆盖率不低于重构前
- [ ] 无性能回退
- [ ] 所有 service 行为与重构前一致
- [ ] 文档更新完整

### 8.3 架构标准

- [ ] 依赖方向正确：Service → Provider
- [ ] 职责清晰：Provider（数据访问）、Aggregator（数据聚合）、Service（业务逻辑）
- [ ] 代码复用：LLM 模块零成本复用所有数据访问

---

## 9. 下一步行动

1. **阶段 0：准备工作**（当前）
   - [ ] 评审本总计划
   - [ ] 编写 `docs/coding-rules/provider-standards.md`
   - [ ] 准备测试环境（安装 pytest-snapshot）
   - [ ] 创建测试数据生成器

2. **阶段 1：启动试点**
   - [ ] 迁移 diary_provider（3 天）
   - [ ] 迁移 mood_provider（2 天）
   - [ ] 评估试点结果，调整方案

3. **后续阶段**
   - 按照重构顺序逐步推进
   - 每个阶段完成后评估，必要时调整计划
