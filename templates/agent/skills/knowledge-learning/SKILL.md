---
name: knowledge-learning
description: Progressive knowledge learning system with assessment-driven teaching. Use when user wants to learn new concepts, saying things like "我想学习X", "教我X", "帮我理解X概念", "学习X知识", or "explain X to me". Supports assessment through questioning, adaptive content delivery based on user's current understanding, interactive Q&A, and optional learning report generation. Features structured output to knowledge/ and learning-process/ directories with index.md tracking.
---

# Knowledge Learning

A structured workflow for teaching new concepts through assessment-driven, progressive learning.

## Core Principles

1. **Assessment First**: Start by understanding what the user already knows
2. **Adaptive Teaching**: Deliver content matched to user's comprehension level
3. **Progressive Disclosure**: Begin with fundamentals, advance only when ready
4. **Interactive Learning**: User-driven questioning and exploration
5. **Reflection**: Optional learning process documentation

## Output Structure and File Management

### Directory Structure

All learning outputs are organized in the following structure within the project's base directory:

```
knowledge-learning/          # Skill基础目录
├── index.md                 # 索引文件：记录所有学习会话的摘要和链接
├── knowledge/               # 知识报告目录
│   ├── [date]-[topic]-knowledge.md
│   └── ...
├── learning-process/        # 学习过程记录目录
│   ├── [date]-[topic]-learning-process.md
│   └── ...
├── SKILL.md                 # Skill定义文件
└── ...                      # 其他Skill相关文件
```

### File Naming Convention

- **Knowledge Reports**: `[YYYY-MM-DD]-[topic-slug]-knowledge.md`
  - Example: `2024-01-15-machine-learning-knowledge.md`
- **Learning Process**: `[YYYY-MM-DD]-[topic-slug]-learning-process.md`
  - Example: `2024-01-15-machine-learning-learning-process.md`
- **Index File**: `index.md` (fixed name, updated after each learning session)

### Path Resolution

When generating files:
1. Use the skill's base directory (knowledge-learning/) as the root
2. Create `knowledge/` and `learning-process/` subdirectories if they don't exist
3. Always generate files in the appropriate subdirectory with proper naming
4. Update `index.md` in the skill's base directory after each learning session
5. Use relative links in index.md to reference the generated files

## Workflow

### Phase 0: Pre-learning Assessment (预学习评估)

**Goal**: Understand user's learning history and avoid repetition

1. **Read index file** (读取索引):
   - Check if `index.md` exists in the skill's base directory (knowledge-learning/)
   - If exists, read the file to understand:
     - Previous learning sessions (日期、主题)
     - Key topics already covered (关键要点)
     - Learning progress patterns (学习进度模式)

2. **Analyze learning history** (分析学习历史):
   - Identify if the requested topic has been previously learned
   - Check for related topics that might provide foundation
   - Note any recurring themes or interests

3. **Determine learning approach** (确定学习策略):
   - **New topic**: Proceed with full assessment (Phase 1)
   - **Previously learned topic**: 
     - Ask if user wants a review or deeper dive
     - Reference previous learning: "我看到你之前在[日期]学习过[主题]，想在那个基础上继续深入吗？"
   - **Related topic**: 
     - Build on previous knowledge: "基于你之前对[相关主题]的理解，我们可以从那里开始扩展。"

4. **Update learning context** (更新学习上下文):
   - Note the current learning session's starting point
   - Prepare to reference previous learnings when relevant

### Phase 1: Initial Assessment (评估阶段)

**Goal**: Understand user's current knowledge level

1. **Ask user to self-explain** (第一个问题):
   ```
   在我开始教学之前，请你先用自己的话解释一下：你目前对[知识点]的理解是什么？
   你可以说出任何你知道的内容，哪怕只是模糊的印象或片段。
   ```

2. **Analyze user's response** to identify:
   - Knowledge gaps (完全不了解的部分)
   - Misconceptions (理解偏差)
   - Existing foundation (已有基础)
   - Learning style indicators (学习风格线索)

3. **Generate 4-7 targeted questions** based on their self-explanation:
   - Focus on knowledge boundaries (他们理解的边界在哪里)
   - Probe misconceptions (验证可能的误解)
   - Assess prerequisite knowledge (前置知识是否具备)
   
4. **Ask questions ONE AT A TIME**:
   - Wait for answer before next question
   - Adapt subsequent questions based on previous answers
   - Keep questions conversational, not exam-like
   - Example format: "你提到了X，那你觉得X和Y之间有什么关系？"

