# Issue 4: 命令响应增强 - /continue 和 /new

## 必读文档

在开始实现前，请阅读以下文档：

1. **PRD**: `.scratch/wechat-session-enhancement/prd.md`
   - 重点阅读：Solution 第 4、5 点、Implementation Decisions 第 6 节
2. **实现分析**: `.scratch/wechat-session-enhancement/implementation-analysis.md`
   - 重点阅读：实施顺序阶段 4、约束确认第 2.2 节
3. **编码规范**: `docs/coding-rules/backend-core-rules.md`
   - 重点阅读：类型注解、文档字符串、日志记录
4. **测试规范**: `docs/coding-rules/test-rules.md`
   - 重点阅读：测试目录结构、验证方法
5. **现有命令实现**: `lifeprism/llm/agent/loop.py` 的 `_process_cmd()` 方法
   - 理解现有命令处理模式

## Parent

无（这是独立的功能切片）

## What to build

增强 `/continue` 命令显示最后两轮对话，增强 `/new` 命令提示如何恢复上一个会话。让用户在切换会话时能快速回忆上下文，在创建新会话时知道如何回到之前的工作。

完整的端到端路径包括：
- 修改 `/continue <session_id>` 命令逻辑，加载 session，提取最后两轮对话
- 修改 `/new` 命令逻辑，获取当前 session_id，在响应中提示恢复指令
- 编写单元测试，验证响应格式
- 通过微信实际测试命令效果

## Acceptance criteria

### /continue 命令增强

- [ ] 修改 `lifeprism/llm/agent/loop.py` 的 `_process_cmd()` 方法
- [ ] 在 `/continue` 命令分支中增加逻辑：
  - [ ] 验证 session_id 存在（保留现有逻辑）
  - [ ] 调用 `session_manager.get_or_create_session(session_id)` 加载 session
  - [ ] 从 `session.messages` 中提取最后两轮对话：
    - [ ] 最后一条 `role == "user"` 的消息
    - [ ] 最后一条 `role == "assistant"` 的消息
  - [ ] 如果消息少于两轮，显示现有内容
  - [ ] 构造响应文本：
    ```
    [SUCCESS] 继续会话 <session_id>
    
    最后两轮对话：
    user:
    <user_content>
    
    A:
    <assistant_content>
    ```
- [ ] 保持原有错误处理逻辑（session 不存在时的提示）
- [ ] 记录 INFO 级别日志

### /new 命令增强

- [ ] 在 `/new` 命令分支中增加逻辑：
  - [ ] 在创建新 session 前，从 `msg.session_id` 获取 `old_session_id`
  - [ ] 如果 `old_session_id` 不为 None，构造响应文本：
    ```
    [SUCCESS] 新建会话 <new_session_id> --- 可以开始新的聊天了！
    
    可以通过使用以下指令恢复上一个会话：
    /continue <old_session_id>
    ```
  - [ ] 如果 `old_session_id` 为 None（首次创建），不显示恢复提示
- [ ] 保持原有逻辑（创建 session、保存、返回 session_id）
- [ ] 记录 INFO 级别日志

### 测试

- [ ] 创建 `test/core/unit/llm/agent/test_loop_cmd.py`（如果不存在）
- [ ] 标记 `@pytest.mark.core`
- [ ] 测试 `/continue` 命令：
  - [ ] 响应包含最后两轮对话
  - [ ] session 消息少于两轮时的处理
  - [ ] session 不存在时返回错误
- [ ] 测试 `/new` 命令：
  - [ ] 有上一个 session 时，响应包含恢复提示
  - [ ] 首次创建 session 时，不显示恢复提示
- [ ] 通过微信发送 `/continue` 和 `/new` 命令，验证响应格式

## Blocked by

None - 可立即开始（与 Issue 1-3 并行）
