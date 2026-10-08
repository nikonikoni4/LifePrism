## 写入指南

在这里写入临时的经验教训，不作为正式的规则

## 经验教训

1. **CI 报告分发事实准确**：在编写0002号CI-report.md时将未分发的子agent写成了已分发，这个是AI幻觉，将本地检查当做已经分发了subagent
2. **使用已有子agent prompt模板时不要擅自改写**：当skill已经明确给出prompt文件和分发模板时，应该直接使用原prompt，只允许补充最小运行上下文，不能自行压缩、总结或重写任务定义与输出契约。
3. **docs-code-consistency-checker 不能因为修改了 authority/specs 索引文件本身就触发**：它检查的是 `docs/authority/index.md`、`docs/specs/index.md` 目录文档中定义的触发规则是否被当前变更命中，而不是”只要这两个索引文件被修改就触发”。当前这次变更全部是 md 文档和 git 文档，没有代码/配置/架构事实变更，不应分发该checker。
4. **skill 写法要避免触发条件歧义**：`docs-code-consistency-checker` 的触发描述如果只写”当变更内容能够触发 docs/authority/index.md, docs/specs/index.md 目录文档中的触发规则时”，容易被误解成”修改这两个文档就触发”。应明确写成”当当前变更命中这两个索引所声明的触发规则对应范围时才触发，而非修改索引文件本身”。
5. **subagent 平台错误要与流程判断分开记录**：这次 `docs-code-consistency-checker` 子agent还出现了 high demand 报错，但这属于平台执行错误，不改变”该checker本轮本就不该触发”的流程结论，记录时需要分开写清楚。
6. **设计 API 响应前必须核对被调用函数真实返回值**：日记 AI 总结设计中误把 report 的 `AISummaryResponse` 契约套用到 `ai_diary_summary`，但该函数只返回 summary content，不能提供 `tokens_usage`。以后复用相似 API 模式前必须先检查底层函数返回结构，避免设计出无法实现的响应字段。
7. **文件系统操作前必须检查路径存在性**：修复 `skill.py` bug 时发现 `get_skills_list()` 直接调用 `Path.iterdir()` 而不检查目录是否存在，导致 `FileNotFoundError`。所有涉及文件系统遍历的操作（`iterdir()`, `glob()` 等）都应该先用 `path.exists()` 检查，失败时返回合理的默认值（空列表/空字符串）并记录警告日志，而不是让异常传播到调用方。
8. **反复出现的 bug 要深挖竞态条件根因**：日记界面日历点击后滚动条跳到顶部的 bug 已修复多次仍反复出现，根本原因是 React 状态更新的竞态条件。onClick 中 `setActiveDate` 和 `setShouldScrollToDate(false)` 都是异步的，useEffect 依赖 `activeDate` 触发时，`shouldScrollToDate` 可能还未更新为 false，导致滚动逻辑执行。**正确做法是用 useRef 替代 useState**，因为 `ref.current` 修改是同步的，完全避免竞态。当事件处理器中修改标志位，且 useEffect 需要立即读取最新值时，必须用 useRef。
9. **storage key 与 keyring username 不是同一个概念**：`wechat_token` 是 storage.yaml 中的字段名，但 keyring 中历史使用的 username 是 `wechat_bot_token`（PRD 规范）。`SettingsManager._get_storage_key_from_keyring(key_name)` 之前直接用 `key_name` 作为 keyring username 查找，导致读取返回 None。修复方案是在 `SettingsManager` 中添加 `STORAGE_KEY_TO_KEYRING_USERNAME` 映射表，并在 `_get_storage_key_from_keyring` / `_set_storage_key_to_keyring` / `_delete_storage_key_from_keyring` 三个方法中统一使用映射后的 username。读取时还需兼容性回退（先试映射后的 username，再试原始 key_name），删除时同时删除两个 username 的条目。排查此类"key 应该在 keyring 中但读取为空"的 bug 时，应直接用 `python -c "import keyring; print(keyring.get_password('service', 'username'))"` 验证 keyring 中实际存储的 username 是什么。
10. **bug 修复不能把必填字段改为可选来绕过验证错误**：cloud_init.yaml 验证失败提示"缺少必需字段: wechat_token"时，正确做法是排查为什么 wechat_token 为空（根因是 keyring username 不匹配），而不是把 wechat_token 改为可选字段来让验证通过。把必填字段改为可选会掩盖真实的 bug，并且违反用户明确的产品要求。
11. **Service 层调用底层 set 方法必须检查返回值**：`setting_service.update_api_key` 调用 `settings.set_api_key()` 后未检查返回值，失败时仍打印"已安全保存"日志，严重误导排查。任何调用可能失败的底层方法（keyring 写入、文件 IO、网络请求等）都必须检查返回值，失败时抛异常或返回错误，不能静默成功。排查"日志显示成功但功能不工作"的 bug 时，应优先检查日志打印前是否跳过了返回值检查。
12. **前端脱敏值检测必须与后端脱敏格式一致**：后端 `get_for_display` 脱敏格式是 `{前4}...{后4}`（如 `sk-c...6yom`），但前端 `handleApiKeyBlur` 只检测 `*` 字符，导致脱敏值被当作真实 key 保存。任何"后端脱敏 + 前端显示 + 自动保存"的输入框，前端脱敏检测逻辑必须与后端脱敏格式严格对应，否则脱敏值会被当作新值回写，造成数据污染。
13. **前端切换配置项时必须刷新所有关联 state**：`handleProviderChange` 切换 provider 时更新了 `provider`/`modelName`/`apiBase` 但未更新 `apiKey`，导致输入框残留旧 provider 的脱敏值，结合自动保存被误保存到新 provider。任何"切换配置项"的操作（provider 切换、账号切换等）都必须刷新所有关联的输入框 state，不能只更新部分字段。
14. **env_key 为空的 provider 无法使用 keyring**：`DEFAULT_PROVIDER_CONFIG` 中 custom provider 的 `env_key: ""` 为空，导致 `_set_api_key_to_keyring_by_provider` 因 `username=None` 跳过写入，`get_api_key` 也直接返回 None。新增 provider 时 `env_key` 必须配置非空值（作为 keyring 的 username），否则 api_key 永远无法保存和读取。排查"provider 配置了但模型无法使用"的 bug 时，应检查 `env_key` 是否为空。

