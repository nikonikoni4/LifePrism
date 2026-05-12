# 心情数据获取和总结功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 agent_schedule_job.py 的 update_memory 函数中实现心情数据的获取和客观总结功能

**Architecture:** 添加两个辅助函数：get_mood_data 负责时间格式转换和数据获取，summary_moods 负责通过 LLM 进行客观总结。两个函数集成到 update_memory 的第 77 行位置。

**Tech Stack:** Python, datetime, lifeprism.llm.agent.tools.lifeprismsystem, lifeprism.llm.bus

---

## File Structure

**Modify:**
- `lifeprism/llm/function/agent_schedule_job.py` - 添加 get_mood_data 和 summary_moods 函数，集成到 update_memory

**No new files created** - 所有功能添加到现有文件中

---

### Task 1: 实现 get_mood_data 函数

**Files:**
- Modify: `lifeprism/llm/function/agent_schedule_job.py:77`

- [ ] **Step 1: 在文件中添加 get_mood_data 函数（在 summary_activities 函数之后）**

在第 52 行（summary_activities 函数结束后）添加：

```python
def get_mood_data(start_time: str, end_time: str) -> str:
    """获取心情数据
    
    Args:
        start_time: 开始时间，格式为 'YYYY-MM-DD HH:MM:SS'
        end_time: 结束时间，格式为 'YYYY-MM-DD HH:MM:SS'
    
    Returns:
        str: 格式化的心情数据字符串
    """
    # 将时间格式从 'YYYY-MM-DD HH:MM:SS' 转换为 'YYYY-MM-DD'
    start_date = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    end_date = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    
    # 调用 query_user_mood 获取心情数据
    mood_data = query_user_mood(start_date, end_date)
    
    return mood_data
```

- [ ] **Step 2: 验证函数语法正确性**

运行语法检查：
```bash
python -m py_compile lifeprism/llm/function/agent_schedule_job.py
```

Expected: 无输出（表示语法正确）

- [ ] **Step 3: Commit**

```bash
git add lifeprism/llm/function/agent_schedule_job.py
git commit -m "feat(agent_schedule_job): 添加 get_mood_data 函数用于获取心情数据"
```

---

### Task 2: 实现 summary_moods 函数

**Files:**
- Modify: `lifeprism/llm/function/agent_schedule_job.py:70`

- [ ] **Step 1: 在文件顶部添加 MOOD_SUMMARY_SYSTEM_PROMPT 常量（在 ACTIVITY_SUMMARY_SYSTEM_PROMPT 之后）**

在第 37 行（ACTIVITY_SUMMARY_SYSTEM_PROMPT 结束后）添加：

```python
MOOD_SUMMARY_SYSTEM_PROMPT = """## 任务
你需要对用户的心情记录进行客观总结。

## 数据说明
每条心情记录包含：
1. 时间：心情记录的时间
2. 心情分数：用户的心情评分（1-10分）
3. 内容：用户对心情的描述
4. 影响因素：导致该心情的因素

## 总结要求
对每条心情记录，按以下结构进行客观描述（有则写，无则跳过）：
1. 事件经过：简单描述发生了什么
2. 情绪诱因：是什么让这个情绪发生的
3. 情绪本身：用户的情绪状态是什么
4. 用户反应：面对这个情绪，用户的反应是什么

## 核心原则
1. 不要推敲或猜测
2. 仅从客观角度描述，不带任何评价
3. 如果某个组成部分数据中没有，就不写
4. 保持简洁，每条心情总结控制在 100 字以内
"""
```

- [ ] **Step 2: 在 get_mood_data 函数之后添加 summary_moods 函数**

```python
async def summary_moods(mood_data: str) -> str:
    """总结心情数据
    
    Args:
        mood_data: 心情数据字符串
    
    Returns:
        str: 心情总结内容
    """
    # 检查是否有心情数据
    if not mood_data or "无心情记录" in mood_data:
        logger.warning("没有心情数据")
        return "无心情记录"
    
    # 调用 LLM 进行总结
    result = await bus.send(
        InboundMessage(
            MessageType.DREAM_TASK,
            content=f"## 需要总结的心情数据\n{mood_data}",
            extra={"system_prompt": MOOD_SUMMARY_SYSTEM_PROMPT}
        )
    )
    
    # 处理返回结果
    if result.response and result.response.content:
        return result.response.content
    else:
        logger.error(f"心情总结 LLM 返回数据错误: {result}")
        raise ExternalServiceError(f"心情总结 LLM 返回数据错误: {result}")
```

- [ ] **Step 3: 验证函数语法正确性**

运行语法检查：
```bash
python -m py_compile lifeprism/llm/function/agent_schedule_job.py
```

Expected: 无输出（表示语法正确）

- [ ] **Step 4: Commit**

```bash
git add lifeprism/llm/function/agent_schedule_job.py
git commit -m "feat(agent_schedule_job): 添加 summary_moods 函数用于总结心情数据"
```

---

### Task 3: 集成到 update_memory 函数

**Files:**
- Modify: `lifeprism/llm/function/agent_schedule_job.py:77`

