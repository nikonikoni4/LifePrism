## 2026-07-06-repository-initialization-flow
 - updated_at : 2026-07-06
 - path: docs/flows/2026-07-06-repository-initialization-flow.md
 - 触发规则：需要理解 Repository 层初始化流程、3 个 DB 实例创建、表结构初始化、数据库迁移、默认数据填充、资源文件初始化时读取
 - 内容摘要：RepoInitState 数据流，覆盖模块导入时 DB 实例创建与连接池初始化（__init__.py）、LWTableManager 配置驱动建表（timestamps/update_at 分支）、migration_runner 版本检测-备份-执行流程、data_initializer 空表检测与默认数据填充（固定 ID + 冲突处理）、resource_initializer 打包/开发环境分支资源复制（OVERWRITE_DIR_LIST 强制覆盖）共 5 条链路

## 2026-07-06-repository-data-access-flow
 - updated_at : 2026-07-06
 - path: docs/flows/2026-07-06-repository-data-access-flow.md
 - 触发规则：需要理解 Repository 数据访问路径、GoalAggregator 多表聚合查询、DiaryProvider 单表 CRUD、连接池生命周期、QueryOptions 不可变查询时读取
 - 内容摘要：DataAccessTrace 数据流，覆盖读路径（GoalAggregator 多表聚合 6 节点）和写路径（DiaryProvider 单表插入 5 节点）两条典型链路、连接池获取-归还生命周期、元数据驱动 CRUD（_TABLE_NAME/_PRIMARY_KEY 白名单防注入）、N+1 查询模式、replace 默认风险等 6 项反常设计

## 2026-07-06-config-initialization-flow
 - updated_at : 2026-07-06
 - path: docs/flows/2026-07-06-config-initialization-flow.md
 - 触发规则：需要理解配置系统初始化、SettingsManager 和 ProviderManager 单例初始化链路、config.yaml 加载与迁移时读取
 - 内容摘要：ConfigInitState 数据流，串联 SettingsManager 和 ProviderManager 两个单例的完整初始化链路，覆盖 config_base_path 解析、config.yaml 加载与迁移、lifeprism_data_path 三级优先级解析、日志配置、安全检查、白名单目录解析，以及 ProviderManager 对 providers.yaml 的并行初始化

## 2026-07-06-llm-provider-call-flow
 - updated_at : 2026-07-06
 - path: docs/flows/2026-07-06-llm-provider-call-flow.md
 - 触发规则：需要理解 LLM Provider 调用全链路、create_llm_client() 工厂创建、LiteLLMProvider 多服务商适配、CustomProvider OpenAI SDK 直连、chat_with_retry() 重试降级、Token 用量持久化时读取
 - 内容摘要：LLMCallTrace 数据流，覆盖 create_llm_client() Provider 创建（settings -> find_by_name -> is_direct 路由）、LiteLLMProvider.chat() 完整路径（消息清理 -> 模型名解析 -> Prompt Caching -> 参数覆盖 -> 消息规范化 -> acompletion -> XML 解析）、CustomProvider.chat() 直连路径（AsyncOpenAI -> 响应解析）、chat_with_retry() 重试降级（瞬态错误重试 + 图片降级）、LLMUsageDataProvider Token 用量持久化共 5 条链路

## 2026-07-06-llm-agent-loop-flow
 - updated_at : 2026-07-06
 - path: docs/flows/2026-07-06-llm-agent-loop-flow.md
 - 触发规则：需要理解 Agent 主循环完整流程、消息分发、命令处理、Context 组装、工具注册与调用循环、自动压缩时读取
 - 内容摘要：AgentExecutionTrace 数据流，覆盖消息消费与分发（loop() -> consume_inbound() -> asyncio.Task）、命令处理分支（/new /continue /session-list 仅 WeChat 渠道）、通用消息处理主线（Context 构建 -> 工具注册 -> auto_compact -> _run_agent_loop -> publish_outbound）、LLM 工具调用循环（while 循环 最多 20 轮 + 单工具错误上限 5 次 + 超限强制文本回复）、Context 构建（CHAT 五层 / CLASSIFY / GENERAL_TASK / DREAM_TASK 四路分支）、自动压缩（token 阈值检测 -> 独立 LLM 压缩 -> last_compacted_loc 标记）共 6 条链路

## 2026-07-06-llm-tool-execution-flow
 - updated_at : 2026-07-06
 - path: docs/flows/2026-07-06-llm-tool-execution-flow.md
 - 触发规则：需要理解 LLM 工具调用全链路、ToolRegistry 注册与执行机制、参数类型转换（cast_params）与 JSON Schema 校验（validate_params）、文件系统安全沙箱（白名单路径比对 + Shell 版命令黑名单）、工具结果序列化与错误反馈时读取
 - 内容摘要：ToolExecutionTrace 数据流，覆盖工具注册（MessageType -> ToolRegistry.register -> get_definitions -> llm.chat tools=...）、通用执行路径（lookup -> cast_params 类型转换 -> validate_params 7 维校验 -> execute -> 异常 ERROR 返回）、文件系统安全沙箱（Path.resolve + relative_to 白名单比对 + Shell 版 25+ 命令黑名单正则匹配）、结果序列化与反馈（dict/list json.dumps -> session.add_message -> 错误计数 >5 警告注入 -> build_prompt 重建 messages -> 再次 llm.chat）共 4 条链路，以 ReadFileTool 和 UserActivitySummaryTool 为典型穿透路径