15. **工具转接测试必须显式覆盖目标数据库路径，防止污染真实数据**：编写 mcp/ 工具转接服务时，测试脚本一开始直接读取 config.yaml 的默认 db_path（真实库 lifewatch_ai.db），导致 create mood/behavior_note/custom_record_type 等写操作全部写入了真实数据库（污染 2 条 mood、2 条 block、2 个 type+4 字段+2 动态表、1 条 reading_log），清理后才意识到。根因：lifeprism.repository 在模块导入时用 settings.lw_db_path 建连接池，而 test 直接 load_config() 未覆盖路径。正确做法：(1) 测试脚本默认强制指向副本库（如 "lifewatch_ai - 副本.db"），并加"非副本命名"警告；(2) tool_bridge 支持 MCP_DB_PATH 环境变量覆盖；(3) 写入类工具测试应创建独立测试类型而非复用真实类型表。排查"测试后真实库多了数据"时，应对比副本/真实库的 MCP 标记数据差异。
16. **SettingsManager 单例在模块导入时即实例化，monkeypatch 类属性对已实例化对象无效**：lifeprism 的 SettingsManager 在 `from lifeprism.config import settings_manager` 时（模块底部 `settings = SettingsManager()`）就完成 _initialize()。想通过 `SettingsManager.lw_db_path = property(...)` 覆盖路径，必须在**任何 lifeprism 模块导入之前**执行（本方案通过 init_lifeprism() 先调用）。同理，开发环境 config_base_path 是相对路径 `Path("localData")`，从 mcp/ 目录运行时会在 mcp/ 下产生 localData 垃圾，需在导入前 os.chdir 到项目根让相对路径解析到项目根的 localData，再显式覆盖 settings._lifeprism_data_path。
17. **MCP stdio server 的 stdout 是协议通道，必须把日志重定向到 stderr**：mcp SDK 通过 stdout 传 JSON-RPC，lifeprism logger 的 StreamHandler 写 sys.stdout 会污染协议流（表现为客户端解析 JSONRPCMessage 失败）。解决：在导入 lifeprism 之前先 `logging.basicConfig(handlers=[StreamHandler(sys.stderr)])`，利用 basicConfig 幂等特性（已有 handler 则跳过）阻止 lifeprism 添加 stdout handler。
18. **myagent 重试通过 IoC 注册，不嵌套在 provider 请求内**：2026-10-03 用户纠正将重试写进 provider 的错误方案。应先参考 lifeprismevalue/llm/llm_retry.py，在 AgentContext.register_policy 挂载 REQUEST_ERROR waterfall；策略只返回 decision/policy，由 loop 负责预算、退避、请求重放和 llm/retry 记录。provider 保持单次请求与错误分类，避免双重重试和绕过事件生命周期。
19. **聊天 Session 目录不要按渠道细分**：2026-10-07 用户纠正，原先把聊天存到 chat/<channel>（local/wechat 分开）是错的。channel 的职责只是消息收发路由与事件字段，不参与业务存储归属；业务存储归属只按 chat/workflow/task 分类。同一用户从不同渠道进入的是同一段聊天，必须能跨渠道在同一 session 继续。判定原则：当某个字段既用于"消息路由"又疑似用于"数据归属"时，先确认它是否真的是归属维度，不要顺手拿它当目录名。

