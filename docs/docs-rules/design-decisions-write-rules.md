---
version: 1.1
created_at: 2026-04-13
updated_at: 2026-04-14
last_updated: 迁移 design-decisions 规则到 docs/docs-rules
abstract: design-decisions.md 的写入规则，状态变化规则。
---

# design-decisions.md

## 1. 目的

这份文档只负责 design-decision 正式文档的编写规则。

1. 作用：
   - 规定 design-decisions 文档的输出契约
   - 定义状态机以及状态流转过程
2. 不包括：
   - 编写触发规则

## 2. 输出契约

1. 输出文件名称：YYYY-MM-DD-<内容简要>.md

2. frontmatter：

   ```yaml
   version:
   created_at:
   updated_at:
   last_updated:
   abstract:
   status:
   ```

   - `status`：包含 `stable` 和 `deprecated`

3. 状态机：

   - 创建后默认视为 `status = stable`
   - 当新决定推翻旧决定时，旧文档进入 `deprecated`

4. 输出内容章节

   需要包含：`背景介绍/现状`、`决定`、`涉及范围`、`为什么要做这个决定`

5. 输出模板

   ```md
   ## 版本
   
   | 版本 | 更新内容 |
   | ---- | -------- |
   | 1.0 | 创建 xx 决定 |
   
   ## 背景介绍/现状
   在这里需要明确说明当下遇到的问题是什么
   
   ## 决定
   在这里需要说明做了什么决定
   
   ## 涉及范围
   
   ## 为什么要做这个决定
   ```
