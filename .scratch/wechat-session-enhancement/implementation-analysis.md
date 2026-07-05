# 微信会话管理增强功能 - 实现分析

## 一、难度评估

### 整体难度：中等（3/5）

**理由**：
- ✅ **简单部分**：命令响应增强、提示词更新、工具注册都是直接修改
- ⚠️ **中等部分**：工具实现涉及文件读取、数据聚合、兼容性处理
- ⚠️ **复杂部分**：chat_history.json 的 session_id 传递链路需要追踪调用点

### 子任务难度分解

| 任务 | 难度 | 工作量 | 风险点 |
|------|------|--------|--------|
| 1. ChatHistoryManager.add_content() 签名修改 | 低 | 0.5h | 调用点可能遗漏 |
| 2. agent_schedule_job 调用点修改 | 低 | 0.5h | 需要确保 session.id 可用 |
| 3. QuerySessionListTool 实现 | 中 | 2h | 文件解析、数据聚合逻辑 |
| 4. QuerySessionHistoryTool 实现 | 低 | 1h | 简单的文件读取和过滤 |
| 5. 工具注册和导出 | 低 | 0.5h | 无风险 |
| 6. /continue 命令增强 | 中 | 1h | 消息提取逻辑 |
| 7. /new 命令增强 | 低 | 0.5h | 获取 old_session_id |
| 8. templates/agent/chat/tool.md 更新 | 低 | 1h | 需要清晰表达 AI 行为规范 |
| 9. 测试编写 | 中 | 3h | 需要构造测试数据环境 |

**预计总工作量**：10-12 小时

---

## 二、实现前约束确认

### 2.1 仓库规则约束

#### A. 编码规范（来自 backend-core-rules.md）

✅ **必须遵守**：
1. **类型注解**：所有函数签名必须有完整类型注解
   ```python
   def add_content(self, content: str, session_id: str | None = None) -> None:
   ```

2. **文档字符串**：使用 Google 风格，包含 Args、Returns
   ```python
   """
   添加聊天历史记录
   
   Args:
       content: 总结内容
       session_id: 会话 ID，为 None 时不关联会话
   
   Returns:
       None
   """
   ```

3. **日志记录**：使用 `get_logger(__name__)`，关键操作记录 INFO 级别
   ```python
   logger.info(f"查询会话列表: date_filter={date_filter}, 结果数={len(result)}")
   logger.warning(f"Session {session_id} 不存在")
   logger.error(f"查询会话列表失败: {e}")
   ```

4. **错误处理分层**：
   - **工具层（Tool）**：捕获异常，返回 `f"{ERROR}xxx"` 格式的错误消息
   - **命令处理（AgentLoop._process_cmd）**：直接返回 OutboundMessage，不抛出异常
   - 不使用 `except Exception` 捕获所有错误

5. **数据路径统一**：通过 `settings_manager` 获取路径，禁止自行解析
   ```python
   # ✅ 正确
   session_path = settings.session_path
   
   # ❌ 错误
   session_path = Path("lifeprismData/session")
   ```

#### B. 测试规范（来自 test-rules.md）

✅ **必须遵守**：
1. **测试目录**：
   - 工具测试 → `test/core/unit/llm/tools/test_session_query.py`
   - 命令测试 → `test/core/unit/llm/agent/test_loop_cmd.py`（或扩展现有）
   - 标记为 `@pytest.mark.core`

2. **数据来源**：
   - 工具测试使用临时目录 + 真实文件，不 mock
   - 命令测试可以 mock session_manager

3. **验证方式**：
   - 简单结果：断言（assert）
   - 复杂结果：类型判断 + 合理性检查

#### C. 工具规范（来自 base.py 和现有工具）

✅ **必须遵守**：
1. **继承 Tool 基类**
2. **实现三个属性**：`name`、`description`、`parameters`
3. **实现 execute() 方法**：async，返回 str 或结构化数据
4. **错误返回格式**：`f"{ERROR}xxx"`，成功可选 `f"{SUCCESS}xxx"`
5. **参数校验**：通过 JSON Schema 定义，工具基类会自动校验

### 2.2 最小改动原则

#### A. 不改动现有逻辑的约束

✅ **遵守的边界**：
1. **SessionManager**：不修改现有方法，只使用现有接口
   - 使用 `get_session_path_by_id()`、`show_session_list()` 等现有静态方法
   - 不修改 Session 数据结构

