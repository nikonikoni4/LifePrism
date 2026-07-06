# Flow 文档更新检查工具

## 工具说明

### 1. `sync_docs.py` - 自动同步行号
**功能**：自动更新 flow 文档中 `<key_function>` 标签内的函数行号

**特性**：
- 防抖机制（10 分钟间隔）
- 运行 AST 扫描器获取最新函数位置
- 自动更新 `last_update` 时间戳

**使用方法**：
```bash
# 手动运行
python scripts/docs_update/sync_docs.py

# 通过 hook 自动触发（读取 flow 文档时）
```

---

### 2. `check_flow_outdated.py` - 检查 flow 文档是否需要更新
**功能**：检查 git diff 中的函数变化是否影响 flow 文档

**检查方法**：
1. 从 git diff 提取变化的 Python 文件
2. 解析每个文件中变化的函数定义（通过 `def` 关键字）
3. 读取所有 flow 文档的 `<key_function>` 标签
4. 匹配检查：如果变化的函数在某个 flow 的 key_function 中，报告需要检查

**使用方法**：
```bash
# 检查暂存区（用于 pre-commit hook）
python scripts/docs_update/check_flow_outdated.py --staged

# 检查最近 3 次提交
python scripts/docs_update/check_flow_outdated.py --commits 3

# 检查指定提交范围
python scripts/docs_update/check_flow_outdated.py --range HEAD~5..HEAD
```

**输出示例**：
```
============================================================
Flow 文档更新检查
============================================================

变化的文件数：2
  agents_hub/core/agent/base_agent.py: 2 个函数
  agents_hub/core/orchestration/group_chat.py: 1 个函数

扫描 flow 文档数：7

============================================================
⚠️  以下 flow 文档可能需要更新：
============================================================

📄 agent-call-lifecycle.md
   - agents_hub/core/agent/base_agent.py:base_agent.Agent.run
   - agents_hub/core/agent/base_agent.py:base_agent.Agent._process_message

📄 agent-initialization.md
   - agents_hub/core/orchestration/group_chat.py:group_chat.GroupChat._init_agents

============================================================
提示：共 2 个 flow 文档可能需要检查
============================================================
```

---

### 3. `pre-commit-check-flow.py` - Git pre-commit hook
**功能**：在 `git commit` 前自动检查 flow 文档是否需要更新

**安装方法**：
```bash
# 方法 1：创建软链接（推荐，方便更新脚本）
ln -s ../../scripts/docs_update/pre-commit-check-flow.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# 方法 2：复制文件
cp scripts/docs_update/pre-commit-check-flow.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# Windows 用户
# 在 Git Bash 中执行上述命令，或手动复制文件到 .git/hooks/pre-commit
```

**行为**：
- 每次 `git commit` 时自动运行
- 检查暂存区的函数变化
- 如果有 flow 文档需要更新，显示警告
- **不阻塞提交**（允许提交继续）
- **记录检查结果到日志**：`scripts/docs_update/flow-check.log`

**日志记录**：
- 每次检查都会追加记录到 `flow-check.log`
- 包含时间戳、检查结果、详细输出
- 方便因任务繁忙无法立即修复时查看历史记录

**Git Worktree 支持**：
- 通过 `git rev-parse --show-toplevel` 动态获取仓库根目录
- Worktree 中的 hook 会正确找到主仓库的脚本和日志路径
- 日志始终写入主仓库的 `scripts/docs_update/flow-check.log`

**卸载方法**：
```bash
rm .git/hooks/pre-commit
```

---

## 工作流程

### 开发过程
1. 修改代码（如修改 `Agent.run()` 函数）
2. `git add` 暂存修改
3. `git commit` 提交
4. **pre-commit hook 自动运行**，提示相关 flow 文档
5. 根据提示检查并更新相关 flow 文档
6. 提交 flow 文档更新

### 定期检查
```bash
# 检查最近 10 次提交是否有遗漏的 flow 更新
python scripts/docs_update/check_flow_outdated.py --commits 10
```

---

## Flow 文档维护原则

### key_function 是维护入口
- `<key_function>` 标签声明了所有关键函数
- 通过监控这些函数的变化，判断 flow 是否需要更新
- 链路描述中明确调用的函数必须在 key_function 中声明

### 只记录关键函数
- 减少维护成本：简单逻辑用文字描述（如"构建 prompt"、"格式化消息"）
- 只记录对 Flow 对象有直接影响的函数（状态变化、持久化、跨模块、分支、集合点）
- 工具函数、辅助函数、格式化函数通常不需要记录

### 函数签名格式
```markdown
<key_function last_update="2026-06-18T10:34:37+08:00">
- agents_hub/core/agent/base_agent.py
  - base_agent.Agent.run:858
  - base_agent.Agent._process_message:202
- agents_hub/core/orchestration/group_chat.py
  - group_chat.GroupChat.send_message_to_agent:563
</key_function>
```

格式规则：
- 类方法：`FileName.ClassName.method_name:行号`
- 模块函数：`FileName.function_name:行号`

---

## 常见问题

### Q: 为什么 hook 不阻塞提交？
A: 设计目标是"提醒而不阻塞"，因为：
- Flow 文档更新不应该阻塞紧急修复
- 开发者可以在提交后再更新 flow 文档
- 通过定期检查脚本补充遗漏的更新

如果需要阻塞提交，修改 `pre-commit-check-flow.py` 最后的 `sys.exit(0)` 为 `sys.exit(result.returncode)`

### Q: 检查脚本如何判断函数变化？
A: 通过解析 `git diff` 的输出：
- 匹配 `+def function_name(` 或 `-def function_name(` 行
- 提取函数名
- 与 flow 文档的 key_function 中的函数名匹配

### Q: 如果漏报或误报怎么办？
A: 这是基于简单的文本匹配，可能有误报：
- **漏报**：修改函数内容但不修改函数定义行 → 不会触发检查
- **误报**：修改函数定义但不影响 flow 逻辑 → 会触发检查

建议：把检查结果作为提醒，人工判断是否真的需要更新

---

## 文件清单

```
scripts/docs_update/
├── sync_docs.py                      # 自动同步行号（10 分钟防抖）
├── check_flow_outdated.py            # 检查 flow 是否需要更新
├── pre-commit-check-flow.py          # Pre-commit hook
├── README.md                         # 本文档
└── .last_sync_time                   # sync_docs.py 的防抖状态文件（自动生成）
```
