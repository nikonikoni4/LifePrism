---
version: 1.0
created_at: 2026-08-18
updated_at: 2026-08-18
last_updated: 创建文档初稿
abstract: chat agent 自定义规则（custom_prompt.md）采用 user role 前缀区动态注入而非 system prompt 追加，用角色层级表达"用户规则低于系统规则"，同构 Claude Code 的 CLAUDE.md 注入机制。
status: decided
---

# custom prompt 以 user role 前缀注入

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

chat agent 需要一个类似 CLAUDE.md 的用户自定义规则功能：用户把任意规则写进 `agent/chat/custom_prompt.md`，每次 LLM 调用自动加载。现有机制（`Context._build_bootstrap()` 加载的 soul.md/agent.md/tool.md/user.md）全部以 system role 拼进 system prompt，无法表达"这是用户自定义内容，不应凌驾于系统规则之上"的层级语义。触发决策的真实问题：**新增的用户规则文件应该以什么角色、在什么位置注入 LLM 上下文**。

### 讨论范围

- custom_prompt.md 的注入角色（system vs user）与注入位置（前缀区 vs 会话历史）
- 注入时机（组装期动态注入 vs 首轮持久化）
- 注入格式（包裹方式、说明文本位置）
- 文件生命周期（初始化创建、同步行为）

### 非讨论范围

- 具体代码实现细节（`build_prefix_messages` 的函数签名等，见后续实现）
- agent/chat/ 下其他规则文件的加载机制（已定为"渐进式加载"，由 custom_prompt.md 内维护索引 + agent 按需 read_file，无自动扫描）
- system prompt 内动态内容破坏缓存的问题（`_bulid_recent_state()` 位于 stable 区，与本决策无关，另行记录）

### 模糊信息的明确定义

- `custom prompt`：用户为 AI 撰写的自定义规则文件，位于 `agent/chat/custom_prompt.md`，文件内容纯净（不含任何包裹标签）
- `前缀区`：每次 LLM 调用时由系统组装、不写入会话历史的消息前缀（system prompt + custom prompt 注入），位于 `tools -> system -> messages` 拼接顺序的稳定前缀段

### 问题深度

涉及消息结构约定与提示词层级语义的架构原则问题：角色选择（system/user）同时影响指令优先级、prompt caching 命中率、provider 兼容性三个维度，且一旦上线用户开始写规则，切换注入方式会改变规则的实际效力层级，属于难以逆转的约定。

## 现状

- 现有用户可编辑提示词文件（soul.md/agent.md/tool.md/user.md/identity.md）全部由 `Context._build_bootstrap()` 拼接进 **system role** 的 system prompt
- `_run_agent_loop` 每轮工具调用后用 `session.get_history_message()` 重建 messages，消息只能组装期注入，不能预组装
- auto_compact 只压缩 session 历史（JSONL 持久化部分），不触及组装期前缀
- 项目经 LiteLLM 接入多家 provider，请求形态为"一条 system 在最前 + user/assistant/tool 历史"
- 事实核查结论（2026-08，第一手 + 源码泄露分析交叉验证）：当前 Claude Code 以 **user role** 将 CLAUDE.md 注入 `messages[0]` 区域（system-reminder 块，一次性、不进持久化历史）；拼接顺序 `tools -> system -> messages`，稳定内容靠前是缓存工程共识

## 决策前提

1. 【事实，已验证】当前 Claude Code（2026-08 版本）以 user role 将 CLAUDE.md 内容经 `<system-reminder>` 块注入首条 user 消息区域，不写入持久化会话历史
2. 【用户明确表达的判断】custom prompt 属于用户自定义规则，**不应凌驾于系统规则之上**；以 user role（位于 system 之后）注入在提示词层级上低于 system prompt，虽无法完全规避提示词注入的潜在危害，但能在一定程度上缓解
3. 【事实，多源确认】Anthropic 拼接顺序为 `tools -> system -> messages`，稳定内容前置 + 动态内容后置是 prompt caching 的工程共识；组装期注入的前缀区内容不参与 auto_compact
4. 【假设】所接入的 OpenAI-compatible provider 普遍接受连续两条 user 消息（注入消息后紧跟历史首条 user 消息），无角色交替强制校验

## 可选方案

### 方案 A：system prompt 内追加段落

把 custom_prompt.md 内容拼进现有 `build_system_prompt` 输出（与 soul.md/agent.md 等一致）。

