# 说明
在这个文档中编写待修复的bug或记录重要的bug，以## 1（序号）开始编写，包含bug描述，以及bug修复状态

## 1. LLM 分类结果中 link_to_goal 缺少验证

**状态**: 待修复

**发现日期**: 2026-02-01

**问题描述**:

在 `lifeprism/server/services/data_processing_service.py` 中，LLM 分类结果的 `category` 和 `sub_category` 有完整的验证逻辑（`_validate_classification_results` 方法，第 464-532 行），但 `link_to_goal` 字段没有任何验证。

**问题代码位置**: 第 409-414 行、第 434-439 行

```python
# 当前代码：只是简单地 get，没有验证
goal_id = goal_name_to_id.get(item.link_to_goal) if item.link_to_goal else None
if item.link_to_goal:
    logger.debug(f"  [DEBUG] 单用途 '{app}': link_to_goal='{item.link_to_goal}' -> goal_id='{goal_id}'")
```

**问题影响**:

1. 如果 LLM 返回了一个不存在的 goal name（拼写错误、幻觉等），`get()` 会静默返回 `None`
2. 用户不会收到任何警告，不知道 goal 关联失败了
3. 数据会以 `link_to_goal_id = None` 存入数据库，丢失了 LLM 原本想要关联的意图

**对比 category 的验证逻辑**:

```python
# category 有完整验证（第 498-504 行）
if cat not in category_tree:
    logger.warning(f"    ⚠ 索引 {idx}: 主分类'{cat}'不在分类树中，修正为None")
    df.at[idx, 'category'] = None
    invalid_count += 1
```

**建议修复方案**:

在 `_validate_classification_results` 方法中增加对 `link_to_goal` 的验证，或在转换时添加警告日志：

```python
# 方案1：在转换时添加警告
goal_id = goal_name_to_id.get(item.link_to_goal) if item.link_to_goal else None
if item.link_to_goal and goal_id is None:
    logger.warning(f"    ⚠ '{app}': LLM 返回的 link_to_goal='{item.link_to_goal}' 不存在于系统中，已忽略")

# 方案2：在 _validate_classification_results 中统一验证
# 需要传入 goal_name_to_id 映射，检查 link_to_goal 是否有效
```

**相关文件**:
- `lifeprism/server/services/data_processing_service.py`