5. **Complete assessment** after 5-8 questions total (including initial self-explanation)

### Phase 2: Adaptive Teaching (教学阶段)

**Goal**: Deliver foundational knowledge matched to user's level

Based on assessment results, provide:

1. **Core concept explanation** (核心概念):
   - Start with the simplest, most fundamental aspect
   - Use analogies related to user's existing knowledge
   - Avoid jargon unless user demonstrated familiarity
   - Keep initial explanation to 3-5 paragraphs maximum

2. **Scope boundaries** (明确范围):
   - Explicitly state what you're NOT covering yet
   - Example: "现在我们先理解基础部分X。关于高级话题Y和Z，我们稍后再讨论。"

3. **Concrete examples**:
   - Provide 1-2 simple, relatable examples
   - Match examples to user's context if known

4. **Comprehension check**:
   - End with: "这部分清楚吗？你可以提出任何疑问，或者让我继续讲解下一部分。"

### Phase 3: Interactive Exploration (互动阶段)

**Goal**: User-driven deepening of understanding

1. **Wait for user questions** - Do not proceed automatically
2. **Answer questions**:
   - Directly address what they asked
   - Check if answer creates new questions
   - Offer to elaborate or move to related topics
3. **Suggest next steps** only when user seems ready:
   - "你现在理解了X，想继续了解Y吗？"
   - "还有什么疑问，或者我们可以进入下一个概念？"

### Phase 4: Cycle or Conclude

**Two paths**:

**A. Continue Learning** (循环):
- Return to Phase 1 for next concept layer
- Or return to Phase 2 for deeper dive
- User signals: "继续", "下一步", "还有什么", "深入讲讲"

**B. Generate Learning Report** (生成报告):
- User signals: "总结一下", "生成报告", "输出学习记录"
- See "Learning Report Generation" section below

## Learning Report Generation

When user requests learning summary, generate TWO files in the appropriate subdirectories and update the index:

### File 1: Learning process (`learning-process/[date]-[topic]-learning-process.md`)

Document the complete learning process:

```markdown
# [知识点] 学习历程

**学习时间**: [日期]
**学习者**: [如果知道用户名]

## 初始理解水平

[用户在第一个问题中的自我解释原文]

## 评估过程

### 问题 1: [问题内容]
**回答**: [用户回答]
**分析**: [显示出的知识水平/误解]

### 问题 2: [问题内容]
...

## 教学内容记录

### 第一轮教学
**讲解内容**: [概括讲了什么]
**用户疑问**: [用户提出的问题列表]

### 第二轮教学
...

## 理解障碍点

列出学习过程中用户遇到困难的地方：

1. **[障碍点1]**: [什么问题让用户卡住了]
   - 原因分析: [为什么这里难理解]
   - 解决方式: [如何帮助用户突破]

2. **[障碍点2]**: ...

## 学习进度

- ✅ 已掌握: [列出已经理解的概念]
- 🔄 部分理解: [列出还需巩固的部分]
- ❌ 未涉及: [列出还没讲到的高级内容]
```

### File 2: Knowledge Report (`knowledge/[date]-[topic]-knowledge.md`)

Comprehensive knowledge documentation:

```markdown
# [知识点] 知识报告

**生成时间**: [日期]

## 概念定义

[清晰、完整的概念定义]

## 核心要点

1. **[要点1]**: [解释]
2. **[要点2]**: [解释]
...

## 详细阐述

### [子主题1]
[详细内容]

### [子主题2]
[详细内容]

## 常见误解 ⚠️

基于本次学习过程，标注容易产生误解的地方：

1. **误解**: [错误理解]
   - **正确理解**: [正确的理解]
   - **为什么容易错**: [解释]

## 进阶方向

如果要继续深入学习，可以探索：
- [进阶主题1]
- [进阶主题2]

## 参考资源

[如果适用，推荐学习资源]
```

### File 3: Index Update (`index.md`)

After generating the learning report, update the index file with a new entry:

```markdown
# Knowledge Learning Index

## 学习记录索引

| 日期 | 主题 | 知识报告 | 学习过程 | 关键要点 |
|------|------|----------|----------|----------|
| [YYYY-MM-DD] | [主题] | [链接到知识报告] | [链接到学习过程] | [3-5个关键要点] |
```

