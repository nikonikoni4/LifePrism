---
version: 2.0
created_at: 2026-04-10
updated_at: 2026-07-14
last_updated: 新增文件同步冲突处理方案 ADR
abstract: 架构决策目录索引，用于导航 ADR 文档并说明长期设计取舍。
---

## dynamic-tables-sync-definition-comparison
- updated_at: 2026-07-16
- path: `docs/adr/2026-07-16-dynamic-tables-sync-definition-comparison.md`
- 触发规则：当需要理解动态表同步的触发机制、为什么新增端点拉取云端定义、为什么删除 get_all_sync_tables、或修改动态表建表流程时读取
- 内容摘要：采用"拉取云端定义 → 本地 slug 对比 → 双向建表"方案，替代原 pull 前后快照对比。新增 `GET /api/sync/dynamic-tables-definitions` 端点查询云端 types + fields 两张 meta 表，本地用 slug 集合对比触发双向建表（本地建表只执行 DDL 不写 meta，让 pull 统一同步数据）。删除 `get_all_sync_tables`，动态表列表由建表步骤产出。决策前提：动态表字段不会被修改（前提 1）、主备模式（前提 2）、sync_once 期间无并发修改（前提 3，假设，需独立决策并发锁）。

## file-sync-conflict-resolution
- updated_at: 2026-07-16
- path: `docs/adr/2026-07-14-file-sync-conflict-resolution.md`
- 触发规则：当需要理解文件同步的冲突处理方案、为什么白名单只包含 session/diary/agent/user、account.json 为什么改数据库存储、或修改文件同步的增量识别和冲突判定逻辑时读取
- 内容摘要：五个关联决策——（决策 1）采用 per-file version tracking（parent_hash + current_hash + 11 状态决策矩阵）替代纯 LWW mtime 比较；（决策 2）同步白名单对齐 Agent 工具白名单（ALLOWED_DIRS + session），chat_history.json 明确排除（云端无 dreaming task 不会变更）；（决策 3）MD 冲突由 AI 驱动解决（新增 CONFLICT_RESOLVE 消息类型），AI 直接拿到两份文档内联内容，可用 read_file 读相关上下文做智能合并，替代用户手动处理。冲突备份路径为 sync_conflict/{timestamp}/，不在 SYNC_DIRECTORIES 和 ALLOWED_DIRS 中，AI 无法直接读取，仅做安全兜底；（决策 4）account.json 改为数据库存储（wechat_account_state 表），从文件白名单移除；（决策 5）API 协议采用三阶段设计（check → fetch/push → verify），mtime 第一重过滤 + hash 精确判断 + verify 一致性校验。v2.3 补充：决策 5 原遗漏"文件存在性判断"讨论，导致回归 bug（云端重装后本地未改文件被错误 SKIP），修复方案为 check 端点新增返回 `all_paths`（完整路径清单）。决策基于主备模式前提（同一时间只有一端 Agent 工作），备选触发覆盖 6 种前提失效场景。

## sync-full-sync-strategy
- updated_at: 2026-07-14
- path: `docs/adr/2026-07-14-sync-full-sync-strategy.md`
- 触发规则：当需要理解同步系统全量同步触发机制、为什么不做云端维护同步时间、或修改 LWW 冲突解决中"时间相等"处理逻辑时读取
- 内容摘要：两个关联决策——（决策 1）全量同步采用"重置同步进度按钮"方案（清空本地 last_sync_time 触发全量同步），否决"云端维护 sync_state 表"方案。核心原因：方案二是务实的最小可行方案，方案一引入云端状态管理复杂度且在多客户端轮流同步场景下存在静默数据丢失风险。（决策 2）LWW 中 updated_at 相等时跳过而非覆盖，Push 端 `>` 改为 `>=`，Pull 端新增相等跳过分支。决策前提：当前单客户端使用模式，方案二能完全覆盖换服务器/云端 DB 重置/本地 DB 重置场景。备选触发：多客户端场景出现时重新评估方案一。

## custom-records-time-string-not-convert
- updated_at: 2026-07-13
- path: `docs/adr/2026-07-13-custom-records-time-string-not-convert.md`
- 触发规则：当需要理解自定义记录模块中自定义字段的时间处理策略、为什么自定义字段时间不做 UTC 转换、或计划新增系统级 datetime 字段时读取
- 内容摘要：两个关联决策——（决策 A）自定义字段中的时间视为普通字符串，原样存储原样显示，不做时区转换；核心原因是自定义字段是"用户数据"而非"系统时间"。（决策 B，未来方向）为动态表新增必填系统级 datetime 字段替代 created_at 做日期筛选，Agent 输入本地 YYYY-MM-DD HH:MM:SS 经格式校验后转 UTC ISO 存储。决策 A 的前提：自定义字段不用于查询/筛选、field_type 不引入 date/datetime 类型、YYYY-MM-DD HH:MM:SS 格式天然字典序=时间序。

## date-to-utc-conversion-boundary
- updated_at: 2026-07-13
- path: `docs/adr/2026-07-13-date-to-utc-conversion-boundary.md`
- 触发规则：当需要理解前端日期查询的转换位置、单表/聚合查询的参数传递策略、或新增日期查询 API 时读取
- 内容摘要：确立日期到 UTC 时间范围的转换边界为"组件内转换"（组件 onChange 回调），系统内部保持 UTC ISO 8601 纯净格式。单表查询：有 date 字段传 date，只有 datetime 传 start_time/end_time（UTC）。聚合查询（混合表）传 date + start_time/end_time，后端根据表结构选择使用哪个参数。决策基于：工程复用性不存在（只有 2 处转换）、架构清晰性优先、前端日期来源可靠（input[type="date"] 保证格式）。决策前提：转换需求量 <= 5 个 API、无统一 DatePicker 组件、14 行代码重复可接受。

## time-conversion-layering
- updated_at: 2026-07-12
- path: `docs/adr/2026-07-12-time-conversion-layering.md`
- 触发规则：当需要理解时间转换在哪个层级进行、为什么不用装饰器自动转换、或新增 LLM 工具时参考转换模式时读取
- 内容摘要：确立时间转换的层级边界——前端负责双向转换（就近转换原则），后端工具函数输入输出保持 UTC ISO 8601。转换发生在 execute 方法层（工具调用入口），而非工具函数内部或 Repository 层。决策基于：代码可读性与显式性 > 自动化、后端工具函数可被非 LLM 调用（需保持 UTC 纯净）。

## key-fallback-strategy
- updated_at: 2026-07-14
- path: `docs/adr/2026-07-09-key-fallback-strategy.md`
- 触发规则：当需要理解密钥存储策略、Key 为什么从 config.yaml 迁移到 storage.yaml、storage.yaml 的命名原因、run_mode 隔离逻辑、或修改云端/本地的 Key 读取写入路径时读取
- 内容摘要：v1.0 决策 keyring + config.yaml fallback，否决 .env 环境变量方案。v1.1 将 Key 从 config.yaml 分离到 storage.yaml（权限 600），