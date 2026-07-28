"""资源文件初始化模块

启动时扫描 templates 根目录下所有文件，检查目标路径是否存在，不存在则复制。

- 打包环境：bundle_dir 为 PyInstaller 的 sys._MEIPASS，模板根为 bundle_dir/templates/
- 非打包环境：bundle_dir 为仓库根目录下的 templates/（与源码 templates 目录一致）

路径映射规则：
  templates/config/...  -> config_base_path/config/...
  templates/<其他>/...  -> lifeprism_data_path/<其他>/...

强制覆盖策略（覆盖优先级：bootstrap.md 特殊跳过 > OVERWRITE_FILE_LIST > OVERWRITE_DIR_LIST > 仅复制不覆盖）：
0. bootstrap.md 特殊跳过（最高优先级，防御性保护）：仅在 agent/chat 目录首次出现
   时复制。用户完成引导后会删除 bootstrap.md，下次启动若 agent/chat 已存在则不再
   复制，避免反复出现。**此判断必须早于所有覆盖逻辑**，防止 OVERWRITE_DIR_LIST
   误包含 "agent" 时绕过保护导致 bug 复发（历史 bug 见
   docs/history-bugs/2026-07-27-bootstrap-md-recurring-after-overwrite.md）。
1. OVERWRITE_FILE_LIST：精确文件路径白名单，用于混杂系统提示词与用户数据的目录
   （如 agent/chat/ 下既有系统提示词 soul.md/agent.md/tool.md，又有用户数据
   identity.md、引导文件 bootstrap.md）。仅覆盖白名单内文件，保护用户数据。
2. OVERWRITE_DIR_LIST：第一级子目录白名单，整个目录下所有文件强制覆盖
   （如 prompts/，全部为系统级提示词，无用户数据）。
3. 其余文件遵循"仅复制不覆盖"原则，保护用户数据。
"""

import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# templates/ 下以此子目录开头的文件映射到 config_base_path，其余映射到 lifeprism_data_path
_CONFIG_SUBDIR = "config"

# 需要强制覆盖的目录列表（按 templates/ 第一级子目录匹配）
# 仅包含纯系统级、无用户数据的目录
OVERWRITE_DIR_LIST = ["prompts"]

# 需要强制覆盖的特定文件白名单（相对 templates/ 的 POSIX 路径，精确匹配）
# 用于混杂系统提示词与用户数据的目录（如 agent/）
# 仅覆盖系统级提示词，保护用户数据（identity.md）与引导文件（bootstrap.md）
OVERWRITE_FILE_LIST = {
    "agent/README.md",
    "agent/chat/agent.md",
    "agent/chat/soul.md",
    "agent/chat/tool.md",
    "agent/classify/agent.md",
    "agent/skills/knowledge-learning/SKILL.md",
}


def initialize_resources() -> None:
    """
    初始化资源文件

    扫描模板根目录下所有文件，按强制覆盖策略处理：
    - bootstrap.md 特殊跳过（最高优先级）：agent/chat 已存在时不再复制
    - OVERWRITE_FILE_LIST 命中 → 强制覆盖（精确文件路径）
    - OVERWRITE_DIR_LIST 命中 → 强制覆盖（第一级子目录）
    - 其余 → 仅当目标不存在时复制

    保护用户数据：identity.md、classify_preference.md 等不在
    强制覆盖白名单内，遵循"仅复制不覆盖"原则。
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

    # 记录初始化前 agent/chat 目录是否已存在
    # 用于决定是否复制 bootstrap.md：用户完成引导后会删除 bootstrap.md，
    # 下次启动若 agent/chat 已存在则不再复制，避免反复出现
    agent_chat_existed_before = (data_path / "agent/chat").exists()

    for source in templates_dir.rglob("*"):
        if not source.is_file():
            continue

        # 相对于 templates/ 的路径，如 config/config.json 或 docs/user_guide.md
        rel = source.relative_to(templates_dir)
        rel_posix = rel.as_posix()

        # 第一级子目录决定目标基础路径
        target = config_path / rel if rel.parts[0] == _CONFIG_SUBDIR else data_path / rel

        # 优先级 0（最高，防御性保护）：bootstrap.md 特殊跳过
        # 必须早于所有覆盖逻辑，防止 OVERWRITE_DIR_LIST 误包含 "agent" 时绕过保护
        # 导致 bug 复发（历史 bug 见 docs/history-bugs/2026-07-27-bootstrap-md-recurring-after-overwrite.md）
        if rel_posix == "agent/chat/bootstrap.md" and agent_chat_existed_before:
            logger.debug("agent/chat 目录已存在，跳过复制 bootstrap.md: %s", target)
            continue

        # 优先级 1：精确文件路径白名单命中 → 强制覆盖
        if rel_posix in OVERWRITE_FILE_LIST:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            logger.debug("已强制覆盖资源文件(文件白名单): %s", target)
            continue

        # 优先级 2：第一级子目录白名单命中 → 强制覆盖
        if rel.parts[0] in OVERWRITE_DIR_LIST:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            logger.debug("已强制覆盖资源文件(目录白名单): %s", target)
            continue

        # 优先级 3：仅复制不覆盖（保护用户数据）
        if target.exists():
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        logger.debug("已初始化资源文件: %s", target)
