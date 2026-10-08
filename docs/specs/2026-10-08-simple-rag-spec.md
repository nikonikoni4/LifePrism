---
version: 1.1
created_at: 2026-10-08
updated_at: 2026-10-08
last_updated: 补齐 agent_only 实际接收入口，验证正常模式发送和云端接收流程
abstract: 个人资料与日记的版本化 RAG 索引；固定豆包嵌入和阿里云重排模型、默认 vec 检索、可选 BM25、每日记忆更新后独立单向同步完整 SQLite 快照。
---

# Simple RAG

## 版本

| 版本 | 更新内容 |
|------|---------|
| 1.0 | 设置、原生检索工具、每日完整构建与云端快照发布 |
| 1.1 | 接通独立 agent_only 启动入口；验证实际 HTTP 上传、确认失败重试与 SSH 地址选择；补齐代理上传限制 |

## Overview

为聊天 Agent 提供个人资料和日记的语义检索，返回文本片段与来源文件。用户在设置中配置独立模型密钥并启用功能。本地拥有索引构建权，云端接收完整索引后提供检索。

## Scope

覆盖递归 Markdown 索引、vec/own_bm25、可选 rerank、版本发布和每日本地到云端同步。业务数据库和源文件的双向同步仍由现有同步模块负责。

## Functional Checklist

- [x] RAG、rerank 默认关闭，默认索引目录为 `user`、`diary`。
- [x] 模型和 base_url 固定，独立密钥只写安全存储，读取接口仅返回配置状态。
- [x] 构建 vec 和 own_bm25；工具默认只检索 vec，显式关键词可启用 BM25。
- [x] 完整重建移除已删除来源；构建和校验失败保留旧索引。
- [x] 每日记忆更新后构建，再独立上传；上传失败复用当日索引重试。
- [x] 启动补执行、数据目录迁移、启动后开启记忆更新的补执行。
- [x] 云端认证、限量上传、只读检验、版本幂等与原子发布。
- [x] 查询固定版本，活跃版本不被清理；rerank 失败回退粗排。

## Technical Contract

### 配置

| 字段 | 类型 | 默认与约束 |
|------|------|------------|
| rag.enabled | bool | false；开启前需 embedding key |
| rag.rerank_enabled | bool | false；开启前需 rerank key |
| rag.index_directories | string[] | user、diary；至少一个、安全相对目录、不重复且不互相包含 |
| rag_embedding_api_key | string | 独立安全存储；空值表示删除并关闭 RAG |
| rag_rerank_api_key | string | 独立安全存储；空值表示删除并关闭 rerank |

目录相对于 `lifeprism_data_path`，只收集递归 `*.md`。绝对路径、上级路径及通过符号链接逃出数据根的来源被拒绝。`rag`、`config`、`logs`、`database`、`screenshots` 不可作为索引根。

| 用途 | 固定模型 | 固定 base_url |
|------|----------|----------------|
| embedding | doubao-embedding-vision（2048 维） | https://ark.cn-beijing.volces.com/api/plan/v3 |
| rerank | qwen3.7-text-rerank | https://llm-v1wy4r670fcws401.cn-beijing.maas.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank |

### 设置 API

| 方法与路径 | 请求 | 响应 | 路由处理函数 |
|------------|------|------|--------------|
| GET /api/v2/settings/rag | 无 | RagSettings | get_rag_settings |
| PATCH /api/v2/settings/rag | 可选 enabled、rerank_enabled、index_directories | RagSettings | update_rag_settings |
| PUT /api/v2/settings/rag/keys/{purpose} | `{api_key: string}`，最大 4096 字符；purpose 为 embedding 或 rerank | RagSettings | update_rag_key |

PATCH 省略字段表示保留，显式 null 或额外字段返回 422；模型、base_url 不可通过 API 修改。RagSettings 包含 `enabled: bool`、`rerank_enabled: bool`、`index_directories: string[]`、`embedding` 和 `rerank`。两个模型对象均包含 `model: string`、`base_url: string`、`configured: bool`，不包含密钥。开启缺少凭据的功能返回 422。

### 检索工具

`rag_search(query: string, k: int = 5, use_bm25: bool = false)`；query 非空，k 为 1–20。默认 vec；只有明确的人名、项目名或术语等关键词才选择 BM25 通道，与 vec 结果融合。开启重排后先召回至少 20 条候选，再截取 k 条；重排故障返回粗排结果。

成功返回原文片段及数据根相对来源路径；标注行号为清洗后文本行号，不能当作原文件行号。空结果返回提示；失败返回不包含服务商凭据的工具错误。仅在 RAG 开启时加入 CHAT 工具集，每轮刷新工具配置。

### 索引与数据库

独立存放于数据根 `rag/versions/{version}/index.db`，不注册到业务数据库的 LWW 表同步。`current.json` 指向当前版本，`daily.json` 保存每日状态。保留最新三版及正在查询的旧版。

数据库结构由 simple_rag 管理；LifePrism 不自行拆分虚拟表和影子表：

| 表 | 字段与约束 |
|----|------------|
| chunk_data | chunk_id、path、created_at、updated_at、content 为非空 text；start_line、end_line 为非空 integer；chunk_id、path 各有索引；相同 chunk 可有多个来源行 |
| chunks | vec0 虚拟表；chunk_id 与 2048 维 cosine 向量，伴随扩展管理的影子表 |
| own_bm25_docs | doc_id integer 主键；chunk_id text 非空唯一；dl integer 非空且 >=0 |
| own_bm25_postings | term text、doc_id integer、tf integer 非空且 >0；主键 (term, doc_id)，WITHOUT ROWID；反向索引 (doc_id, term) |
| own_bm25_stats | singleton integer 主键且为1；n、total_dl integer 非空且 >=0 |

