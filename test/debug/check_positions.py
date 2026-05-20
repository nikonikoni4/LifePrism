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

                print(f'version_content 总长度: {len(version_content)}')
                print(f'搜索范围: 6 到 {len(version_content) - 3}')
                print(f'version_content 中 ``` 的数量: {version_content.count("```")}')

                # 找出所有 ``` 的位置
                positions = []
                pos = 0
                while True:
                    pos = version_content.find('```', pos)
                    if pos == -1:
                        break
                    positions.append(pos)
                    pos += 3

                print(f'所有 ``` 的位置: {positions}')

                # 检查每个位置后面的字符
                for p in positions:
                    next_char_pos = p + 3
                    while next_char_pos < len(version_content) and version_content[next_char_pos] in ' \t':
                        next_char_pos += 1
                    if next_char_pos < len(version_content):
                        next_char = version_content[next_char_pos]
                        print(f'位置 {p} 后面的字符: {repr(next_char)}')
                    else:
                        print(f'位置 {p} 后面已经到达末尾')

                break
        break
