import sys
sys.path.insert(0, '.')
from lifeprism.llm.utils.md_os import prompts_md_load
from pathlib import Path

# 测试文件
test_file = Path('test/debug/test_prompts.md')

print("=" * 80)
print("测试嵌套代码块解析")
print("=" * 80)

data = prompts_md_load(test_file)

# 测试 test_prompt（有嵌套）
print("\n1. test_prompt (有嵌套代码块):")
print("-" * 80)
test_prompt = data['prompts']['test_prompt']['versions']['v1']
print(f"长度: {len(test_prompt)}")
print(f"包含 '## YYYY-MM-DD': {'## YYYY-MM-DD' in test_prompt}")
print(f"包含 '### subtitle': {'### subtitle' in test_prompt}")
print(f"包含 '这是内部代码块后面的内容': {'这是内部代码块后面的内容' in test_prompt}")
print(f"包含 '# document.md': {'# document.md' in test_prompt}")
print(f"包含 '这是第二个内部代码块后面的内容': {'这是第二个内部代码块后面的内容' in test_prompt}")
print(f"包含 '这是最后的内容': {'这是最后的内容' in test_prompt}")
print(f"``` 的数量: {test_prompt.count('```')}")

print("\n完整内容:")
print(test_prompt)

# 测试 simple_prompt（无嵌套）
print("\n" + "=" * 80)
print("2. simple_prompt (无嵌套代码块):")
print("-" * 80)
simple_prompt = data['prompts']['simple_prompt']['versions']['v1']
print(f"长度: {len(simple_prompt)}")
print(f"包含 '### task': {'### task' in simple_prompt}")
print(f"包含 '规则一': {'规则一' in simple_prompt}")
print(f"``` 的数量: {simple_prompt.count('```')}")

print("\n完整内容:")
print(simple_prompt)
