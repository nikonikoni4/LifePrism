## 2026-07-16-cloud-missing-files-skipped-by-false-assumption

- updated_at: 2026-07-16
- path: `docs/history-bugs/2026-07-16-cloud-missing-files-skipped-by-false-assumption.md`
- 触发规则：在排查云端重装后本地文件不再同步、session JSONL 文件之前能同步改了冲突策略后不能了、`_sync_files_full_flow` 中 `remote_state is None` 分支逻辑、`/pull-files/check` 端点返回值结构、`file_sync_state` 表状态与同步行为关系时阅读
- 内容摘要：**回归 bug（P0，已修复）** — 从纯 mtime LWW 切换到 per-file version tracking 后，check 端点只返回 mtime 过滤的变更文件，不返回完整路径清单。本地用 `local_parent is not None` 猜测"云端有但未改"，导致云端已缺失文件被错误 SKIP。修复方案：check 端点新增返回 `all_paths`（完整路径清单），本地用它做存在性判断替代猜测。经 git history 调查发现**旧 mtime LWW 逻辑（`1d7637c8` 之前）也有同样问题**：push 侧只收集 `mtime > last_sync_time` 的文件，云端重装 + 本地未改时同样推不了（首次同步能成功只因 `last_sync_time` 为空被置为 1970 年）。此 bug 是"远端状态未显式查询"的设计通病，不因新旧策略而消失。设计教训：远端状态必须显式查询，不能用本地元数据猜测。

## 2026-07-14-sync-key-regeneration-and-config-fallback

- updated_at: 2026-07-14
- path: `docs/history-bugs/2026-07-14-sync-key-regeneration-and-config-fallback.md`
- 触发规则：在修改云端配置生成逻辑（`cloud_config_generator.py`、`cloud_config_api.py`）、修改同步 API Key 读取逻辑（`sync_config.py`）、用户反馈"生成的同步 Key 始终是同一个测试值"、讨论同步 API Key 的生成/更新/轮换策略、排查 config.yaml 中的 `sync_api_key` 字段如何被消费时阅读
- 内容摘要：记录了同步 API Key 的四个关联问题：(1) 前端生成云端配置时无确认键，用户无法选择"保留当前 Key"还是"更换 Key"；(2) Key 读取链路被 config.yaml fallback 污染，导致 `get_sync_api_key()` 将 config.yaml 中手动写入的弱 Key 当作"已有的 Key"，`secrets.token_urlsafe(32)` 永不触发；(3) 所有 Key（sync_api_key、wechat_token、Provider API Key）统一到 `storage.yaml` 专用文件，通过 `run_mode` 控制读写——本地仅 keyring，云端才用文件 fallback。config.yaml 移除所有 Key 字段；(4) keyring 顶层 import 导致 Linux 模块加载崩溃，修复方案为懒加载（`_get_keyring()` 仅在 Windows 上首次调用时导入），subagent 评估确认可行，改造 5 个文件约 64 行。

## 2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite

- updated_at: 2026-07-14
- path: `docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md`
- 触发规则：在排查本地与云端数据不一致、定时同步不执行、启动时未拉取云端新增数据、`SyncClient`/`start_scheduled_sync`/`sync_once` 是否被实际调用、云端首次部署后本地文档被空文档反向覆盖、基于 `mtime` 的 LWW 文件冲突解决在空文件 vs 有内容文件场景下失效时阅读
- 内容摘要：**严重生产级 bug（P0，待修复）** - 记录了两个关联问题：(1) 数据同步链路未打通，`SyncClient` 在 `main.py:331` 实例化后从未调用 `start_scheduled_sync()` 和启动时 `sync_once()`，导致 Spec 要求的"启动时同步"和"每 10 分钟定时同步"完全失效，仅关闭时和前端手动触发可用；(2) 文件 LWW 算法只比较 `mtime` 不比较内容，云端新部署自动创建的空文档（mtime 为当前时间）会反向覆盖本地有内容的文档（mtime 为历史时间），造成数据丢失。Bug 1 修复前 Bug 2 被掩盖未暴露，必须一起修复。Bug 2 给出 4 个候选方案（云端不创建空文档/LWW 加内容大小判断/首次同步只 push/云端初始化标记）待讨论选择。附录包含思源笔记同步机制调研（git-like 内容寻址快照 + 3-way merge），提供短期/中期/长期三档改造方案参考。