## 2026-07-06-config-path-resolution-flow
 - updated_at : 2026-07-06
 - path: docs/flows/2026-07-06-config-path-resolution-flow.md
 - 触发规则：需要理解 config_base_path 和 lifeprism_data_path 的解析逻辑、6 种环境组合、三级优先级决策、数据迁移及安全检查时读取
 - 内容摘要：ResolvedPaths 数据流，覆盖 config_base_path 固定路径解析（打包/开发分支）、lifeprism_data_path 三级优先级（yaml > env var > default）、update() 触发数据迁移、派生路径自动推算、打包环境安全检查共 5 条链路

## 2026-07-06-llm-wechat-message-flow
 - updated_at : 2026-07-06
 - path: docs/flows/2026-07-06-llm-wechat-message-flow.md
 - 触发规则：需要理解微信 Channel 启动认证、消息长轮询处理、媒体下载解密、Channel 停止保存等完整消息通路时读取
 - 内容摘要：WechatMessageTrace 数据流，覆盖 Channel 启动与认证（keyring+文件双层 token、旧格式兼容迁移、QR 登录分支）、消息轮询与解析（getupdates 游标长轮询、parse_message 消息提取、is_allowed 权限检查、media 媒体下载、bus.send 总线交互、LLM 日志记录、session_id 更新、统一持久化、sendmessage 回复发送）、媒体 AES-ECB 解密下载、Channel 停止兜底保存共 4 条链路

## 2026-07-06-llm-session-lifecycle-flow
 - updated_at : 2026-07-06
 - path: docs/flows/2026-07-06-llm-session-lifecycle-flow.md
 - 触发规则：需要理解 Session 生命周期管理、JSONL 持久化格式、内存缓存机制、自动压缩（auto_compact）、ChatHistoryManager 聊天历史提取时读取
 - 内容摘要：SessionLifecycleTrace 数据流，覆盖 Session 创建（UUID 生成 + JSONL 初始化）、加载（缓存命中/文件读取两条子路径）、消息追加与自动压缩（token 超标检测 + LLM 压缩）、持久化（JSONL 格式契约 + 图片 base64 剥离）、删除与缓存管理共 5 条链路，含内存缓存 + JSONL 文件双层架构说明

## 2026-07-11-custom-type-lifecycle-flow
 - updated_at : 2026-07-11
 - path: docs/flows/2026-07-11-custom-type-lifecycle-flow.md
 - 触发规则：需要理解自定义记录类型从创建到删除的完整数据流、meta表+DDL事务、动态SET子句更新、字段角色更新时读取
 - 内容摘要：CustomRecordType+CustomRecordField 数据流，覆盖创建类型（5层校验→事务INSERT types+INSERT fields+CREATE TABLE）、查询类型列表（SELECT types + N次SELECT fields组装）、查询单个类型详情、更新展示配置（动态SET子句+debounce自动保存）、更新字段展示角色（乐观更新+失败回滚+双条件WHERE防误更新）、删除类型（事务DROP TABLE+DELETE fields+DELETE types 逆序操作）共 6 条链路，含 LLM Tool 绕过 Service 层和 Repository 不继承 LWBaseDataProvider 等反常设计说明

## 2026-07-11-custom-entry-crud-flow
 - updated_at : 2026-07-11
 - path: docs/flows/2026-07-11-custom-entry-crud-flow.md
 - 触发规则：需要理解自定义记录条目的录入/查询/删除数据流、REST/AI双通道架构、动态SQL拼接、分页双查询、AI智能重试机制时读取
 - 内容摘要：CustomRecordEntry 数据流，覆盖录入记录REST路径（动态列INSERT+field_key白名单校验）、录入记录AI Tool路径（绕过Service+SUCCESS/ERROR字符串返回+valid_fields引导重试）、分页查询（COUNT+SELECT双查询+日期范围动态WHERE）、AI查询（固定page=1+limit默认50不分页）、删除记录（with块外抛EntityNotFound防连接池异常）共 5 条链路，含双通道架构和动态SQL拼接安全说明

## 2026-07-11-custom-card-rendering-flow
 - updated_at : 2026-07-11
 - path: docs/flows/2026-07-11-custom-card-rendering-flow.md
 - 触发规则：需要理解前端卡片渲染管线、L1/L2/L3三层布局引擎、多正文叠加、空字段过滤、三布局分支渲染、确定性字段着色时读取
 - 内容摘要：CardLayoutResult 数据流（纯前端），覆盖布局分析核心管线（空值过滤→resolveRole三级优先级→标题竞争分配→布局模式决策）、L2 overrides构建（从fields.display_role提取）、L3模板预设解析（getTemplatePreset返回CSS类名）、EntryCard三布局分支渲染（note多正文叠加/compact键值对/tight纯标签云）、字段颜色确定性分配、日期分组共 6 条链路，含数据驱动布局和模板-布局正交设计说明
