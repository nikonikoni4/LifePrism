---
module: example
description: 示例模块的 prompts
author: your_name
---

# example_prompt

## metadata

```yaml
active_version: v1
version_history:
  v1:
    created_at: 2026-05-13
    change_reason: 初始版本
```

## v1

### 任务
这是一个示例 prompt，用于演示 prompt 文件的格式。

### 输入说明
1. 输入参数1：说明
2. 输入参数2：说明

### 输出要求
1. 输出格式：说明
2. 输出内容：说明

### 核心原则
1. 原则1
2. 原则2

---

# another_example

## metadata

```yaml
active_version: v2
version_history:
  v2:
    created_at: 2026-05-13
    change_reason: 优化输出格式，增加更详细的说明
  v1:
    created_at: 2026-05-13
    change_reason: 初始版本
```

## v2

### 任务
这是另一个示例 prompt，展示多版本管理。

### 说明
这是 v2 版本，包含了更详细的说明和优化的输出格式。

### 参数注入示例
如果需要参数注入，可以使用 Python 的 format 语法：
- 用户名称：{user_name}
- 日期：{date}

## v1

### 任务
这是另一个示例 prompt。

### 说明
这是 v1 版本，比较简单。
