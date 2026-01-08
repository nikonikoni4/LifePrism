"""
测试 LLM 是否会重复调用工具

测试1：明确指令调用 1~8，看看是否会重复
测试2：不明确指令，只告诉不能重复，看看行为
"""

from langchain.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from lifeprism.llm.llm_classify.utils import create_ChatTongyiModel
from typing import Annotated


# ============================================
# 简单的测试工具
# ============================================
@tool
def process_number(number: Annotated[int, "要处理的数字，范围 1-10"]) -> str:
    """
    处理一个数字（范围 1-10）。
    每个数字只需要处理一次，不要重复处理。
    """
    print(f"    ✅ 工具被调用: process_number({number})")
    return f"""数字 {number} 已处理完成：1. 电脑使用时间占比
0~24h内电脑活跃时间占比：0.0 0.0 0.0 0.0 0.0 0.6 0.9 0.8 0.8 0.9 0.8 0.8
2. 分段活跃统计与分类占比
  - 时段1（2026-01-03 00:00:00 至 2026-01-03 05:59:59）
    - 分类占比:
      - 电脑空闲时间: 5小时59分钟（100.0%）
    - 主要活动记录:
      - lifewatch-ai - antigravity - implementation plan（antigravity）: 6分钟
      - lifewatch-ai - antigravity - report_service.py（antigravity）: 4分钟
      - lifewatch-ai - antigravity - report_api.py（antigravity）: 4分钟
      - lifewatch-ai - antigravity - report_schemas.py（antigravity）: 3分钟
      - lifewatchai（msedge）: 2分钟
  - 时段2（2026-01-03 05:59:59 至 2026-01-03 11:59:59）
    - 分类占比:
      - 电脑空闲时间: 4小时53分钟（81.44%）
      - 工作/学习: 53分钟（14.75%）
         - 编程: 48分钟（13.38%）
         - 计划: 3分钟（0.97%）
         - 学习: 1分钟（0.39%）
      - 其他: 8分钟（2.3%）
      - 娱乐: 5分钟（1.52%）
         - 看电视: 5分钟（1.52%）
    - 主要活动记录:
      - lifewatch-ai - antigravity - launch_lifewatch.py（antigravity）: 26分钟
      - lifewatchai（msedge）: 10分钟
      - lifewatch-ai - antigravity - data_clean.py（antigravity）: 6分钟
      - lifewatch-ai - antigravity - settings_manager.py（antigravity）: 5分钟
      - lifewatch-ai - antigravity - llm_lw_data_provider.py（antigravity）: 5分钟
  - 时段3（2026-01-03 11:59:59 至 2026-01-03 17:59:59）
    - 分类占比:
      - 工作/学习: 4小时17分钟（71.48%）
         - 编程: 3小时59分钟（66.55%）
         - 学习: 14分钟（3.96%）
         - 计划: 3分钟（0.96%）
      - 电脑空闲时间: 56分钟（15.7%）
      - 其他: 34分钟（9.7%）
      - 娱乐: 11分钟（3.13%）
         - 看电视: 11分钟（3.13%）
    - 主要活动记录:
      - 唐朝诡事录之长安-电视剧全集-完整版视频在线观看-爱奇艺（msedge）: 28分钟
      - lifewatch-ai - antigravity - report_summary.py（antigravity）: 8分钟
      - 唐朝诡事录之长安-电视剧全集-完整版视频在线观看-爱奇艺（msedge）: 7分钟
      - lifewatchai（msedge）: 6分钟
      - lifewatch-ai - antigravity - llm_lw_data_provider.py（antigravity）: 6分钟
  - 时段4（2026-01-03 17:59:59 至 2026-01-03 23:59:59）
    - 分类占比:
      - 工作/学习: 3小时29分钟（58.1%）
         - 编程: 3小时21分钟（55.95%）
         - 学习: 4分钟（1.15%）
         - 计划: 3分钟（0.92%）
      - 电脑空闲时间: 1小时1分钟（17.05%）
      - 娱乐: 50分钟（14.14%）
         - 看电视: 48分钟（13.38%）
         - 打游戏: 2分钟（0.76%）
      - 其他: 38分钟（10.7%）

3. 目标时间投入
  - 完成lifewatch项目: 7小时43分钟

4. 今日重点与任务
date: 2026-01-03
- focus : 1. 实现report界面
2. 实现AI多日总结
3. 实现AI月总结
- todos: 100%
  1. 修复分类时goal的相关bug completed
  2. 完成月界面前后端 completed
  3. 完成ai总结功能 completed

5. 与前一天对比
### 分类时间变化
| 分类 | 上周期 | 本周期 | 变化 |
|------|--------|--------|------|
| 其他 | 2.6h | 1.4h | -48.5% |
| 娱乐 | 1.1h | 1.1h | +3.7% |
| 工作/学习 | 10.0h | 8.7h | -13.6% |

### 目标投入变化"""