## 2026-07-13-timeline-custom-block-date-query-datetime-field

- updated_at: 2026-07-13
- path: `docs/history-bugs/2026-07-13-timeline-custom-block-date-query-datetime-field.md`
- 触发规则：在排查前端传日期参数查询、数据库表只有 datetime 字段、查询结果不完整、时区转换错误、SQLite 字符串比较失败时阅读
- 内容摘要：**标准模板** - 记录了 timeline_custom_block 前端传本地日期 `date=2026-07-13` 查询，但数据库表只有 UTC datetime 字段 `start_time`，导致 Repository 层直接拼接字符串 `"2026-07-13 00:00:00"` 与 UTC ISO 格式 `"2026-07-12T21:20:00.000Z"` 进行字符串比较失败。修复方案是前端传 UTC 时间范围 `start_time/end_time`，后端直接使用。包含完整的根因分析、修复方案、验证方法、预防措施，作为此类问题的标准模板。

## 2026-07-11-cloud-init-provider-display-name-mismatch

- updated_at: 2026-07-11
- path: `docs/history-bugs/2026-07-11-cloud-init-provider-display-name-mismatch.md`
- 触发规则：在排查云端 `reinit-config` 失败、cloud_init.yaml 验证报 "未找到 llm.provider 对应的 provider"、provider 配置了 display_name 和内部 name 两套命名时阅读
- 内容摘要：记录了 `CloudInitializer._validate()` 直接用 display_name 匹配 providers[].name（内部 name）导致精确匹配失败的问题。根源是项目 Provider 系统有两层命名，cloud_init.yaml 的 `llm.provider` 来自 `settings.get("provider")`（display_name），而 `providers[].name` 是内部 name，验证时缺少 `get_provider_id()` 转换。测试用例 mock 数据用的是内部 name 恰好绕过了此 bug。

## 2026-07-09-run-mode-persisted-to-yaml

- updated_at: 2026-07-09
- path: `docs/history-bugs/2026-07-09-run-mode-persisted-to-yaml.md`
- 触发规则：在排查不同部署模式（full/web_demo/agent_only）行为不一致、sync_service 在 web_demo 下仍允许同步、schedule_service 在 web_demo 下仍注册定时任务、wechat channel 云端路由不生效时阅读
- 内容摘要：记录了 `run_mode` 被定义在 `DEFAULTS` 中导致首次启动写入 yaml，之后切换入口不会更新。三个入口文件都没有显式设置当前运行模式，完全依赖 yaml 中始终为 `"full"` 的值，导致所有模式守卫失效。修复方案是引入 `_runtime_config` 字典分离运行时配置和持久化配置，三个入口文件显式注入对应 run_mode。

## 2026-07-09-monitor-type-none-aw-db-crash

- updated_at: 2026-07-09
- path: `docs/history-bugs/2026-07-09-monitor-type-none-aw-db-crash.md`
- 触发规则：在云端部署（agent_only / web_demo）遇到数据清洗任务报错、AW 数据库文件不存在的 FileNotFoundError、`monitor_type: none` 却走了 ActivityWatch 分支时阅读
- 内容摘要：记录了云端 `monitor_type: none` 导致 `data_clean.py` 数据源选择逻辑落入 `else` 分支，触发 `ProcessorAWDataProvider` → `AWBaseDataProvider._validate_database()` → `FileNotFoundError`。虽然 issue #11 已将 `aw_db_manager` 改为懒加载避免 import 崩溃，但首次数据清洗触发 `get_connection()` 时仍会因 AW 数据库文件不存在而失败。修复方案是在 `data_clean.py` 增加 `elif monitor_type == "none"` 分支直接返回空数据。

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
- 内容摘要：整理了 dnd-kit 修改 transform 引起的"层叠上下文封闭"从而致菜单被底部节点遮挡的原理，以及应用 React Portals 和 Floating UI 的标准处理方案。
