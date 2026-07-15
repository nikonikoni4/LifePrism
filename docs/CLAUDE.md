# Docs 地图导航

## 文档类型快速判定

| 类型 | 路径 | 一句话定义 | 是否必须修复 |
|------|------|-----------|--------------|
| **已知限制** | `docs/known-limitations/` | 当前系统就是这样运作的，是设计选择或现实约束，不是 bug。给 AI/开发者提供"为什么不能动"的上下文 | 不一定，多数接受现状 |
| **技术债** | `docs/technical-debt/` | 代码不够好，未来应该改，当前能跑。有明确代码位置 + 修复方向 | 必须修复，只是时间问题 |
| **待办/调研** | `docs/progress/` | 已识别问题或机会，但方案未定。过程性文档，不提供长期项目上下文 | 待定 |

### 判定决策树

1. 方案是否已确定？否 → `progress`
2. 已确定修复方向后：
   - 动机是"突破现实约束/架构前提" → `known-limitations`
   - 动机是"代码质量/设计错位" → `technical-debt`
3. 同一事实兼具两种属性时，两边都写，但视角不同：
   - `known-limitations` 写事实 + 前提 + 为什么接受（AI 上下文）
   - `technical-debt` 写代码位置 + 修复方案 + 影响范围（开发指引）
   - 互相引用

### 生命周期

- `progress` 中条目方案一旦确定：
  - 修复方向明确 → 拆出 `technical-debt` + `plans/active/` 任务
  - 仅接受现状 → 迁移到 `known-limitations`
  - 原 `progress` 文档归档或删除

详细规则见 `docs/docs-rules/known-limitations-and-debt-rules.md`。
