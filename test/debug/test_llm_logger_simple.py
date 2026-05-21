"""简单测试 llm_call_logger 配置读取"""
import sys
sys.path.insert(0, '.')

from lifeprism.config import settings
from lifeprism.llm.utils import llm_call_logger

print("=" * 60)
print("测试 LLM 调用记录器配置")
print("=" * 60)

# 1. 检查配置
print(f"\n1. 配置检查:")
config_value = settings.get('llm_call_logger_enabled', None)
print(f"   - config.yaml 中的值: {config_value}")
print(f"   - llm_call_logger.enabled: {llm_call_logger.enabled}")

# 2. 检查日志目录
print(f"\n2. 日志目录:")
print(f"   - log_dir: {llm_call_logger.log_dir}")
print(f"   - log_dir 存在: {llm_call_logger.log_dir.exists()}")

# 3. 测试启用/禁用
print(f"\n3. 测试启用/禁用:")
print(f"   - 初始状态: {llm_call_logger.enabled}")

llm_call_logger.enabled = True
print(f"   - 设置为 True 后: {llm_call_logger.enabled}")

llm_call_logger.enabled = False
print(f"   - 设置为 False 后: {llm_call_logger.enabled}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
