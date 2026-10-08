# LifePrism Simple RAG 接入：首轮调研与建议

2026-10-08。仅代码调研和方案，未修改功能代码、未安装依赖、未进行联网模型调用或云端上传。

## 需求对应

| 项目 | 建议行为 |
| --- | --- |
| RAG 开关 | 设置模块新增开关；建议默认关闭，待用户确认 |
| 索引目录 | 数据根目录下的相对目录，默认 user、diary；递归扫描 Markdown，与参考实现保持一致 |
| 构建通道 | 固定 vec + own_bm25，不混同检索通道 |
| 工具检索 | 参数 query、k、可选 use_bm25（默认 false）；默认只查 vec，true 时增加 own_bm25 通道，与 vec 结果按现有 RRF 机制融合 |
| rerank | 独立开关；建议默认关闭，开启后 vec 候选经阿里云重排 |
| 模型设置 | API Key 可保存/替换；model 和 base_url 只读，由后端固定，不能仅靠前端禁用 |
| 模型事实 | 参考 embedding 是 doubao-embedding-vision，2048 维；rerank 是 qwen3.7-text-rerank |
| 密钥 | 建议独立 RAG embedding/rerank 凭据槽，复用 SettingsManager 本地 keyring / 云端 storage.yaml 路由；响应只给配置状态或脱敏值 |
| 同步方向 | 用户已确认：每天更新完本地索引后，单独向云端同步这份索引一次；不反向同步索引 |

参考豆包地址是 https://ark.cn-beijing.volces.com/api/plan/v3；阿里云使用工作空间专属的完整原生 rerank URL，不能假设任意账号均能使用同一地址。正式固定地址需以目标部署账号为准。simple_rag 的配置构造器应显式传入全部值，不依赖参考项目的 .env 自动装配。

用户已确认 BM25 作为工具可选参数。use_bm25 的参数说明及工具描述须明确：只有查询包含明确关键词（例如人名、项目名、具体术语或需精确匹配的词语）时才选择 true；概括性、语义性问题保持 false。该参数只控制本次检索，不改变索引构建通道，也不控制 rerank 开关。

## 已有实现与入口

- 参考：`D:/desktop/软件开发/RAG/explore/实际测试/vec_bm25_rrf_rerank在不同数据集下的表现/` 的 index.py、retrieval.py、rag_tool.py。实验索引中明确注明 explore 为验证代码，应使用正式 simple_rag 包并在 LifePrism 中写业务装配。
- `lifeprism/llm/runtime_tools/__init__.py::build_tools` 是生产工具入口；`lifeprism/llm/runtime/service.py` 每轮准备工具，适合配置变更后在下一轮刷新。
- 设置链路为 SettingsManager → setting_service → setting_schemas/setting_api → frontend/apps/settings。新增 RAG 分区应独立组件，避免继续扩大 SettingsApp。
- `pyproject.toml` 尚未包含 simple-rag；开发期可仿照 myagent 使用本地路径来源，正式发布需要可安装包来源。
- `lifeprism.spec` 需要收集 sqlite-vec 动态库；参考 pyinstaller 探索只验证收集方式，没有打包运行通过的证据。

## 索引更新需要业务编排

simple_rag 的 pipeline 支持切分、合并、嵌入、存储，但不判断文件变更、不删除旧 chunk。重复跑可能主键冲突或留下旧内容。delete_by_path 会删掉所有涉及该文件的 chunk，包括合并进来的其他文件的来源。

因此首次建议先做完整目录切分和生成候选索引版本，避免直接增量删写跨文件 chunk。有内容变化时全量嵌入成本较高，后续可按嵌入输入指纹复用向量；指纹必须包含模型、维度、渲染后的实际文本与相关策略，不能只凭 chunk_id 判断。用户已确认每日更新后再单独同步，首次版本是否采用全量重建仍应结合真实语料成本确定。

构建失败保留旧版本；构建时应读取稳定语料副本或检查文件变化，避免一天的索引混入不同时间的正文。并发聊天期间不能通过全局 chdir 来满足相对路径要求，应以数据根为基准建立稳定来源标识。路径需拒绝越界、重复目录和符号链接逃逸。

来源行号是清洗后文本的位置，不是原始文件的位置。首期可返回来源文件、标题和正文，或明确标注该行号口径；如果要点击跳到原文，必须建立原始行号映射。云端每天更新导致来源原文可能已变，应显示索引生成时间。

## vec0 与影子表同步结论

现有业务表同步使用 updated_at 增量、JSON 行传输、LWW 写入和墓碑协议；文本同步传输正文并进行冲突合并。这些不适合直接处理 vec0 内部影子表。