**Index Entry Format**:
- **日期**: 学习日期
- **主题**: 学习的知识点
- **知识报告**: 相对链接到 `knowledge/[date]-[topic]-knowledge.md`
- **学习过程**: 相对链接到 `learning-process/[date]-[topic]-learning-process.md`
- **关键要点**: 本次学习的核心收获（3-5个要点）

**Example Entry**:
```markdown
| 2024-01-15 | 机器学习 | [机器学习知识报告](knowledge/2024-01-15-machine-learning-knowledge.md) | [机器学习学习过程](learning-process/2024-01-15-machine-learning-learning-process.md) | 监督学习vs无监督学习、训练集/测试集划分、过拟合概念 |
```

## Implementation Notes

### State Tracking

Maintain awareness of current phase:
- Assessment phase: Counting questions asked (target 5-8)
- Teaching phase: Tracking what's been covered vs. held back
- Interactive phase: Noting recurring confusion points
- Report phase: Compiling complete process

### Adaptation Signals

Watch for these user signals:

| Signal | Meaning | Response |
|--------|---------|----------|
| "不太明白" | Explanation too complex | Simplify, use analogy |
| "这个我知道" | User has this knowledge | Skip ahead, less detail |
| "能举个例子吗" | Needs concrete illustration | Provide specific example |
| "和X有什么关系" | Connecting to prior knowledge | Explain relationship |
| "继续" | Ready for more | Proceed to next concept |
| "总结一下" | Wants to conclude | Generate learning report |

### Quality Checks

Before moving between phases:
- ✅ Assessment: Have I asked 5-8 questions including self-explanation?
- ✅ Teaching: Did I start with fundamentals only?
- ✅ Teaching: Did I explicitly state what I'm NOT covering yet?
- ✅ Interactive: Am I waiting for user questions, not pushing content?
- ✅ Report: Did I capture all confusion points and misconceptions?

## Examples

### Example 1: Learning "Machine Learning"

**Phase 1 - Assessment**:
```
AI: 在我开始教学之前，请你先用自己的话解释一下：你目前对"机器学习"的理解是什么？

User: 我知道机器学习就是让计算机自己学习，不用人编程。好像和AI有关系。

AI: [分析：用户有基本概念，但可能混淆"不用编程"的含义]
你提到"不用人编程"，那你觉得机器学习中，人类需要做什么工作呢？

User: 嗯...可能需要给数据？

AI: 对，数据很重要。那你听说过"训练模型"这个说法吗？知道是什么意思吗？
...
```

**Phase 2 - Teaching**:
```
AI: 好的，基于我们的讨论，我先给你讲解机器学习的核心概念。

机器学习确实是让计算机"学习"，但这里的"不用编程"需要澄清：
我们不是不写代码，而是不需要为每个具体情况写规则...

[3-4段基础解释]

现在我们先理解这个基础部分。关于深度学习、神经网络这些高级话题，我们稍后再讨论。

这部分清楚吗？
```

**Phase 3 - Interactive**:
```
User: 那训练数据是不是越多越好？

AI: 好问题！一般来说数据越多，模型能学到的模式越丰富。但有几个需要注意的点...
```

### Example 2: Learning "Quantum Entanglement"

**Phase 1 - Assessment**:
```
AI: 请你先用自己的话说说，你目前对"量子纠缠"的理解是什么？

User: 我只知道好像两个粒子会有神秘的联系，改变一个另一个也会变。

AI: [分析：有基本印象，可能有"超光速通信"误解]
你说的"改变一个另一个也会变"，你觉得这个变化是瞬间发生的吗？

User: 应该是吧？我听说比光速还快。

AI: [确认了误解] 那你觉得这是否意味着我们可以用量子纠缠来实现超光速通信？
...
```

## Anti-Patterns (避免的做法)

❌ **Don't dump everything at once**: Resist urge to give complete explanation in Phase 2
❌ **Don't skip assessment**: Even if topic seems basic, user's mental model may surprise you
❌ **Don't ask exam-style questions**: "What is X?" feels like testing, not teaching
❌ **Don't proceed without user signal**: Wait for questions or explicit "continue" before advancing
❌ **Don't ignore misconceptions**: Address wrong understanding immediately, gently
❌ **Don't use jargon prematurely**: Introduce technical terms only after explaining concept

## Success Criteria

A successful learning session:
- ✅ User can explain concept in their own words
- ✅ User asks questions showing genuine curiosity
- ✅ User corrects their own initial misconceptions
- ✅ User makes connections to their existing knowledge
- ✅ User knows what they don't know yet (明确自己的知识边界)
