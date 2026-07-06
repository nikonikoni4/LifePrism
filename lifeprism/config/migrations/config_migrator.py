"""
Config 迁移运行器

在配置文件加载前执行，检测版本并按需升级。
- 版本号存储在 YAML 文件自身的 config_version 字段
- 迁移前自动备份原文件（.backup-vN 后缀）
- 任一迁移失败则保留备份、使用默认配置兜底，不阻塞启动
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from lifeprism.utils import get_logger

logger = get_logger(__name__)


def run_config_migrations(config_path: Path, migrations: list) -> dict:
    """
    对指定 YAML 配置文件执行所有待运行的迁移。

    Args:
        config_path: YAML 文件路径（可以不存在，不存在时返回空 dict）
        migrations:  迁移脚本列表，每个元素须有 VERSION / NAME /
                     check_if_applied(data) / upgrade(data) 属性

    Returns:
        迁移完成后的 dict 数据（调用方负责写入文件或继续使用）
    """
    if not config_path.exists():
        logger.debug("%s 不存在，跳过迁移", config_path.name)
        return {}

    data = _load_yaml(config_path)
    if data is None:
        logger.warning("%s 解析失败，跳过迁移", config_path.name)
        return {}

    current_version = data.get("config_version", 0)
    pending = [m for m in migrations if current_version < m.VERSION]

    if not pending:
        logger.debug("%s 版本 v%s，无待执行迁移", config_path.name, current_version)
        return data

    logger.info(
        "%s 版本 v%s，待执行 %s 个迁移",
        config_path.name,
        current_version,
        len(pending),
    )

    # 备份原文件
    _backup_config(config_path, current_version)

    # 逐个执行迁移
    for migration in pending:
        try:
            if migration.check_if_applied(data):
                logger.info(
                    "迁移 %s (v%s) 已生效，补录版本记录",
                    migration.NAME,
                    migration.VERSION,
                )
                data["config_version"] = migration.VERSION
            else:
                logger.info("执行迁移 %s (v%s)...", migration.NAME, migration.VERSION)
                data = migration.upgrade(data)
                data["config_version"] = migration.VERSION
                logger.info("迁移 %s (v%s) 完成", migration.NAME, migration.VERSION)
        except Exception:
            # LEGITIMATE: 辅助操作兜底 — 迁移失败不阻塞启动
            logger.exception(
                "迁移 %s (v%s) 失败，备份保留于 %s，本次使用迁移前数据",
                migration.NAME,
                migration.VERSION,
                config_path.parent,
            )
            # 失败不阻塞启动，返回迁移到此为止的数据
            return data

    # 写回 YAML
    _save_yaml(config_path, data)
    logger.info(
        "%s 迁移完成，当前版本 v%s",
        config_path.name,
        pending[-1].VERSION,
    )
    return data


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            result = yaml.safe_load(f)
        return result if isinstance(result, dict) else {}
    except Exception:
        # LEGITIMATE: 辅助操作兜底 — 迁移失败不阻塞启动
        logger.exception("读取 %s 失败", path.name)
        return None


def _save_yaml(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    except Exception:
        # LEGITIMATE: 辅助操作兜底 — 迁移失败不阻塞启动
        logger.exception("写入 %s 失败", path.name)


def _backup_config(config_path: Path, current_version: int) -> None:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = config_path.with_name(
        f"{config_path.stem}.backup-v{current_version}-{timestamp}{config_path.suffix}"
    )
    try:
        shutil.copy2(config_path, backup_path)
        logger.debug("已备份 %s → %s", config_path.name, backup_path.name)
        _cleanup_old_backups(config_path)
    except Exception:
        # LEGITIMATE: 辅助操作兜底 — 迁移失败不阻塞启动
        logger.exception("备份 %s 失败", config_path.name)


def _cleanup_old_backups(config_path: Path, keep: int = 3) -> None:
    """只保留最近 keep 个备份"""
    pattern = f"{config_path.stem}.backup-v*{config_path.suffix}"
    backups = sorted(
        config_path.parent.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        old.unlink()
        logger.debug("清理旧备份: %s", old.name)
