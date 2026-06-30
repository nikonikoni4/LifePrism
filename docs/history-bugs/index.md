## 2026-06-30-read-file-max-chars-causes-excessive-tool-calls

- updated_at: 2026-06-30
- path: `docs/history-bugs/2026-06-30-read-file-max-chars-causes-excessive-tool-calls.md`
- 触发规则：在排查 DREAM_TASK 工具调用次数异常多（接近 MAX_TOOL_CALL=20）、LLM 反复读取同一文件、read_ratio 永远 < 1.0、read_file 返回内容被截断时阅读
- 内容摘要：记录了 `read_file` 工具 `max_chars` 默认值 1024 导致内容被硬截断，`read_ratio` 永远 < 1.0，LLM 误以为文件未读完而反复尝试不同参数读取，一次 `update_memory` 消耗全部 20 次工具调用预算。解决方案是去掉 `max_chars`，用 `limit` 控制输出量，`read_ratio` 恢复准确。

## 2026-06-30-custom-provider-missing-xml-tool-call-parsing

- updated_at: 2026-06-30
- path: `docs/history-bugs/2026-06-30-custom-provider-missing-xml-tool-call-parsing.md`
- 触发规则：在排查 `is_direct: true` 的 provider（Xiaomi MIMO、Azure OpenAI 等）工具调用不执行、`llm_call_logger` 记录的 output 是 `<tool_call>` XML 文本而非最终回复、多轮工具调用第二次失败时阅读
- 内容摘要：记录了 `CustomProvider._parse()` 缺少 XML 工具调用解析，而模型 mimo-v2.5 在多轮对话中第二次响应将工具调用以 XML 格式写入 `content` 而非原生 `msg.tool_calls`，导致 `tool_calls=[]`、工具链中断、XML 文本被当作最终输出记录到日志。解决方案是从 `LiteLLMProvider` 搬来 `_parse_xml_tool_calls` 和回退逻辑。

## 2026-06-29-diary-calendar-scroll-race-condition

- updated_at: 2026-06-29
- path: `docs/history-bugs/2026-06-29-diary-calendar-scroll-race-condition.md`
- 触发规则：在排查日记界面日历点击后自动滚动、滚动条跳到顶部、React 状态更新竞态条件、useEffect 依赖竞态问题时阅读
- 内容摘要：记录了日记界面右侧日历点击后左侧滚动条自动跳到顶部的反复出现的 bug。根本原因是 React 状态更新的竞态条件：onClick 中 `setActiveDate` 和 `setShouldScrollToDate(false)` 都是异步的，useEffect 触发时 shouldScrollToDate 可能还未更新为 false，导致滚动逻辑执行。解决方案是使用 useRef 替代 useState，因为 ref.current 修改是同步的，完全避免竞态条件。

## 2026-05-26-message-content-type-mismatch

- updated_at: 2026-05-26
- path: `docs/history-bugs/2026-05-26-message-content-type-mismatch.md`
- 触发规则：在排查图片/多模态消息丢失、上下文长度异常膨胀、InboundMessage.content 类型错误、MessageContent 类使用时阅读
- 内容摘要：记录了 `InboundMessage.content` 类型不统一（str | list | None）导致的两个问题：1. f-string 拼接 list 使图片变成纯文本字符串无法识别 2. Base64 图片 list 被字符串化导致 token 爆炸。解决方案包括新增 `MessageContent` 类统一归一化、`InboundMessage.__post_init__` 强制转换、context.py 返回多模态列表、llm_provider 增加类型校验。

## 2026-05-26-screenshot-analysis-clean-response-too-strict

- updated_at: 2026-05-26
- path: `docs/history-bugs/2026-05-26-screenshot-analysis-clean-response-too-strict.md`
- 触发规则：在排查截图分析结果为 None、LLM 有输出但行为分析为空、调整 `_clean_llm_response` 清洗策略、恢复 `cleaned_response = _clean_llm_response(response)` 调用时阅读
- 内容摘要：记录了 `screenshot_analysis.py` 中 LLM 响应清洗策略过严的问题；当模型没有严格按照预期格式输出时，有效内容可能被过滤为空并返回 `"None"`。建议采用宽松清洗和原文兜底，避免截图分析结果丢失。

## 2026-05-22-floating-window-dialog-memory-leak

- updated_at: 2026-05-22
- path: `docs/history-bugs/2026-05-22-floating-window-dialog-memory-leak.md`
- 触发规则：在排查浮窗或对话框相关的内存泄露问题、实现新的对话框通信机制、发现监听器未被清理的问题、排查 Promise 永久挂起的问题、实现窗口间通信时阅读
- 内容摘要：记录了 What Am I Doing 浮窗中 `record-activity` 对话框被直接关闭时，监听器未被清理导致的内存泄露问题。修复方案包括注册 `dialog-closed` 监听器、实现清理逻辑、确保 Promise 正确 resolve。包含两种对话框通信模式的对比和最佳实践。

## 2026-04-30-screenshot-timestamp-format-mismatch

- updated_at: 2026-04-30
- path: `docs/history-bugs/2026-04-30-screenshot-timestamp-format-mismatch.md`
- 触发规则：在排查截图分析查询失败、时间戳格式不匹配、SQLite 时间范围查询返回空结果时阅读
- 内容摘要：记录了修改 screen_captures 表时间戳格式后，查询时使用 ISO 格式导致无法匹配数据库格式的 bug，以及截图数量限制和动态 chunk 大小的优化方案。

## 2026-04-25-electron-native-dialog-focus-loss

- updated_at: 2026-04-25
- path: `docs/history-bugs/2026-04-25-electron-native-dialog-focus-loss.md`
- 触发规则：在排查 Electron 应用中使用 window.confirm/alert/prompt 后输入框无法输入、焦点丢失，或 window.electronAPI undefined 错误时阅读
- 内容摘要：记录了 Electron 原生对话框导致输入框焦点丢失的已知 bug，以及 window.electronAPI 调用缺少可选链和降级方案导致的崩溃问题。包含完整的解决方案和 18 个文件的修复记录。

## 2026-04-22-multiprocessing-infinite-loop

- updated_at: 2026-04-22
- path: `docs/history-bugs/2026-04-22-multiprocessing-infinite-loop.md`
- 触发规则：在排查 Windows 打包环境下后端无限启动、端口被大量占用、multiprocessing 子进程异常行为时阅读
- 内容摘要：记录了 Windows 下 multiprocessing.Process 在 PyInstaller 打包后因缺少 freeze_support() 导致子进程重复执行主程序逻辑，引发后端无限启动循环的严重 bug。

## 2026-04-19-chain-node-menu-occlusion

- updated_at: 2026-04-19
- path: `docs/history-bugs/2026-04-19-chain-node-menu-occlusion.md`
- 触发规则：在排查包含弹窗、拖拽操作或多层嵌套列表组件导致的 z-index 层叠/遮挡等渲染错误时阅读
- 内容摘要：整理了 dnd-kit 修改 transform 引起的”层叠上下文封闭”从而致菜单被底部节点遮挡的原理，以及应用 React Portals 和 Floating UI 的标准处理方案。
