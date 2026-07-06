"""资源文件初始化模块

启动时扫描 templates 根目录下所有文件，检查目标路径是否存在，不存在则复制。

- 打包环境：bundle_dir 为 PyInstaller 的 sys._MEIPASS，模板根为 bundle_dir/templates/
- 非打包环境：bundle_dir 为仓库根目录下的 templates/（与源码 templates 目录一致）

路径映射规则：
  templates/config/...  -> config_base_path/config/...
  templates/<其他>/...  -> lifeprism_data_path/<其他>/...
"""
import sys
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# templates/ 下以此子目录开头的文件映射到 config_base_path，其余映射到 lifeprism_data_path
_CONFIG_SUBDIR = "config"

# 需要强制覆盖的目录列表，无论目标文件是否存在都会覆盖
OVERWRITE_DIR_LIST = ["prompts","tool","agent"]
def initialize_resources() -> None:
    """
    初始化资源文件

    扫描模板根目录下所有文件，不存在于目标路径则复制。
    """
    from lifeprism.config.settings_manager import settings

    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)
        templates_dir = bundle_dir / "templates"
    else:
        bundle_dir = Path(__file__).resolve().parent.parent.parent / "templates"
        templates_dir = bundle_dir
    data_path = settings.lifeprism_data_path
    config_path = settings.config_base_path

    if not templates_dir.exists():
        logger.warning("内嵌 templates 目录不存在，跳过资源初始化: %s", templates_dir)
        return

    # 记录初始化前 agent/chat 目录是否已存在，用于决定是否跳过 bootstrap.md 复制
    agent_chat_existed_before = (data_path / "agent/chat").exists()

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

        # 如果文件所在目录在强制覆盖列表中，则无论是否存在都覆盖
        if rel.parts[0] in OVERWRITE_DIR_LIST:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            logger.debug("已强制覆盖资源文件: %s", target)
            continue

        # 特殊处理：如果 agent/chat 目录在初始化前已存在，跳过复制 bootstrap.md
        if rel.as_posix() == "agent/chat/bootstrap.md" and agent_chat_existed_before:
            logger.debug("agent/chat 目录已存在，跳过复制 bootstrap.md: %s", target)
            continue

        if target.exists():
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        logger.debug("已初始化资源文件: %s", target)
