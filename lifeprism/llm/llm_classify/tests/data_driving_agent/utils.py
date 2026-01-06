import os
import re

def get_skill_non_json_content(file_path: str) -> str:
    """
    读取 skills.md 文件中的非 JSON 数据（Markdown 描述部分）。
    移除 YAML frontmatter 和 ```json ``` 代码块。
    """
    if not os.path.exists(file_path):
        return ""
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除 YAML frontmatter (--- ... ---)
    # 使用 multiline 匹配开头的 --- 和 结尾的 ---
    content = re.sub(r'^---\s*\n.*?\n---\s*(\n|$)', '', content, flags=re.DOTALL | re.MULTILINE)
    
    # 移除所有 ```json ... ``` 代码块
    content = re.sub(r'```json.*?```', '', content, flags=re.DOTALL)
    
    return content.strip()


if __name__ == "__main__":
    file_path = r"lifeprism\llm\llm_classify\tests\data_driving_agent\skills.md"
    content = get_skill_non_json_content(file_path)
    print(content)