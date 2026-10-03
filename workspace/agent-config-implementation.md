# Agent 配置

- 类型：lifeprism/config/agent_config.py 的 AgentSettings，通过 settings.agent 读取。
- 写入：settings.set('agent', config.model_dump())；或 settings.update({'agent': {...}})。参数先校验，随后由 SettingsManager 保存 config.yaml。读取部分配置时补默认值；未知字段和无效类型报错。
- context 初始化时读取快照；已存在的 context 不热更新，后续新 context 使用最新配置。
- step_limit 默认 20，max_retry_count 默认 3；后者是 myagent 每轮共享重试预算。
- llm_retry 默认开启，base_delay=1、multiplier=2、cap=30；只通过 request/error 返回裁决，loop 负责执行。Retry-After 可超过本地 cap。
- tool_guard 固定开启，不提供 enabled 配置；直接注册 myagent ToolUseGuard 到 TOOL_CALL。默认 allow_paths 是 user/diary/agent；空列表拒绝护栏所管理的路径调用。
- 相对 allow_paths 用 lifeprism_data_path 为基准，注册前 resolve；使用正斜杠，不允许 .. 或符号链接逃出数据根。当前平台绝对路径可用，外平台绝对路径拒绝。
- 护栏只覆盖 myagent 中列出的路径工具；既有文件工具仍有自己的 allowed_dir_path 限制，两个检查都要通过。不能将护栏当成全部工具的统一沙箱。
- 示例见 workspace/agent-config-example.yaml。

旧 enabled 字段读取时忽略，重新保存会移除；即使旧配置为 false 也不能关闭护栏。
