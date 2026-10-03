# Provider 最小错误契约（2026-10-03）

已实现，属于 P3 的分类基础；没有实现恢复策略或宣告 P3 完成。

## 阅读顺序

1. `lifeprism/llm/providers/errors.py`：ProviderErrorKind、LLMProviderError、SDK 分类入口。
2. `lifeprism/llm/providers/llm_providers/base.py`：严格工具参数解析、一次请求、流式错误和关闭契约。
3. `custom_provider.py` / `litellm_provider.py`：Claude CLI 完成 SDK 接线；Codex 修正嵌套流关闭和模型元数据。
4. `lifeprism/llm/runtime/provider.py`：转换流式协议错误，保留异常对象和部分输出事实。
5. `test/core/unit/llm/test_provider_errors.py`：可执行行为示例。

## 分类树

LLMError → LLMProviderError，kind 为 connection / timeout / rate_limit / unavailable / request / quota_exceeded / invalid_response / unknown。
request 的 reason 区分 authentication / permission / not_found / invalid / context_limit / content_policy / unsupported。

错误保留 provider、model、status_code、provider_error_code、phase、partial_output、retry_after 和原始 cause。分类先考虑明确预算错误，再考虑具体 SDK 异常类型，最后回退到 HTTP 状态。普通编程错误和取消不包装。不根据宽泛错误文本猜测类别。

## 行为变化

- chat 和 stream_chat 通过异常上报失败，不把失败当成助手回答。
- OpenAI 客户端 max_retries=0；LiteLLM 请求 num_retries/max_retries=0。
- chat_with_retry 保留名称和生成参数默认值，但只调用一次，不重试或自动删图。
- 工具 JSON 仅正常 object 转成 dict；无效或非 object JSON 原样保留为 str，交给工具层处理；序列化不二次编码。
- 原始工具流仍交给 myagent；length 仍是正常截断响应。
- SDK request/error 异常对象路径沿用 myagent，未修改其 IoC/HITL。

## 验证及边界

相关错误、adapter 和 runtime 回归共 50 项通过，限定文件 Ruff 检查通过。未发真实供应商请求，未重新生成安装/冻结包。
旧 `test/core/unit/test_provider.py` 引用已不存在的 `lifeprism.llm.providers.base`，独立收集失败，保留历史测试未修改。
新的异常契约可能影响依赖 finish_reason=error 文本的旧调用方；后续恢复策略需显式消费异常。
未实现重试、熔断、切换模型、人在回路或业务 Session 适配。SDK 未提供具体财务错误代码的 429 默认 rate_limit；不根据模糊配额描述猜测余额耗尽。
