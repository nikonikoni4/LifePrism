# CONTEXT

> 术语表（glossary）。只放领域概念定义，不放实现细节。

## 术语

### custom prompt（自定义规则文件）

用户为 AI 撰写的自定义规则，存放于 `agent/chat/custom_prompt.md`。文件本身内容纯净（不含任何包裹标签）。区别于系统提示词（soul/agent/tool/bootstrap 等，system role 注入）：custom prompt 以 **user role** 注入，位于 system 之后、对话历史之前的稳定前缀区。每台设备首次启动时以空文件自动创建；空文件不注入。跨设备同步。

### prefix messages（前缀消息）

每次 LLM 调用时由系统组装、不写入会话历史的消息前缀：`[system prompt] + [custom prompt 注入（可选）]`。位于稳定前缀区，对 prompt caching 友好；不进入 auto_compact 压缩范围。

### 渐进式规则加载（progressive rule loading）

仅 `custom_prompt.md` 一个文件被自动注入；agent 在 `agent/chat/` 下创建的其他规则文件不自动加载，由 custom_prompt.md 内维护的链接索引 + agent 按需 `read_file` 实现。
