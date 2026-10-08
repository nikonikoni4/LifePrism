# Simple RAG 调研证据

用户要求：RAG 开关；索引目录默认 user、diary；构建 vec 与 own_bm25，工具默认只查 vec；rerank 开关；豆包 embedding 与阿里云 rerank 的 API key 可配置，model/base_url 固定；每天一次本地到云端同步，优先考虑独立模块。

用户进一步明确：每天更新完索引后，RAG index 单独同步云端一次；不再将本地刷新频率作为单独选项询问。后续已批准 RAG 和 rerank 初始关闭。

2026-10-08 补充确认：工具暴露可选 BM25 参数，默认关闭；描述中明确只有查询包含明确关键词时才选择。方案采用 use_bm25=false，true 时增加 own_bm25 检索通道；该参数不改变索引构建或 rerank 设置。

工作区已有未跟踪文件 scripts/migrate_session_v1.py、test/debug/test_mimo_stream_diagnostic.py，本任务不处理。

已读证据：
- RAG/explore/index.md、实际测试/index.md、vec_bm25_rrf_rerank在不同数据集下的表现/{README.md,index.py,retrieval.py,rag_tool.py}。
- RAG/simple_rag/{config/config.py,db/database.py,indexing/indexing.py,retrieval/retrieval.py,chunking/structured_file/md_chunk_by_title.py}。
- LifePrism docs/coding-rules/index.md、docs/docs-rules/{index.md,docs-write-rules.md}、docs/specs/index.md；配置与 myagent 规格、同步规格相关章节；sync-remote-url-access-rules.md。
- lifeprism/{config/settings_manager.py,config/cloud_config_generator.py,llm/runtime/service.py,llm/runtime_tools/__init__.py,sync/sync_client.py,sync/sync_config.py,server/services/schedule_service.py,server/services/setting_service.py,server/schemas/setting_schemas.py}，frontend/apps/settings/SettingsApp.tsx，pyproject.toml。

事实：参考工具使用原生 myagent；simple_rag 未接入本项目依赖；检索可配置 vec 单通道；索引可同时构建 vec 与 own_bm25；simple_rag 数据库自动加载 sqlite-vec，使用 WAL；pipeline 不清旧索引，delete_by_path 会删整个跨文件 chunk；chunking 当前只扫描 md，路径直接进入来源和 ID；行号基于清洗后文本；当前固定示例 embedding=doubao-embedding-vision（2048 维）、rerank=qwen3.7-text-rerank。仅读取 .env 的模型和 URL 字段，未读取或输出 Key。

同步事实：现有 sync_once 是双向业务表和文本文件同步，RAG 不应加入这两条流程；每日 cron 有状态和补执行框架，但任务吞异常/跳过后可能被外层标记执行完成，RAG 需要独立的成功状态语义；云端查询仍需要 embedding Key，可选 rerank Key，索引文件不能代替凭据部署。

未验证：vec0 的 Online Backup 快照、跨 OS 重开与 KNN/BM25 一致性；云端索引热切换；实际打包运行。理论上整库快照保留影子表，不能表述成实测通过。

## 实施结果（2026-10-08）

设置、独立密钥、固定模型、原生工具、完整索引与每日单向快照上传已实现。合并回归 104 passed；前端 3 passed 与生产构建通过。Windows 和 Linux 同一快照 14 表摘要、检索结果和来源一致。存储模块采用 rag_storage.py 避免子模块导入覆盖 rag_repository 单例。正式契约见 docs/specs/2026-10-08-simple-rag-spec.md。生产模型/云端未实际调用；每日完整重嵌入有成本，云端重装后当日已成功状态不会主动检测丢失。

最小 PyInstaller 冻结 exe：FROZEN_RAG_OK，实际加载 vec DLL、jieba 词典，vec 与 own_bm25 查询通过。完整桌面/后端安装包未构建。广域既有回归：配置存储连续写入 Windows PermissionError，定时任务移除在秒边界额外执行；独立 SSH 配置测试通过。

自动审批拒绝递归删除本次 .scratch/rag-linux 与 rag-frozen 临时探针产物（仅返回 blocked by policy，无更具体原因）；未删除，改为加入本地 .git/info/exclude，不影响代码提交范围。

定时任务移除测试已修正为允许既已提交的回调结束，再验证后续周期停止；独立复测 1 passed。未修改 APScheduler 或生产 remove_job 行为。
