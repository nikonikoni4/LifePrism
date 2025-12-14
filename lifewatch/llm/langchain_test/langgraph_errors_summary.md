# LangGraph 开发错误总结

> 文档创建时间：2025-12-09  
> 项目：LifeWatch-AI  
> 文件：`langgrap_test.py`

---

## 📋 目录

1. [错误一：StructuredTool 对象不可调用](#错误一structuredtool-对象不可调用)
2. [错误二：图节点返回值错误](#错误二图节点返回值错误)
3. [错误三：对 LLM 工具调用的误解](#错误三对-llm-工具调用的误解)
4. [最佳实践总结](#最佳实践总结)

---

## 错误一：StructuredTool 对象不可调用

### ❌ 错误信息

```
TypeError: 'StructuredTool' object is not callable
```

### 🔍 错误原因

使用 `@tool` 装饰器装饰的函数会被转换为 `StructuredTool` 对象，**不能像普通函数那样直接调用**。

### 💻 错误代码

```python
from langchain_core.tools import tool

@tool
def get_activity_data():
    """获取活动数据"""
    return [...]

def get_data(state):
    # ❌ 错误：试图直接调用 StructuredTool 对象
    state['result'] = str(get_activity_data())
    return state
```

### ✅ 解决方案

#### 方案 1：改为普通函数（不需要 LLM 调用工具时）

```python
# ✅ 移除 @tool 装饰器
def get_activity_data():
    """获取活动数据"""
    return [...]

def get_data(state):
    # ✅ 可以直接调用
    state['result'] = str(get_activity_data())
    return state
```

#### 方案 2：使用 .invoke() 方法（需要保留为工具时）

```python
@tool
def get_activity_data():
    """获取活动数据"""
    return [...]

def get_data(state):
    # ✅ 使用 .invoke() 方法调用
    state['result'] = str(get_activity_data.invoke({}))
    return state
```

#### 方案 3：分离实现和工具定义（推荐）

```python
# 普通函数：包含实际逻辑
def _get_activity_data_impl():
    """获取活动数据的实现"""
    return [...]

# 工具定义：供 LLM 调用
@tool
def get_activity_data():
    """获取活动数据"""
    return _get_activity_data_impl()

# 在代码中调用普通函数
def get_data(state):
    state['result'] = str(_get_activity_data_impl())
    return state
```

### 📝 关键要点

- `@tool` 装饰器会将函数转换为 `StructuredTool` 对象
- `StructuredTool` 对象必须通过 `.invoke(args)` 方法调用
- 如果不需要 LLM 调用工具，直接使用普通函数即可

---

## 错误二：图节点返回值错误

### ❌ 错误信息

```
langgraph.errors.InvalidUpdateError: Expected dict, got __end__
For troubleshooting, visit: https://docs.langchain.com/oss/python/langgraph/errors/INVALID_GRAPH_NODE_RETURN_VALUE
During task with name 'should_continue' and id 'xxx'
```

### 🔍 错误原因

1. **节点函数返回了 `END`**：LangGraph 的节点函数必须返回 state（字典），不能返回 `END`
2. **将路由函数作为节点添加**：`router` 函数应该只作为条件边的路由函数，不应该作为节点

### 💻 错误代码

```python
def should_continue(state):
    """决定是否继续"""
    # ❌ 错误：节点不能返回 END
    return END

if __name__ == "__main__":
    graph = StateGraph(myMessagesState)
    
    # ❌ 错误：router 不应该作为节点添加
    graph.add_node("router", router)
    graph.add_node("should_continue", should_continue)
    
    # router 既是节点又是条件边函数，导致混乱
    graph.add_conditional_edges(START, router, path_map)
    graph.add_edge("activity_node", "should_continue")
```

### ✅ 解决方案

```python
if __name__ == "__main__":
    graph = StateGraph(myMessagesState)
    
    # ✅ 只添加实际的处理节点
    graph.add_node("activity_node", activity_node)
    graph.add_node("get_data", get_data)
    
    # ✅ router 只作为条件边的路由函数，不作为节点
    path_map = {
        "activity": "get_data",
        "analyze": "activity_node"
    }
    graph.add_conditional_edges(START, router, path_map)
    
    # ✅ 节点直接连接到 END，不需要中间节点
    graph.add_edge("activity_node", END)
    graph.add_edge("get_data", END)
```

### 📝 关键要点

- **节点函数必须返回 state**（字典类型）
- **路由函数返回字符串**（用于选择下一个节点）
- **不要把路由函数作为节点添加**
- **END 只能在 `add_edge()` 中使用**，不能作为函数返回值

---

## 错误三：对 LLM 工具调用的误解

### 🤔 误解内容

认为在创建模型时需要在参数中添加 `function_call` 列表，才能让 LLM 调用工具。

### ✅ 正确理解

#### LLM 工具调用的完整流程

```python
# 步骤 1: 定义工具
@tool
def get_activity_data():
    """获取活动数据"""
    return [...]

# 步骤 2: 创建模型（不需要指定工具）
chat_model = create_ChatTongyiModel()

# 步骤 3: 需要时动态绑定工具
llm_with_tools = chat_model.bind_tools([get_activity_data])

# 步骤 4: LLM 决定是否调用工具
response = llm_with_tools.invoke([
    {"role": "system", "content": "你是助手，可以获取活动数据"},
    {"role": "user", "content": "帮我分析一下我今天都干了什么"}
])

# 步骤 5: 检查是否有工具调用
if response.tool_calls:
    for tool_call in response.tool_calls:
        # 执行工具
        result = get_activity_data.invoke(tool_call['args'])
        
        # 将结果返回给 LLM
        messages.append({
            "role": "tool",
            "content": str(result),
            "tool_call_id": tool_call['id']
        })
    
    # LLM 基于工具结果生成最终答案
    final_response = llm_with_tools.invoke(messages)
```

#### 使用 LangGraph 的 ReAct Agent（推荐）

```python
from langgraph.prebuilt import create_react_agent

# 自动处理工具调用的 agent
agent = create_react_agent(
    model=chat_model,
    tools=[get_activity_data]
)

# 一行代码完成所有工具调用逻辑
result = agent.invoke({
    "messages": [{"role": "user", "content": "帮我分析活动数据"}]
})
```

### 📝 关键要点

- **创建模型和绑定工具是两个独立步骤**
- **使用 `.bind_tools([...])` 动态绑定工具**，不是在创建模型时指定
- **LLM 自己决定是否需要调用工具**
- **工具调用是一个循环过程**：LLM → 工具 → LLM → 最终答案
- **使用 `create_react_agent` 可以自动处理整个流程**

---

## 最佳实践总结

### ✅ LangGraph 节点设计

1. **节点函数必须返回 state**
   ```python
   def my_node(state: MyState):
       # 处理逻辑
       state['result'] = "..."
       return state  # ✅ 必须返回 state
   ```

2. **路由函数返回字符串**
   ```python
   def router(state: MyState):
       # 路由逻辑
       return "next_node_name"  # ✅ 返回节点名称
   ```

3. **清晰的职责分离**
   - 节点：执行具体任务，返回 state
   - 路由函数：决定下一步去哪，返回节点名称
   - 不要混淆两者

### ✅ 工具使用

1. **不需要 LLM 调用时**：使用普通函数
   ```python
   def get_data():
       return [...]
   ```

2. **需要 LLM 调用时**：使用 `@tool` + `.bind_tools()`
   ```python
   @tool
   def get_data():
       return [...]
   
   llm_with_tools = chat_model.bind_tools([get_data])
   ```

3. **两者都需要时**：分离实现
   ```python
   def _get_data_impl():  # 普通函数
       return [...]
   
   @tool
   def get_data():  # 工具定义
       return _get_data_impl()
   ```

### ✅ 图结构设计

```python
graph = StateGraph(MyState)

# 添加节点
graph.add_node("node1", node1_func)
graph.add_node("node2", node2_func)

# 条件边：router 只是函数，不是节点
graph.add_conditional_edges(START, router_func, path_map)

# 普通边
graph.add_edge("node1", END)
graph.add_edge("node2", END)
```

---

## 🎯 总结

通过这次调试，我们学到了：

1. **`@tool` 装饰器的本质**：将函数转换为 StructuredTool 对象
2. **LangGraph 节点的规则**：必须返回 state，不能返回 END
3. **路由函数的作用**：只用于条件边，不作为节点
4. **LLM 工具调用的正确方式**：使用 `.bind_tools()` 动态绑定

这些都是 LangGraph 开发中的核心概念，理解它们能帮助我们更好地构建复杂的 AI 工作流！

---

## 📚 参考资源

- [LangGraph 官方文档](https://langchain-doc.cn/)
- [LangChain Tools 文档](https://python.langchain.com/docs/modules/agents/tools/)
- [LangGraph Error Reference](https://docs.langchain.com/oss/python/langgraph/errors/)
