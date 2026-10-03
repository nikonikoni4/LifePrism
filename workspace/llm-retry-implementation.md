# LLM Retry IoC 接入（2026-10-03）

参考 agent/src/lifeprismevalue/llm/llm_retry.py。

- lifeprism/llm/providers/llm_retry.py 的 LLMRetry.request_error_event 只返回 backoff_retry / policy；不 sleep、不调用 provider、不维护次数。
- Runtime 创建 AgentContext 后注册 AgentPolicySpec(REQUEST_ERROR, [handler], owner)。
- AgentConfig.max_retry_count=3，预算为每个 turn，跨模型步骤共享，由 myagent loop 管理。
- connection / timeout / rate_limit / unavailable 且无 partial_output 时认领；配额耗尽、请求错误、响应错误、未知错误、取消和编程错误委托 _next。
- loop 负责 1/2/4 秒指数退避（cap=30 秒），Retry-After 作为等待下限，服务端建议可能超过 cap；不添加自定义抖动。
- provider chat/stream_chat/chat_with_retry 和 SDK 都保持单次请求。后台及聊天 AgentRuntime 均走注册策略；直接调用 provider 的业务函数不会自动重试。
- 部分输出中断不认领，避免重放重复答案；HITL、工具错误策略未实现。
- 撤回最初错误的 provider 边界重试实现。