## 2026-10-07 Session 提取审查教训
- 原生turn游标推进到已结束边界时，必须包含边界之前因崩溃缺少turn/end的用户消息；不能只枚举带turn/end的轮次，否则游标会越过未提取内容。末尾未结束轮次仍等待后续边界。
- 日期Markdown的子标题查找必须同时限定起点和终点，终点为下一日期块，避免把内容写进未来同名章节。

- 2026-10-08：真实记忆任务存在两个同名user.md时，只有recent_state路径明确会诱导模型选择daily_data/user.md。任务必须明确给出聊天实际读取的user/user.md以及recent_state完整路径，并用原生tool/call轨迹验证目标，不能只以函数返回成功或任一同名文件变化认定完成。

- 2026-10-08：迁移微信命令时只验证新内核和渠道引用，没有完整比对旧AgentLoop._process_cmd的用户可见契约，遗漏/new即时创建与旧会话恢复指令、/continue最近对话回顾、/session-list日期筛选和用户消息摘要。后续迁移渠道命令须先从Git提取旧成功/错误回复及副作用，再逐项写回归测试；不能把新内核接通当作交互行为全部恢复。

## 2026-10-08 微信 transport 与人在回路边界纠正
- 用户指出：微信只负责收发，会话命令不能写在渠道适配器中；人在回路继续订阅 myagent 事件，并通过注入 client 展示问题、接收决定。
- 教训：抽取业务文件不足以解决耦合，必须明确原执行任务、交互 Future 和统一输出入口的拥有者；下一条用户输入只解决待答交互，不能再次等待上次执行结果或启动普通 user turn。
- 源码核实后纠正此前并发假设：微信 `_poll_loop` 实际逐条 await 消息处理，会被 execute 阻塞。必须让提交入口及时返回，由会话服务持有执行任务。
- 区分 step finally 内的可恢复错误 waterfall 与 turn/end 的终态，不在未核实源码时把 finally 一概当成清理结束。

## 2026-10-08 工具调用混合输出的归因
- 用户指出不同工具名被合并；检查 session 分片确认两个不同 call_id 使用相同 index=0，而 ProviderAdapter 仅按 index 累积，覆盖 ID 并拼接 name/arguments。
- 教训：非法 arguments 不能直接归因于模型输出；先比对分片中的 index、call_id 和最终聚合结果。区分原生 tool_calls 拼接与 XML 解析路径，未保存原始 SDK 流时不声称已证实服务端原始输出。

## 2026-10-08：RAG 索引更新与同步顺序

用户明确要求：每天更新完本地索引后，再单独向云端同步 RAG index 一次。我此前把本地每日更新和及时更新拆成选项，增加了理解负担。以后先沿用用户的业务顺序：每日索引更新成功 → 独立云端同步一次；不要无必要引入另一个刷新模式，也不要把顺序澄清当成用户已批准失败重试或补执行策略。

## 2026-10-08：审查结论区分任务范围

- 用户指出会话迁移脚本不属于当前 RAG 实现范围。审查覆盖未跟踪文件时，应明确区分既有文件与本次实现，不将范围外发现当作 RAG 的阻塞项；用户要求提交全部内容时按其明确范围执行，不擅自修复范围外问题。
## 2026-10-08：同步测试覆盖实际部署入口

- 用户提醒正常启动与 agent-only 使用不同入口。此前只在 `main.py` 条件注册接收路由，而实际云端由 `main_agent_only.py` 创建独立应用，单独挂载 router 的测试未覆盖这个缺口。
- 修复后从真实 `_run_agent_and_api` 捕获创建的应用，并通过临时 TCP 端口验证正常模式调度、上传、云端发布、确认和失败重试。以后多入口功能必须检查每个实际入口的路由、模式和生命周期接线，不能用 router 单测替代部署入口验证。