- [ ] **Step 1: 在 update_memory 函数的第 77 行添加心情数据获取和总结调用**

在第 77 行（`# 获取心情数据，并总结` 注释下方）添加：

```python
    # 获取心情数据，并总结
    mood_data = get_mood_data(start_time, end_time)
    mood_summary_content = await summary_moods(mood_data)
```

- [ ] **Step 2: 验证函数语法正确性**

运行语法检查：
```bash
python -m py_compile lifeprism/llm/function/agent_schedule_job.py
```

Expected: 无输出（表示语法正确）

- [ ] **Step 3: Commit**

```bash
git add lifeprism/llm/function/agent_schedule_job.py
git commit -m "feat(agent_schedule_job): 在 update_memory 中集成心情数据获取和总结"
```

---

### Task 4: 编写测试脚本验证功能

**Files:**
- Create: `test/unit/llm/function/test_mood_summary.py`

- [ ] **Step 1: 创建测试文件目录**

```bash
mkdir -p test/unit/llm/function
```

- [ ] **Step 2: 编写测试脚本**

```python
"""
心情数据获取和总结功能测试
"""
import asyncio
from datetime import datetime, timedelta
from lifeprism.llm.function.agent_schedule_job import get_mood_data, summary_moods


async def test_get_mood_data():
    """测试 get_mood_data 函数"""
    print("=" * 50)
    print("测试 get_mood_data 函数")
    print("=" * 50)
    
    # 使用今天的日期
    today = datetime.now().strftime('%Y-%m-%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    start_time = f"{today} 04:00:00"
    end_time = f"{tomorrow} 04:00:00"
    
    print(f"查询时间范围: {start_time} ~ {end_time}")
    
    mood_data = get_mood_data(start_time, end_time)
    print(f"\n获取到的心情数据:\n{mood_data}")
    
    return mood_data


async def test_summary_moods(mood_data: str):
    """测试 summary_moods 函数"""
    print("\n" + "=" * 50)
    print("测试 summary_moods 函数")
    print("=" * 50)
    
    summary = await summary_moods(mood_data)
    print(f"\n心情总结结果:\n{summary}")
    
    return summary


async def main():
    """主测试函数"""
    try:
        # 测试 get_mood_data
        mood_data = await test_get_mood_data()
        
        # 测试 summary_moods
        if mood_data and "无心情记录" not in mood_data:
            await test_summary_moods(mood_data)
        else:
            print("\n没有心情数据，跳过总结测试")
        
        print("\n" + "=" * 50)
        print("测试完成")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: 运行测试脚本**

```bash
cd D:\desktop\软件开发\LifeWatch-AI
python test/unit/llm/function/test_mood_summary.py
```

Expected: 
- 如果有心情数据：显示获取的心情数据和总结结果
- 如果无心情数据：显示 "无心情记录"

- [ ] **Step 4: 验证输出格式**

检查总结输出是否符合要求：
1. 每条心情记录都有总结
2. 总结包含：事件经过、情绪诱因、情绪本身、用户反应（有则写）
3. 总结客观，无评价性语言
4. 每条总结简洁（约 100 字以内）

- [ ] **Step 5: Commit**

```bash
git add test/unit/llm/function/test_mood_summary.py
git commit -m "test(agent_schedule_job): 添加心情数据获取和总结功能测试"
```

---

## Self-Review Checklist

**Spec Coverage:**
- ✅ 数据获取层 (get_mood_data) - Task 1
- ✅ 总结层 (summary_moods) - Task 2
- ✅ System Prompt - Task 2, Step 1
- ✅ 集成到 update_memory - Task 3
- ✅ 测试功能 - Task 4

**Placeholder Scan:**
- ✅ 无 TBD、TODO
- ✅ 所有代码块完整
- ✅ 所有命令具体

**Type Consistency:**
- ✅ get_mood_data 返回 str
- ✅ summary_moods 接收 str，返回 str
- ✅ 时间格式一致：输入 'YYYY-MM-DD HH:MM:SS'，转换为 'YYYY-MM-DD'
- ✅ 函数签名与设计文档一致

**Dependencies:**
- ✅ datetime - 已在文件中导入
- ✅ query_user_mood - 已在文件中导入
- ✅ bus, InboundMessage, MessageType - 已在文件中导入
- ✅ ExternalServiceError - 已在文件中导入
- ✅ logger - 已在文件中定义

---

## Notes

1. **时间格式转换**：get_mood_data 将 'YYYY-MM-DD HH:MM:SS' 转换为 'YYYY-MM-DD'，因为 query_user_mood 只接受日期格式
2. **空数据处理**：summary_moods 检查 mood_data 是否包含 "无心情记录"，如果是则直接返回，避免无效的 LLM 调用
3. **异步处理**：summary_moods 是异步函数，因为需要 await bus.send()
4. **错误处理**：LLM 调用失败时抛出 ExternalServiceError，与文件中其他函数保持一致
5. **测试策略**：使用今天的日期进行测试，确保能获取到实际数据（如果有的话）
