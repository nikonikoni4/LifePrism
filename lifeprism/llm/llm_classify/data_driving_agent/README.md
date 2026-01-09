# Data Driving Agent V2

数据驱动的 LLM Agent 执行器，支持多线程上下文隔离和灵活的节点调度。

---

## 执行顺序
按照节点id顺序执行，必须一个线程完成之后才能继续下一个线程

## 新线程的上下文初始化

### 触发时机

新线程的上下文初始化（`data_in`）**只在创建新线程时执行一次**。

```python
# 主执行循环
for node in self.plan.nodes:
    if node.thread_id not in self.context["messages"]:  # ← 只有线程不存在时
        self._create_thread(node.thread_id, node)  # ← 才创建线程并注入 data_in
```

### `_create_thread` 方法行为

```python
def _create_thread(self, thread_id, node):
    if thread_id in self.context["messages"]:
        return  # ← 线程已存在，直接返回，不执行 data_in 逻辑
    
    # 创建新线程并处理 data_in
    source_thread = node.data_in_thread or self.main_thread_id # 默认为 main
    if node.data_in_slice:
        injected = source_msgs[start:end]
    else:
        injected = [source_msgs[-1]]  # 默认取最后一条
```

### 示例场景

线程 `q1` 有 3 个节点 n1, n2, n3：

| 节点 | 线程状态 | data_in 配置 | 实际效果 |
|------|----------|-------------|---------|
| n1 | 线程不存在 → 创建 | `data_in_slice=[0,2]` | ✅ 生效，注入消息 |
| n2 | 线程已存在 | `data_in_slice=[-1,None]` | ❌ 被忽略 |
| n3 | 线程已存在 | `data_in_thread="other"` | ❌ 被忽略 |

### 重要特性

1. **只有第一个节点的 data_in 生效**：同一线程上只有触发线程创建的节点（通常是第一个节点）的 `data_in` 配置会生效
2. **后续节点的 data_in 被忽略**：线程已存在时，`_create_thread` 直接返回，不会执行任何数据注入
3. **data_in 配置项**：
   - `data_in_thread`: 指定数据来源线程（默认为 `main`）
   - `data_in_slice`: 指定消息切片范围 `[start, end)`（默认取最后一条）

## 线程数据合并

### 核心机制

执行器支持多线程消息隔离，子线程可以通过 `data_out` 标志将结果合并到父线程。

**关键方法：**

| 方法 | 作用 |
|------|------|
| `_set_data_out(thread_id, ...)` | 设置线程的输出数据（覆盖式） |
| `_merge_data_out(thread_id, target_thread_id)` | 将 data_out 合并到目标线程的 messages |

### 执行流程

每个节点执行时：

```python
content = handler(node)           # 执行节点处理器

if node.data_out:                 # 只有 data_out=True 才执行
    # 目标线程由 data_out_thread 决定，默认为 main
    target_thread = node.data_out_thread or self.main_thread_id
    self._merge_data_out(node.thread_id, target_thread)
```

节点处理器内部（如 `_execute_llm_first_node`）：

```python
if node.data_out:                 # 只有 data_out=True 才执行
    self._set_data_out(thread_id, node_type, description, content)
```

### 示例场景

假设子线程 `q1` 有 3 个节点：

| 节点 | data_out | _set_data_out | _merge_data_out_to_parent | data_out["q1"] | 父线程新增消息 |
|------|----------|---------------|---------------------------|----------------|---------------|
| n1 | ✅ True | ✅ → "结果1" | ✅ 执行 | "结果1" | +"结果1" |
| n2 | ❌ False | ❌ 不执行 | ❌ 不执行 | "结果1"（不变） | 无 |
| n3 | ✅ True | ✅ → "结果3" | ✅ 执行 | "结果3"（覆盖） | +"结果3" |

**最终状态：**

```python
# data_out 字典只保留最后一个值
self.context["data_out"]["q1"] = {"content": "结果3"}

# 父线程 messages 包含所有 data_out=True 节点的输出
parent_messages = [
    ...,
    AIMessage(content="结果1"),  # n1 合并的
    AIMessage(content="结果3"),  # n3 合并的
]
```

### 重要特性

1. **不会重复合并**：每个 `data_out=True` 的节点恰好执行一次 set + merge
2. **中间节点不影响输出**：`data_out=False` 的节点不会触发任何合并操作
3. **灵活的外发目标**：每个节点通过 `data_out_thread` 独立决定其外发目标。若未指定，则默认外发到 `main` 线程。同一线程的不同节点甚至可以外发到不同的目标线程。

### 数据流示意

```
主线程 (main)
    │
    ├── 子线程 q1
    │   ├── n1 (data_out=True)  ──→ 合并到 main
    │   ├── n2 (data_out=False)     (不合并)
    │   └── n3 (data_out=True)  ──→ 合并到 main
    │
    └── 子线程 q2
        └── n4 (data_out=True)  ──→ 可以合并到 main 或其他线程
```

> **注意**：`data_out` 字典只保留每个线程的最后一个输出值，但父线程的 messages 会保留所有合并的消息。