# ============================================
# 测试函数
# ============================================
def run_test(test_name: str, initial_prompt: str, max_rounds: int = 5):
    """
    运行测试
    
    Args:
        test_name: 测试名称
        initial_prompt: 初始 prompt
        max_rounds: 最大循环次数（防止无限循环）
    """
    print(f"\n{'='*60}")
    print(f"🧪 {test_name}")
    print(f"{'='*60}")
    print(f"📝 Prompt: {initial_prompt[:100]}...")
    print()
    
    # 创建 LLM 并绑定工具
    llm = create_ChatTongyiModel(enable_search=False, enable_thinking=False)
    llm = llm.bind_tools([process_number])
    
    # 维护消息列表
    messages = [HumanMessage(content=initial_prompt)]
    
    # 记录已调用的数字
    called_numbers = []
    
    round_count = 0
    while round_count < max_rounds:
        round_count += 1
        print(f"--- 第 {round_count} 轮 ---")
        
        # 调用 LLM
        print(messages)
        result = llm.invoke(messages)
        messages.append(result)
        
        # 检查是否有 tool_calls
        if not (hasattr(result, 'tool_calls') and result.tool_calls):
            print(f"  → LLM 返回最终结果（无 tool_calls）")
            if result.content:
                print(f"  → 内容: {result.content[:200]}...")
            break
        
        # 执行工具调用
        print(f"  → LLM 请求调用 {len(result.tool_calls)} 个工具")
        
        for tool_call in result.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")
            
            number = tool_args.get("number", "?")
            
            # 检查是否重复
            if number in called_numbers:
                print(f"    ⚠️ 重复调用! process_number({number}) - 已经调用过的数字: {called_numbers}")
            else:
                called_numbers.append(number)
            
            # 执行工具
            tool_result = process_number.invoke(tool_args)
            messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))
            
        print(f"  → 已调用的数字: {called_numbers}")
        print()
    
    # 输出统计
    print(f"\n📊 测试结果统计:")
    print(f"  - 总轮数: {round_count}")
    print(f"  - 调用的数字: {called_numbers}")
    print(f"  - 调用次数: {len(called_numbers)}")
    
    # 检查是否有重复
    unique_numbers = set(called_numbers)
    if len(unique_numbers) < len(called_numbers):
        duplicates = [n for n in called_numbers if called_numbers.count(n) > 1]
        print(f"  ❌ 存在重复调用: {set(duplicates)}")
    else:
        print(f"  ✅ 没有重复调用")
    
    return called_numbers


# ============================================
# 测试1：明确指令调用 1~8
# ============================================
def test1_explicit_instructions():
    """测试1：明确告诉 LLM 调用 1~8"""
    prompt = """你有一个工具 process_number，可以处理数字 1-10。

请按顺序调用工具处理数字 1, 2, 3, 4, 5, 6, 7, 8（共8个数字）。

规则：
1. 每个数字只需要处理一次，不要重复处理
2. 如果所有8个数字都处理完了，就不要再调用工具，直接返回"全部处理完成"
3. 你可以一次调用多个工具

开始执行吧！"""
    
    return run_test("测试1：明确指令调用 1~8", prompt)


# ============================================
# 测试2：不明确指令，只说不能重复
# ============================================
def test2_no_explicit_instructions():
    """测试2：不明确指令，只告诉不能重复"""
    prompt = """你有一个工具 process_number，可以处理数字 1-10。

请使用这个工具处理一些数字。

规则：
1. 每个数字只能处理一次，绝对不能重复处理同一个数字
2. 如果你认为已经处理了足够的数字，就停止调用工具并返回总结
3. 你可以一次调用多个工具

开始执行吧！"""
    
    return run_test("测试2：不明确指令，只说不能重复", prompt)


# ============================================
# 测试3：模拟 query 节点的场景（更接近实际情况）
# ============================================
def test3_simulated_query_node():
    """测试3：模拟 query 节点场景，带有更多上下文"""
    prompt = """# 历史消息
assistant: 根据分析，我需要查询以下时段的详细数据：
- 时段 1: 08:00-10:00
- 时段 2: 12:00-14:00
- 时段 3: 15:00-17:00
- 时段 4: 19:00-21:00

# 工具可调用次数限制
工具 process_number 可以调用 10 次

# 你需要按照下面要求完成任务：
依据上一步的查询要求，按要求调用 process_number 工具处理数字 1, 2, 3, 4（对应4个时段）。
不能重复处理已经处理过的数字，若所有数字都处理了，返回"完成"，不调用任何工具。"""
    
    return run_test("测试3：模拟 query 节点场景", prompt)


# ============================================
# 主函数
# ============================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔬 LLM Tool Calling 重复调用测试")
    print("="*60)
    
    # 运行测试
    result1 = test1_explicit_instructions()
    
    print("\n" + "-"*60 + "\n")
    
    result2 = test2_no_explicit_instructions()
    
    print("\n" + "-"*60 + "\n")
    
    result3 = test3_simulated_query_node()
    
    # 总结
    print("\n" + "="*60)
    print("📋 测试总结")
    print("="*60)
    print(f"测试1 调用序列: {result1}")
    print(f"测试2 调用序列: {result2}")
    print(f"测试3 调用序列: {result3}")