建议独立 `rag/index.db`，通过 SQLite Online Backup API 生成一致、独立的数据库快照，上传完整快照。SQLite 的整库页面备份按机制应保留虚拟表定义、影子表及 BLOB；它无需逐表解析或单独操作影子表。但是本轮未实测 sqlite-vec 跨机器兼容性，所以这是待验证的首选方案。

不要直接复制仍在写入的 WAL 主文件，不要逐张影子表覆盖，不要将索引塞入现有 Markdown/JSONL 文件同步。

备选方案是导出 chunk、向量和来源等逻辑记录，在云端通过公开接口重建 vec/BM25，避免手写影子表。不过其协议、批处理和原子发布更复杂，优先用于快照跨版本兼容失败或全量传输成本不可接受时。

## 独立每日发布模块

建议 `lifeprism/rag/` 负责索引版本、查询和生命周期；`lifeprism/sync/rag_sync.py` 负责每日上传协议；ScheduleService 只调度。独立业务状态和模块可以复用现有同步认证、SSH 隧道与 HTTP 客户端，不必另造连接体系。所有远程请求遵守 SyncClient._read_remote_url 的统一入口规则。

流程：同步源文档完成（必要时先完成记忆更新）→ 本地候选索引构建/校验 → Online Backup 快照 → 附 manifest 上传 → 云端暂存 → SHA-256/大小/格式与模型版本校验 → sqlite-vec 重开、KNN/BM25 冒烟 → 发布新版本 → 返回确认 → 本地记录成功日期与版本。

manifest 包含版本标识、schema/SQLite/sqlite-vec 版本信息、embedding 模型/维度、切分配置、源文件指纹和生成时间；API Key 不进入索引或 manifest。云端必须另外具备 embedding Key，查询向量不会因为上传了索引而免除模型调用。cloud_init 配置生成与初始化需接入 RAG 设置和凭据。

云端使用版本目录和原子当前版本指针，避免替换仍打开的 WAL 数据库；请求在开始时固定版本，旧版本直到活跃请求释放后清理。Windows 文件占用与 Linux 文件替换语义不同，需一并验证。

“每天一次”建议定义为用户时区内每天成功发布最多一次，同日失败可重试；成功状态只在云端确认后写入。重启补执行、重复上传同版本幂等、无变更是否免传以及云端重装后补发，均应具有明确语义。不能把现有 cron 的执行完成记录直接等同上传成功。

每日索引只代表该生成时刻的知识；云端之后新增/修改的日记在本地拉取并重新建库前不会出现在 RAG 中。原文同步继续保持原协议，单向限制仅适用于索引。

## 分阶段实施建议（待批准）

1. 验证同步可行性：临时最小数据库包含 vec、chunk_store、own_bm25；保持 WAL 有未 checkpoint 数据；backup 后以相同扩展重开，检查所有表和固定查询结果；Windows 生成到 Linux 重开。无真实 API 和生产上传依赖。
2. 设置契约与独立密钥：默认值、只读模型/URL、API Key 读写、前端 RAG 分区、云端初始化；验证密钥不泄露与固定字段不可被请求覆盖。
3. 本地索引与 rag_search：稳定来源路径、完整候选构建、失败保留旧版本、vec 默认通道、use_bm25 可选参数及明确关键词使用说明、可选 rerank、按每轮刷新工具配置；验证跨文件合并和删除不留下错误索引。
4. 每日单向发布：复用认证/隧道，上传暂存、manifest 校验、幂等发布、成功状态、失败重试/补执行、旧请求版本保留。
5. 集成与打包：并发查询/发布、损坏包拒绝、云端缺失/重装、配置禁用、API 故障和 Windows/Linux/sqlite-vec 版本一致性；验证动态库实际随包加载。

## 已批准并实现

RAG 和 rerank 默认关闭；独立密钥；固定参考模型与地址；完整重建接在每日记忆更新之后，再独立上传。失败重试、启动补执行、rerank 回退均获批准。BM25 作为 use_bm25=false 的可选工具参数，仅明确关键词时开启。

实际验证：Windows 与 Linux sqlite-vec 0.1.6 重开同一 WAL 在线备份快照，14 个持久表摘要、来源、vec/BM25 检索一致；104 项后端测试和 3 项前端测试通过，Vite 生产构建通过。实现契约以 docs/specs/2026-10-08-simple-rag-spec.md 为准。

限制：每日完整嵌入有 API 成本；云端重装后的当日索引缺失不自动检测；运行中设置/key 修改需要重新部署 cloud_init，不包含在索引二进制包中。未使用真实凭据调用模型或部署生产云端。
