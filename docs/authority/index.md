## path-config.md

- updated_at: 2026-02-12
- path: `docs/authority/path-config.md`
- 触发规则：修改路径配置相关代码时阅读（settings_manager.py、配置文件路径、数据路径迁移）
- 内容摘要：路径配置体系权威参考，定义 config_base_path（固定）、lifeprism_data_path（可迁移）、数据库路径（自动推算）的解析规则和优先级

## plandoc-sync.md

- updated_at: 2026-02-26
- path: `docs/authority/plandoc-sync.md`
- 触发规则：修改计划书 MD 同步逻辑时阅读（plandoc_sync_service.py、taskpool_service.py、todoblock 解析）
- 内容摘要：计划书 MD 文档与数据库双向同步规则，定义 todoblock 格式、锚点规范、缩进父子关系算法、同步触发时机
