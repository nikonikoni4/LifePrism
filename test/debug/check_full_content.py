import sys
sys.path.insert(0, '.')
from lifeprism.llm.utils.md_os import prompts_md_load
from pathlib import Path

data = prompts_md_load(Path('templates/prompts/schedule_prompts.md'))
v1 = data['prompts']['update_memory']['versions']['v1']

print('总长度:', len(v1))
print('包含的 ``` 数量:', v1.count('```'))
print('\n最后200字符:')
print(v1[-200:])
print('\n完整内容:')
print(v1)
