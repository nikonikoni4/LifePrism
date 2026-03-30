# Agent 目录说明

本目录存放所有 Agent 的配置文件与记忆文件。当前有两个 Agent：chat 和 classify，均为工具型 Agent（被动响应，不自主运行）。

---

## 目录结构总览

```
agent/
├── chat/                      # Chat Agent
│   ├── bootstrap.md           # 系统级启动说明
│   ├── agent.md               # System Prompt（角色定义）
│   ├── memory.md              # 长期蒸馏记忆
│   └── session_log/           # 跨会话短期记忆
│       └── YYYY-MM-DD.md
├── classify/                  # Classify Agent（纯自动流程）
│   ├── agent.md               # System Prompt（角色定义）
│   └── classify_preference.md # 分类偏好配置
└── skills/                    # 共享技能
```

---

## 文档设计原则

同 user/ 目录，遵循三条原则：单一职责、明确写入与读取时机、渐进式披露（frontmatter 摘要优先）。

### Frontmatter 规范

```yaml
---
name: 文档名称
summary: 一句话描述当前文档核心内容
read_priority: high | on_demand
last_updated: YYYY-MM-DD
last_event: 触发本次更新的事件简述
---
```

---

## Chat Agent `chat/`

Chat Agent 负责与用户直接对话，提供系统解释、行为查询、日常陪伴等功能。

**启动加载顺序：**
```
1. agent.md                          → 确认角色与行为准则
2. user/user.md                      → 了解用户基本轮廓
3. memory.md                         → 加载长期稳定语义记忆
4. session_log/今天.md + 昨天.md     → 仅在需要连续性时按需加载近期对话上下文
```

### chat/bootstrap.md
- **存放内容**：Chat Agent 初始化时的启动流程和基本约束
- **单一职责**：定义 Chat Agent 每次会话的加载顺序和初始化规则
- **写入权限**：仅人工维护，Agent 不写入
- **读取时机**：每次 Chat Agent 会话初始化时首先读取

### chat/agent.md
- **存放内容**：Chat Agent 的 System Prompt，定义角色、能力边界、行为准则
- **单一职责**：告诉 Agent 它是谁、能做什么、不能做什么
- **写入权限**：仅人工维护，Agent 不写入
- **读取时机**：每次会话初始化时首先读取

### chat/memory.md
- **存放内容**：从 session_log 和 user/behavior.md 蒸馏而来的长期稳定语义，包括长期偏好、稳定行为模式、持续目标、重要关系状态与经反复验证的洞察
- **单一职责**：为 Chat Agent 提供可常驻的长期用户语义上下文，让 Agent 在不同会话中保持稳定认知，而不依赖具体历史对话
- **写入权限**：Agent 定期维护
- **写入时机**：定期从 session_log + behavior.md 中提炼，删除过时内容，保持精简
- **读取时机**：每次 Chat Agent 会话初始化时读取，作为默认长期上下文层
- **关键规则**：
  1. 只保留跨时间稳定、脱离原会话后仍然成立的高层语义
  2. 内容必须高度浓缩，不随每次对话线性增长
  3. 事件只有在已经沉淀为长期结论时才可写入，不保留事件叙述本身
- **禁止写入**：短期有用但长期无关紧要的内容（归入 session_log）、原始对话记录、一次性聊天结论、短期任务进展、未经验证的推断

### chat/session_log/YYYY-MM-DD.md
- **存放内容**：每次会话结束后的全面摘要，包括对话主题、推进的任务、知识性问答要点、需要在下次会话延续的上下文
- **单一职责**：为 Chat Agent 提供跨会话的短期上下文，让下一个会话窗口无需重新建立背景
- **写入权限**：Agent 在会话结束时写入
- **写入时机**：每次会话结束时写入当天日期文件
- **读取时机**：
  1. 用户明确提及上次/之前的对话、计划、承诺时
  2. 当前对话明显在延续尚未完成的话题或任务时
  3. 当前消息出现需要近期连续性才能解释的指代时
- **生命周期**：短期保留（建议 7 天），定期由 memory.md 蒸馏后清理
- **与 memory.md 的区别**：session_log 是按需调用的短期情景记录（含知识性问答等），memory.md 是默认常驻的长期稳定语义记忆
- **与 behavior.md 的区别**：session_log 记录对话全貌（agent 视角），behavior.md 只提炼有行为语义价值的内容（用户行为视角）

---

## Classify Agent `classify/`

Classify Agent 负责对电脑使用数据进行分类，是纯工具型 Agent，不需要用户上下文。

**启动加载顺序：**
```
1. agent.md               → 确认角色与分类规则
2. classify_preference.md → 加载用户自定义分类偏好
```

### classify/agent.md
- **存放内容**：Classify Agent 的 System Prompt，定义分类规则、类别体系、处理逻辑
- **单一职责**：告诉 Agent 如何对电脑使用数据进行分类
- **写入权限**：仅人工维护，Agent 不写入
- **读取时机**：每次分类任务开始时首先读取

### classify/classify_preference.md
- **存放内容**：用户对数据分类方式的个性化偏好，例如将某类应用归入「学习」而非「娱乐」的自定义规则
- **单一职责**：覆盖默认分类规则，实现用户个性化分类
- **写入权限**：用户在前端确认「纳入偏好设置」后写入，Agent 不主动推断写入
- **写入时机**：用户在前端修改数据分类并确认时
- **读取时机**：每次分类任务开始时，在 agent.md 之后读取，作为规则覆盖层
- **禁止写入**：行为数据本身、对分类习惯的心理分析

---

## skills/
- **存放内容**：Chat Agent 和 Classify Agent 共享的可复用技能模块
- **单一职责**：封装可复用的能力，避免在多个 agent.md 中重复定义
- **写入权限**：仅人工维护
