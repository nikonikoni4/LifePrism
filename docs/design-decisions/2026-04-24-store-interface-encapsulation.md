---
version: 1.0
created_at: 2026-04-24
updated_at: 2026-04-24
last_updated: 明确 repository repository 接口强封装决策，禁止 service 层通过 .provider 访问底层实现
abstract: 记录 repository 层在 provider/aggregator 并存阶段的接口边界决策，统一上层只通过 repository 方法访问，降低混用与误用风险。
status: stable
---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 repository 接口强封装决策文档 |

## 背景介绍/现状

当前项目的 `repository` 层目标是“对外统一 `repository` 接口”，上层通过 `from lifeprism.repository import xxx_store` 使用数据能力。  
在分类模块中，`category_store` 实际映射到 `CategoryAggregator`，而该聚合类内部又持有 `category_provider` 与 `sub_category_provider`。这使得上层调用存在两种写法并存：

- `category_store.insert_category(data)`
- `category_store.category_provider.insert_category(data)`

虽然两种写法都可运行，但它们表达的边界不同，且会导致调用习惯分裂。

## 问题

存在以下持续性风险：

1. 认知成本高：调用方需要先判断当前 repository 是否可直接调用，还是需要穿透 `.provider`。
2. 规范不一致：不同模块（如单表 repository 与聚合 repository）暴露能力形态不同，容易形成“局部经验迁移错误”。
3. AI/协作误用风险高：在自动补全或 AI 生成代码时，常出现一处走 repository、一处走 `.provider` 的混用。
4. 架构边界被弱化：service 层感知到底层 provider 细节，后续重构会扩大影响面。

## 决定

采用 **方案 A：强封装 + 受控透传**，具体如下：

1. service 层只能调用 `xxx_store` 对外暴露的方法，不允许直接调用 `xxx_store.xxx_provider.*`。
2. 对于上层需要且高频的能力，由 aggregator/repository 增加同名或语义清晰的方法进行透传。
3. 透传范围采用白名单策略（优先 CRUD 与常用查询），不做无边界全量暴露。
4. 当存在特殊底层能力需求时，应先在 repository 层新增正式接口，而不是由业务层绕过边界直连 provider。

## 涉及范围

- `lifeprism/repository/__init__.py` 中对外导出的 `*_store` 访问约定
- 聚合类（如 `CategoryAggregator`）的对外方法设计
- server service 层对 repository 的调用方式
- 团队协作、代码评审与 AI 生成代码的接口一致性约束

## 为什么要做这个决定

1. 降低认知负担：统一“只看 repository 接口”，减少调用前判断分支。
2. 提升一致性：避免同类对象在不同文件中出现调用风格漂移。
3. 控制变更影响：隐藏 provider 细节后，底层实现替换或重构不直接外溢到业务层。
4. 适配协作现实：在多人协作与 AI 辅助编码场景下，强约束比“约定优先”更能减少误用。

## 参考资料

- 项目内架构说明：`lifeprism/repository/__init__.py`（Store 统一对外接口注释）
- Law of Demeter（最少知识原则）：https://en.wikipedia.org/wiki/The_Law_of_Demeter
- Repository 与持久层边界实践（Microsoft）：https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/infrastructure-persistence-layer-design
