---
module: test
description: 测试嵌套代码块解析
author: test
---

# test_prompt

## metadata

```yaml
active_version: v1
version_history:
  v1:
    created_at: 2026-05-18
    change_reason: 测试嵌套代码块
```

## v1

```md
### task
这是一个测试 prompt，用于验证嵌套代码块的解析。

### 数据说明
1. 文本结构：
```md
## YYYY-MM-DD
### subtitle
```
2. 这是内部代码块后面的内容

### 更多规则
1. 另一个结构：
```md
# document.md
## section
```
2. 这是第二个内部代码块后面的内容

### 结束
这是最后的内容，应该被完整提取。
```

---

# simple_prompt

## metadata

```yaml
active_version: v1
version_history:
  v1:
    created_at: 2026-05-18
    change_reason: 简单测试
```

## v1

```md
### task
这是一个简单的 prompt，没有嵌套代码块。

### 规则
1. 规则一
2. 规则二
```
