"""
skill加载
skill 分为 2个类型：
1. 常驻技能，每次都需要加载全部内容的
2. 自主加载，每次只加载frontmatter的内容（agent需要加载某个skill，通过使用readfile进行自主加载）


"""

from lifeprism.config import settings
from pathlib import Path
from lifeprism.utils import get_logger
import re
import yaml
import json
logger = get_logger(__name__)

class SkillLoad:
    _ALWAYS_LOAD = [
    ]
    def __init__(self):
        self.skill_path = Path(settings.lifeprism_data_path + "/agent/skills" )

    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content

    def load_skill_content(self,skill_name) -> str | None:
        """ 加载去除frontmatter的skill正文 """
        path = self.skill_path / f"{skill_name}/skill.md"
        if path.exists():
            # 读取文件
            content = path.read_text(encoding="utf-8")
            # 
            return self._strip_frontmatter(content)

        else:
            logger.warning(f"{str(path)}不存在，无法加载{skill_name}skill, ")
        return None


    def load_skill_frontmatter(self, skill_name: str) -> dict | None:
        """加载 skill.md 顶部的 YAML frontmatter，解析为 dict。无文件、无 frontmatter 或解析失败时返回 None。"""
        path = self.skill_path / f"{skill_name}/skill.md"
        if not path.exists():
            logger.warning(f"{str(path)}不存在，无法加载{skill_name}skill, ")
            return None
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return None
        match = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n", content, re.DOTALL)
        if not match:
            return None
        yaml_block = match.group(1)
        try:
            parsed = yaml.safe_load(yaml_block)
        except yaml.YAMLError as e:
            logger.warning(f"{path} frontmatter YAML 解析失败: {e}")
            return None
        if parsed is None:
            return None
        if not isinstance(parsed, dict):
            logger.warning(f"{path} frontmatter 根节点不是 YAML mapping（dict）")
            return None
        return parsed

    def load_skills(self,load_skills_name :list[str] | None = None) -> str:
        """ 读取所有load_skills """
        if load_skills_name is None:
            load_skills_name = []
        elif isinstance(load_skills_name,str):
            load_skills_name = [load_skills_name]

        load_skills_name = set(self._ALWAYS_LOAD + load_skills_name)
        parts = []
        for skill_name in load_skills_name:
            content = self.load_skill_content(skill_name)
            if content:
                parts.append(f"### Skill: {skill_name}\n\n{content}")
                
        return "\n\n---\n\n".join(parts) if parts else ""

    def load_frontmatters(self, loaded_skills_name: list[str] | None = None) -> str:
        """ 加载除已经加载的skill以外的所有skill 的 frontmatters
            args:
                loaded_skills_name : 本轮要需要加载的skills， 在加载frontmatters时应该排除这些内容
        """
        if loaded_skills_name is None:
            loaded_skills_name = []
        elif isinstance(loaded_skills_name, str):
            loaded_skills_name = [loaded_skills_name]
        loaded_skills_name = set(self._ALWAYS_LOAD + loaded_skills_name)
        
        all_skills = self.get_skills_list()
        parts = ["### 可用skill列表\n需要使用特定技能时请读取对应的路径文件："]

        for skill in all_skills:
            if skill not in loaded_skills_name:
                fm = self.load_skill_frontmatter(skill)
                if fm is not None:
                    desc = fm.get("description", "无描述")
                    path_str = str(self.skill_path / f"{skill}/skill.md")
                    
                    skill_md = f"- **{skill}**\n  - 描述: {desc}\n  - 路径: `{path_str}`"
                    # 兼容展示除name和description以外的所有扩展字段
                    for k, v in fm.items():
                        if k not in ("name", "description"):
                            skill_md += f"\n  - {k}: {v}"
                            
                    parts.append(skill_md)
            
        return "\n\n".join(parts)
        

    def get_skills_list(self) ->list[str]:
        """ 获取所有skills list ,返回skill名称列表"""
        # 获取数据目录skill下的所有skill
        return  [f.name for f in self.skill_path.iterdir() if f.is_dir()]

if __name__ == "__main__":
    skill_load = SkillLoad()
    print(skill_load.get_skills_list())
    print(skill_load.load_frontmatters())