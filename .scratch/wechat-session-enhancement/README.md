# 微信会话管理增强功能

## 功能概述

为微信渠道添加会话管理功能，允许用户：
- 查询历史会话列表
- 预览会话内容
- 切换到指定会话继续对话
- 通过 AI 辅助选择正确的会话

## 文档索引

| 文档 | 说明 |
|------|------|
| [prd.md](prd.md) | 产品需求文档，包含 15 个用户故事和实现决策 |
| [implementation-analysis.md](implementation-analysis.md) | 实现分析，包含约束、安全考虑和实现顺序 |
| [test-summary.md](test-summary.md) | 测试总结，包含测试覆盖度和运行方式 |
| [end-to-end-test-plan.md](end-to-end-test-plan.md) | 端到端测试计划（10 个手动测试用例） |
| [issue-*.md](.) | 5 个 issue 文件，详细描述每个实现阶段 |

## 快速开始

### 1. 运行自动化测试

**Windows:**
```bash
.scratch/wechat-session-enhancement/run-all-tests.bat
```

**Linux/Mac:**
```bash
bash .scratch/wechat-session-enhancement/run-all-tests.sh
```

**手动运行:**
```bash
# 工具测试
python -m pytest test/core/unit/llm/test_session_query_tool.py -v

# 命令测试
python -m pytest test/core/integration/llm/agent/test_loop_cmd.py -v

# ChatHistoryManager 测试
python -m pytest test/core/unit/llm/chat_history/test_chat_history_session_id.py -v
```

### 2. 端到端测试

参考 [end-to-end-test-plan.md](end-to-end-test-plan.md)，在真实微信环境中测试所有功能。

## 功能说明

### 1. 数据层增强

**ChatHistoryManager** 添加 `session_id` 支持：
- `add_content(content, session_id=None)` - 保存聊天历史时关联 session_id
- 向后兼容：不传 session_id 时不写入该字段
- 文件格式：`lifeprismData/user/daily_data/chat_history.json`

### 2. 工具层

#### QuerySessionListTool
查询会话列表，支持日期过滤。

**输入参数：**
- `date_filter` (可选): 日期过滤（YYYY-MM-DD 格式）

**返回格式：**
```json
{
  "session-001": {
    "last_summary": "讨论了 Python 异步编程",
    "last_user_message": "能给我举个例子吗？"
  },
  "session-002": {
    "last_summary": "帮助用户调试数据库连接问题",
    "last_user_message": "还是报同样的错误"
  }
}
```

#### QuerySessionHistoryTool
预览指定会话的最近 N 轮对话。

**输入参数：**
- `session_id` (必需): 会话 ID
- `limit` (可选): 返回轮数，默认 10，最大 50

**返回格式：**
```json
[
  {
    "role": "user",
    "content": "能给我举个例子吗？",
    "timestamp": "2026-07-01T10:05:00"
  },
  {
    "role": "assistant",
    "content": "当然可以！...",
    "timestamp": "2026-07-01T10:06:00"
  }
]
```

### 3. 命令增强

#### /continue 命令
```
/continue <session_id>
```

**功能：**
- 切换到指定会话
- 显示最后两轮对话（如果有）
- 如果消息少于两轮，显示现有内容

**输出示例：**
```
[SUCCESS] 继续会话 session-123

最后两轮对话：
user:
能给我举个例子吗？

A:
当然可以！这是一个简单的例子：
...
```

#### /new 命令
```
/new
```

**功能：**
- 创建新会话
- 如果有上一个会话，提示如何恢复

**输出示例：**
```
[SUCCESS] 新建会话 session-456 --- 可以开始新的聊天了！

可以通过使用以下指令恢复上一个会话：
/continue session-123
```

### 4. AI 辅助切换

