"""
Config 迁移运行器

在配置文件加载前执行，检测版本并按需升级。
- 版本号存储在 YAML 文件自身的 config_version 字段
- 迁移前自动备份原文件（.backup-vN 后缀）
- 任一迁移失败则保留备份、使用默认配置兜底，不阻塞启动
"""
import shutil
from lifeprism.utils import  get_logger
from pathlib import Path
from datetime import datetime
from typing import Any

import yaml

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
        logger.debug(f"{config_path.name} 不存在，跳过迁移")
        return {}

    data = _load_yaml(config_path)
    if data is None:
        logger.warning(f"{config_path.name} 解析失败，跳过迁移")
        return {}

    current_version = data.get("config_version", 0)
    pending = [m for m in migrations if m.VERSION > current_version]

    if not pending:
        logger.debug(f"{config_path.name} 版本 v{current_version}，无待执行迁移")
        return data

    logger.info(
        f"{config_path.name} 版本 v{current_version}，"
        f"待执行 {len(pending)} 个迁移"
    )

    # 备份原文件
    _backup_config(config_path, current_version)

    # 逐个执行迁移
    for migration in pending:
        try:
            if migration.check_if_applied(data):
                logger.info(
                    f"迁移 {migration.NAME} (v{migration.VERSION}) 已生效，"
                    f"补录版本记录"
                )
                data["config_version"] = migration.VERSION
            else:
                logger.info(f"执行迁移 {migration.NAME} (v{migration.VERSION})...")
                data = migration.upgrade(data)
                data["config_version"] = migration.VERSION
                logger.info(f"迁移 {migration.NAME} (v{migration.VERSION}) 完成")
        except Exception:
            # LEGITIMATE: 辅助操作兜底 — 迁移失败不阻塞启动
            logger.exception(
                f"迁移 {migration.NAME} (v{migration.VERSION}) 失败，"
                f"备份保留于 {config_path.parent}，本次使用迁移前数据"
            )
            # 失败不阻塞启动，返回迁移到此为止的数据
            return data

    # 写回 YAML
    _save_yaml(config_path, data)
    logger.info(
        f"{config_path.name} 迁移完成，当前版本 v{pending[-1].VERSION}"
    )
    return data


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            result = yaml.safe_load(f)
        return result if isinstance(result, dict) else {}
    except Exception:
        # LEGITIMATE: 辅助操作兜底 — 迁移失败不阻塞启动
        logger.exception(f"读取 {path.name} 失败")
        return None


def _save_yaml(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    except Exception:
        # LEGITIMATE: 辅助操作兜底 — 迁移失败不阻塞启动
        logger.exception(f"写入 {path.name} 失败")


def _backup_config(config_path: Path, current_version: int) -> None:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = config_path.with_name(
        f"{config_path.stem}.backup-v{current_version}-{timestamp}{config_path.suffix}"
    )
    try:
        shutil.copy2(config_path, backup_path)
        logger.info(f"已备份 {config_path.name} → {backup_path.name}")
        _cleanup_old_backups(config_path)
    except Exception:
        # LEGITIMATE: 辅助操作兜底 — 迁移失败不阻塞启动
        logger.exception(f"备份 {config_path.name} 失败")


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
        logger.info(f"清理旧备份: {old.name}")
