"""
资源文件初始化模块

打包环境启动时，检查数据目录下的资源文件是否存在，
不存在则从 exe 内嵌资源（sys._MEIPASS）复制到目标路径。

开发环境不执行任何操作（文件直接从源码位置读取）。
"""
import sys
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# 资源文件映射：(exe 内嵌相对路径, 目标子路径, 目标基础路径类型)
# 目标基础路径类型: "data" = lifeprism_data_path, "config" = config_base_path
_RESOURCE_FILES = [
    # docs
    ("templates/docs/user_guide.md", "docs/user_guide.md", "data"),
    ("templates/docs/user_guide_guide.md", "docs/user_guide_guide.md", "data"),
    # workflow
    ("templates/workflow/daily_summary_plan.json", "workflow/daily_summary_plan.json", "data"),
    ("templates/workflow/weekly_summary_plan.json", "workflow/weekly_summary_plan.json", "data"),
    ("templates/workflow/skill.md", "workflow/skill.md", "data"),
    # config
    ("templates/config/config.json", "config/config.json", "config"),
    # plan
    ("templates/plan/示例-planDoc.md", "plan/示例-planDoc.md", "data"),
]


def initialize_resources() -> None:
    """
    初始化资源文件（仅打包环境执行）

    检查每个资源文件是否存在于目标路径，不存在则从 exe 内嵌资源复制。
    """
    if not getattr(sys, 'frozen', False):
        return

    from lifeprism.config.settings_manager import settings

    bundle_dir = Path(sys._MEIPASS)
    data_path = Path(settings.lifeprism_data_path)
    config_path = Path(settings.config_base_path)

    for source_rel, target_rel, base_type in _RESOURCE_FILES:
        source = bundle_dir / source_rel
        if base_type == "config":
            target = config_path / target_rel
        else:
            target = data_path / target_rel

        if target.exists():
            continue

        if not source.exists():
            logger.warning(f"内嵌资源不存在，跳过: {source_rel}")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        logger.info(f"已初始化资源文件: {target}")
