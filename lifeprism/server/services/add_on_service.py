"""
Add-on 扩展功能业务逻辑层

纯函数模块，提供扩展文件夹的 CRUD 操作
"""

import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from lifeprism.config.settings_manager import settings
from lifeprism.server.schemas.add_on_schemas import (
    CreateExpandDirRequest,
    UpdateExpandDirRequest,
    ExpandDirItem,
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
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON 文件损坏: {e}")
        return {"expand_dirs": []}
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        return {"expand_dirs": []}


def _save_data(data: dict) -> None:
    """原子性写入 JSON 数据文件"""
    file_path = _get_data_file_path()

    # 写入临时文件
    temp_fd, temp_path = tempfile.mkstemp(
        dir=file_path.parent,
        suffix='.tmp'
    )
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 原子性重命名
        os.replace(temp_path, file_path)
    except Exception as e:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logger.error(f"保存配置文件失败: {e}")
        raise RuntimeError("保存配置失败")


def _generate_next_id(existing_dirs: List[dict]) -> str:
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
    """验证路径是否存在且可访问"""
    try:
        p = Path(path)
        return p.exists() and p.is_dir()
    except Exception:
        return False


def get_all_expand_dirs() -> List[ExpandDirItem]:
    """获取所有扩展文件夹配置"""
    data = _read_data()
    expand_dirs = data.get("expand_dirs", [])

    # 转换为响应模型
    result = []
    for item in expand_dirs:
        try:
            result.append(ExpandDirItem(**item))
        except Exception as e:
            logger.warning(f"跳过无效的配置项: {e}")
            continue

    # 按 ID 升序排列
    result.sort(key=lambda x: int(x.id))
    return result


def create_expand_dir(data: CreateExpandDirRequest) -> ExpandDirItem:
    """创建新的扩展文件夹配置"""
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
        "created_at": datetime.now().isoformat()
    }

    expand_dirs.append(new_item)
    file_data["expand_dirs"] = expand_dirs

    # 保存
    _save_data(file_data)

    return ExpandDirItem(**new_item)


def update_expand_dir(id: str, data: UpdateExpandDirRequest) -> ExpandDirItem:
    """更新扩展文件夹配置"""
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
        "created_at": expand_dirs[target_index].get("created_at", datetime.now().isoformat())
    }

    expand_dirs[target_index] = updated_item
    file_data["expand_dirs"] = expand_dirs

    # 保存
    _save_data(file_data)

    return ExpandDirItem(**updated_item)


def delete_expand_dir(id: str) -> None:
    """删除扩展文件夹配置（仅删除配置，不删除磁盘文件）"""
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
