"""测试配置迁移脚本"""
import sys
sys.path.insert(0, '.')

from pathlib import Path
import yaml
import shutil
from datetime import datetime

from lifeprism.config.migrations.config_migrator import run_config_migrations
from lifeprism.config.migrations.scripts import SETTINGS_MIGRATIONS

print("=" * 60)
print("测试配置迁移脚本 s006_add_llm_call_logger_enabled")
print("=" * 60)

# 创建测试配置文件
test_config_dir = Path("test/debug/temp_config")
test_config_dir.mkdir(parents=True, exist_ok=True)
test_config_path = test_config_dir / "test_config.yaml"

# 1. 测试从旧版本迁移
print("\n1. 测试从版本 5 迁移到版本 6:")
old_config = {
    "config_version": 5,
    "user_name": "测试用户",
    "screen_analysis_ignore": []
}

with open(test_config_path, 'w', encoding='utf-8') as f:
    yaml.dump(old_config, f, allow_unicode=True)

print(f"   - 创建测试配置文件: {test_config_path}")
print(f"   - 初始版本: {old_config['config_version']}")
print(f"   - 包含 llm_call_logger_enabled: {'llm_call_logger_enabled' in old_config}")

# 运行迁移
result = run_config_migrations(test_config_path, SETTINGS_MIGRATIONS)

print(f"\n   迁移后:")
print(f"   - 最终版本: {result.get('config_version')}")
print(f"   - 包含 llm_call_logger_enabled: {'llm_call_logger_enabled' in result}")
print(f"   - llm_call_logger_enabled 值: {result.get('llm_call_logger_enabled')}")

# 2. 测试已应用的情况
print("\n2. 测试配置已包含 llm_call_logger_enabled 的情况:")
existing_config = {
    "config_version": 6,
    "user_name": "测试用户",
    "llm_call_logger_enabled": True
}

test_config_path2 = test_config_dir / "test_config2.yaml"
with open(test_config_path2, 'w', encoding='utf-8') as f:
    yaml.dump(existing_config, f, allow_unicode=True)

print(f"   - 初始版本: {existing_config['config_version']}")
print(f"   - llm_call_logger_enabled 初始值: {existing_config['llm_call_logger_enabled']}")

result2 = run_config_migrations(test_config_path2, SETTINGS_MIGRATIONS)

print(f"\n   迁移后:")
print(f"   - 最终版本: {result2.get('config_version')}")
print(f"   - llm_call_logger_enabled 值: {result2.get('llm_call_logger_enabled')}")
print(f"   - 值是否保持不变: {result2.get('llm_call_logger_enabled') == True}")

# 清理测试文件
print("\n3. 清理测试文件:")
shutil.rmtree(test_config_dir)
print(f"   - 已删除测试目录: {test_config_dir}")

print("\n" + "=" * 60)
print("迁移测试完成")
print("=" * 60)
