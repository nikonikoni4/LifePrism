"""
skill加载
skill 分为 2个类型：
1. 常驻技能，每次都需要加载全部内容的
2. 自主加载，每次只加载frontmatter的内容（agent需要加载某个skill，通过使用readfile进行自主加载）


"""

import re
from typing import Any

import yaml

from lifeprism.config import settings
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class SkillLoad:
    _ALWAYS_LOAD = ["user-data-guide"]

    def __init__(self):
        self.skill_path = settings.lifeprism_data_path / "agent" / "skills"

    def _escape_xml(self, s: Any) -> str:
        """XML 特殊字符转义"""
        if s is None:
            return ""
        if not isinstance(s, str):
            s = str(s)
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end() :].strip()
        return content

    def load_skill_content(self, skill_name) -> str | None:
        """加载去除frontmatter的skill正文"""
        path = self.skill_path / f"{skill_name}/skill.md"
        if path.exists():
            # 读取文件
            content = path.read_text(encoding="utf-8")
            #
            return self._strip_frontmatter(content)

        else:
            logger.warning("%s不存在，无法加载%s skill,", str(path), skill_name)
        return None

    def load_skill_frontmatter(self, skill_name: str) -> dict | None:
        """加载 skill.md 顶部的 YAML frontmatter，解析为 dict。无文件、无 frontmatter 或解析失败时返回 None。"""
        path = self.skill_path / f"{skill_name}/skill.md"
        if not path.exists():
            logger.warning("%s不存在，无法加载%s skill,", str(path), skill_name)
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
            logger.warning("%s frontmatter YAML 解析失败: %s", path, e)
            return None
        if parsed is None:
            return None
        if not isinstance(parsed, dict):
            logger.warning("%s frontmatter 根节点不是 YAML mapping（dict）", path)
            return None
        return parsed

    def load_skills(self, load_skills_name: list[str] | None = None) -> str:
        """读取并以 XML 格式返回已加载正文的技能内容"""
        if load_skills_name is None:
            load_skills_name = []
        elif isinstance(load_skills_name, str):
            load_skills_name = [load_skills_name]

        load_skills_name = set(self._ALWAYS_LOAD + load_skills_name)

        lines = ['<skills type="loaded">']
        for skill_name in load_skills_name:
            content = self.load_skill_content(skill_name)
            if content:
                # fm = self.load_skill_frontmatter(skill_name) or {}
                # description = fm.get("description", "")

                lines.append(f'  <skill name="{self._escape_xml(skill_name)}">')
                # if description:
                #     lines.append(f'    <description>{self._escape_xml(description)}</description>')
                lines.append("    <content>")
                lines.append(self._escape_xml(content))
                lines.append("    </content>")
                lines.append("  </skill>")

        lines.append("</skills>")
        return "\n".join(lines) if len(lines) > 2 else ""

    def load_frontmatters(self, loaded_skills_name: list[str] | None = None) -> str:
        """加载除已经加载的 skill 以外的所有 skill 的 frontmatters (可用技能列表)
        args:
            loaded_skills_name : 本轮要加载的 skills，在加载 frontmatters 时应该排除这些内容
        """
        if loaded_skills_name is None:
            loaded_skills_name = []
        elif isinstance(loaded_skills_name, str):
            loaded_skills_name = [loaded_skills_name]
        loaded_skills_name = set(self._ALWAYS_LOAD + loaded_skills_name)

        all_skills = self.get_skills_list()

        lines = ['<skills type="available">']
        for skill in all_skills:
            if skill not in loaded_skills_name:
                fm = self.load_skill_frontmatter(skill)
                if fm is not None:
                    name = self._escape_xml(skill)
                    desc = self._escape_xml(fm.get("description", "无描述"))
                    path_str = self._escape_xml(str(self.skill_path / f"{skill}/skill.md"))

                    lines.append(f'  <skill name="{name}">')
                    lines.append(f"    <description>{desc}</description>")
                    lines.append(f"    <location>{path_str}</location>")

                    # 兼容展示除name和description以外的所有扩展字段
                    for k, v in fm.items():
                        if k not in ("name", "description"):
                            safe_k = self._escape_xml(k)
                            safe_v = self._escape_xml(v)
                            lines.append(f"    <{safe_k}>{safe_v}</{safe_k}>")

                    lines.append("  </skill>")

        lines.append("</skills>")
        return "\n".join(lines) if len(lines) > 2 else ""

    def get_skills_list(self) -> list[str]:
        """
        获取所有skills list ,返回skill名称列表

        Returns:
            list[str]: skill名称列表，如果目录不存在则返回空列表
        """
        if not self.skill_path.exists():
            logger.warning("skills目录不存在: %s, 已创建", self.skill_path)
            self.skill_path.mkdir(parents=True, exist_ok=True)
            return []
        return [f.name for f in self.skill_path.iterdir() if f.is_dir()]


if __name__ == "__main__":
    skill_load = SkillLoad()
    print(skill_load.get_skills_list())
    print(skill_load.load_frontmatters())
