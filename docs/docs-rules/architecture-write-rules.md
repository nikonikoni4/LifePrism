---
version: 1.2
created_at: 2026-04-10
updated_at: 2026-04-14
last_updated: 迁移 architecture 规则到 docs/docs-rules
abstract: docs/ARCHITECTURE.md 的专属写作规则，约束其内容边界、必备覆盖面和更新触发条件。
---

# architecture-write-rules

`docs/ARCHITECTURE.md` 的目标是让第一次进入项目的人或 AI 快速看见全貌，因此必须遵守：

<rules>

1. 保持简洁，只写系统地图，不写局部实现细节。
2. 必须覆盖：
   - 项目整体定位
   - 主要物理目录及职责
   - 抽象系统分层
   - 前端架构
   - 后端架构
   - 主干数据流
   - 关键依赖方向
   - 文档导航
3. 优先说明稳定结构，不要写当前一次任务才会用到的临时方案。
4. 当以下内容发生变化时，应同步检查是否需要更新：
   - 顶层模块职责
   - 前后端主分层
   - 关键数据流
   - 关键依赖方向
   - 文档体系边界

</rules>

<never_do>

不要把 `docs/ARCHITECTURE.md` 写成规则手册、接口文档或执行计划。

</never_do>
