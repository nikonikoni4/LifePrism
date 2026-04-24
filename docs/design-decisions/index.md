---
version: 1.2
created_at: 2026-04-10
updated_at: 2026-04-24
last_updated: 新增 store 接口强封装决策文档索引
abstract: 架构决策目录索引，用于导航 ADR 文档并说明长期设计取舍。
---

## store-interface-encapsulation
- updated_at: 2026-04-24
- path: `docs/design-decisions/2026-04-24-store-interface-encapsulation.md`
- 触发规则：当需要统一 storage 上层调用边界，并明确禁止业务层穿透 `.provider` 时读取
- 内容摘要：确立 `store` 强封装策略，采用受控透传替代上层直连 provider，降低混用与误用风险。