当用户说"我想切换到之前的会话"时，AI 会：
1. **主动询问**：上次讨论的内容是什么？时间范围是什么？
2. **调用工具**：根据用户回答调用 `query_session_list` 查询
3. **按序号列出**：第1个、第2个、第3个...（不是 session_id）
4. **等待用户选择**：不自动切换
5. **识别选择**：用户说"第2个"或"关于数据库的那个"
6. **生成指令**：返回完整的 `/continue <session_id>` 指令

详见：`templates/agent/chat/tool.md` - "会话切换辅助" 章节

## 测试状态

### ✅ 自动化测试：30/30 通过（100%）

| 测试类型 | 通过/总数 | 覆盖范围 |
|---------|----------|---------|
| 工具测试 | 16/16 ✅ | QuerySessionListTool, QuerySessionHistoryTool |
| 命令测试 | 9/9 ✅ | /continue, /new, 边界情况 |
| 数据层测试 | 5/5 ✅ | ChatHistoryManager session_id 功能 |

### 📋 端到端测试：待执行

参考 [end-to-end-test-plan.md](end-to-end-test-plan.md) 进行真实环境测试。

## 技术细节

### 循环导入问题解决

**问题：** `lifeprism.llm.providers.dataset_providers` 导入 `lifeprism.server.services` 导致循环依赖

**解决方案：**
1. 删除 `lifeprism/llm/providers/dataset_providers/` 目录
2. 使用 `lifeprism.repository.LWBaseDataProvider` 替代
3. 所有测试通过 ✅

详见：[test-summary.md](test-summary.md) - "循环导入问题已解决" 章节

### 文件结构

```
lifeprism/
├── llm/
│   ├── session/
│   │   └── manager.py              # ChatHistoryManager（已修改）
│   ├── agent/
│   │   ├── loop.py                  # /continue 和 /new 命令（已增强）
│   │   └── tools/
│   │       ├── session_query.py     # 新增工具
│   │       └── __init__.py          # 导出工具
│   └── function/
│       └── agent_schedule_job.py    # 定时任务（已修改）
└── templates/
    └── agent/
        └── chat/
            └── tool.md              # AI 提示词（已增强）

test/
├── core/
│   ├── unit/
│   │   └── llm/
│   │       ├── test_session_query_tool.py          # 工具测试
│   │       └── chat_history/
│   │           └── test_chat_history_session_id.py # 数据层测试
│   └── integration/
│       └── llm/
│           └── agent/
│               └── test_loop_cmd.py                 # 命令测试

.scratch/wechat-session-enhancement/
├── README.md                        # 本文件
├── prd.md                           # 产品需求文档
├── implementation-analysis.md       # 实现分析
├── test-summary.md                  # 测试总结
├── end-to-end-test-plan.md         # 端到端测试计划
├── run-all-tests.bat               # 测试脚本 (Windows)
├── run-all-tests.sh                # 测试脚本 (Linux/Mac)
└── issue-*.md                      # Issue 文件
```

## 常见问题

### Q: 如何切换到历史会话？
A: 
1. 直接使用命令：`/continue <session_id>`
2. 或者告诉 AI："我想切换到之前的会话"，AI 会引导你选择

### Q: 如何查看会话列表？
A: 告诉 AI："我想看看之前的会话列表"，AI 会调用工具查询并展示

### Q: session_id 是什么格式？
A: 格式如 `abc123-def456-ghi789`，系统自动生成，存储在 `lifeprismData/session/` 目录下

### Q: 旧的聊天记录怎么办？
A: 系统完全向后兼容，旧记录没有 `session_id` 字段，不影响正常使用

### Q: 如何验证功能是否正常？
A: 
1. 运行自动化测试：`run-all-tests.bat` 或 `run-all-tests.sh`
2. 执行端到端测试：参考 `end-to-end-test-plan.md`

## 下一步

1. ✅ 自动化测试全部通过
2. 📋 执行端到端测试（验证 AI 行为）
3. 📋 根据实际效果调整提示词
4. 📋 收集用户反馈

---

**状态**: 实现完成，自动化测试通过 ✅

**最后更新**: 2026-07-05
