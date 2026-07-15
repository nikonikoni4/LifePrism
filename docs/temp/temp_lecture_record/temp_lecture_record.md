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

