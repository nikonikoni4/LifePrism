import sys
sys.path.insert(0, '.')
from pathlib import Path
import re

# 读取文件
file_path = Path('templates/prompts/schedule_prompts.md')
content = file_path.read_text(encoding='utf-8')

# 找到 update_memory 的 v1 部分
blocks = re.split(r'\n---\s*\n', content)

for block in blocks:
    if '# update_memory' in block:
        # 找到 v1 版本
        version_pattern = re.compile(r'^##\s+(v\d+)\s*\n', re.MULTILINE)
        for match in version_pattern.finditer(block):
            if match.group(1) == 'v1':
                version_start = match.end()
                # 找到下一个二级标题
                next_match = re.search(r'^##\s+', block[version_start:], re.MULTILINE)
                if next_match:
                    version_end = version_start + next_match.start()
                else:
                    version_end = len(block)

                version_content = block[version_start:version_end].strip()
                print('原始内容前200字符:')
                print(repr(version_content[:200]))
                print()
                print('startswith 检查:', version_content.startswith('```md'))
                print('前10个字符:', repr(version_content[:10]))

                # 测试我的算法
                if version_content.startswith('```md'):
                    print('\n进入解析逻辑')
                    first_newline = version_content.find('\n')
                    print('first_newline:', first_newline)

                    if first_newline != -1:
                        content_start = first_newline + 1
                        print('content_start:', content_start)
                        print('从 content_start 开始的前50字符:', repr(version_content[content_start:content_start+50]))
                else:
                    print('\n未进入解析逻辑')
                break
        break