BM25 的 seen/query 临时表属于连接，不参与传输。上传使用 SQLite Online Backup 得到的完整独立文件，包含 WAL 已提交页面、vec0 和持久影子表。验证涵盖摘要、长度、扩展版本、完整性、各通道 chunk ID 一致性以及实际 KNN/BM25 查询。

### 单向同步 API

仅 `agent_only` 接收，使用现有 `Authorization: Bearer {sync_api_key}`。独立云端入口 `lifeprism.server.main_agent_only._run_agent_and_api` 注册业务数据同步与 RAG 索引同步路由，默认监听 `127.0.0.1:8102`。正常入口 `lifeprism.server.main` 固定为 full，绑定应用 SyncClient 到每日 RAG 调度，负责发送；云端不注册构建/发送任务。

经过 Nginx 的同步代理须显式配置 `client_max_body_size 512m`；模板同时关闭请求缓冲并设置 300 秒代理超时，详见 [云端 HTTPS 部署](../deployment/cloud-https-setup.md)。现有线上代理需部署者同步更新并重载。

POST `/api/sync/rag-index` 请求体是原始 SQLite 二进制，`X-RAG-Manifest` 是 Base64 编码的 JSON（最多 8192 字符），大小最多 512 MiB。成功响应 `{version: string, sha256: string}`。摘要、结构或版本校验失败返回 422，超限返回 413，非云端模式返回 403；旧索引保持可用。相同版本与相同 manifest 重发幂等，拒绝不同内容重用版本或回退到更早版本。

GET `/api/sync/rag-index` 返回 `{manifest: IndexManifest | null}`，供诊断使用。

IndexManifest 全部字段：

| 字段 | 类型与约束 |
|------|------------|
| version | 32 位小写十六进制字符串 |
| schema_version | integer，固定 1 |
| embedding_model | string，固定 doubao-embedding-vision |
| dimensions | integer，固定 2048 |
| sqlite_vec_version | string，必须与接收端一致 |
| created_at | 带时区的 datetime，UTC ISO 8601 |
| sha256 | 64 位小写十六进制字符串 |
| size | integer，1–512 MiB |
| chunk_count | integer，>=0 |
| source_fingerprint | 64 位小写十六进制字符串 |
| directories | string[]，与配置目录相同安全约束 |
| max_token | integer，固定 384 |
| min_tokens | integer，固定 50 |

### 每日状态

每天本地 10:00 的记忆/日记任务结束后完整构建索引，再单独上传一次。没有启用记忆任务时由独立 RAG 任务构建。关机错过时间在启动后补执行；15 分钟轮询重试。仅 full 模式且 RAG 开启时执行。

`daily.json` 的 `built_date`、`synced_date` 为用户本地日期 YYYY-MM-DD，另存 `version`、`sha256`。构建成功先提交 built_date；只有云端确认同一 version 和 sha256 才提交 synced_date。当日上传失败不重新嵌入；构建失败允许重新构建。当日成功后不再上传。使用全局 LOCAL_TASK 互斥，避免与既有云端业务同步重叠。

<key_function>
- lifeprism/rag/service.py
  - service.RagService.build:231
  - service.RagService.search:290
  - service.RagService.install:157
- lifeprism/sync/rag_sync.py
  - rag_sync.DailyRagJob.run:74
  - rag_sync.RagSyncSender.upload:30
- lifeprism/server/api/rag_settings_api.py
  - rag_settings_api.get_rag_settings:15
  - rag_settings_api.update_rag_settings:21
  - rag_settings_api.update_rag_key:34
- lifeprism/server/api/rag_sync_api.py
  - rag_sync_api.receive_index:22
  - rag_sync_api.get_index_manifest:52
- lifeprism/server/main_agent_only.py
  - main_agent_only._run_agent_and_api:286
</key_function>

## Design Rationale

完整快照传输避免业务行同步遗漏 vec0 影子表；候选库校验后发布保证构建失败不损坏在线索引。固定模型和扩展版本使本地与云端使用一致的向量契约。构建状态与上传状态分离使网络重试不重复消耗 embedding。

每日完整重嵌入会产生按语料规模计算的 API 成本。当天成功上传后云端被清空，需要到下一日重新发布；本版本不自动探测已成功上传版本的丢失。配置和密钥通过 cloud_init 导出/初始化传递，运行中修改不会随索引包传递；需要重新部署配置。源文件在每日任务之间的改动要等下一轮索引才可检索。

## Interaction / UX Notes

设置页提供独立 RAG 区域、两个开关、目录编辑、只读模型/地址及两组密钥保存/清除。先保存 embedding key 再启用 RAG；需要重排时另存 rerank key。云端需同步部署本版本后端和最新 cloud_init 配置，并配置现有同步地址/认证。

## Out of Scope

- [配置管理](2026-04-20-config-spec.md)：安全存储、路径迁移与配置读写。
- [同步总览](2026-07-16-data-sync-overview.md)：业务数据库和源文件同步。
- [SSH 隧道](2026-07-26-data-sync-ssh-tunnel-spec.md)：统一远端地址入口和连接生命周期。
- [Agent Runtime](2026-10-03-myagent-runtime-spec.md)：工具运行与聊天事件生命周期。