2. **ChatHistoryManager**：只增加参数，不改变现有行为
   - `add_content()` 增加可选参数 `session_id: str | None = None`
   - 向后兼容：不传 session_id 时，数据格式与旧版一致

3. **AgentLoop**：只在现有分支增加工具注册，不改变流程
   - 在 `if msg.type == MessageType.CHAT:` 分支末尾增加两行注册
   - 命令处理逻辑增强，不改变现有返回格式的基本结构

#### B. 修改点清单（所有需要改动的位置）

| 文件 | 修改类型 | 影响范围 |
|------|----------|----------|
| `lifeprism/llm/session/manager.py` | 签名修改 | ChatHistoryManager.add_content() |
| `lifeprism/llm/function/agent_schedule_job.py` | 调用点修改 | process_session_message() |
| `lifeprism/llm/agent/tools/session_query.py` | 新增文件 | 无影响 |
| `lifeprism/llm/agent/tools/__init__.py` | 导出修改 | 增加两个导出 |
| `lifeprism/llm/agent/loop.py` | 工具注册 | _process_msg() 增加 2 行 |
| `lifeprism/llm/agent/loop.py` | 命令增强 | _process_cmd() 两个分支 |
| `templates/agent/chat/tool.md` | 内容增加 | 增加一个章节 |

**总修改文件数**：6 个现有文件 + 1 个新文件

### 2.3 最佳实践约束

#### A. 性能考虑

⚠️ **潜在风险**：
1. **QuerySessionListTool**：
   - 需要遍历所有 session.jsonl 文件（可能 100+）
   - 需要加载并解析完整的 chat_history.json

🛡️ **缓解方案**：
1. **初版实现**：不做优化，接受性能代价
2. **后续优化**（如果需要）：
   - 限制返回结果数量（如最多 20 个）
   - 缓存 session metadata
   - 增加分页支持

#### B. 数据一致性

⚠️ **已知问题**：
- `chat_history.json` 的 `session_id` 由定时任务 `process_session_message()` 每 2 小时写入
- 新创建的 session 在前 2 小时内没有对应的 summary

🛡️ **处理方案**：
1. **QuerySessionListTool**：
   - 如果某个 session 没有 summary，`last_summary` 返回空字符串 `""`
   - 不抛出错误，这是预期行为
   - 在工具描述中说明：`last_summary` 可能为空（session 刚创建）

#### C. 兼容性保证

✅ **向后兼容策略**：
1. **ChatHistoryManager.add_content()**：
   - `session_id` 参数为可选（默认 None）
   - 旧调用点不传 session_id 时，不写入该字段（与旧格式一致）
   - 新调用点传入 session_id 时，写入新格式

2. **QuerySessionListTool**：
   - 读取 chat_history.json 时，跳过没有 session_id 的记录
   - 不报错，兼容混合数据（旧格式 + 新格式）

### 2.4 安全性约束

#### A. 文件访问安全

✅ **必须检查**：
1. **路径遍历攻击**：
   - 只读取 `settings.session_path` 下的 `.jsonl` 文件
   - 不接受用户提供的文件路径

2. **文件存在性检查**：
   ```python
   # QuerySessionHistoryTool
   if not session_path.exists():
       return f"{ERROR}会话 {session_id} 不存在"
   ```

3. **文件读取异常处理**：
   ```python
   try:
       with open(file, encoding='utf-8') as f:
           # 读取逻辑
   except Exception as e:
       logger.error(f"读取 session {session_id} 失败: {e}")
       return f"{ERROR}读取会话失败: {e}"
   ```

#### B. 数据隐私

⚠️ **注意事项**：
- session 内容可能包含敏感信息
- 工具返回的数据会被 LLM 处理，然后发送到微信
- **风险点**：无需特殊处理，用户本身就是通过微信与自己的 session 交互

#### C. 输入验证

✅ **必须验证**：
1. **日期格式验证**：
   ```python
   # date_filter 必须是 YYYY-MM-DD 格式
   if date_filter and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_filter):
       return f"{ERROR}日期格式错误，应为 YYYY-MM-DD"
   ```

2. **limit 参数验证**：
   ```python
   # limit 在 JSON Schema 中定义最小 1，最大 50
   # Tool 基类会自动验证，无需手动检查
   ```

