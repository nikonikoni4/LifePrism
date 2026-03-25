"""资源文件初始化模块

打包环境启动时，扫描 bundle_dir/templates/ 下所有文件，
检查目标路径是否存在，不存在则复制。

路径映射规则：
  templates/config/...  -> config_base_path/config/...
  templates/<其他>/...  -> lifeprism_data_path/<其他>/...

开发环境不执行任何操作（文件直接从源码位置读取）。
"""
import sys
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# templates/ 下以此子目录开头的文件映射到 config_base_path，其余映射到 lifeprism_data_path
_CONFIG_SUBDIR = "config"


def initialize_resources() -> None:
    """
    初始化资源文件（仅打包环境执行）

    扫描 bundle_dir/templates/ 下所有文件，不存在于目标路径则复制。
    """
    if not getattr(sys, 'frozen', False):
        return

    from lifeprism.config.settings_manager import settings

    bundle_dir = Path(sys._MEIPASS)
    templates_dir = bundle_dir / "templates"
    data_path = Path(settings.lifeprism_data_path)
    config_path = Path(settings.config_base_path)

    if not templates_dir.exists():
        logger.warning(f"内嵌 templates 目录不存在，跳过资源初始化: {templates_dir}")
        return

    for source in templates_dir.rglob("*"):
        if not source.is_file():
            continue

        # 相对于 templates/ 的路径，如 config/config.json 或 docs/user_guide.md
        rel = source.relative_to(templates_dir)

        # 第一级子目录决定目标基础路径
        if rel.parts[0] == _CONFIG_SUBDIR:
            target = config_path / rel
        else:
            target = data_path / rel

        if target.exists():
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        logger.info(f"已初始化资源文件: {target}")
