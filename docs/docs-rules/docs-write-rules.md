---
version: 1.5
created_at: 2026-04-09
updated_at: 2026-04-14
last_updated: 迁移文档规则到 docs/docs-rules 与 docs/coding-rules 双目录
abstract: docs 总写作规则，先定义文档类型，再按类型约束正式文档、导航文档、规则文档和临时文档。
---

# Docs-write-rules

## 1. 文档定义

<rules>

### 1. 临时文档

- 路径：`docs/temp/**/*.md`

### 2. 导航文档

- 路径：`docs/**/index.md`

### 3. 规则文档

- 路径：
  - `docs/docs-rules/*.md`
  - `docs/coding-rules/*.md`
- 排除：
  - `docs/docs-rules/index.md`
  - `docs/coding-rules/index.md`

### 4. 正文文档

- 路径：`docs/**/*.md`
- 排除：
  - `docs/temp/**/*.md`
  - `docs/**/index.md`
  - `docs/docs-rules/*.md`
  - `docs/coding-rules/*.md`

## 2. 正式文档通用规则

1. 每个正式 `md` 文档都必须包含 frontmatter：

   ```yaml
   version:
   created_at:
   updated_at:
   last_updated:
   abstract:
   ```

2. 字段含义：
   - `version` 使用 `A.B` 格式；重大调整时 `A + 1`，其余更新时 `B + 1`
   - `last_updated` 记录最近一次修改的主要内容
   - `abstract` 是该文档的摘要，用于让 LLM 快速了解主要内容

3. 通用正式文档命名规范

   - 采用日期+内容简要的方式：YYYY-MM-DD-<内容简要>.md。
   - 若具体文档规定了特殊的命名规范，应该遵守专业的命名规范。

## 3. 各类型文档规则

### 1. 导航文档

1. 当你在 `docs/` 的某个子目录新增或删除正式文档时，需要同步维护该目录的 `index.md`。
2. 导航文档必须位于 `docs/**/index.md`，不可在其他目录新增导航文档，这样会增加目录复杂度。
3. 导航文档每个文件索引都需要包含：`updated_at`、`path`、触发规则和内容摘要。
4. 导航文档模板

   ```md
   ## docs-write-rule
   - updated_at : 2026-04-07
   - path: `docs/docs-rules/docs-write-rules.md`
   - 触发规则：写入任何 `docs/` 正式文档前都需要阅读
   - 内容摘要：docs文件夹内正式文档编辑的规则
   ```
5. 空目录内容：当index.md为空时编写：

```md
<index-write-guide>
导航文档每一项模板：
## xxxx
 - updated_at : YYYY-MM-DD
 - path: 
 - 触发规则：
 - 内容摘要：

当写入第一条数据之后删除该内容（index-write-guide）
</index-write-guide>
```



### 2. 正文文档

1. 每个正文文档正文开头都需要有 `## 版本` 章节，例如：

   ```md
   ## 版本
   
   | 版本 | 更新内容 |
   | ---- | -------- |
   | 1.0 | 创建文档初稿 |
   ```

### 3. 临时文档

1. 临时文件、草稿或暂时无法归类的内容放在 `docs/temp`。

## 4. 按需加载规则

1. 写正式 `spec` 前，读取 `docs/docs-rules/spec-write-rules.md`
2. 写正式 `plan` 前，读取 `docs/docs-rules/plan-write-rules.md`
3. 写正式 `flow` 前，读取 `docs/docs-rules/flow-write-guide.md`
4. 修改或编写 `docs/ARCHITECTURE.md` 时，读取 `docs/docs-rules/architecture-write-rules.md`

</rules>

<never_do>

1. 不要把 `brainstorming` 直接产出的设计稿原样放入正式文档目录 `docs/specs` 内。
2. 不要在未经用户授权时直接在 `docs` 目录下新增孤儿文档。
3. 不要在 `docs/docs-rules/**.md`、`docs/coding-rules/**.md` 和 `docs/**/index.md` 的文档添加上版本章节。

</never_do>
