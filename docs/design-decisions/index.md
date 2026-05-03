---
version: 1.2
created_at: 2026-04-10
updated_at: 2026-04-24
last_updated: 新增 repository 接口强封装决策文档索引
abstract: 架构决策目录索引，用于导航 ADR 文档并说明长期设计取舍。
---

## repository-interface-encapsulation
- updated_at: 2026-04-24
- path: `docs/design-decisions/2026-04-24-repository-interface-encapsulation.md`
- 触发规则：当需要统一 repository 上层调用边界，并明确禁止业务层穿透 `.provider` 时读取
- 内容摘要：确立 `repository` 强封装策略，采用受控透传替代上层直连 provider，降低混用与误用风险。

## llm-tool-separation-for-detail-query
- updated_at: 2026-05-03
- path: `docs/design-decisions/2026-05-03-llm-tool-separation-for-detail-query.md`
- 触发规则：当设计 LLM Agent 工具时，需要决策是否合并功能相似但信息密度差异大的工具
- 内容摘要：电脑使用详细日志查询工具设计决策，选择独立工具而非合并到聚合查询工具，基于信息密度差异（30-60倍）、使用场景差异和 LLM 工具调用可理解性考虑。核心原则：职责清晰 > 工具数量少，避免误触发 > 统一接口。
