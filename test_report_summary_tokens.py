"""
测试 report_summary 函数的 tokens 使用量跟踪功能
"""
from lifewatch.llm.llm_classify.function.report_summary import daily_summary, multi_days_summary
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_daily_summary():
    """测试每日总结的 tokens 使用量跟踪"""
    print("\n" + "="*60)
    print("测试每日总结 (daily_summary)")
    print("="*60)
    
    date = "2026-01-01"
    options = ["时间分布", "主要活动"]
    
    try:
        result = daily_summary(date, options)
        
        print(f"\n返回类型: {type(result)}")
        print(f"返回键: {result.keys() if isinstance(result, dict) else 'N/A'}")
        
        if isinstance(result, dict):
            print(f"\n总结内容 (前100字符): {result.get('content', '')[:100]}...")
            print(f"\nTokens 使用量:")
            tokens_usage = result.get('tokens_usage', {})
            print(f"  - 输入 tokens: {tokens_usage.get('input_tokens', 0)}")
            print(f"  - 输出 tokens: {tokens_usage.get('output_tokens', 0)}")
            print(f"  - 总 tokens: {tokens_usage.get('total_tokens', 0)}")
        else:
            print(f"\n警告: 返回值不是字典类型，而是 {type(result)}")
            
        print("\n✅ 每日总结测试完成")
        return True
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_multi_days_summary():
    """测试多日总结的 tokens 使用量跟踪"""
    print("\n" + "="*60)
    print("测试多日总结 (multi_days_summary)")
    print("="*60)
    
    start_time = "2026-01-01 00:00:00"
    end_time = "2026-01-03 23:59:59"
    split_count = 3
    options = ["时间分布", "主要活动", "趋势分析"]
    
    try:
        result = multi_days_summary(start_time, end_time, split_count, options)
        
        print(f"\n返回类型: {type(result)}")
        print(f"返回键: {result.keys() if isinstance(result, dict) else 'N/A'}")
        
        if isinstance(result, dict):
            print(f"\n总结内容 (前100字符): {result.get('content', '')[:100]}...")
            print(f"\nTokens 使用量:")
            tokens_usage = result.get('tokens_usage', {})
            print(f"  - 输入 tokens: {tokens_usage.get('input_tokens', 0)}")
            print(f"  - 输出 tokens: {tokens_usage.get('output_tokens', 0)}")
            print(f"  - 总 tokens: {tokens_usage.get('total_tokens', 0)}")
        else:
            print(f"\n警告: 返回值不是字典类型，而是 {type(result)}")
            
        print("\n✅ 多日总结测试完成")
        return True
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("开始测试 report_summary 函数")
    print("="*60)
    
    # 测试每日总结
    daily_success = test_daily_summary()
    
    # 测试多日总结
    multi_success = test_multi_days_summary()
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"每日总结测试: {'✅ 通过' if daily_success else '❌ 失败'}")
    print(f"多日总结测试: {'✅ 通过' if multi_success else '❌ 失败'}")
    print("="*60)
