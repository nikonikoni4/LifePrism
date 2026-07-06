"""
Add-on 扩展功能业务逻辑层

纯函数模块，提供扩展文件夹的 CRUD 操作
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from lifeprism.config.settings_manager import settings
from lifeprism.server.schemas.add_on_schemas import (
    CreateExpandDirRequest,
    ExpandDirItem,
    UpdateExpandDirRequest,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


def _get_data_file_path() -> Path:
    """获取扩展文件夹配置文件路径"""
    base_path = Path(settings.lifeprism_data_path)
    expand_dir = base_path / "expand_dir"
    expand_dir.mkdir(parents=True, exist_ok=True)
    return expand_dir / "expand_meta_data.json"


def _read_data() -> dict:
    """读取 JSON 数据文件"""
    file_path = _get_data_file_path()
    if not file_path.exists():
        return {"expand_dirs": []}

    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error("JSON 文件损坏: error=%s", e)
        raise ValueError(f"配置文件格式错误: {e}") from e
    except OSError as e:
        logger.error("读取配置文件失败: error=%s", e)
        raise OSError(f"无法读取配置文件: {e}") from e


def _save_data(data: dict) -> None:
    """原子性写入 JSON 数据文件"""
    file_path = _get_data_file_path()

    # 写入临时文件
    temp_fd, temp_path = tempfile.mkstemp(dir=file_path.parent, suffix=".tmp")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 原子性重命名
        os.replace(temp_path, file_path)
    except OSError as e:
        # 清理临时文件
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError as cleanup_error:
            logger.warning("清理临时文件失败: error=%s", cleanup_error)
        logger.error("保存配置文件失败: error=%s", e)
        raise RuntimeError("保存配置失败") from e


def _generate_next_id(existing_dirs: list[dict]) -> str:
    """生成下一个 ID（数字字符串，从 1 开始自增）"""
    if not existing_dirs:
        return "1"

    max_id = 0
    for item in existing_dirs:
        try:
            num = int(item["id"])
            max_id = max(max_id, num)
        except (ValueError, KeyError):
            continue

    return str(max_id + 1)


def _validate_path(path: str) -> bool:
    """验证路径是否存在且可访问，且不在系统关键目录中"""
    try:
        p = Path(path).resolve()

        # 禁止系统关键目录
        forbidden_dirs = [
            Path.home() / "AppData",
            Path("C:/Windows") if os.name == "nt" else Path("/etc"),
            Path("C:/Program Files") if os.name == "nt" else Path("/sys"),
            Path("/proc") if os.name != "nt" else None,
        ]
        forbidden_dirs = [d for d in forbidden_dirs if d is not None]

        for forbidden in forbidden_dirs:
            try:
                if p.is_relative_to(forbidden.resolve()):
                    logger.warning("拒绝访问系统目录: path=%s", p)
                    return False
            except (ValueError, OSError):
                continue

        return p.exists() and p.is_dir()
    except (OSError, ValueError) as e:
        logger.warning("路径验证失败: path=%s, error=%s", str(p), e)
        return False


def get_all_expand_dirs() -> list[ExpandDirItem]:
    """
    获取所有扩展文件夹配置

    Returns:
        List[ExpandDirItem]: 扩展文件夹配置列表，按 ID 升序排列

    Raises:
        ValueError: 配置文件格式错误
        IOError: 无法读取配置文件
    """
    data = _read_data()
    expand_dirs = data.get("expand_dirs", [])

    # 转换为响应模型
    result = []
    for item in expand_dirs:
        try:
            result.append(ExpandDirItem(**item))
        except Exception as e:
            logger.warning("跳过无效的配置项: error=%s", e)
            continue

    # 按 ID 升序排列
    result.sort(key=lambda x: int(x.id))
    return result


def create_expand_dir(data: CreateExpandDirRequest) -> ExpandDirItem:
    """
    创建新的扩展文件夹配置

    Args:
        data: 创建请求数据，包含 name, path, description, ai_index

    Returns:
        ExpandDirItem: 创建成功的扩展文件夹配置

    Raises:
        ValueError: 路径不存在、无法访问或已被添加
        RuntimeError: 保存配置失败
    """
    # 验证路径
    if not _validate_path(data.path):
        raise ValueError(f"路径不存在或无法访问: {data.path}")

    # 读取现有数据
    file_data = _read_data()
    expand_dirs = file_data.get("expand_dirs", [])

    # 检查路径是否重复
    for item in expand_dirs:
        if item.get("path") == data.path:
            raise ValueError(f"该路径已被添加: {data.path}")

    # 生成新 ID
    new_id = _generate_next_id(expand_dirs)

    # 创建新记录
    new_item = {
        "id": new_id,
        "name": data.name,
        "path": data.path,
        "description": data.description,
        "ai_index": data.ai_index,
        "created_at": datetime.now().isoformat(),
    }

    expand_dirs.append(new_item)
    file_data["expand_dirs"] = expand_dirs

    # 保存
    _save_data(file_data)

    logger.info("创建扩展文件夹: folder_id=%s", new_id)

    return ExpandDirItem(**new_item)


def update_expand_dir(id: str, data: UpdateExpandDirRequest) -> ExpandDirItem:
    """
    更新扩展文件夹配置

    Args:
        id: 扩展文件夹 ID
        data: 更新请求数据，包含 name, path, description, ai_index

    Returns:
        ExpandDirItem: 更新后的扩展文件夹配置

    Raises:
        ValueError: 路径不存在、无法访问、已被添加或 ID 不存在
        RuntimeError: 保存配置失败
    """
    # 验证路径
    if not _validate_path(data.path):
        raise ValueError(f"路径不存在或无法访问: {data.path}")

    # 读取现有数据
    file_data = _read_data()
    expand_dirs = file_data.get("expand_dirs", [])

    # 查找目标项
    target_index = None
    for i, item in enumerate(expand_dirs):
        if item.get("id") == id:
            target_index = i
            break

    if target_index is None:
        raise ValueError(f"扩展文件夹不存在: {id}")

    # 检查路径是否与其他项重复
    for i, item in enumerate(expand_dirs):
        if i != target_index and item.get("path") == data.path:
            raise ValueError(f"该路径已被添加: {data.path}")

    # 更新记录（保留 id 和 created_at）
    updated_item = {
        "id": id,
        "name": data.name,
        "path": data.path,
        "description": data.description,
        "ai_index": data.ai_index,
        "created_at": expand_dirs[target_index].get("created_at", datetime.now().isoformat()),
    }

    expand_dirs[target_index] = updated_item
    file_data["expand_dirs"] = expand_dirs

    # 保存
    _save_data(file_data)

    logger.info("更新扩展文件夹: folder_id=%s", id)

    return ExpandDirItem(**updated_item)


def delete_expand_dir(id: str) -> None:
    """
    删除扩展文件夹配置（仅删除配置，不删除磁盘文件）

    Args:
        id: 扩展文件夹 ID

    Raises:
        ValueError: ID 不存在
        RuntimeError: 保存配置失败
    """
    # 读取现有数据
    file_data = _read_data()
    expand_dirs = file_data.get("expand_dirs", [])

    # 查找并删除
    found = False
    for i, item in enumerate(expand_dirs):
        if item.get("id") == id:
            expand_dirs.pop(i)
            found = True
            break

    if not found:
        raise ValueError(f"扩展文件夹不存在: {id}")

    file_data["expand_dirs"] = expand_dirs

    # 保存
    _save_data(file_data)

    logger.info("删除扩展文件夹: folder_id=%s", id)