**优势**

- 与现有机制完全一致，无新消息形态
- 无连续 user 消息的 provider 兼容性风险

**劣势**

- 用户规则与系统提示词同级，无法表达"用户规则低于系统规则"的层级语义，提示词注入无缓解
- 与 Claude Code 已验证行为不一致，失去同构参照

### 方案 B：user role 前缀区动态注入（当前选择）

在 `Context` 新增 `build_prefix_messages()`，组装期读取 custom_prompt.md，以 user role 插在 system 之后、会话历史之前，`<system-reminder>` 块内含来源说明 + 管理方式 + 文件原文；不写入 session JSONL。

**优势**

- 角色层级正确：用户规则位于 system 之后，语义上低于系统规则（前提 2）
- 同构 Claude Code 当前实现（前提 1），有业界已验证参照
- 不落会话历史：auto_compact 永远压不掉、用户改文件下一轮生效、旧 session 行为一致
- 位于稳定前缀区，prompt caching 友好

**劣势**

- 依赖 provider 接受连续 user 消息（前提 4，假设）
- 每次 LLM 调用固定消耗 custom prompt 的 token，无上限

### 方案 C：首轮持久化 user 消息

会话首轮把 custom prompt 作为 user 消息写入 session JSONL。

**优势**

- 符合"对话历史"语义，历史中可见

**劣势**

- auto_compact 可能在压缩时丢失规则注入
- 用户中途修改文件后，已存在的会话不生效
- 新旧 session 行为不一致

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 前提 1 + 2 成立，前提 4（provider 兼容连续 user）成立 | 方案 B | 当前选择 |
| 规则完全无法遵守（模型持续无视规则 / 把规则误解为对话内容 / provider 拒绝连续 user 消息） | 方案 A | 备选触发条件（用户明确设定） |

## 最终决策

当前成立的前提：前提 1（Claude Code 实证行为）、前提 2（用户规则层级语义）、前提 3（缓存工程共识）均成立；前提 4 为待运行验证的假设。

因此选择**方案 B：user role 前缀区动态注入**。

前提失效时的切换路径：当出现"规则完全无法遵守"的信号（指令遵循度持续失效、provider 角色序列报错），切换到方案 A（system prompt 追加），代价是放弃层级语义与 Claude Code 同构性。

## 决策原因

1. 层级语义是首要动机：用户自定义内容不应凌驾于系统规则，角色位置（system 之后）是表达该层级的最直接手段，兼作提示词注入的缓解措施（对应前提 2 与问题界定）
2. 对齐业界已验证实现降低风险：Claude Code 的同构设计意味着消息结构经过大规模生产验证，避免了自创约定的未知坑（对应前提 1）
3. 组装期注入同时解决三个工程问题（compact 丢失、热更新、旧 session 一致性），且位于缓存稳定前缀区，工程代价最低（对应前提 3）

## 后续影响

- **实现契约**（已批准待实施）：`templates/agent/chat/custom_prompt.md` 空文件模板（走 resource_initializer 优先级 3 仅复制不覆盖，**禁止**加入 OVERWRITE_FILE_LIST）；`Context.build_prefix_messages()` 返回 `[system] + [可选 custom prompt 注入]`；仅 `MessageType.CHAT` 且内容 strip 后非空才注入；`build_prompt()` 删除；`_run_agent_loop` 签名改为接收 `prefix_messages: list`
- **同步零改动**：`agent/` 目录白名单天然覆盖；空文件被 `is_empty_content` 过滤不进 file_sync_state；写入内容后自动进入 LWW 同步；不加入 `EXCLUDED_FILENAMES`（规则跟人走，跨设备同步）
- **测试迁移**：`test_conflict_resolve_loop.py` 4 处 patch `build_system_prompt`（str 返回值）需改为 patch `build_prefix_messages`（list 返回值）；新增单测覆盖文件缺失/为空/有内容/非 CHAT 四分支
- **待验证事项**：前提 4（连续 user 消息 provider 兼容性）需在实施后跨 provider 实测；若某 provider 报错，缓解手段是在注入消息尾部补一条占位 assistant 消息，而非整体切换方案
- **已知限制**：custom prompt 无 token 上限，文件过大将挤压有效上下文（未来可考虑截断告警）；agent 可自改 custom_prompt.md，规则误写会影响后续所有会话（与 identity.md 同级风险）