---

## 三、实现风险和缓解措施

### 风险 1：调用点遗漏

**描述**：`ChatHistoryManager.add_content()` 的调用点可能不止 `agent_schedule_job.py` 一处

**缓解措施**：
1. 使用 grep 查找所有调用点：
   ```bash
   grep -rn "add_content" lifeprism/
   ```
2. 逐个检查，确认是否需要传入 session_id

### 风险 2：文件格式解析错误

**描述**：session.jsonl 或 chat_history.json 格式可能与预期不符（损坏、旧版本）

**缓解措施**：
1. 使用 try-except 包裹 JSON 解析
2. 遇到解析错误时跳过该文件，记录警告日志
3. 不让单个文件的错误影响整体查询

### 风险 3：性能问题

**描述**：session 数量很多时（100+），遍历所有文件可能很慢

**缓解措施**：
1. 初版接受性能代价，在实际使用中观察
2. 如果确实很慢，后续优化：
   - 限制返回结果数量
   - 按 updated_at 倒序，只遍历最近的 N 个 session

### 风险 4：提示词效果不理想

**描述**：AI 可能不按预期的流程引导用户（不询问时间、不按序号列出等）

**缓解措施**：
1. 提示词使用明确的指令（"必须"、"第一步"、"第二步"）
2. 提供示例格式
3. 通过实际使用迭代优化

---

## 四、实施检查清单

### 实现前

- [ ] 确认所有修改点已列出
- [ ] 确认测试策略（单元测试 + 集成测试）
- [ ] 确认日志记录策略
- [ ] 确认错误处理策略

### 实现中

- [ ] 每个函数都有类型注解和文档字符串
- [ ] 所有文件路径通过 settings_manager 获取
- [ ] 所有异常都被正确捕获和转换
- [ ] 所有修改点都记录了日志

### 实现后

- [ ] 运行所有测试，确保通过
- [ ] 手动测试核心流程（命令、工具）
- [ ] 检查日志输出是否符合预期
- [ ] 检查兼容性（旧数据、空数据）

---

## 五、建议实施顺序

### 阶段 1：数据层修改（无风险）
1. 修改 `ChatHistoryManager.add_content()` 签名（增加可选参数）
2. 修改 `agent_schedule_job.py` 调用点（传入 session_id）
3. **验证点**：运行系统，检查新生成的 chat_history.json 是否包含 session_id

### 阶段 2：工具实现（核心）
1. 实现 `QuerySessionListTool`
2. 实现 `QuerySessionHistoryTool`
3. 编写单元测试
4. **验证点**：测试通过，工具返回正确格式的数据

### 阶段 3：工具集成（低风险）
1. 在 `loop.py` 注册工具
2. 在 `__init__.py` 导出工具
3. **验证点**：启动系统，检查工具是否出现在 CHAT 类型的工具列表中

### 阶段 4：命令增强（中等风险）
1. 修改 `/continue` 命令逻辑
2. 修改 `/new` 命令逻辑
3. 编写命令测试
4. **验证点**：通过微信发送命令，检查响应格式

### 阶段 5：提示词优化（需要迭代）
1. 更新 `templates/agent/chat/tool.md`
2. **验证点**：通过实际对话测试 AI 行为

---

## 六、总结

### 可以开始实现的理由

✅ **充分准备**：
1. 修改点清晰，影响范围可控（6 个现有文件 + 1 个新文件）
2. 遵守所有仓库规则（编码规范、测试规范、工具规范）
3. 兼容性策略明确（向后兼容旧数据）
4. 风险已识别，缓解措施已制定
5. 实施顺序合理，每个阶段都有验证点

### 推荐的实施策略

1. **先小步实现，再完善**：
   - 先实现基本功能（工具 + 命令），不考虑极端情况
   - 跑通核心流程后，再补充边界情况处理
   - 最后优化提示词

2. **充分测试**：
   - 每个阶段都编写对应的测试
   - 手动测试覆盖核心用户场景

3. **监控实际使用效果**：
   - 记录详细日志
   - 根据实际使用反馈迭代优化

### 开始实施？

**建议**：可以开始实施，从阶段 1（数据层修改）开始。

如果你同意以上分析，我可以立即开始实现。如果有任何疑问或需要调整的地方，请告诉我。
